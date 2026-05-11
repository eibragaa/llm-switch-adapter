#!/usr/bin/env python3
"""
LLM Switch Adapter — Multi-account & multi-provider router for AI coding tools.

Usage:
    switch-adapter codex add <name> <email>     Add a new Codex account (login + snapshot)
    switch-adapter codex list                   List Codex accounts with status
    switch-adapter codex switch <name>          Switch to a specific Codex account
    switch-adapter codex next                   Auto-detect rate limit → switch to next
    switch-adapter codex status                 Show current account + rate-limit status

    switch-adapter route <prompt>               Classify & route prompt to best provider
    switch-adapter route exec <prompt>          Route AND execute through Hermes
    switch-adapter cost [--days N]             Show cost summary

    switch-adapter test                         Run self-test
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure we can import local modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from account_manager import (
    _parse_exhausted_at,
    add_account,
    list_accounts,
    snapshot_tool_config,
    switch_symlink,
    get_current_account,
    log,
)
from codex_switcher import (
    status as codex_status,
    switch_to_next,
    detect_rate_limit_via_exec,
    mark_exhausted,
    reset_exhausted,
)
from hermes_router import route, route_execute, get_cost_summary


# ── codex commands ───────────────────────────────────────────────────────
def cmd_codex_add(args):
    """codex add <name> <email> — Login + snapshot current codex state."""
    name = args.name
    email = args.email

    print(f"\n📦 Adding Codex account: {name} ({email})")
    print("   Make sure you've already run `codex login` for this account.")
    print("   The current ~/.codex state will be snapshotted.\n")

    # Register account
    add_account("codex", name, email)

    # Snapshot current state
    try:
        dst = snapshot_tool_config("codex", name)
        print(f"✅ Snapshot saved: {dst}")
    except Exception as e:
        print(f"❌ Snapshot failed: {e}")
        sys.exit(1)

    print(f"\n💡 Now you can switch with: switch-adapter codex switch {name}")


def cmd_codex_list(args):
    """List all codex accounts."""
    current = get_current_account("codex")
    accounts = list_accounts("codex")

    if not accounts:
        print("No Codex accounts registered.")
        print("Add one with: switch-adapter codex add <name> <email>")
        return

    print(f"\n📋 Codex Accounts ({len(accounts)} total)\n")
    for name, acc in accounts.items():
        marker = "← ACTIVE" if name == current else ""
        status_icon = "🔴" if acc.get("exhausted") else "🟢"
        cooldown = ""
        if acc.get("exhausted"):
            from account_manager import AccountStatus

            a = AccountStatus(
                name=name,
                email=acc.get("email", ""),
                exhausted=True,
                exhausted_at=_parse_exhausted_at(acc.get("exhausted_at")),
            )
            remaining = a.time_until_reset()
            if remaining > 0:
                cooldown = f" (resets in {remaining:.0f}min)"
            else:
                cooldown = " (cooldown expired — ready!)"
        print(f"  {status_icon} {name}  ({acc.get('email', '?')}) {marker}{cooldown}")

    print()


def cmd_codex_switch(args):
    """Switch to a specific codex account."""
    name = args.name
    try:
        switch_symlink("codex", name)
        print(f"✅ Switched Codex → {name}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("   Available accounts:")
        for acc_name in list_accounts("codex"):
            print(f"     - {acc_name}")
        sys.exit(1)


def cmd_codex_next(args):
    """Auto-detect rate limit and switch to next available account."""
    print("🔍 Checking current Codex account...")
    result = switch_to_next()
    if result:
        print(f"✅ Switched to: {result}")
    else:
        print("❌ No available accounts. All exhausted.")
        status = codex_status()
        for acc in status["accounts"]:
            if acc.get("cooldown_remaining_min"):
                print(f"   {acc['name']}: resets in {acc['cooldown_remaining_min']}min")


def cmd_codex_status(args):
    """Show detailed codex status."""
    status = codex_status()
    print(f"\n📊 Codex Status")
    print(f"   Active account: {status['current'] or 'None (no symlink)'}\n")

    # Check current for rate limit
    if status["current"]:
        print("   Testing current account for rate limits...")
        limit = detect_rate_limit_via_exec()
        if limit and limit["limited"]:
            print(f"   🔴 RATE LIMITED: {limit['message']}")
            if limit.get("reset_at"):
                print(f"   ⏰ Reset at: {limit['reset_at']}")
        elif limit is None:
            print("   🟢 No rate limit detected")
        else:
            print(f"   ⚠️  Check failed: {limit}")

    print()
    for acc in status["accounts"]:
        icon = "←" if acc["active"] else " "
        state = "🔴 exhausted" if acc["exhausted"] else "🟢 ready"
        extra = ""
        if acc.get("cooldown_remaining_min"):
            extra = f" ({acc['cooldown_remaining_min']}min remaining)"
        print(f"  {icon} {acc['name']}: {state}{extra}")
    print()


# ── route commands ───────────────────────────────────────────────────────
def cmd_route(args):
    """Classify and route a prompt."""
    prompt = args.prompt
    routing = route(prompt)

    print(f"\n🧠 Complexity Analysis")
    print(f"   Prompt ({len(prompt)} chars): {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"   Complexity: {routing['complexity'].upper()}")
    print(f"   Provider:   {routing['provider']}")
    print(f"   Model:      {routing['model']}")
    print(f"   Cost:       ${routing['cost_per_1k_tokens']:.6f}/1K tokens")
    print(f"   Tier:       {routing['description']}")
    print()


def cmd_route_exec(args):
    """Route AND execute a prompt."""
    prompt = args.prompt
    routing = route(prompt)

    print(f"\n🚀 Executing via {routing['description']}...")
    print(f"   Model: {routing['model']}")
    print()

    result = route_execute(prompt)

    print(f"\n{'✅' if result['success'] else '❌'} Task {result['task_id']}")
    print(f"   Elapsed: {result['elapsed_sec']}s")
    if result["output"]:
        print(f"\n{result['output']}")
    print()


def cmd_route_dispatch(args):
    """Handle route command — classify or execute based on --exec flag."""
    if not args.prompt:
        print("Usage: switch-adapter route <prompt> [--exec]")
        return
    if args.exec:
        cmd_route_exec(args)
    else:
        cmd_route(args)


def cmd_cost(args):
    """Show cost summary."""
    days = args.days or 7
    summary = get_cost_summary(days)

    print(f"\n💰 Cost Summary (last {days} days)")
    print(f"   Total tasks: {summary['total_tasks']}")
    print()

    if summary["by_complexity"]:
        print("   By Complexity:")
        for level, count in sorted(summary["by_complexity"].items()):
            print(f"     {level}: {count}")
        print()

    if summary["by_provider"]:
        print("   By Provider:")
        for provider, stats in sorted(summary["by_provider"].items()):
            success_rate = (
                f"{stats['success'] / stats['tasks'] * 100:.0f}%"
                if stats["tasks"] > 0
                else "N/A"
            )
            print(f"     {provider}: {stats['tasks']} tasks ({success_rate} success)")
        print()


def cmd_test(args):
    """Run self-test."""
    print("🧪 Running Switch Adapter self-test...\n")

    # Test 1: Complexity classifier
    print("1. Complexity Classifier")
    tests = [
        ("fix import typo in main.py", "low"),
        ("refactor the auth module to use async", "medium"),
        ("debug the memory leak in production", "high"),
        ("what is a decorator?", "low"),
        ("implement a complete REST API with auth", "high"),
    ]
    from hermes_router import classify_complexity

    all_ok = True
    for prompt, expected in tests:
        result = classify_complexity(prompt)
        ok = result == expected
        if not ok:
            all_ok = False
        status = "✅" if ok else "❌"
        print(f"   {status} [{result:6s}] {prompt}")

    # Test 2: Codex accounts
    print("\n2. Codex Accounts")
    accounts = list_accounts("codex")
    print(f"   Registered accounts: {len(accounts)}")
    for name in accounts:
        print(f"     - {name}")

    # Test 3: Current symlink
    print("\n3. Current Symlink")
    current = get_current_account("codex")
    print(f"   Active: {current or 'None'}")

    # Test 4: Rate limit detection
    print("\n4. Rate Limit Detection")
    limit = detect_rate_limit_via_exec()
    if limit and limit["limited"]:
        print(f"   🔴 Rate limited: {limit['message']}")
    elif limit is None:
        print("   🟢 No rate limit detected")
    else:
        print(f"   ⚠️  {limit}")

    print(f"\n{'✅ All tests passed' if all_ok else '⚠️  Some tests failed'}")


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LLM Switch Adapter — Route AI tasks to the cheapest available provider.",
        usage="switch-adapter <command> [<args>]",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # codex
    codex_parser = subparsers.add_parser("codex", help="Codex account management")
    codex_sub = codex_parser.add_subparsers(dest="subcommand")

    p = codex_sub.add_parser("add", help="Add a new Codex account")
    p.add_argument("name", help="Account name (e.g. conta1_outlook)")
    p.add_argument("email", help="Account email")
    p.set_defaults(func=cmd_codex_add)

    p = codex_sub.add_parser("list", help="List Codex accounts")
    p.set_defaults(func=cmd_codex_list)

    p = codex_sub.add_parser("switch", help="Switch to a specific account")
    p.add_argument("name", help="Account name")
    p.set_defaults(func=cmd_codex_switch)

    p = codex_sub.add_parser("next", help="Auto-switch to next available account")
    p.set_defaults(func=cmd_codex_next)

    p = codex_sub.add_parser("status", help="Show detailed status")
    p.set_defaults(func=cmd_codex_status)

    # route <prompt> — classify only (no subcommand needed)
    p = subparsers.add_parser("route", help="Classify a prompt and suggest best provider")
    p.add_argument("prompt", nargs="?", help="The task prompt")
    p.add_argument("--exec", "-e", action="store_true", help="Execute after routing")
    p.set_defaults(func=cmd_route_dispatch)

    # cost
    p = subparsers.add_parser("cost", help="Show cost summary")
    p.add_argument("--days", type=int, help="Number of days (default: 7)")
    p.set_defaults(func=cmd_cost)

    # test
    p = subparsers.add_parser("test", help="Run self-test")
    p.set_defaults(func=cmd_test)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
