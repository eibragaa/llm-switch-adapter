#!/usr/bin/env python3
"""
Dashboard Data Service
Unified data layer for Switch Adapter web dashboard.
Aggregates data from provider-costs, provider-benchmarks, and cost JSONL logs.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict

# ── Paths ─────────────────────────────────────────────────────────────────
COSTS_DB = Path("/root/.hermes/provider-costs/costs.db")
BENCHMARKS_DB = Path("/root/.hermes/provider-benchmarks/benchmarks.db")
COSTS_JSONL = Path("/root/repositorio/switch-adapter/accounts/logs/costs.jsonl")

# ── Model Catalog (from provider_registry.py) ────────────────────────────
MODEL_CATALOG = {
    "free_local": [
        {
            "key": "ollama",
            "name": "Ollama Local",
            "model_id": "deepseek-v4-flash:cloud",
            "provider_slug": "ollama-local",
            "cost_label": "FREE",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "tier": "low",
            "category": "Free Local",
            "is_paid": False,
        }
    ],
    "free_cloud": [
        {
            "key": "ollama_cloud",
            "name": "Ollama Cloud",
            "model_id": "deepseek-v4-flash",
            "provider_slug": "ollama-launch",
            "cost_label": "FREE",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "tier": "medium",
            "category": "Free Cloud/API",
            "is_paid": False,
        },
        {
            "key": "nous",
            "name": "NousResearch",
            "model_id": "stepfun/step-3.7-flash:free",
            "provider_slug": "nous",
            "cost_label": "FREE",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "tier": "high",
            "category": "Free Cloud/API",
            "is_paid": False,
        },
        {
            "key": "openrouter",
            "name": "OpenRouter",
            "model_id": "qwen/qwen3-coder:free",
            "provider_slug": "openrouter",
            "cost_label": "FREE",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "tier": "all",
            "category": "Free Cloud/API",
            "is_paid": False,
        },
        {
            "key": "nvidia",
            "name": "Nvidia",
            "model_id": "qwen/qwen3-coder-480b",
            "provider_slug": "nvidia",
            "cost_label": "FREE",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "tier": "medium",
            "category": "Free Cloud/API",
            "is_paid": False,
        },
    ],
    "subscription": [],
    "paid_apis": [
        {
            "key": "deepseek",
            "name": "DeepSeek",
            "model_id": "deepseek-v4-flash",
            "provider_slug": "deepseek",
            "cost_label": "$0.00028/1K",
            "cost_per_1k_input": 0.00007,
            "cost_per_1k_output": 0.00028,
            "tier": "high",
            "category": "Paid APIs",
            "is_paid": True,
        },
    ],
}

# Flatten for lookup
ALL_MODELS = {}
for cat_models in MODEL_CATALOG.values():
    for m in cat_models:
        ALL_MODELS[m["key"]] = m


class DashboardDataService:
    """Unified data access for the dashboard."""

    def __init__(self):
        self._cache = {}
        self._cache_ttl = 60  # seconds
        self._cache_time = {}

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            age = (datetime.now(timezone.utc) - self._cache_time[key]).total_seconds()
            if age < self._cache_ttl:
                return self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = value
        self._cache_time[key] = datetime.now(timezone.utc)

    # ── Cost Summary ──────────────────────────────────────────────────────

    def get_cost_summary(self, days: int = 30) -> dict:
        """Aggregated cost data across all providers."""
        cache_key = f"cost_summary_{days}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Query costs.db (track-provider-costs.py data)
        providers_data = []
        total_calls = 0
        total_tokens = 0
        total_cost = 0.0
        free_tokens = 0
        paid_tokens = 0

        if COSTS_DB.exists():
            conn = sqlite3.connect(COSTS_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT provider, model, status, cost_estimated, timestamp
                FROM provider_costs
                WHERE timestamp >= ? AND status = 'ok'
                ORDER BY timestamp DESC
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()
            conn.close()

            # Aggregate by provider
            agg: dict[str, dict] = {}

            for row in rows:
                p = row["provider"]
                if p not in agg:
                    agg[p] = {
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost": 0.0,
                    }
                agg[p]["calls"] += 1
                agg[p]["cost"] += row["cost_estimated"] or 0
                total_calls += 1
                total_cost += row["cost_estimated"] or 0

            # Get latency stats
            for provider in agg:
                conn = sqlite3.connect(COSTS_DB)
                cur = conn.execute(
                    """
                    SELECT AVG(latency_ms) as avg_lat
                    FROM provider_costs
                    WHERE provider = ? AND status = 'ok' AND timestamp >= ?
                    """,
                    (provider, cutoff),
                )
                r = cur.fetchone()
                conn.close()
                avg_lat = r[0] if r and r[0] else 0
                agg[provider]["avg_latency"] = avg_lat

            for provider, data in agg.items():
                model_info = ALL_MODELS.get(provider, {})
                is_paid = model_info.get("is_paid", False)

                # 7-day and 30-day costs
                cost_7d = sum(
                    r["cost_estimated"] or 0
                    for r in rows
                    if r["provider"] == provider
                    and datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                    >= datetime.now(timezone.utc) - timedelta(days=7)
                )
                cost_30d = data["cost"]

                monthly_proj = (cost_7d / 7) * 30 if cost_7d > 0 else 0

                providers_data.append(
                    {
                        "name": provider,
                        "model": model_info.get("model_id", provider),
                        "display_name": model_info.get("name", provider),
                        "is_paid": is_paid,
                        "calls_total": data["calls"],
                        "tokens_input": data["input_tokens"],
                        "tokens_output": data["output_tokens"],
                        "cost_usd_total": round(float(data["cost"]), 6),
                        "cost_usd_7d": round(float(cost_7d), 6),
                        "cost_usd_30d": round(float(cost_30d), 6),
                        "monthly_projection": round(float(monthly_proj), 6),
                        "avg_latency_ms": round(data.get("avg_latency", 0)),
                    }
                )

                if is_paid:
                    paid_tokens += data["input_tokens"] + data["output_tokens"]
                else:
                    free_tokens += data["input_tokens"] + data["output_tokens"]

        # Also parse JSONL for more accurate token counts
        tokens_by_model = self._parse_jsonl_tokens(days)
        for p in providers_data:
            key = p["name"]
            if key in tokens_by_model:
                p["tokens_input"] = tokens_by_model[key]["input"]
                p["tokens_output"] = tokens_by_model[key]["output"]
                total_tokens += p["tokens_input"] + p["tokens_output"]

        result = {
            "period": {
                "start": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d"),
                "end": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
            "providers": providers_data,
            "totals": {
                "calls": total_calls,
                "tokens": total_tokens,
                "cost_usd": round(total_cost, 6),
                "free_tokens": free_tokens,
                "paid_tokens": paid_tokens,
            },
        }

        self._set_cache(cache_key, result)
        return result

    def _parse_jsonl_tokens(self, days: int) -> dict:
        """Parse costs.jsonl for token breakdown by model."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = defaultdict(lambda: {"input": 0, "output": 0})

        if not COSTS_JSONL.exists():
            return dict(result)

        try:
            with open(COSTS_JSONL) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                        model = entry.get("model", "")
                        input_tok = entry.get("input_tokens", 0)
                        output_tok = entry.get("output_tokens", 0)
                        # Map to provider key
                        provider_key = entry.get("provider", "")
                        if provider_key == "opencode_go":
                            provider_key = "opencode_go"
                        elif provider_key == "ollama_local":
                            provider_key = "ollama"
                        elif provider_key == "ollama_launch":
                            provider_key = "ollama_cloud"
                        result[provider_key]["input"] += input_tok
                        result[provider_key]["output"] += output_tok
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

        return dict(result)

    # ── Token Usage by Model ──────────────────────────────────────────────

    def get_tokens_by_model(self, days: int = 30) -> dict:
        """Detailed token usage per model with daily breakdown.
        
        Note: Token counts are estimated from cost data since the logging
        doesn't currently capture per-request token usage."""
        cache_key = f"tokens_by_model_{days}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        models_data = []

        # Use costs.db data since JSONL doesn't have token counts
        daily_by_model = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "cost": 0.0}))
        totals_by_model = defaultdict(lambda: {"calls": 0, "cost": 0.0})

        if COSTS_DB.exists():
            conn = sqlite3.connect(COSTS_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT provider, model, cost_estimated, timestamp
                FROM provider_costs
                WHERE timestamp >= ? AND status = 'ok'
                ORDER BY timestamp DESC
                """,
                (cutoff.isoformat(),),
            )
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                provider = row["provider"]
                model = row["model"]
                cost = row["cost_estimated"] or 0.0
                ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                date_str = ts.strftime("%Y-%m-%d")

                key = f"{provider}:{model}"
                daily_by_model[key][date_str]["calls"] += 1
                daily_by_model[key][date_str]["cost"] += cost

                totals_by_model[key]["calls"] += 1
                totals_by_model[key]["cost"] += cost

        # Build response with model catalog info
        for key, totals in totals_by_model.items():
            provider, model = key.split(":", 1) if ":" in key else (key, key)
            model_info = ALL_MODELS.get(provider, {})

            daily_list = []
            for date_str in sorted(daily_by_model[key].keys()):
                d = daily_by_model[key][date_str]
                daily_list.append(
                    {
                        "date": date_str,
                        "calls": d["calls"],
                        "cost": round(d["cost"], 6),
                    }
                )

            models_data.append(
                {
                    "provider": provider,
                    "model": model,
                    "display_name": model_info.get("name", model),
                    "is_paid": model_info.get("is_paid", False),
                    "cost_per_1k_input": model_info.get("cost_per_1k_input", 0.0),
                    "cost_per_1k_output": model_info.get("cost_per_1k_output", 0.0),
                    "daily": daily_list,
                    "totals": {
                        "calls": totals["calls"],
                        "cost": round(totals["cost"], 6),
                    },
                }
            )

        result = {"models": models_data}
        self._set_cache(cache_key, result)
        return result

    # ── Model Registry ────────────────────────────────────────────────────

    def get_model_registry(self, health: dict | None = None) -> dict:
        """Structured model catalog from provider_registry + health."""
        health = health or {}

        categories = []
        for cat_key, cat_models in MODEL_CATALOG.items():
            if not cat_models:
                continue
            models_out = []
            for m in cat_models:
                key = m["key"]
                status = health.get(key, {}).get("status", "unknown")
                models_out.append(
                    {
                        "key": key,
                        "name": m["name"],
                        "model_id": m["model_id"],
                        "provider_slug": m["provider_slug"],
                        "cost": m["cost_label"],
                        "tier": m["tier"],
                        "status": status,
                        "category": m["category"],
                        "is_paid": m["is_paid"],
                        "cost_per_1k_input": m.get("cost_per_1k_input", 0.0),
                        "cost_per_1k_output": m.get("cost_per_1k_output", 0.0),
                    }
                )
            categories.append({"name": cat_models[0]["category"], "models": models_out})

        return {"categories": categories}

    # ── Benchmarks ────────────────────────────────────────────────────────

    def get_benchmarks(self, provider: str) -> dict | None:
        """Get latest benchmark for a provider."""
        if not BENCHMARKS_DB.exists():
            return None

        conn = sqlite3.connect(BENCHMARKS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT timestamp, latency_ms, time_to_first_token_ms, status, model
            FROM benchmark_results
            WHERE provider = ? AND status = 'ok'
            ORDER BY timestamp DESC LIMIT 1
            """,
            (provider,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "timestamp": row["timestamp"],
                "latency_ms": row["latency_ms"],
                "ttft_ms": row["time_to_first_token_ms"],
                "status": row["status"],
                "model": row["model"],
            }
        return None

    def get_all_benchmarks(self) -> dict:
        """Get latest benchmarks for all providers."""
        if not BENCHMARKS_DB.exists():
            return {}

        conn = sqlite3.connect(BENCHMARKS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT b.provider, b.timestamp, b.latency_ms, b.time_to_first_token_ms, b.status, b.model
            FROM benchmark_results b
            JOIN (
                SELECT provider, MAX(timestamp) as max_ts
                FROM benchmark_results
                WHERE status = 'ok'
                GROUP BY provider
            ) latest ON b.provider = latest.provider AND b.timestamp = latest.max_ts
            """
        )
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row["provider"]] = {
                "timestamp": row["timestamp"],
                "latency_ms": row["latency_ms"],
                "ttft_ms": row["time_to_first_token_ms"],
                "status": row["status"],
                "model": row["model"],
            }
        return result


# ── Singleton ─────────────────────────────────────────────────────────────
_data_service = None


def get_data_service() -> DashboardDataService:
    global _data_service
    if _data_service is None:
        _data_service = DashboardDataService()
    return _data_service


if __name__ == "__main__":
    import sys

    service = get_data_service()

    if len(sys.argv) > 1:
        if sys.argv[1] == "costs":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            print(json.dumps(service.get_cost_summary(days), indent=2))
        elif sys.argv[1] == "tokens":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            print(json.dumps(service.get_tokens_by_model(days), indent=2))
        elif sys.argv[1] == "models":
            print(json.dumps(service.get_model_registry(), indent=2))
        elif sys.argv[1] == "benchmarks":
            print(json.dumps(service.get_all_benchmarks(), indent=2))
    else:
        # Full test
        print("=== Cost Summary (30d) ===")
        print(json.dumps(service.get_cost_summary(30), indent=2))
        print("\n=== Tokens by Model (30d) ===")
        print(json.dumps(service.get_tokens_by_model(30), indent=2))
        print("\n=== Model Registry ===")
        print(json.dumps(service.get_model_registry(), indent=2))
        print("\n=== Benchmarks ===")
        print(json.dumps(service.get_all_benchmarks(), indent=2))