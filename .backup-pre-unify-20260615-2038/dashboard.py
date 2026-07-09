"""
Dashboard — Live health checks for all providers in the Switch Adapter pool.

Pings each provider with a lightweight request to determine:
  - Online/offline status + latency
  - Rate-limit remaining (when API allows)
  - Estimated daily usage vs cap
  - Cost spent (from local cost log)

No API keys are stored here — reads from Hermes config or env.
Uses curl via subprocess for reliability (better timeout control).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from provider_registry import (
    PROVIDER_MAP,
    ALL_PROVIDERS,
    DISPLAY_ORDER,
    status_is_usable,
)

BASE_DIR = Path(__file__).resolve().parent
COST_LOG = BASE_DIR / "accounts" / "logs" / "costs.jsonl"


# ── helpers ───────────────────────────────────────────────────────────────

def _curl(method: str, url: str, headers: dict = None,
          data: str = None, timeout: int = 5) -> dict:
    """curl via subprocess. Returns {status, body, elapsed}."""
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "--max-time", str(timeout),
           "-X", method]
    for k, v in (headers or {}).items():
        cmd.extend(["-H", f"{k}: {v}"])
    if data:
        cmd.extend(["-d", data])

    start = time.time()
    try:
        result = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=timeout + 2)
        elapsed = round(time.time() - start, 2)
        output = result.stdout.strip()
        if not output:
            return {"status": 0, "body": result.stderr[:200] or "No output",
                    "elapsed": elapsed}
        *body_lines, code_str = output.rsplit("\n", 1)
        body = "\n".join(body_lines)
        status = int(code_str) if code_str.isdigit() else 0
        return {"status": status, "body": body[:5000], "elapsed": elapsed}
    except subprocess.TimeoutExpired:
        return {"status": 0, "body": "TIMEOUT", "elapsed": timeout}
    except Exception as e:
        return {"status": 0, "body": str(e)[:200], "elapsed": round(time.time() - start, 2)}


# Cache for auth.json (avoid reading from disk 7x per refresh)
_auth_cache = {"data": None, "mtime": 0}

def _get_credential(provider: str) -> str:
    """Get access token for a provider from Hermes auth.json credential pool.
    Cached in memory to avoid reading from disk on every call."""
    auth_path = Path(os.environ.get("HOME", "/root")) / ".hermes" / "auth.json"
    
    # Check if cache needs refresh (file changed or first access)
    try:
        current_mtime = os.path.getmtime(auth_path)
        if current_mtime != _auth_cache["mtime"]:
            with open(auth_path) as f:
                _auth_cache["data"] = json.load(f)
                _auth_cache["mtime"] = current_mtime
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    
    # Get credential from cached data
    try:
        pool = _auth_cache["data"].get("credential_pool", {})
        creds = pool.get(provider, [])
        if creds and isinstance(creds, list) and len(creds) > 0:
            return creds[0].get("access_token", "")
    except (KeyError, IndexError, AttributeError):
        pass
    return ""


def _curl_model_check(url: str, timeout: int = 5) -> dict:
    """Like _curl but returns full model list without body truncation."""
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "--max-time", str(timeout), url]
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        elapsed = round(time.time() - start, 2)
        output = result.stdout.strip()
        if not output:
            return {"status": 0, "body": "No output", "elapsed": elapsed, "models": []}
        *body_lines, code_str = output.rsplit("\n", 1)
        body = "\n".join(body_lines)
        status = int(code_str) if code_str.isdigit() else 0
        models = []
        try:
            data = json.loads(body)
            models = [m["id"] for m in data.get("data", [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return {"status": status, "body": body[:200], "elapsed": elapsed, "models": models}
    except Exception as e:
        return {"status": 0, "body": str(e)[:200], "elapsed": round(time.time() - start, 2), "models": []}


# ── provider checks ──────────────────────────────────────────────────────

def check_ollama(model: str = "deepseek-v4-flash:cloud") -> dict:
    """Check if Ollama is running and model is available."""
    r = _curl("GET", "http://localhost:11434/api/tags", timeout=3)
    if r["status"] != 200:
        return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                "detail": "Ollama server not responding", "limit_remaining": None}

    model_available = False
    loaded_models = []
    try:
        data = json.loads(r["body"])
        loaded_models = [m["name"] for m in data.get("models", [])]
        model_available = any(model in m for m in loaded_models)
    except (json.JSONDecodeError, KeyError):
        pass

    r2 = _curl("GET", "http://localhost:11434/api/ps", timeout=3)
    model_loaded = False
    try:
        ps_data = json.loads(r2["body"])
        model_loaded = any(model in m["name"] for m in ps_data.get("models", []))
    except (json.JSONDecodeError, KeyError):
        pass

    return {
        "status": "online" if model_available else "no_model",
        "elapsed": max(r["elapsed"], 0.0),
        "model": model,
        "detail": "Loaded" if model_loaded else "Available" if model_available else f"Model '{model}' not found",
        "limit_remaining": "\u267e\ufe0f",
        "model_loaded": model_loaded,
        "loaded_models": loaded_models,
    }


def check_openrouter() -> dict:
    """Check OpenRouter availability."""
    r = _curl("GET", "https://openrouter.ai/api/v1/models",
              headers={"Accept": "application/json"}, timeout=5)
    if r["status"] != 200:
        return {"status": "offline", "elapsed": r["elapsed"],
                "model": "qwen/qwen3-coder:free",
                "detail": f"HTTP {r['status']}: {r['body'][:80]}",
                "limit_remaining": None}

    api_key = os.environ.get("OPENROUTER_API_KEY") or _get_credential("openrouter")
    usage_info = ""
    if api_key:
        r2 = _curl("GET", "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        if r2["status"] == 200:
            try:
                data = json.loads(r2["body"]).get("data", {})
                usage = data.get("usage", 0)
                limit = data.get("limit", 0)
                if limit:
                    usage_info = f"  |  Used: {usage}/{limit}"
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass

    model_found = "qwen3-coder" in r["body"].lower()
    status_text = f"Model available{usage_info}" if model_found else f"API OK{usage_info}"
    return {"status": "online", "elapsed": r["elapsed"],
            "model": "qwen/qwen3-coder:free", "detail": status_text,
            "limit_remaining": None, "limit_max": None, "limit_reset": None}


def check_ollama_cloud(model: str = "deepseek-v4-flash") -> dict:
    """Check Ollama Cloud API availability."""
    api_key = os.environ.get("OLLAMA_API_KEY") or _get_credential("ollama")
    r = _curl_model_check("https://ollama.com/v1/models", timeout=5)
    if r["status"] != 200:
        return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                "detail": f"HTTP {r['status']}: {r['body'][:80]}", "limit_remaining": None}

    model_available = any(model in m for m in r.get("models", []))
    detail = "Models online"
    if api_key:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "."}],
            "max_tokens": 1,
        })
        r2 = _curl("POST", "https://ollama.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    data=payload, timeout=10)
        if r2["status"] == 200:
            detail = "Online | Auth: OK"
            try:
                usage = json.loads(r2["body"]).get("usage", {})
                if usage:
                    detail += f" | {usage.get('total_tokens', '?')} tokens"
            except (json.JSONDecodeError, KeyError):
                pass
        elif r2["status"] in (401, 403):
            detail = "Online | Auth: invalid key"
        else:
            detail = f"Online | API: HTTP {r2['status']}"
    else:
        detail = "No API key | status only"

    return {"status": "online" if model_available else "limited",
            "elapsed": r["elapsed"], "model": model, "detail": detail,
            "limit_remaining": None}


def check_nous(model: str = "stepfun/step-3.7-flash:free") -> dict:
    """Check NousResearch inference API (free tier)."""
    def _get_nous_credentials():
        """Return (access_token, agent_key) from credential pool or env."""
        access_token = os.environ.get("NOUS_API_KEY") or _get_credential("nous")
        agent_key = ""
        try:
            auth_path = Path(os.environ.get("HOME", "/root")) / ".hermes" / "auth.json"
            with open(auth_path) as f:
                data = json.load(f)
            creds = data.get("credential_pool", {}).get("nous", [])
            if creds and isinstance(creds, list):
                agent_key = creds[0].get("agent_key", "")
        except Exception:
            agent_key = ""
        return access_token, agent_key

    access_token, agent_key = _get_nous_credentials()
    # Try access_token first
    for token, label in [(access_token, "access_token"), (agent_key, "agent_key")]:
        if not token:
            continue
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "."}], "max_tokens": 1})
        r = _curl("POST", "https://inference-api.nousresearch.com/v1/chat/completions",
                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                  data=payload, timeout=8)
        if r["status"] == 200:
            return {"status": "online", "elapsed": r["elapsed"], "model": model,
                    "detail": f"{model} free | $0.00", "limit_remaining": "infinite"}
        elif r["status"] in (401, 403):
            # try next token
            continue
        elif r["status"] == 429:
            return {"status": "rate_limited", "elapsed": r["elapsed"], "model": model,
                    "detail": "Rate limited (429)", "limit_remaining": None}
        else:
            return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                    "detail": f"HTTP {r['status']}: {r['body'][:80]}", "limit_remaining": None}
    # If all tokens failed with auth errors
    return {"status": "no_key", "elapsed": 0, "model": model,
            "detail": "No valid NousResearch token (access_token/agent_key)", "limit_remaining": None}


def check_nvidia(model: str = "qwen/qwen3-coder-480b-a35b-instruct") -> dict:
    """Check Nvidia NIM availability via a minimal API call."""
    api_key = os.environ.get("NVIDIA_API_KEY") or _get_credential("nvidia")
    if not api_key:
        return {"status": "no_key", "elapsed": 0, "model": model,
                "detail": "No API key configured in Hermes", "limit_remaining": None}

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
    })
    r = _curl("POST", "https://integrate.api.nvidia.com/v1/chat/completions",
              headers={"Authorization": f"Bearer {api_key}",
                       "Content-Type": "application/json"},
              data=payload, timeout=8)
    if r["status"] == 200:
        return {"status": "online", "elapsed": r["elapsed"], "model": model,
                "detail": "OK", "limit_remaining": None}
    elif r["status"] == 429:
        return {"status": "rate_limited", "elapsed": r["elapsed"], "model": model,
                "detail": "Rate limited (429)", "limit_remaining": None}
    elif r["status"] in (401, 403):
        return {"status": "no_key", "elapsed": r["elapsed"], "model": model,
                "detail": "No API key configured", "limit_remaining": None}
    else:
        return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                "detail": f"HTTP {r['status']}: {r['body'][:80]}", "limit_remaining": None}


def check_opencode_go(model: str = "deepseek-v4-flash") -> dict:
    """Check OpenCode Go API availability (subscription: $10/mo)."""
    api_key = os.environ.get("OPENCODE_GO_API_KEY") or _get_credential("opencode-go")
    if not api_key:
        return {"status": "no_key", "elapsed": 0, "model": model,
                "detail": "No API key (set OPENCODE_GO_API_KEY)", "limit_remaining": None}

    r = _curl_model_check("https://opencode.ai/go/v1/models", timeout=8)
    if r["status"] == 200 and r.get("models"):
        return {"status": "online", "elapsed": r["elapsed"], "model": model,
                "detail": f"{len(r['models'])} models | sub $10/mo", "limit_remaining": "subscription"}

    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "."}], "max_tokens": 1})
    r2 = _curl("POST", "https://opencode.ai/go/v1/chat/completions",
               headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
               data=payload, timeout=10)
    if r2["status"] == 200:
        return {"status": "online", "elapsed": r2["elapsed"], "model": model,
                "detail": "Online | sub $10/mo", "limit_remaining": "subscription"}
    elif r2["status"] in (401, 403):
        return {"status": "no_key", "elapsed": r2["elapsed"], "model": model,
                "detail": f"Auth failed ({r2['status']})", "limit_remaining": None}
    elif r2["status"] == 404:
        return {"status": "offline", "elapsed": r2["elapsed"], "model": model,
                "detail": "API restructuring (404)", "limit_remaining": "subscription"}
    else:
        return {"status": "offline", "elapsed": r2["elapsed"], "model": model,
                "detail": f"HTTP {r2['status']}: {r2['body'][:60]}", "limit_remaining": None}


def check_deepseek() -> dict:
    """Check DeepSeek API availability."""
    api_key = os.environ.get("DEEPSEEK_API_KEY") or _get_credential("deepseek")
    r = _curl("GET", "https://api.deepseek.com/user/balance",
              headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
              timeout=5)
    if r["status"] == 200:
        try:
            data = json.loads(r["body"])
            balance = data.get("balance", 0)
            return {"status": "online", "elapsed": r["elapsed"],
                    "model": "deepseek-v4-flash",
                    "detail": f"Balance: ${balance:.2f}", "balance": balance}
        except (json.JSONDecodeError, KeyError):
            pass

    r2 = _curl("GET", "https://api.deepseek.com/v1/models",
               headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
               timeout=5)
    if r2["status"] != 0:
        return {"status": "online" if r2["status"] < 500 else "offline",
                "elapsed": r2["elapsed"], "model": "deepseek-v4-flash",
                "detail": f"HTTP {r2['status']}" if r2["status"] < 500 else "API error",
                "balance": None}
    return {"status": "unreachable", "elapsed": r2["elapsed"],
            "model": "deepseek-v4-flash",
            "detail": f"Unreachable ({r2['body'][:60]})", "balance": None}


# Flag para garantir que sys.path.insert roda apenas UMA vez
_codex_syspath_added = False

def check_codex_accounts() -> list[dict]:
    """Check all Codex accounts status."""
    global _codex_syspath_added
    try:
        if not _codex_syspath_added:
            sys.path.insert(0, str(BASE_DIR))
            _codex_syspath_added = True
        from codex_switcher import status as codex_status
        from account_manager import get_current_account
    except ImportError:
        return [{"name": "error", "status": "error", "detail": "Could not import codex modules"}]

    status_data = codex_status()
    accounts_info = []
    current = get_current_account("codex")
    for acc in status_data["accounts"]:
        name = acc["name"]
        is_active = acc["active"]
        if acc["exhausted"]:
            cooldown = acc.get("cooldown_remaining_min", 0)
            status = f"rate_limited ({cooldown:.0f}min)" if cooldown and cooldown > 0 else "ready"
        else:
            status = "ready"
        accounts_info.append({"name": name, "email": acc.get("email", ""),
                              "status": status, "active": is_active,
                              "detail": "<< ATIVA" if is_active else ""})
    accounts_info.sort(key=lambda a: (0 if a["active"] else 1))
    return accounts_info


# ── Finbot token consumption ────────────────────────────────────────────

CACHE_FILE = "/tmp/finbot_usage_cache.json"
CACHE_TTL = 3600

def check_finbot_usage() -> dict:
    """Read Finbot token usage from cache, fallback to SSH."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            ts = cached.get("timestamp", "")
            data = cached.get("data", {})
            if ts:
                cached_time = datetime.fromisoformat(ts)
                age = (datetime.now(timezone.utc) - cached_time).total_seconds()
                if age < CACHE_TTL:
                    return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
        pass

    def _write_cache(data: dict) -> None:
        """Write data to cache file."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data
                }, f, indent=2)
        except (OSError, TypeError):
            pass  # Non-critical — cache write failure is silent

    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
           "finbot@100.126.136.58",
           "cd /home/finbot/finbot && .venv/bin/python scripts/ollama-usage.py"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            err = {"status": "error", "detail": f"SSH exit {result.returncode}",
                    "providers": {}, "total_requests": 0}
            _write_cache(err)
            return err
        data = json.loads(result.stdout)
        if "error" in data:
            err = {"status": "error", "detail": data["error"], "providers": {}, "total_requests": 0}
            _write_cache(err)
            return err
        data["status"] = "ok"
        data["_source"] = "ssh_fallback"
        _write_cache(data)  # ← Escrever no cache!
        return data
    except subprocess.TimeoutExpired:
        err = {"status": "error", "detail": "SSH timeout", "providers": {}, "total_requests": 0}
        _write_cache(err)
        return err
    except json.JSONDecodeError as e:
        err = {"status": "error", "detail": f"JSON: {e}", "providers": {}, "total_requests": 0}
        _write_cache(err)
        return err
    except Exception as e:
        err = {"status": "error", "detail": str(e)[:200], "providers": {}, "total_requests": 0}
        _write_cache(err)
        return err


# ── Tailscale ────────────────────────────────────────────────────────────

def check_tailscale() -> dict:
    """Get Tailscale status and peer info."""
    try:
        # Get local Tailscale IP
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        local_ip = result.stdout.strip() if result.returncode == 0 else "N/A"
        
        # Get peer status
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {"status": "error", "local_ip": local_ip, "peers": [], "detail": "tailscale status failed"}
        
        data = json.loads(result.stdout)
        peers = []
        for peer in data.get("Peer", {}).values():
            peers.append({
                "dns_name": peer.get("DNSName", "").rstrip("."),
                "tailscale_ip": peer.get("TailscaleIPs", ["N/A"])[0] if peer.get("TailscaleIPs") else "N/A",
                "online": peer.get("Online", False),
                "last_seen": peer.get("LastSeen", ""),
                "active": peer.get("Active", False),
            })
        
        online_peers = sum(1 for p in peers if p["online"])
        total_peers = len(peers)
        
        return {
            "status": "connected" if total_peers > 0 else "no_peers",
            "local_ip": local_ip,
            "peers": peers,
            "online_count": online_peers,
            "total_count": total_peers,
            "dashboard_url": f"http://{local_ip}:8080",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "local_ip": "N/A", "peers": [], "detail": "Tailscale command timeout"}
    except FileNotFoundError:
        return {"status": "not_installed", "local_ip": "N/A", "peers": [], "detail": "tailscale not installed"}
    except (json.JSONDecodeError, KeyError) as e:
        return {"status": "error", "local_ip": "N/A", "peers": [], "detail": str(e)[:100]}
    except Exception as e:
        return {"status": "error", "local_ip": "N/A", "peers": [], "detail": str(e)[:100]}


# ── cost stats ──────────────────────────────────────────────────────────

def get_cost_stats(days: int = 1) -> dict:
    """Aggregate cost stats from local log file."""
    if not COST_LOG.exists():
        return {"today_tasks": 0, "today_free": 0, "today_paid": 0,
                "today_errors": 0, "estimated_cost_usd": 0,
                "by_provider": {}, "by_complexity": {}}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = {"today_tasks": 0, "today_free": 0, "today_paid": 0,
             "today_errors": 0, "estimated_cost_usd": 0,
             "by_provider": {}, "by_complexity": {}}
    free_providers = {"ollama-local", "ollama_cloud", "openrouter", "nvidia", "nous", "opencode-go"}

    with open(COST_LOG) as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")[:10]
                if ts != today:
                    continue
                stats["today_tasks"] += 1
                provider = entry.get("provider", "?")
                complexity = entry.get("complexity", "?")
                if provider in free_providers:
                    stats["today_free"] += 1
                else:
                    stats["today_paid"] += 1
                    stats["estimated_cost_usd"] += 0.00014
                if not entry.get("success", True):
                    stats["today_errors"] += 1
                stats["by_provider"].setdefault(provider, 0)
                stats["by_provider"][provider] += 1
                stats["by_complexity"].setdefault(complexity, 0)
                stats["by_complexity"][complexity] += 1
            except (json.JSONDecodeError, KeyError):
                continue

    stats["estimated_cost_usd"] = round(stats["estimated_cost_usd"], 6)
    return stats


# ── dashboard builder ─────────────────────────────────────────────────────

def build_dashboard() -> dict:
    """Run all health checks in parallel and return structured dashboard data."""
    checks = {
        "ollama": lambda: check_ollama("deepseek-v4-flash:cloud"),
        "ollama_cloud": lambda: check_ollama_cloud("deepseek-v4-flash"),
        "nous": lambda: check_nous("stepfun/step-3.7-flash:free"),
        "openrouter": check_openrouter,
        "nvidia": lambda: check_nvidia("qwen/qwen3-coder-480b-a35b-instruct"),
        "deepseek": check_deepseek,
        "codex": check_codex_accounts,
        "finbot_usage": check_finbot_usage,
        "tailscale": check_tailscale,
        "costs": get_cost_stats,
    }
    
    results = {}
    
    # Run all checks in parallel with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in checks.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result(timeout=15)  # 15s timeout per check
            except Exception as e:
                results[key] = {"status": "error", "detail": str(e)[:100]}
    
    # Add model registry data
    try:
        from provider_registry import PROVIDER_MAP, ALL_PROVIDERS, DISPLAY_ORDER
        from dashboard_data import get_data_service
        service = get_data_service()
        results["models"] = service.get_model_registry()
    except Exception:
        results["models"] = {"categories": []}
    
    results["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return results


# ── TUI render (data-driven) ────────────────────────────────────────────

def _bar(used: float, total: float, width: int = 30) -> str:
    ratio = min(used / total, 1.0) if total > 0 else 0
    filled = int(ratio * width)
    empty = width - filled
    if ratio > 0.8:
        color = "\033[91m"
    elif ratio > 0.5:
        color = "\033[93m"
    else:
        color = "\033[92m"
    return f"{color}{chr(9608) * filled}\033[90m{chr(9617) * empty}\033[0m {int(ratio * 100)}%"


def render_dashboard(data: dict) -> str:
    """Render the dashboard as a terminal string (ANSI colors)."""
    S = "\033[0m"
    B = "\033[1m"
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    C = "\033[36m"
    GR = "\033[90m"

    def sep(): return f"  {GR}{chr(9472) * 55}{S}"

    lines = []
    lines.append("")
    lines.append(f"  {B}{C}\U0001f3af SWITCH ADAPTER — STATUS DOS PROVIDERS{S}")
    lines.append(f"  {GR}{data['timestamp']}{S}")
    lines.append(sep())

    # ── Provider lines (data-driven from registry) ──
    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        p = data.get(key, {})
        if not prov or not p:
            continue
        status = p.get("status", "offline")
        elapsed = p.get("elapsed", 0)
        icon = prov.icon(status)
        lat = f"{GR}{elapsed}s{S}" if elapsed < 1 else f"{Y}{elapsed}s{S}"

        lines.append(f"  {icon} {B}{prov.name}{S} ({GR}{prov.model}{S})")
        lines.append(f"     {status.upper()}  |  Latencia: {lat}")
        detail = p.get("detail", "")
        if detail:
            lines.append(f"     {GR}{detail}{S}")
        lines.append("")

    # ── Finbot ──
    fu = data.get("finbot_usage", {})
    if fu.get("status") == "ok":
        lines.append(f"  {B}{C}  FINBOT — Consumo de Tokens{S}")
        for key, prov_f in sorted(fu.get("providers", {}).items()):
            t = prov_f.get("today", {})
            tt = prov_f.get("total", {})
            pd_color = G if t.get("requests", 0) == 0 else Y
            lines.append(f"  {pd_color}\u25cf{S} {B}{prov_f.get('provider', '?').upper()}{S} ({GR}{prov_f.get('model', '?')}{S})")
            if t.get("requests", 0) > 0:
                lines.append(f"     {B}Hoje:{S} {t['requests']} reqs  |  Prompt: {t['prompt_tokens']}  |  Completion: {t['completion_tokens']}  |  {B}Total: {t['total_tokens']} tokens{S}")
            lines.append(f"     {GR}Desde tracking:{S} {tt.get('requests', 0)} reqs  |  Prompt: {tt.get('prompt_tokens', 0)}  |  Completion: {tt.get('completion_tokens', 0)}  |  {B}Total: {tt.get('total_tokens', 0)} tokens{S}")
        if not fu.get("providers"):
            lines.append(f"     {GR}Aguardando requisicoes — bot reiniciado recentemente{S}")
        lines.append("")
    elif fu.get("status") == "error" and fu.get("detail"):
        lines.append(f"  {GR}  FINBOT {S}{R}\u25cf{S} {GR}{fu.get('detail','')[:80]}{S}")
        lines.append("")

    # ── Codex ──
    lines.append(f"  {B}{C}\U0001f4cb CODEX (OpenAI Codex CLI){S}")
    for acc in data["codex"]:
        if "rate_limited" in acc.get("status", ""):
            dot = R + "\u25cf" + S
            status_txt = f"{R}\u23f3 {acc['status']}{S}"
        elif acc.get("status") == "ready":
            dot = G + "\u25cf" + S
            status_txt = "Pronto"
        else:
            dot = Y + "\u25cf" + S
            status_txt = acc.get("status", "?")
        active_marker = f"  {C}{B}<< ATIVA{S}" if acc.get("active") else ""
        lines.append(f"  {dot} {acc['name']} ({GR}{acc['email']}{S}){active_marker}")
        lines.append(f"     {status_txt}")
    lines.append("")

    # ── Cost stats ──
    lines.append(sep())
    c = data["costs"]
    total = c["today_tasks"]
    free = c["today_free"]
    paid = c["today_paid"]
    errors = c["today_errors"]
    cost = c["estimated_cost_usd"]
    savings = max(0, total - paid)

    lines.append(f"  {B}\U0001f4ca USO HOJE \u2014 {total} tarefa(s){S}")
    lines.append(f"  {G}Gratis: {free}{S}  |  {Y}Pago: {paid}{S}  |  {R}Erros: {errors}{S}")
    if total > 0:
        free_pct = int(free / total * 100) if total else 0
        paid_pct = 100 - free_pct
        bar_chart = G + chr(9608) * free_pct + S + Y + chr(9608) * paid_pct + S
        lines.append(f"  {bar_chart}")
        if cost > 0:
            lines.append(f"  Custo: ${cost:.4f}")
        lines.append(f"  {G}\U0001f4b0 Economia: {savings}/{total} tarefas em free{S}")
    else:
        lines.append(f"  {GR}Nenhuma tarefa roteada hoje{S}")
    lines.append("")

    # ── Tailscale ──
    ts = data.get("tailscale", {})
    if ts:
        ts_status = ts.get("status", "unknown")
        local_ip = ts.get("local_ip", "N/A")
        online = ts.get("online_count", 0)
        total_peers = ts.get("total_count", 0)
        dash_url = ts.get("dashboard_url", "")
        
        lines.append(sep())
        lines.append(f"  {B}\U0001f310 TAILSCALE MESH{S}")
        status_emoji = G + "\u25cf" + S if ts_status == "connected" else Y + "\u25cf" + S if ts_status == "no_peers" else R + "\u25cf" + S
        lines.append(f"  {status_emoji} Status: {ts_status.upper()}  |  IP: {local_ip}")
        lines.append(f"  Peers: {G}{online}{S}/{total_peers} online")
        if dash_url:
            lines.append(f"  Dashboard: {C}{dash_url}{S}")
        for peer in ts.get("peers", []):
            peer_emoji = G + "\u25cb" + S if peer["online"] else R + "\u25cb" + S
            lines.append(f"  {peer_emoji} {peer['dns_name']} ({peer['tailscale_ip']})  {'Online' if peer['online'] else 'Offline'}")
        lines.append("")

    # ── Route suggestion (from registry) ──
    lines.append(sep())
    lines.append(f"  {B}\U0001f4a1 SUGESTAO DE ROTA{S}")
    from hermes_router import recommend_best_provider
    rec = recommend_best_provider(data)
    for tier in ["low", "medium", "high"]:
        r = rec[tier]
        icon = {"low": G, "medium": Y, "high": R}[tier]
        label = tier.upper()
        if r.get("available"):
            lines.append(f"     {icon}{label}{S}   \u2192 {r['provider']} ({r['cost']})")
        else:
            lines.append(f"     {R}{label}{S}   \u2192 Indisponivel (usar {r['provider']})")
    lines.append("")
    lines.append(f"  {GR}switch-adapter route \"<tarefa>\"  para rotear{S}")
    lines.append(f"  {GR}switch-adapter dashboard watch     para live{S}")
    lines.append("")

    return "\n".join(lines)


# ── JSON output ──────────────────────────────────────────────────────────
def render_json(data: dict) -> str:
    """Compact JSON output for machine parsing."""
    output = {}
    for key in DISPLAY_ORDER:
        if key in data:
            o = data[key]
            output[key] = {"status": o.get("status", "unknown"),
                           "latency_ms": o.get("elapsed", 0),
                           "model": o.get("model", "")}
    output["codex"] = {
        a["name"]: {"status": a["status"], "active": a["active"]}
        for a in data.get("codex", [])}
    output["costs"] = {"tasks_today": data["costs"]["today_tasks"],
                       "free_today": data["costs"]["today_free"],
                       "paid_today": data["costs"]["today_paid"]}
    # Add Tailscale for web UI
    ts = data.get("tailscale", {})
    if ts:
        output["tailscale"] = {
            "status": ts.get("status", "unknown"),
            "local_ip": ts.get("local_ip", ""),
            "online_count": ts.get("online_count", 0),
            "total_count": ts.get("total_count", 0),
            "dashboard_url": ts.get("dashboard_url", ""),
            "peers": [
                {"dns_name": p.get("dns_name", ""),
                 "tailscale_ip": p.get("tailscale_ip", ""),
                 "online": p.get("online", False)}
                for p in ts.get("peers", [])
            ]
        }
    # Add models registry for web UI
    if "models" in data:
        output["models"] = data["models"]
    return json.dumps(output, indent=2)


if __name__ == "__main__":
    data = build_dashboard()
    if "--json" in sys.argv:
        print(render_json(data))
    else:
        os.environ.setdefault("FORCE_COLOR", "1")
        print(render_dashboard(data))
