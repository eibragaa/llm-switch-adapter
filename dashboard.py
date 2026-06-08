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


def _get_credential(provider: str) -> str:
    """Get access token for a provider from Hermes auth.json credential pool."""
    auth_path = Path(os.environ.get("HOME", "/root")) / ".hermes" / "auth.json"
    try:
        with open(auth_path) as f:
            data = json.load(f)
        pool = data.get("credential_pool", {})
        creds = pool.get(provider, [])
        if creds and isinstance(creds, list) and len(creds) > 0:
            return creds[0].get("access_token", "")
    except (FileNotFoundError, json.JSONDecodeError, KeyError, IndexError):
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


def check_nous(model: str = "stepfun/step-3.5-flash") -> dict:
    """Check NousResearch inference API (free tier)."""
    api_key = os.environ.get("NOUS_API_KEY") or _get_credential("nous")
    if not api_key:
        return {"status": "no_key", "elapsed": 0, "model": model,
                "detail": "No API key (set NOUS_API_KEY or nous credential)",
                "limit_remaining": None}
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "."}], "max_tokens": 1})
    r = _curl("POST", "https://inference-api.nousresearch.com/v1/chat/completions",
              headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
              data=payload, timeout=8)
    if r["status"] == 200:
        return {"status": "online", "elapsed": r["elapsed"], "model": model,
                "detail": "step-3.5-flash free | $0.00", "limit_remaining": "infinite"}
    elif r["status"] in (401, 403):
        return {"status": "no_key", "elapsed": r["elapsed"], "model": model,
                "detail": f"Auth failed ({r['status']})", "limit_remaining": None}
    elif r["status"] == 429:
        return {"status": "rate_limited", "elapsed": r["elapsed"], "model": model,
                "detail": "Rate limited (429)", "limit_remaining": None}
    else:
        return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                "detail": f"HTTP {r['status']}: {r['body'][:80]}", "limit_remaining": None}


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
        return {"status": "limited", "elapsed": r2["elapsed"], "model": model,
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


def check_codex_accounts() -> list[dict]:
    """Check all Codex accounts status."""
    try:
        sys.path.insert(0, str(BASE_DIR))
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

    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
           "finbot@100.126.136.58",
           "cd /home/finbot/finbot && .venv/bin/python scripts/ollama-usage.py"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"status": "error", "detail": f"SSH exit {result.returncode}",
                    "providers": {}, "total_requests": 0}
        data = json.loads(result.stdout)
        if "error" in data:
            return {"status": "error", "detail": data["error"], "providers": {}, "total_requests": 0}
        data["status"] = "ok"
        data["_source"] = "ssh_fallback"
        return data
    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "SSH timeout", "providers": {}, "total_requests": 0}
    except json.JSONDecodeError as e:
        return {"status": "error", "detail": f"JSON: {e}", "providers": {}, "total_requests": 0}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200], "providers": {}, "total_requests": 0}


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
    """Run all health checks and return structured dashboard data."""
    return {
        "ollama": check_ollama("deepseek-v4-flash:cloud"),
        "ollama_cloud": check_ollama_cloud("deepseek-v4-flash"),
        "nous": check_nous("stepfun/step-3.5-flash"),
        "openrouter": check_openrouter(),
        "nvidia": check_nvidia("qwen/qwen3-coder-480b-a35b-instruct"),
        "opencode_go": check_opencode_go("deepseek-v4-flash"),
        "deepseek": check_deepseek(),
        "codex": check_codex_accounts(),
        "finbot_usage": check_finbot_usage(),
        "costs": get_cost_stats(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


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

    lines.append(f"  {B}\U0001f4ca USO HOJE — {total} tarefa(s){S}")
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
    return json.dumps(output, indent=2)


if __name__ == "__main__":
    data = build_dashboard()
    if "--json" in sys.argv:
        print(render_json(data))
    else:
        os.environ.setdefault("FORCE_COLOR", "1")
        print(render_dashboard(data))
