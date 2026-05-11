"""
Account Manager — Snapshot + Symlink engine for CLI tool account switching.

Concept:
    ~/.account_manager/data/<account_name>/  ← stores full config snapshots
    ~/.codex  →  symlink →  ~/.account_manager/data/<account_name>/

Supports: Codex, Git, Firebase CLI, or any XDG-compatible tool.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "accounts" / "data"
CONFIG_FILE = BASE_DIR / "accounts" / "accounts.json"
LOG_FILE = BASE_DIR / "accounts" / "logs" / "switch.log"


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line)


# ── config utils ─────────────────────────────────────────────────────────
def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def expand_path(p: str) -> Path:
    """Expand ~ and return absolute path WITHOUT following symlinks."""
    return Path(os.path.expanduser(p)).absolute()


# ── snapshot ─────────────────────────────────────────────────────────────
def snapshot_tool_config(tool: str, account_name: str, lightweight: bool = True) -> Path:
    """Copy the tool's current config dir into the data store.

    Args:
        tool: Tool name ('codex', etc.)
        account_name: Name for this snapshot
        lightweight: If True, only copy auth/config files (skip logs, sessions, caches)
    """
    cfg = load_config()
    tool_cfg = cfg.get("tools", {}).get(tool)
    if not tool_cfg:
        raise ValueError(f"Unknown tool: {tool}")

    src = expand_path(tool_cfg["config_path"])
    dst = DATA_DIR / f"{tool}_{account_name}"

    if not src.exists():
        raise FileNotFoundError(f"Tool config dir not found: {src}")

    # Remove symlink if it exists (don't follow it)
    if src.is_symlink():
        log(f"WARNING: {src} is a symlink. Snapshotting the TARGET instead.")
        src = src.resolve()

    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    if lightweight:
        # Only copy auth + config files
        ESSENTIAL_PATTERNS = ["auth.json", "config.toml", "config.json",
                              "installation_id", "version.json", "models_cache.json"]
        SKIP_NAMES = {"log", "cache", "sessions", "tmp", ".tmp", "plugins",
                      "skills", "rules", "shell_snapshots", "memories",
                      "history.jsonl", "hooks.json", "state_5.sqlite"}

        for item in src.iterdir():
            if item.name in SKIP_NAMES:
                continue
            if item.name.endswith(".sqlite") or item.name.endswith(".sqlite-wal") or item.name.endswith(".sqlite-shm"):
                continue
            if item.name in ESSENTIAL_PATTERNS or item.suffix in [".json", ".toml"]:
                dst_item = dst / item.name
                if item.is_dir():
                    shutil.copytree(item, dst_item)
                else:
                    shutil.copy2(item, dst_item)
    else:
        shutil.copytree(src, dst, symlinks=False)

    log(f"Snapshot saved ({'lightweight' if lightweight else 'full'}): {src} → {dst}")
    return dst


# ── symlink switch ───────────────────────────────────────────────────────
def check_process_running(process_name: str) -> bool:
    """Check if a process with the given name is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def clean_lock_files(target: Path) -> None:
    """Remove .pid, .lock, .sock files from the target directory."""
    for pattern in ["*.pid", "*.lock", "*.sock", "*.lck"]:
        for f in target.glob(pattern):
            f.unlink()
            log(f"Cleaned lock file: {f}")


def switch_symlink(tool: str, account_name: str) -> bool:
    """Switch the tool's config dir symlink to point to a snapshot."""
    cfg = load_config()
    tool_cfg = cfg["tools"].get(tool)
    if not tool_cfg:
        raise ValueError(f"Unknown tool: {tool}")

    target = expand_path(tool_cfg["config_path"])
    snapshot_dir = DATA_DIR / f"{tool}_{account_name}"

    if not snapshot_dir.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_dir}")

    # Safety: check if tool is running
    tool_binary = tool
    if check_process_running(tool_binary):
        log(f"WARNING: {tool} process detected. Switch may cause issues.")
        # Non-fatal — user's choice

    # Backup if real dir (not symlink)
    if target.exists() and not target.is_symlink():
        backup = Path(str(target) + ".backup." + time.strftime("%Y%m%d_%H%M%S"))
        shutil.move(str(target), str(backup))
        log(f"Backed up real dir to: {backup}")

    # Remove existing
    if target.is_symlink() or target.exists():
        target.unlink()

    # Clean lock files from snapshot before linking
    clean_lock_files(snapshot_dir)

    # Create symlink
    target.symlink_to(snapshot_dir, target_is_directory=True)
    log(f"Switched {tool} → {account_name}  ({snapshot_dir})")

    return True


def get_current_account(tool: str) -> Optional[str]:
    """Return the current active account name (from symlink target)."""
    cfg = load_config()
    tool_cfg = cfg["tools"].get(tool)
    if not tool_cfg:
        return None

    target = expand_path(tool_cfg["config_path"])
    if not target.is_symlink():
        return None

    resolved = target.resolve()
    # Extract account name from path: .../data/codex_<name>/
    rel = resolved.relative_to(DATA_DIR)
    # Remove tool prefix: codex_<name> → <name>
    parts = rel.name.split("_", 1)
    return parts[1] if len(parts) > 1 else rel.name


# ── account registry ─────────────────────────────────────────────────────
@dataclass
class AccountStatus:
    name: str
    email: str
    exhausted: bool = False
    exhausted_at: Optional[float] = None
    usage_pct: Optional[int] = None
    cooldown_minutes: int = 180

    def is_available(self) -> bool:
        if not self.exhausted:
            return True
        if self.exhausted_at is None:
            return False
        elapsed = (time.time() - self.exhausted_at) / 60
        return elapsed >= self.cooldown_minutes

    def time_until_reset(self) -> float:
        if not self.exhausted or self.exhausted_at is None:
            return 0
        elapsed = (time.time() - self.exhausted_at) / 60
        return max(0, self.cooldown_minutes - elapsed)


def list_accounts(tool: str) -> list[dict]:
    cfg = load_config()
    tool_cfg = cfg["tools"].get(tool, {})
    return tool_cfg.get("accounts", {})


def add_account(tool: str, name: str, email: str) -> None:
    """Register a new account without snapshotting yet."""
    cfg = load_config()
    if tool not in cfg["tools"]:
        raise ValueError(f"Unknown tool: {tool}")

    cfg["tools"][tool]["accounts"][name] = {
        "email": email,
        "exhausted": False,
        "exhausted_at": None,
        "usage_pct": None,
    }
    save_config(cfg)
    log(f"Account added: {tool}/{name} ({email})")


def mark_exhausted(tool: str, name: str, usage_pct: int = 100) -> None:
    cfg = load_config()
    acc = cfg["tools"][tool]["accounts"].get(name)
    if acc:
        acc["exhausted"] = True
        acc["exhausted_at"] = time.time()
        acc["usage_pct"] = usage_pct
    save_config(cfg)
    log(f"Marked exhausted: {tool}/{name} ({usage_pct}%)")


def reset_exhausted(tool: str, name: str) -> None:
    cfg = load_config()
    acc = cfg["tools"][tool]["accounts"].get(name)
    if acc:
        acc["exhausted"] = False
        acc["exhausted_at"] = None
        acc["usage_pct"] = None
    save_config(cfg)
    log(f"Reset exhausted: {tool}/{name}")
