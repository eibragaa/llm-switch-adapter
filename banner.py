"""
Banner — Compact provider status + real-time recommendation.
Shows the best provider to use RIGHT NOW with Braille graphical bars.

Usage:
    switch-adapter banner           # Colored terminal banner (animated Braille!)
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

from dashboard import build_dashboard, _get_credential
from hermes_router import recommend_best_provider
from provider_registry import PROVIDER_MAP, DISPLAY_ORDER

# ── Braille bar patterns ──────────────────────────────────────────────
# 7 fill levels per Braille character (empty -> full)
BRAILLE_STEPS = ['\u2800', '\u28c0', '\u28e4', '\u28e6', '\u28f6', '\u28f7', '\u28ff']
# Subtle pulse pattern for empty area (animation)
BRAILLE_GLOW  = ['\u2800', '\u2804', '\u2802', '\u2801', '\u2802', '\u2804']
# Wave patterns for filled area shimmer (animation)
BRAILLE_WAVE  = ['\u28ff', '\u28f7', '\u28fe', '\u28ff', '\u28e7', '\u28ff']

STEPS = len(BRAILLE_STEPS)  # 7


# ── Braille Bar Engine ────────────────────────────────────────────────

def _braille_bar(ratio: float, width: int = 9, animated: bool = False,
                 frame: int = 0) -> str:
    """Draw a horizontal bar using Braille Unicode characters."""
    full = int(ratio * width)
    partial = int(((ratio * width) - full) * STEPS)

    bar_chars = []
    for i in range(width):
        if i < full:
            if animated and width > 2:
                wave_idx = (frame + i * 5) % len(BRAILLE_WAVE)
                bar_chars.append(BRAILLE_WAVE[wave_idx])
            else:
                bar_chars.append(BRAILLE_STEPS[-1])  # full
        elif i == full and partial > 0:
            bar_chars.append(BRAILLE_STEPS[partial])
        else:
            if animated and width > 2:
                glow_idx = (frame + i * 2) % len(BRAILLE_GLOW)
                bar_chars.append(BRAILLE_GLOW[glow_idx])
            else:
                bar_chars.append(BRAILLE_STEPS[0])  # empty
    return ''.join(bar_chars)


def _health_braille(status: str, elapsed: float, width: int = 9,
                    animated: bool = False, frame: int = 0) -> str:
    """Draw a health bar using Braille chars based on status + latency."""
    if status == "online":
        if elapsed < 0.5:
            return _braille_bar(1.0, width, animated, frame)
        elif elapsed < 2:
            return _braille_bar(0.75, width, animated, frame)
        else:
            return _braille_bar(0.5, width, animated, frame)
    elif status == "no_model":
        return _braille_bar(0.4, width, animated, frame)
    elif status == "limited":
        return _braille_bar(0.5, width, animated, frame)
    elif status == "no_key":
        return _braille_bar(0.25, width, animated, frame)
    elif status == "rate_limited":
        return _braille_bar(0.1, width, animated, frame)
    else:
        return _braille_bar(0.0, width, animated, frame)


# ── icons (from registry but with static emoji vars for Python 3.12 safety) ──

_ICON_MAP = {
    "online": "🟢",
    "no_model": "🟡",
    "limited": "🟡",
    "offline": "🔴",
    "no_key": "🟡",
    "rate_limited": "🔴",
    "ready": "🟢",
    "error": "⚪",
}

def _icon(s: str) -> str:
    return _ICON_MAP.get(s, "⚪")


# ── Banner builder ─────────────────────────────────────────────────────

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


# ── Terminal renderer (data-driven) ─────────────────────────────────────

def _render_terminal(data: dict, rec: dict, ts: str) -> str:
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    C = "\033[36m"
    B = "\033[1m"
    GR = "\033[90m"
    S = "\033[0m"

    lines = []
    W = 52

    # Header
    lines.append("")
    lines.append(f"  {B}{C}\u2554{chr(9552) * (W - 2)}\u2557{S}")
    lines.append(f"  {B}{C}\u2551  \u25c6 SWITCH ADAPTER \u2014 BRAILLE STATUS \u25c6{' ' * (W - 48)}\u2551{S}")
    lines.append(f"  {B}{C}\u2551{S}  {GR}{ts}{S}{' ' * (W - 26 - len(ts))}{B}{C}\u2551{S}")
    lines.append(f"  {B}{C}\u255a{chr(9552) * (W - 2)}\u255d{S}")
    lines.append("")
    lines.append(f"  {B}{GR}PROVIDER BRAILLE BARS{S}")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")

    # Data-driven provider rows
    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        p = data.get(key, {})
        if not prov or not p:
            continue
        status = p.get("status", "offline")
        elapsed = p.get("elapsed", 0)
        icon = _icon(status)
        hbar = _health_braille(status, elapsed)
        lat_str = f"{elapsed:.1f}s" if elapsed > 0 else "\u2014"

        if status == "online":
            label = f"{G}{prov.name:12s}{S}"
        elif status in ("no_model", "no_key", "limited"):
            label = f"{Y}{prov.name:12s}{S}"
        else:
            label = f"{R}{prov.name:12s}{S}"

        if status == "online":
            bar_colored = f"{G}{hbar}{S}"
        elif status in ("no_model", "no_key", "limited"):
            bar_colored = f"{Y}{hbar}{S}"
        elif status == "offline":
            bar_colored = f"{R}{hbar}{S}"
        else:
            bar_colored = f"{GR}{hbar}{S}"

        lines.append(f"  {icon} {label} {bar_colored}  {GR}{lat_str}{S}")

    # Finbot
    fu = data.get("finbot_usage", {})
    if fu.get("status") == "ok":
        lines.append("")
        lines.append(f"  {B}{GR}FINBOT TOKEN CONSUMPTION{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for key, fu_prov in sorted(fu.get("providers", {}).items()):
            t = fu_prov.get("today", {})
            tt = fu_prov.get("total", {})
            pd_color = G if t.get("requests", 0) == 0 else C
            if t.get("requests", 0) > 0:
                lines.append(f"  {pd_color}\u25cf{S} {B}{fu_prov.get('provider','?').upper()}{S} ({GR}{fu_prov.get('model','?')}{S})")
                lines.append(f"     {B}Today:{S} {t['total_tokens']} tokens ({t['requests']} reqs, P:{t['prompt_tokens']} C:{t['completion_tokens']})")
            else:
                lines.append(f"  {GR}\u25cf{S} {B}{fu_prov.get('provider','?').upper()}{S} ({GR}{fu_prov.get('model','?')}{S})")
            lines.append(f"     {GR}Total tracked:{S} {tt.get('total_tokens', 0)} tokens ({tt.get('requests', 0)} reqs)")
        if not fu.get("providers"):
            lines.append(f"  {GR}Aguardando requisicoes \u2014 bot reiniciado{S}")
    elif fu.get("status") == "error" and fu.get("detail"):
        lines.append("")
        lines.append(f"  {R}\u25cf{S} FINBOT {GR}{fu['detail'][:60]}{S}")

    # Codex
    if data.get("codex"):
        lines.append("")
        lines.append(f"  {B}{GR}CODEX ACCOUNTS{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for acc in data["codex"]:
            if acc["status"] == "ready":
                dot = f"{G}\u25cf{S}"
                bar = f"{G}{_braille_bar(1.0, 10)}{S}"
            elif "rate_limited" in acc["status"]:
                dot = f"{R}\u25cf{S}"
                bar = f"{R}{_braille_bar(0.2, 10)}{S}"
            else:
                dot = f"{Y}\u25cf{S}"
                bar = f"{Y}{_braille_bar(0.5, 10)}{S}"
            active_m = f"  {C}\u2190 active{S}" if acc.get("active") else ""
            lines.append(f"  {dot} Codex ({acc['name']}) {bar}{active_m}")

    # Usage bar
    costs = data.get("costs", {})
    total = costs.get("today_tasks", 0)
    free_tasks = costs.get("today_free", 0)
    paid_tasks = costs.get("today_paid", 0)
    errors = costs.get("today_errors", 0)

    lines.append("")
    lines.append(f"  {B}{GR}TODAY'S USAGE{S}")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")

    if total > 0:
        free_pct = int(free_tasks / total * 100)
        paid_pct = int(paid_tasks / total * 100) if total > 0 else 0
        err_pct = int(errors / total * 100) if total > 0 else 0
        usage_bar = f"{G}{_braille_bar(free_pct / 100, 10)}{S}"
        lines.append(f"  {B}Total: {total} tarefas{S}")
        lines.append(f"  {usage_bar}")
        lines.append(f"  {G}Free{S}: {free_tasks} ({free_pct}%)  {Y}Paid{S}: {paid_tasks} ({paid_pct}%)  {R}Errors{S}: {errors}")
    else:
        lines.append(f"  {GR}Nenhuma tarefa roteada hoje{S}")

    # Per provider breakdown
    by_provider = costs.get("by_provider", {})
    if by_provider and total > 0:
        lines.append("")
        lines.append(f"  {B}{GR}PER PROVIDER{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for provider, count in sorted(by_provider.items(), key=lambda x: -x[1]):
            pct = int(count / total * 100)
            bar = _braille_bar(pct / 100, width=8)
            lines.append(f"  {provider:12s} {bar}  {count} tasks")

    # Recommendation
    lines.append("")
    lines.append(f"  {B}{GR}{chr(9472) * (W - 3)}{S}")
    lines.append(f"  {B}{C}RECOMMENDATION{S}")
    lines.append("")
    lines.append(f"  {G}LOW{S}    \u2794 {rec['low']['provider']:20s}  {GR}({G}FREE{GR}){S}" if rec["low"]["available"]
                 else f"  {R}LOW    \u2794 Unavailable{S}")
    lines.append(f"  {Y}MEDIUM{S} \u2794 {rec['medium']['provider']:20s}  {GR}({G}FREE{GR}){S}" if rec["medium"]["available"]
                 else f"  {R}MEDIUM \u2794 Unavailable{S}")
    lines.append(f"  {C}HIGH{S}   \u2794 {rec['high']['provider']:20s}  {GR}({rec['high']['cost']}){S}" if rec["high"]["available"]
                 else f"  {R}HIGH   \u2794 Unavailable{S}")

    if rec["codex"]["best_account"]:
        lines.append(f"  {G}CODEX{S}  \u2794 {rec['codex']['best_account']}")
    elif rec["codex"]["all_exhausted"]:
        lines.append(f"  {R}CODEX  \u2794 All accounts rate-limited{S}")

    lines.append("")
    lines.append(f"  {B}\U0001f3af BEST VALUE:{S} {C}{rec['overall']['best_value']}{S}")
    if rec["overall"].get("reason"):
        lines.append(f"     {GR}{rec['overall']['reason']}{S}")
    if rec["overall"].get("savings_today") and rec["overall"]["savings_today"] != "\u2014":
        lines.append(f"     {G}\U0001f4b0 Savings today: {rec['overall']['savings_today']}{S}")

    lines.append("")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
    lines.append(f"  {GR}switch-adapter route \"<task>\"   para rotear{S}")
    lines.append(f"  {GR}switch-adapter dashboard        status completo{S}")
    lines.append(f"  {GR}switch-adapter watch            live tracking{S}")
    lines.append("")

    return "\n".join(lines)


# ── Simple renderer (Telegram/cron) ────────────────────────────────────

def _render_simple(data: dict, rec: dict, ts: str) -> str:
    lines = []
    _green = "\U0001f7e2"  # 🟢
    _yellow = "\U0001f7e1"  # 🟡
    _red = "\U0001f534"  # 🔴
    _gray = "\u26aa"  # ⚪

    lines.append("\u25c6 SWITCH ADAPTER")
    lines.append(f"   {ts}")
    lines.append("")

    # Data-driven provider rows
    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        p = data.get(key, {})
        if not prov or not p:
            continue
        status = p.get("status", "offline")
        elapsed = p.get("elapsed", 0)
        icon = _icon(status)
        hbar = _health_braille(status, elapsed, width=9)
        lines.append(f"  {icon} {prov.name:12s} {hbar}  {status.upper()} ({elapsed:.1f}s)")

    # Finbot
    fu = data.get("finbot_usage", {})
    if fu.get("status") == "ok":
        for key, fu_prov in sorted(fu.get("providers", {}).items()):
            t = fu_prov.get("today", {})
            tt = fu_prov.get("total", {})
            fu_icon = _icon("online") if t.get("requests", 0) > 0 else _icon("no_model")
            fu_bar = _health_braille("online" if t.get("requests", 0) > 0 else "no_model", 0.5)
            lines.append(f"  {fu_icon} Finbot     {fu_bar}  {fu_prov.get('model','?')}")
            if t.get("requests", 0) > 0:
                lines.append(f"     Hoje: {t['total_tokens']} tokens  |  Total: {tt.get('total_tokens', 0)} tokens")
            else:
                lines.append(f"     Total tracked: {tt.get('total_tokens', 0)} tokens")
        if not fu.get("providers"):
            lines.append(f"  {_icon('no_model')} Finbot     {' ' * 18}  Waiting for requests")
    elif fu.get("status") == "error":
        lines.append(f"  {_icon('error')} Finbot     {' ' * 18}  {fu.get('detail','')[:50]}")

    lines.append("")
    for acc in data["codex"]:
        active = "  \u2190 ATIVA" if acc.get("active") else ""
        ready = acc["status"] == "ready"
        bar = _braille_bar(1.0, 8) if ready else _braille_bar(0.2, 8)
        lines.append(f"  {_icon('ready' if ready else 'rate_limited')} Codex ({acc['name']}) {bar}{active}")

    costs = data.get("costs", {})
    total = costs.get("today_tasks", 0)
    free_t = costs.get("today_free", 0)
    if total > 0:
        pct = int(free_t / total * 100)
        lines.append(f"  \U0001f4ca Today: {total} tasks ({pct}% free)")
        lines.append(f"     {_braille_bar(pct / 100, 8)}")

    lines.append("")
    lines.append(f"\U0001f4a1 BEST VALUE: {rec['overall']['best_value']}")

    return "\n".join(lines)


# ── HTML renderer ──────────────────────────────────────────────────────

def _render_html(data: dict, rec: dict, ts: str) -> str:
    lines = ["<pre>"]
    lines.append("\u25c6 SWITCH ADAPTER \u2014 WELCOME")
    lines.append(f"   {ts}")
    lines.append("")

    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        p = data.get(key, {})
        if not prov or not p:
            continue
        status = p.get("status", "offline")
        lines.append(f"  {_icon(status)} {prov.name}: {status.upper()}")

    # Finbot
    fu = data.get("finbot_usage", {})
    if fu.get("status") == "ok":
        for key, fu_prov in sorted(fu.get("providers", {}).items()):
            tt = fu_prov.get("total", {})
            t = fu_prov.get("today", {})
            hi = _icon("online") if t.get("requests", 0) > 0 else _icon("no_model")
            lines.append(f"  {hi} Finbot ({fu_prov.get('model','?')}): {tt.get('total_tokens', 0)} tokens tracked")
            if t.get("requests", 0) > 0:
                lines.append(f"     Today: {t['total_tokens']} tokens")
    elif fu.get("status") == "error":
        lines.append(f"  {_icon('error')} Finbot: {fu['detail'][:50]}")
    else:
        lines.append(f"  {_icon('no_model')} Finbot:     No data")

    for acc in data["codex"]:
        active = " << ATIVA" if acc.get("active") else ""
        lines.append(f"  {_icon('ready' if acc['status'] == 'ready' else 'rate_limited')} Codex {acc['name']}{active}")

    lines.append("")
    lines.append(f"\U0001f4a1 BEST VALUE: {rec['overall']['best_value']}")
    lines.append("</pre>")

    return "\n".join(lines)


# ── Terminal Animation ────────────────────────────────────────────────

def _show_banner_animated():
    """Display the terminal banner with animated Braille bars (~3s)."""
    data = build_dashboard()
    rec = recommend_best_provider(data)
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")

    static = _render_terminal(data, rec, ts)
    total_lines = static.count("\n") + 1
    num_frames = 18

    for frame in range(num_frames + 1):
        is_animated = frame < num_frames
        out = _render_terminal_animated(data, rec, ts, frame, is_animated)
        print(f"\033[{total_lines}A", end="", flush=True)
        print(out, end="", flush=True)
        if is_animated:
            time.sleep(0.1)

    print()


def _render_terminal_animated(data: dict, rec: dict, ts: str,
                              frame: int, animated: bool) -> str:
    """Same as _render_terminal but with animated Braille bars."""
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    C = "\033[36m"
    B = "\033[1m"
    GR = "\033[90m"
    S = "\033[0m"

    lines = []
    W = 52

    lines.append("")
    lines.append(f"  {B}{C}\u2554{chr(9552) * (W - 2)}\u2557{S}")
    subtitle = "BRAILLE ANIMATED" if animated else "BRAILLE STATUS"
    lines.append(f"  {B}{C}\u2551  \u25c6 SWITCH ADAPTER \u2014 {subtitle} \u25c6{' ' * (W - 44)}\u2551{S}")
    lines.append(f"  {B}{C}\u2551{S}  {GR}{ts}{S}{' ' * (W - 26 - len(ts))}{B}{C}\u2551{S}")
    lines.append(f"  {B}{C}\u255a{chr(9552) * (W - 2)}\u255d{S}")
    lines.append("")
    lines.append(f"  {B}{GR}PROVIDER BRAILLE BARS{S}")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")

    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        p = data.get(key, {})
        if not prov or not p:
            continue
        status = p.get("status", "offline")
        elapsed = p.get("elapsed", 0)
        icon = _icon(status)
        hbar = _health_braille(status, elapsed, animated=animated, frame=frame)
        lat_str = f"{elapsed:.1f}s" if elapsed > 0 else "\u2014"

        if status == "online":
            label = f"{G}{prov.name:12s}{S}"
        elif status in ("no_model", "no_key", "limited"):
            label = f"{Y}{prov.name:12s}{S}"
        else:
            label = f"{R}{prov.name:12s}{S}"

        if status == "online":
            bar_colored = f"{G}{hbar}{S}"
        elif status in ("no_model", "no_key", "limited"):
            bar_colored = f"{Y}{hbar}{S}"
        elif status == "offline":
            bar_colored = f"{R}{hbar}{S}"
        else:
            bar_colored = f"{GR}{hbar}{S}"

        lines.append(f"  {icon} {label} {bar_colored}  {GR}{lat_str}{S}")

    # Finbot
    fu = data.get("finbot_usage", {})
    if fu.get("status") == "ok":
        lines.append("")
        lines.append(f"  {B}{GR}FINBOT TOKEN CONSUMPTION{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for key, fu_prov in sorted(fu.get("providers", {}).items()):
            t = fu_prov.get("today", {})
            tt = fu_prov.get("total", {})
            pd_color = G if t.get("requests", 0) == 0 else C
            if t.get("requests", 0) > 0:
                lines.append(f"  {pd_color}\u25cf{S} {B}{fu_prov.get('provider','?').upper()}{S} ({GR}{fu_prov.get('model','?')}{S})")
                lines.append(f"     {B}Today:{S} {t['total_tokens']} tokens ({t['requests']} reqs, P:{t['prompt_tokens']} C:{t['completion_tokens']})")
            else:
                lines.append(f"  {GR}\u25cf{S} {B}{fu_prov.get('provider','?').upper()}{S} ({GR}{fu_prov.get('model','?')}{S})")
            lines.append(f"     {GR}Total tracked:{S} {tt.get('total_tokens', 0)} tokens ({tt.get('requests', 0)} reqs)")
        if not fu.get("providers"):
            lines.append(f"  {GR}Aguardando requisicoes \u2014 bot reiniciado{S}")
    elif fu.get("status") == "error" and fu.get("detail"):
        lines.append("")
        lines.append(f"  {R}\u25cf{S} FINBOT {GR}{fu['detail'][:60]}{S}")

    # Codex
    if data.get("codex"):
        lines.append("")
        lines.append(f"  {B}{GR}CODEX ACCOUNTS{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for acc in data["codex"]:
            if acc["status"] == "ready":
                dot = f"{G}\u25cf{S}"
                bar = f"{G}{_braille_bar(1.0, 10, animated, frame)}{S}"
            elif "rate_limited" in acc["status"]:
                dot = f"{R}\u25cf{S}"
                bar = f"{R}{_braille_bar(0.2, 10, animated, frame)}{S}"
            else:
                dot = f"{Y}\u25cf{S}"
                bar = f"{Y}{_braille_bar(0.5, 10, animated, frame)}{S}"
            active_m = f"  {C}\u2190 active{S}" if acc.get("active") else ""
            lines.append(f"  {dot} Codex ({acc['name']}) {bar}{active_m}")

    # Usage
    costs = data.get("costs", {})
    total = costs.get("today_tasks", 0)
    free_tasks = costs.get("today_free", 0)
    paid_tasks = costs.get("today_paid", 0)
    errors = costs.get("today_errors", 0)

    lines.append("")
    lines.append(f"  {B}{GR}TODAY'S USAGE{S}")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")

    if total > 0:
        free_pct = int(free_tasks / total * 100)
        paid_pct = int(paid_tasks / total * 100) if total > 0 else 0
        err_pct = int(errors / total * 100) if total > 0 else 0
        usage_bar = f"{G}{_braille_bar(free_pct / 100, 10, animated, frame)}{S}"
        lines.append(f"  {B}Total: {total} tarefas{S}")
        lines.append(f"  {usage_bar}")
        lines.append(f"  {G}Free{S}: {free_tasks} ({free_pct}%)  {Y}Paid{S}: {paid_tasks} ({paid_pct}%)  {R}Errors{S}: {errors}")
    else:
        lines.append(f"  {GR}Nenhuma tarefa roteada hoje{S}")

    by_provider = costs.get("by_provider", {})
    if by_provider and total > 0:
        lines.append("")
        lines.append(f"  {B}{GR}PER PROVIDER{S}")
        lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
        for provider, count in sorted(by_provider.items(), key=lambda x: -x[1]):
            pct = int(count / total * 100)
            bar = _braille_bar(pct / 100, width=8, animated=animated, frame=frame)
            lines.append(f"  {provider:12s} {bar}  {count} tasks")

    # Recommendation
    lines.append("")
    lines.append(f"  {B}{GR}{chr(9472) * (W - 3)}{S}")
    lines.append(f"  {B}{C}RECOMMENDATION{S}")
    lines.append("")
    lines.append(f"  {G}LOW{S}    \u2794 {rec['low']['provider']:20s}  {GR}({G}FREE{GR}){S}" if rec["low"]["available"]
                 else f"  {R}LOW    \u2794 Unavailable{S}")
    lines.append(f"  {Y}MEDIUM{S} \u2794 {rec['medium']['provider']:20s}  {GR}({G}FREE{GR}){S}" if rec["medium"]["available"]
                 else f"  {R}MEDIUM \u2794 Unavailable{S}")
    lines.append(f"  {C}HIGH{S}   \u2794 {rec['high']['provider']:20s}  {GR}({rec['high']['cost']}){S}" if rec["high"]["available"]
                 else f"  {R}HIGH   \u2794 Unavailable{S}")

    if rec["codex"]["best_account"]:
        lines.append(f"  {G}CODEX{S}  \u2794 {rec['codex']['best_account']}")
    elif rec["codex"]["all_exhausted"]:
        lines.append(f"  {R}CODEX  \u2794 All accounts rate-limited{S}")

    lines.append("")
    lines.append(f"  {B}\U0001f3af BEST VALUE:{S} {C}{rec['overall']['best_value']}{S}")
    if rec["overall"].get("reason"):
        lines.append(f"     {GR}{rec['overall']['reason']}{S}")
    if rec["overall"].get("savings_today") and rec["overall"]["savings_today"] != "\u2014":
        lines.append(f"     {G}\U0001f4b0 Savings today: {rec['overall']['savings_today']}{S}")

    lines.append("")
    lines.append(f"  {GR}{chr(9472) * (W - 3)}{S}")
    lines.append(f"  {GR}switch-adapter route \"<task>\"   para rotear{S}")
    lines.append(f"  {GR}switch-adapter dashboard        status completo{S}")
    lines.append(f"  {GR}switch-adapter watch            live tracking{S}")
    lines.append("")

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
        _show_banner_animated()


if __name__ == "__main__":
    main()
