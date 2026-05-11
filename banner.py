"""
Banner — Compact provider status + real-time recommendation.
Shows the best provider to use RIGHT NOW.

Usage:
    switch-adapter banner           # Colored terminal banner
    switch-adapter banner --simple  # Plain text (for Telegram/cron)
    switch-adapter banner --html    # HTML (for system messages)
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dashboard import (
    build_dashboard,
    _get_credential,
    render_dashboard,
)


def recommend_best_provider(data: dict) -> dict:
    """
    Analyze dashboard data and recommend the best provider
    for each complexity tier RIGHT NOW.
    """
    ollama = data.get("ollama", {})
    openrouter = data.get("openrouter", {})
    nvidia = data.get("nvidia", {})
    deepseek = data.get("deepseek", {})
    codex = data.get("codex", [])

    rec = {
        "low": {"provider": "Ollama Local", "model": "qwen3:4b",
                "cost": "FREE", "available": True},
        "medium": {"provider": "Nvidia Free", "model": "qwen3-coder-480b",
                   "cost": "FREE", "available": True},
        "high": {"provider": "DeepSeek Paid", "model": "deepseek-v4-flash",
                 "cost": "$0.00028/1K", "available": True},
        "codex": {"best_account": None, "all_exhausted": False,
                  "active": None, "available": True},
        "overall": {"best_value": "", "reason": ""},
    }

    # --- LOW tier ---
    if ollama.get("status") == "online" or ollama.get("status") == "no_model":
        rec["low"]["available"] = ollama.get("status") == "online"
        if not rec["low"]["available"]:
            # Try OpenRouter as fallback
            if openrouter.get("status") == "online":
                rec["low"] = {"provider": "OpenRouter Free",
                              "model": "qwen/qwen3-coder:free",
                              "cost": "FREE", "available": True}
    elif openrouter.get("status") == "online":
        rec["low"] = {"provider": "OpenRouter Free",
                      "model": "qwen/qwen3-coder:free",
                      "cost": "FREE", "available": True}
    else:
        rec["low"]["available"] = False

    # --- MEDIUM tier ---
    if nvidia.get("status") == "online":
        rec["medium"] = {"provider": "Nvidia Free",
                         "model": "qwen3-coder-480b",
                         "cost": "FREE", "available": True,
                         "latency": nvidia.get("elapsed", 0)}
    elif ollama.get("status") == "online":
        rec["medium"] = {"provider": "Ollama Local",
                         "model": "qwen3:4b",
                         "cost": "FREE", "available": True}
    elif openrouter.get("status") == "online":
        rec["medium"] = {"provider": "OpenRouter Free",
                         "model": "qwen/qwen3-coder:free",
                         "cost": "FREE", "available": True}
    else:
        rec["medium"]["available"] = False

    # --- HIGH tier ---
    if deepseek.get("status") == "online":
        rec["high"] = {"provider": "DeepSeek Paid",
                       "model": "deepseek-v4-flash",
                       "cost": "$0.00028/1K",
                       "available": True,
                       "balance": deepseek.get("balance", 0)}
    elif openrouter.get("status") == "online":
        rec["high"] = {"provider": "OpenRouter Free",
                       "model": "qwen/qwen3-coder:free",
                       "cost": "FREE (emergency)", "available": True}
    else:
        rec["high"]["available"] = False

    # --- CODEX ---
    ready_accounts = [a for a in codex if a["status"] == "ready"]
    exhausted_accounts = [a for a in codex if "rate_limited" in a["status"]]
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
    if rec["low"]["available"]:
        rec["overall"]["best_value"] = f"LOW → {rec['low']['provider']} ({rec['low']['cost']})"
    elif rec["medium"]["available"]:
        rec["overall"]["best_value"] = f"MEDIUM → {rec['medium']['provider']} ({rec['medium']['cost']})"
    elif rec["high"]["available"]:
        rec["overall"]["best_value"] = f"HIGH → {rec['high']['provider']} ({rec['high']['cost']})"
    else:
        rec["overall"]["best_value"] = "⚠️ Nenhum provider disponível!"

    if rec["overall"]["best_value"]:
        if not rec["low"]["available"] and ollama.get("status") == "no_model":
            rec["overall"]["reason"] = "Dica: rode ollama pull qwen3:4b para ativar provider local gratuito"
        elif paid_tasks > 0 and total > 0:
            pct_paid = int(paid_tasks / total * 100)
            if pct_paid > 30:
                rec["overall"]["reason"] = f"⚠️ {pct_paid}% das tarefas foram pagas — tente tasks mais simples no free"
            else:
                rec["overall"]["reason"] = "✅ Maioria das tarefas em free — keep it up!"

    return rec


def build_banner(style: str = "terminal") -> str:
    """Build the welcome banner with provider status + recommendation."""
    data = build_dashboard()
    rec = recommend_best_provider(data)
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")

    if style == "simple":
        return _render_simple(data, rec, ts)
    elif style == "html":
        return _render_html(data, rec, ts)
    else:
        return _render_terminal(data, rec, ts)


def _icon(s: str) -> str:
    """Status icon."""
    mapping = {
        "online": "🟢",
        "no_model": "🟡",
        "offline": "🔴",
        "no_key": "🟡",
        "rate_limited": "🔴",
        "ready": "🟢",
        "error": "⚪",
    }
    return mapping.get(s, "⚪")


def _render_terminal(data: dict, rec: dict, ts: str) -> str:
    """Colorful terminal banner with ANSI."""
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    C = "\033[36m"
    B = "\033[1m"
    GR = "\033[90m"
    S = "\033[0m"

    lines = []
    lines.append("")
    lines.append(f"  {B}{C}╔══════════════════════════════════════════════╗{S}")
    lines.append(f"  {B}{C}║     🎯 SWITCH ADAPTER — WELCOME              ║{S}")
    lines.append(f"  {B}{C}╚══════════════════════════════════════════════╝{S}")
    lines.append(f"  {GR}{ts}{S}")
    lines.append("")

    # Provider status summary (compact)
    for name, key in [("Ollama", "ollama"), ("OpenRouter", "openrouter"),
                      ("Nvidia", "nvidia"), ("DeepSeek", "deepseek")]:
        p = data[key]
        icon = _icon(p["status"])
        status_str = p["status"].upper()
        lat = f"{p.get('elapsed', 0):.1f}s" if p.get('elapsed', 0) > 0 else "-"
        lines.append(f"  {icon} {name:12s}  {status_str:12s}  {GR}{lat}{S}")

    # Codex
    for acc in data["codex"]:
        dot = G+"●"+S if acc["status"] == "ready" else R+"●"+S
        active = f" {C}← ACTIVE{S}" if acc.get("active") else ""
        lines.append(f"  {dot} Codex ({acc['name']:7s}){active}")

    lines.append("")
    lines.append(f"  {GR}{'─' * 50}{S}")

    # Best recommendation
    lines.append(f"  {B}💡 BEST CHOICE RIGHT NOW{S}")
    lines.append(f"     {G}LOW{S}    → {rec['low']['provider']:20s}  ({Y}FREE{S})" if rec["low"]["available"]
                 else f"     {R}LOW    → Unavailable{S}")
    lines.append(f"     {Y}MEDIUM{S} → {rec['medium']['provider']:20s}  ({Y}FREE{S})" if rec["medium"]["available"]
                 else f"     {R}MEDIUM → Unavailable{S}")
    lines.append(f"     {R}HIGH{S}   → {rec['high']['provider']:20s}  ({rec['high']['cost']})" if rec["high"]["available"]
                 else f"     {R}HIGH   → Unavailable{S}")

    if rec["codex"]["best_account"]:
        lines.append(f"     {G}CODEX{S}  → {rec['codex']['best_account']}")
    elif rec["codex"]["all_exhausted"]:
        lines.append(f"     {R}CODEX  → All accounts rate-limited{S}")

    lines.append("")
    lines.append(f"  {B}🎯 BEST VALUE:{S} {C}{rec['overall']['best_value']}{S}")
    if rec["overall"].get("reason"):
        lines.append(f"     {GR}{rec['overall']['reason']}{S}")
    if rec["overall"].get("savings_today") and rec["overall"]["savings_today"] != "—":
        lines.append(f"     {G}💰 Savings today: {rec['overall']['savings_today']}{S}")

    lines.append("")
    lines.append(f"  {GR}switch-adapter route \"<task>\"  para rotear automaticamente{S}")
    lines.append(f"  {GR}switch-adapter dashboard        para status completo{S}")
    lines.append("")

    return "\n".join(lines)


def _render_simple(data: dict, rec: dict, ts: str) -> str:
    """Plain text (for Telegram/cron)."""
    lines = []
    lines.append(f"🎯 SWITCH ADAPTER")
    lines.append(f"   {ts}")
    lines.append("")

    for name, key in [("Ollama", "ollama"), ("OpenRouter", "openrouter"),
                      ("Nvidia", "nvidia"), ("DeepSeek", "deepseek")]:
        p = data[key]
        lines.append(f"  {_icon(p['status'])} {name}: {p['status'].upper()}")

    for acc in data["codex"]:
        active = " ← ATIVA" if acc.get("active") else ""
        lines.append(f"  {_icon('ready' if acc['status'] == 'ready' else 'rate_limited')} Codex {acc['name']}{active}")

    lines.append("")
    lines.append(f"💡 BEST VALUE: {rec['overall']['best_value']}")
    if rec["overall"].get("reason"):
        lines.append(f"   {rec['overall']['reason']}")

    return "\n".join(lines)


def _render_html(data: dict, rec: dict, ts: str) -> str:
    """HTML format for system messages."""
    lines = ["<pre>"]
    lines.append("🎯 SWITCH ADAPTER — WELCOME")
    lines.append(f"   {ts}")
    lines.append("")

    for name, key in [("Ollama", "ollama"), ("OpenRouter", "openrouter"),
                      ("Nvidia", "nvidia"), ("DeepSeek", "deepseek")]:
        p = data[key]
        lines.append(f"  {_icon(p['status'])} {name}: {p['status'].upper()}")

    for acc in data["codex"]:
        active = " << ATIVA" if acc.get("active") else ""
        lines.append(f"  {_icon('ready' if acc['status'] == 'ready' else 'rate_limited')} Codex {acc['name']}{active}")

    lines.append("")
    lines.append(f"💡 BEST VALUE: {rec['overall']['best_value']}")
    lines.append("</pre>")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Switch Adapter Welcome Banner")
    parser.add_argument("--simple", action="store_true", help="Plain text output")
    parser.add_argument("--html", action="store_true", help="HTML output")
    args = parser.parse_args()

    if args.simple:
        print(build_banner("simple"))
    elif args.html:
        print(build_banner("html"))
    else:
        print(build_banner("terminal"))


if __name__ == "__main__":
    main()
