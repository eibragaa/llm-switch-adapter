"""
Codex Switcher — Rate-limit detection + automatic account switching.

Detects rate limits by parsing `codex exec` output, then triggers
symlink switch to the next available account.
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from account_manager import (
    load_config,
    switch_symlink,
    get_current_account,
    mark_exhausted,
    reset_exhausted,
    list_accounts,
    log,
)


TOOL = "codex"
DEFAULT_TIMEOUT = 120  # seconds


# ── rate-limit detection ─────────────────────────────────────────────────
def parse_rate_limit(output: str) -> Optional[dict]:
    """Parse codex output for rate-limit indicators.

    Returns dict with:
      - limited: bool
      - message: str
      - reset_at: str (e.g. "5:02 AM") or None
    """
    if not output:
        return None

    patterns = [
        r"You've hit your usage limit",
        r"usage limit",
        r"rate limit",
        r"quota exceeded",
    ]

    for pat in patterns:
        if re.search(pat, output, re.IGNORECASE):
            # Try to extract reset time
            reset_match = re.search(
                r"try again at\s+([\d:]+\s*[AP]M)", output, re.IGNORECASE
            )
            return {
                "limited": True,
                "message": re.search(pat, output, re.IGNORECASE).group(0),
                "reset_at": reset_match.group(1) if reset_match else None,
            }

    return None


def detect_rate_limit_via_exec(timeout: int = 10) -> Optional[dict]:
    """Run a minimal codex exec to check if current account is rate-limited.

    Uses a tiny prompt to minimize token cost if the account is still active.
    Returns None if detection fails (couldn't determine), not rate-limited.
    """
    try:
        result = subprocess.run(
            ["codex", "exec", "true"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "CODEX_NO_COLOR": "1"},
        )
        combined = result.stdout + "\n" + result.stderr
        return parse_rate_limit(combined)
    except subprocess.TimeoutExpired:
        log("Rate-limit detection timed out — assuming limited")
        return {"limited": True, "message": "timeout", "reset_at": None}
    except FileNotFoundError:
        return {"limited": True, "message": "codex not installed", "reset_at": None}
    except Exception as e:
        log(f"Rate-limit detection error: {e}")
        return None  # Couldn't determine


# ── account switching ────────────────────────────────────────────────────
def get_available_account() -> Optional[dict]:
    """Find the next available codex account that isn't exhausted."""
    accounts = list_accounts(TOOL)
    current = get_current_account(TOOL)

    for name, acc in accounts.items():
        if acc.get("exhausted"):
            exhausted_at = acc.get("exhausted_at")
            if exhausted_at:
                cooldown = acc.get("cooldown_minutes", 180)
                elapsed = (time.time() - exhausted_at) / 60
                if elapsed >= cooldown:
                    # Cooldown expired — reset and use
                    reset_exhausted(TOOL, name)
                    acc["exhausted"] = False
                else:
                    continue  # Still in cooldown
            else:
                continue

        # Skip current account if we're looking for an alternative
        if name != current:
            return {"name": name, "email": acc.get("email", "unknown")}

    return None


def switch_to_next() -> Optional[str]:
    """Switch to the next available codex account. Returns account name or None."""
    current = get_current_account(TOOL)

    # First, check if current account is rate-limited
    if current:
        limit = detect_rate_limit_via_exec()
        if limit and limit["limited"]:
            mark_exhausted(TOOL, current, 100)
            log(f"Rate limit detected on {current}: {limit['message']}")
            if limit.get("reset_at"):
                log(f"  Reset at: {limit['reset_at']}")

    # Find next available
    next_acc = get_available_account()
    if not next_acc:
        log("No available accounts — all exhausted or in cooldown")
        return None

    # Switch
    switch_symlink(TOOL, next_acc["name"])
    return next_acc["name"]


def status() -> dict:
    """Get full status of all codex accounts."""
    accounts = list_accounts(TOOL)
    current = get_current_account(TOOL)

    result = {"current": current, "accounts": []}

    for name, acc in accounts.items():
        entry = {
            "name": name,
            "email": acc.get("email", "unknown"),
            "exhausted": acc.get("exhausted", False),
            "active": name == current,
        }
        if acc.get("exhausted"):
            exhausted_at = acc.get("exhausted_at")
            if exhausted_at:
                cooldown = acc.get("cooldown_minutes", 180)
                elapsed = (time.time() - exhausted_at) / 60
                remaining = max(0, cooldown - elapsed)
                entry["cooldown_remaining_min"] = round(remaining)
        result["accounts"].append(entry)

    return result
