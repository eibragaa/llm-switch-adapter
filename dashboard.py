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
        return {"status": status, "body": body[:1000], "elapsed": elapsed}
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


# ── provider checks ──────────────────────────────────────────────────────

def check_ollama(model: str = "qwen3:4b") -> dict:
    """Check if Ollama is running and model is available."""
    r = _curl("GET", "http://localhost:11434/api/tags", timeout=3)

    if r["status"] != 200:
        return {
            "status": "offline",
            "elapsed": r["elapsed"],
            "model": model,
            "detail": "Ollama server not responding",
            "limit_remaining": None,
        }

    model_available = False
    try:
        data = json.loads(r["body"])
        models = [m["name"] for m in data.get("models", [])]
        model_available = any(model in m for m in models)
    except (json.JSONDecodeError, KeyError):
        pass

    # Check if model is currently loaded
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
        "detail": f"Loaded" if model_loaded else "Available" if model_available else f"Model '{model}' not found",
        "limit_remaining": "♾️",
        "model_loaded": model_loaded,
        "loaded_models": models if model_available else [],
    }


def check_openrouter() -> dict:
    """
    Check OpenRouter availability.
    Tries the models endpoint (no auth needed) for basic health.
    """
    r = _curl("GET", "https://openrouter.ai/api/v1/models",
              headers={"Accept": "application/json"}, timeout=5)

    if r["status"] != 200:
        return {
            "status": "offline",
            "elapsed": r["elapsed"],
            "model": "qwen/qwen3-coder:free",
            "detail": f"HTTP {r['status']}: {r['body'][:80]}",
            "limit_remaining": None,
        }

    # Try to get usage info via auth/key endpoint
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
                    usage_info = f"  │  Used: {usage}/{limit}"
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass

    model_found = "qwen3-coder" in r["body"].lower()
    status_text = f"Model available{usage_info}" if model_found else f"API OK{usage_info}"
    return {
        "status": "online",
        "elapsed": r["elapsed"],
        "model": "qwen/qwen3-coder:free",
        "detail": status_text,
        "limit_remaining": None,
        "limit_max": None,
        "limit_reset": None,
    }


def check_nvidia(model: str = "qwen/qwen3-coder-480b-a35b-instruct") -> dict:
    """Check Nvidia NIM availability via a minimal API call."""
    api_key = os.environ.get("NVIDIA_API_KEY") or _get_credential("nvidia")

    if not api_key:
        return {"status": "no_key", "elapsed": 0, "model": model,
                "detail": "No API key configured in Hermes", "limit_remaining": None}

    # Use a very tiny inference request (1 token max)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
    })
    r = _curl("POST", "https://integrate.api.nvidia.com/v1/chat/completions",
              headers={
                  "Authorization": f"Bearer {api_key}",
                  "Content-Type": "application/json",
              },
              data=payload, timeout=8)

    if r["status"] == 200:
        return {"status": "online", "elapsed": r["elapsed"], "model": model,
                "detail": "OK", "limit_remaining": None}
    elif r["status"] == 429:
        return {"status": "rate_limited", "elapsed": r["elapsed"], "model": model,
                "detail": "Rate limited (429)", "limit_remaining": None}
    elif r["status"] == 401 or r["status"] == 403:
        return {"status": "no_key", "elapsed": r["elapsed"], "model": model,
                "detail": "No API key configured", "limit_remaining": None}
    else:
        return {"status": "offline", "elapsed": r["elapsed"], "model": model,
                "detail": f"HTTP {r['status']}: {r['body'][:80]}", "limit_remaining": None}


def check_deepseek() -> dict:
    """Check DeepSeek API availability."""
    api_key = os.environ.get("DEEPSEEK_API_KEY") or _get_credential("deepseek")

    # Try balance endpoint
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

    # Fallback: check if the API is reachable at all
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
        from codex_switcher import status as codex_status  # type: ignore
        from account_manager import get_current_account  # type: ignore
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
            if cooldown and cooldown > 0:
                status = f"rate_limited ({cooldown:.0f}min)"
            else:
                status = "ready"
        else:
            status = "ready"

        accounts_info.append({
            "name": name,
            "email": acc.get("email", ""),
            "status": status,
            "active": is_active,
            "detail": "<< ATIVA" if is_active else "",
        })

    accounts_info.sort(key=lambda a: (0 if a["active"] else 1))
    return accounts_info


# ── cost stats (from log) ────────────────────────────────────────────────

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
    free_providers = {"ollama-local", "openrouter", "nvidia"}

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


# ── full dashboard ───────────────────────────────────────────────────────

def build_dashboard() -> dict:
    """Run all health checks and return structured dashboard data."""
    return {
        "ollama": check_ollama(),
        "openrouter": check_openrouter(),
        "nvidia": check_nvidia("qwen/qwen3-coder-480b-a35b-instruct"),
        "deepseek": check_deepseek(),
        "codex": check_codex_accounts(),
        "costs": get_cost_stats(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── TUI render ──────────────────────────────────────────────────────────

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
    return f"{color}{'█' * filled}\033[90m{'░' * empty}\033[0m {int(ratio * 100)}%"


def render_dashboard(data: dict) -> str:
    """Render the dashboard as a terminal string (ANSI colors)."""
    lines = []
    S = "\033[0m"    # reset
    B = "\033[1m"    # bold
    G = "\033[92m"   # green
    Y = "\033[93m"   # yellow
    R = "\033[91m"   # red
    C = "\033[36m"   # cyan
    GR = "\033[90m"  # gray

    def sep(): return f"  {GR}{'─' * 55}{S}"

    # ── Header ──
    lines.append("")
    lines.append(f"  {B}{C}🎯 SWITCH ADAPTER — STATUS DOS PROVIDERS{S}")
    lines.append(f"  {GR}{data['timestamp']}{S}")
    lines.append(sep())

    # ── Provider status helper ──
    def _provider_line(icon, name, model, status, elapsed, detail, extra_lines=None):
        if status == "online" or status == "no_model":
            dot = G + "●" + S
        elif status in ("rate_limited", "no_key"):
            dot = Y + "●" + S
        else:
            dot = R + "●" + S
        lines.append(f"  {dot} {B}{name}{S} ({GR}{model}{S})")
        lat = f"{GR}{elapsed}s{S}" if elapsed < 1 else f"{Y}{elapsed}s{S}"
        lines.append(f"     Status: {status.upper()}  │  Latência: {lat}")
        lines.append(f"     {detail}")
        if extra_lines:
            for el in extra_lines:
                lines.append(f"     {el}")
        lines.append("")

    # ── Ollama ──
    o = data["ollama"]
    if o["status"] == "online":
        dot_ollama = G + "●" + S
        status_ollama = f"{G}Loaded{S}" if o.get("model_loaded") else f"{Y}Available{S}"
    elif o["status"] == "no_model":
        dot_ollama = Y + "●" + S
        available_models = o.get("loaded_models", [])
        if available_models:
            models_str = ", ".join(available_models[:3])
            status_ollama = f"{Y}Model '{o['model']}' not found{S}  │  {GR}Available: {models_str}{S}"
        else:
            status_ollama = f"{Y}Model not found — run: ollama pull {o['model']}{S}"
    else:
        dot_ollama = R + "●" + S
        status_ollama = f"{R}Offline{S}"
    lines.append(f"  {dot_ollama} {B}OLLAMA{S} ({GR}{o['model']}{S})")
    lat = f"{GR}{o['elapsed']}s{S}" if o['elapsed'] < 1 else f"{Y}{o['elapsed']}s{S}"
    lines.append(f"     {status_ollama}  │  Latência: {lat}")
    lines.append(f"     {GR}Local — custo zero, latência zero{S}")
    lines.append("")

    # ── OpenRouter ──
    or_ = data["openrouter"]
    _provider_line(
        "", "OPENROUTER", or_["model"], or_["status"], or_["elapsed"],
        f"{or_['detail']}  │  Limite: ♾ (free tier)"
    )

    # ── Nvidia ──
    n = data["nvidia"]
    if n["status"] == "online":
        dot_n = G + "●" + S
    elif n["status"] == "no_key":
        dot_n = Y + "●" + S
    elif n["status"] == "rate_limited":
        dot_n = R + "●" + S
    else:
        dot_n = R + "●" + S
    lines.append(f"  {dot_n} {B}NVIDIA{S} ({GR}{n['model']}{S})")
    lat = f"{GR}{n['elapsed']}s{S}" if n['elapsed'] < 1 else f"{Y}{n['elapsed']}s{S}"
    if n["status"] == "no_key":
        lines.append(f"     {Y}⚠ No API key configured{S}  │  {lat}")
        lines.append(f"     {GR}Set NVIDIA_API_KEY env var or hermes config{S}")
    else:
        lines.append(f"     {n['status'].upper()}  │  Latência: {lat}")
        lines.append(f"     {n['detail']}")
    lines.append("")

    # ── DeepSeek ──
    d = data["deepseek"]
    bal_str = f"  │  {G}{d.get('detail', '')}{S}" if d.get("balance") is not None else ""
    _provider_line(
        "", "DEEPSEEK", d["model"], d["status"], d["elapsed"],
        f"Custo: $0.00028/1K tokens{bal_str}"
    )

    # ── Codex ──
    lines.append(f"  {B}{C}📋 CODEX (OpenAI Codex CLI){S}")
    for acc in data["codex"]:
        if "rate_limited" in acc["status"]:
            dot = R + "●" + S
            status_txt = f"{R}⏳ {acc['status']}{S}"
        elif acc["status"] == "ready":
            dot = G + "●" + S
            status_txt = "Pronto"
        else:
            dot = Y + "●" + S
            status_txt = acc["status"]
        active_marker = f"  {C}{B}<< ATIVA{S}" if acc["active"] else ""
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

    lines.append(f"  {B}📊 USO HOJE — {total} tarefa(s){S}")
    lines.append(f"  {G}Grátis: {free}{S}  │  {Y}Pago: {paid}{S}  │  {R}Erros: {errors}{S}")

    if total > 0:
        free_pct = int(free / total * 100) if total else 0
        paid_pct = 100 - free_pct
        bar_chart = G + "█" * free_pct + S + Y + "█" * paid_pct + S
        lines.append(f"  {bar_chart}")
        if cost > 0:
            lines.append(f"  Custo: ${cost:.4f}")
        lines.append(f"  {G}💰 Economia: {savings}/{total} tarefas em free{S}")
    else:
        lines.append(f"  {GR}Nenhuma tarefa roteada hoje{S}")
    lines.append("")

    # ── Route suggestion ──
    lines.append(sep())
    lines.append(f"  {B}💡 SUGESTÃO DE ROTA{S}")
    lines.append(f"     {G}LOW{S}    → Ollama Local → OpenRouter Free")
    lines.append(f"     {Y}MEDIUM{S} → Nvidia Free → Ollama → OpenRouter")
    lines.append(f"     {R}HIGH{S}   → DeepSeek Paid")
    lines.append("")
    lines.append(f"  {GR}switch-adapter route \"<tarefa>\"  para rotear{S}")
    lines.append(f"  {GR}switch-adapter dashboard watch     para live {S}")
    lines.append("")

    return "\n".join(lines)


# ── JSON output ──────────────────────────────────────────────────────────
def render_json(data: dict) -> str:
    """Compact JSON output for machine parsing."""
    output = {}
    for key in ["ollama", "openrouter", "nvidia", "deepseek"]:
        o = data[key]
        output[key] = {"status": o["status"], "latency_ms": o["elapsed"],
                       "model": o.get("model", "")}
    output["codex"] = {
        a["name"]: {"status": a["status"], "active": a["active"]}
        for a in data["codex"]}
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
