"""
Hermes Router — Complexity-based provider routing for cost optimization.

Classifies task complexity and routes to the cheapest available provider
based on REAL-TIME health data from the dashboard.

Each tier has a prioritized pool — tries the first, falls back to next.
Also provides cost tracking across providers.
"""

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from provider_registry import (
    PROVIDER_MAP,
    get_providers_for_tier,
    get_best_for_tier,
    status_is_usable,
)


# ── paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
COST_LOG = BASE_DIR / "accounts" / "logs" / "costs.jsonl"


# ── complexity classification ────────────────────────────────────────────
# Tier 1: Fast keyword/regex rules (no LLM needed)
COMPLEXITY_RULES = {
    "low": {
        "keywords": [
            r"\b(lint|format|style|typo|comment|docstring)\b",
            r"\b(what is|how do I|explain briefly|check)\b",
            r"^(fix|add|update)\s+\w+\s+(import|typo|comment|docstring)",
        ],
        "max_length": 150,  # chars
    },
    "medium": {
        "keywords": [
            r"\b(refactor|restructure|optimize|add\s+test)\b",
            r"\b(implement|create)\s+(simple|basic|small|endpoint)",
            r"\b(generate|scaffold)\b",
        ],
        "max_length": 800,
    },
    "high": {
        "keywords": [
            r"\b(debug|architecture|design|migrate|rewrite)\b",
            r"\b(complex|full|complete|entire|system)\b",
            r"\b(security|performance|scale|production)\b",
        ],
        "max_length": float("inf"),
    },
}


# ── provider pools (backward-compat static) ──────────────────────────────
# Used when no health data is available.
# The REGISTRY (provider_registry.py) is the single source of truth.
PROVIDER_POOLS = {}


def get_provider_pool(complexity: str, health_data: dict | None = None
                      ) -> list[dict]:
    """Get the provider pool for a complexity tier.
    
    If health_data is provided, filters by real-time availability.
    Returns list of dicts matching the old format (backward compat).
    """
    providers = get_providers_for_tier(complexity, health_data)
    return [
        {
            "provider": p.provider_slug or p.key,
            "model": p.model,
            "cost_per_1k_tokens": p.cost_per_1k,
            "description": p.description,
            "key": p.key,
        }
        for p in providers
    ]


def classify_complexity(prompt: str) -> str:
    """Classify prompt complexity: 'low', 'medium', or 'high'."""
    prompt_lower = prompt.lower()
    prompt_len = len(prompt)

    # Check high first (most specific patterns)
    for pattern in COMPLEXITY_RULES["high"]["keywords"]:
        if re.search(pattern, prompt_lower):
            return "high"

    if prompt_len > COMPLEXITY_RULES["medium"]["max_length"]:
        return "high"

    # Check medium
    for pattern in COMPLEXITY_RULES["medium"]["keywords"]:
        if re.search(pattern, prompt_lower):
            return "medium"

    if prompt_len > COMPLEXITY_RULES["low"]["max_length"]:
        return "medium"

    # Check low
    for pattern in COMPLEXITY_RULES["low"]["keywords"]:
        if re.search(pattern, prompt_lower):
            return "low"

    # Default: medium (safe middle ground)
    return "medium"


# ── routing ──────────────────────────────────────────────────────────────
def route(prompt: str, health_data: dict | None = None) -> dict:
    """Determine which provider/model to use for a given prompt.

    If health_data is provided (from dashboard), routes based on
    real-time availability instead of static defaults.

    Returns: {provider, model, complexity, cost_per_1k_tokens, pool, description}
    """
    complexity = classify_complexity(prompt)
    pool = get_provider_pool(complexity, health_data)
    best = pool[0] if pool else {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "cost_per_1k_tokens": 0.00028,
        "description": "DeepSeek Paid (emergency fallback)",
        "key": "deepseek",
    }
    return {
        "complexity": complexity,
        "provider": best["provider"],
        "model": best["model"],
        "cost_per_1k_tokens": best["cost_per_1k_tokens"],
        "description": best["description"],
        "pool": pool,
    }


def recommend_best_provider(data: dict) -> dict:
    """Analyze dashboard data and recommend the best provider
    for each complexity tier RIGHT NOW.
    
    Uses the registry + health data to make intelligent choices.
    """
    # Get health-based pools
    rec = {
        "low": {"provider": "N/A", "model": "", "cost": "FREE", "available": False},
        "medium": {"provider": "N/A", "model": "", "cost": "FREE", "available": False},
        "high": {"provider": "N/A", "model": "", "cost": "FREE", "available": False},
        "codex": {"best_account": None, "all_exhausted": False,
                  "active": None, "available": True},
        "overall": {"best_value": "", "reason": "", "savings_today": "—"},
    }
    
    # Best for each tier from health data
    for tier in ["low", "medium", "high"]:
        best = get_best_for_tier(tier, data)
        if best and status_is_usable(data.get(best.key, {}).get("status", "")):
            rec[tier] = {
                "provider": best.name,
                "model": best.model,
                "cost": best.cost_display,
                "available": True,
                "_key": best.key,
            }
        else:
            # Fallback: try ANY provider for this tier (even degraded)
            fallback = get_best_for_tier(tier, None)
            if fallback:
                rec[tier] = {
                    "provider": fallback.name,
                    "model": fallback.model,
                    "cost": fallback.cost_display,
                    "available": False,  # not currently healthy
                    "_key": fallback.key,
                }
    
    # --- CODEX ---
    codex = data.get("codex", [])
    ready_accounts = [a for a in codex if a.get("status") == "ready"]
    exhausted_accounts = [a for a in codex if "rate_limited" in a.get("status", "")]
    active = next((a for a in codex if a.get("active")), None)

    if ready_accounts:
        rec["codex"]["best_account"] = ready_accounts[0]["name"]
        rec["codex"]["active"] = active["name"] if active else ready_accounts[0]["name"]
    elif exhausted_accounts:
        rec["codex"]["all_exhausted"] = True
        rec["codex"]["available"] = False
        rec["codex"]["active"] = active["name"] if active else "N/A"

    # --- OVERALL recommendation ---
    costs = data.get("costs", {})
    total = costs.get("today_tasks", 0)
    free_tasks = costs.get("today_free", 0)
    paid_tasks = costs.get("today_paid", 0)

    if total > 0:
        free_pct = int(free_tasks / total * 100)
        rec["overall"]["savings_today"] = f"{free_pct}% free"
    else:
        rec["overall"]["savings_today"] = "—"

    # Best value pick
    for tier in ["low", "medium", "high"]:
        if rec[tier].get("available"):
            rec["overall"]["best_value"] = f"{tier.upper()} \u2794 {rec[tier]['provider']} ({rec[tier]['cost']})"
            break
    if not rec["overall"]["best_value"]:
        rec["overall"]["best_value"] = "\u26a0 Nenhum provider disponivel!"

    # Smart reason
    ollama = data.get("ollama", {})
    if rec["overall"]["best_value"]:
        if not rec["low"].get("available") and ollama.get("status") == "no_model":
            rec["overall"]["reason"] = "Dica: rode ollama pull deepseek-v4-flash:cloud para ativar modelo local"
        elif paid_tasks > 0 and total > 0:
            pct_paid = int(paid_tasks / total * 100)
            if pct_paid > 30:
                rec["overall"]["reason"] = f"\u26a0 {pct_paid}% das tarefas foram pagas — tente tasks mais simples no free"
            elif pct_paid == 0:
                rec["overall"]["reason"] = "100% free hoje! \U0001f389"
            else:
                rec["overall"]["reason"] = "Maioria das tarefas em free — keep it up!"

    return rec


# ── execution ────────────────────────────────────────────────────────────
def route_execute(
    prompt: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 300,
    health_data: dict | None = None,
) -> dict:
    """Route and execute a prompt through the best provider.

    Tries each provider in the pool until one succeeds (fallback chain).
    If provider/model are specified, they override the router and no fallback.
    If health_data is provided, uses real-time health for routing.
    """
    if provider and model:
        # Manual override — single attempt, no fallback
        task_id = hashlib.md5(f"{prompt}{time.time()}".encode()).hexdigest()[:12]
        start_time = time.time()
        result = _try_provider(prompt, provider, model, timeout)
        elapsed = time.time() - start_time
        _log_cost(task_id, "manual", provider, model,
                  result["success"], elapsed)
        return result

    # Auto-route — try pool in order
    routing = route(prompt, health_data)
    pool = routing["pool"]
    errors = []

    for candidate in pool:
        task_id = hashlib.md5(f"{prompt}{time.time()}{candidate['provider']}".encode()).hexdigest()[:12]
        start_time = time.time()
        result = _try_provider(prompt, candidate["provider"],
                                candidate["model"], timeout)
        elapsed = time.time() - start_time
        _log_cost(task_id, routing["complexity"],
                  candidate["provider"], candidate["model"],
                  result["success"], elapsed)

        if result["success"]:
            return result

        errors.append(f"{candidate['provider']}/{candidate['model']}: {result.get('error', 'unknown')}")

    return {
        "success": False,
        "output": "",
        "error": f"All providers failed: {' | '.join(errors)}",
        "complexity": routing["complexity"],
    }


def _try_provider(prompt: str, provider: str, model: str,
                  timeout: int = 300) -> dict:
    """Execute a single provider attempt."""
    cmd = [
        "hermes", "chat",
        "-q", prompt,
        "--provider", provider,
        "-m", model,
        "--quiet",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "HERMES_NO_COLOR": "1"},
        )
        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = "TIMEOUT"
        success = False
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "provider": provider,
            "model": model,
        }

    return {
        "success": success,
        "output": output[:2000],  # Truncate for display
        "error": None if success else output[:500],
        "provider": provider,
        "model": model,
    }


# ── cost tracking ────────────────────────────────────────────────────────
def _log_cost(
    task_id: str,
    complexity: str,
    provider: str,
    model: str,
    success: bool,
    elapsed: float,
) -> None:
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task_id": task_id,
        "complexity": complexity,
        "provider": provider,
        "model": model,
        "success": success,
        "elapsed_sec": round(elapsed, 1),
    }
    with open(COST_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_cost_summary(days: int = 7) -> dict:
    """Summarize costs for the last N days."""
    if not COST_LOG.exists():
        return {"total_tasks": 0, "by_provider": {}, "by_complexity": {}}

    cutoff = time.time() - (days * 86400)
    by_provider = {}
    by_complexity = {}
    total = 0

    with open(COST_LOG) as f:
        for line in f:
            try:
                entry = json.loads(line)
                entry_time = time.mktime(
                    time.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S")
                )
                if entry_time < cutoff:
                    continue

                provider = entry["provider"]
                complexity = entry["complexity"]

                by_provider.setdefault(provider, {"tasks": 0, "success": 0})
                by_provider[provider]["tasks"] += 1
                if entry["success"]:
                    by_provider[provider]["success"] += 1

                by_complexity.setdefault(complexity, 0)
                by_complexity[complexity] += 1

                total += 1
            except (json.JSONDecodeError, KeyError):
                continue

    return {
        "total_tasks": total,
        "days": days,
        "by_provider": by_provider,
        "by_complexity": by_complexity,
    }
