"""
Hermes Router — Complexity-based provider routing for cost optimization.

Classifies task complexity and routes to:
  - LOW    → OpenRouter free models (qwen/qwen3-coder:free)
  - MEDIUM → Nvidia free models (qwen3-coder, glm4, minimax)
  - HIGH   → DeepSeek paid (deepseek-v4-flash)

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


# Provider routing table
PROVIDER_ROUTES = {
    "low": {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder:free",
        "cost_per_1k_tokens": 0,
        "description": "OpenRouter Free",
    },
    "medium": {
        "provider": "nvidia",
        "model": "qwen/qwen3-coder-480b-a35b-instruct",
        "cost_per_1k_tokens": 0,
        "description": "Nvidia Free (qwen3-coder)",
    },
    "high": {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "cost_per_1k_tokens": 0.00028,  # ~$0.28/M tokens
        "description": "DeepSeek v4 Flash (paid)",
    },
}

# Medium fallback: if Nvidia is down, try other free models
MEDIUM_FALLBACKS = [
    {"provider": "nvidia", "model": "z-ai/glm4.7", "cost_per_1k_tokens": 0},
    {"provider": "nvidia", "model": "minimaxai/minimax-m2.7", "cost_per_1k_tokens": 0},
    {"provider": "openrouter", "model": "qwen/qwen3-coder:free", "cost_per_1k_tokens": 0},
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
def route(prompt: str) -> dict:
    """Determine which provider/model to use for a given prompt.

    Returns: {provider, model, complexity, cost_per_1k_tokens}
    """
    complexity = classify_complexity(prompt)
    route_cfg = PROVIDER_ROUTES[complexity]
    return {
        "complexity": complexity,
        "provider": route_cfg["provider"],
        "model": route_cfg["model"],
        "cost_per_1k_tokens": route_cfg["cost_per_1k_tokens"],
        "description": route_cfg["description"],
    }


# ── execution ────────────────────────────────────────────────────────────
def route_execute(
    prompt: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 300,
) -> dict:
    """Route and execute a prompt through the best provider.

    If provider/model are specified, they override the router.
    """
    if not provider or not model:
        routing = route(prompt)
        provider = routing["provider"]
        model = routing["model"]
    else:
        routing = route(prompt)  # Still classify for logging

    task_id = hashlib.md5(f"{prompt}{time.time()}".encode()).hexdigest()[:12]
    start_time = time.time()

    # Build hermes command
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
        elapsed = time.time() - start_time
        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        output = "TIMEOUT"
        success = False

    # Log cost
    _log_cost(task_id, routing["complexity"], provider, model, success, elapsed)

    return {
        "task_id": task_id,
        "complexity": routing["complexity"],
        "provider": provider,
        "model": model,
        "success": success,
        "elapsed_sec": round(elapsed, 1),
        "output": output[:2000],  # Truncate for display
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
