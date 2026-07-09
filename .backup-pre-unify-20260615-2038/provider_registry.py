"""
Provider Registry — single source of truth for all LLM providers.

Every module (dashboard, banner, router) reads from here so adding
a new provider means editing ONE file, not six.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ProviderDef:
    """Definition of a single provider."""

    # Internal key (also used as dashboard data key)
    key: str
    # Display name (short, for banners/labels)
    name: str
    # Default model identifier
    model: str
    # Cost per 1K tokens as string (for display)
    cost_display: str = "FREE"
    # Cost per 1K tokens as float (for sorting)
    cost_per_1k: float = 0.0
    # Which complexity tiers this provider is eligible for
    tiers: list[str] = field(default_factory=lambda: ["low", "medium", "high"])
    # Priority within tier (lower = tried first)
    tier_priority: dict[str, int] = field(default_factory=dict)
    # Short description
    description: str = ""
    # Provider slug for Hermes routing
    provider_slug: str = ""
    # Base URL if different from default
    base_url: str = ""
    # Whether this is a subscription service
    is_subscription: bool = False
    # Status icons for different states
    icons: dict[str, str] = field(default_factory=lambda: {
        "online": "\U0001f7e2",     # 🟢
        "no_model": "\U0001f7e1",   # 🟡
        "limited": "\U0001f7e1",    # 🟡
        "no_key": "\U0001f7e1",     # 🟡
        "rate_limited": "\U0001f534",  # 🔴
        "offline": "\U0001f534",    # 🔴
        "ready": "\U0001f7e2",      # 🟢
        "error": "\u26aa",          # ⚪
    })

    def icon(self, status: str) -> str:
        return self.icons.get(status, "\u26aa")


# ── All Providers ─────────────────────────────────────────────────────────

ALL_PROVIDERS: list[ProviderDef] = [
    ProviderDef(
        key="ollama",
        name="Ollama",
        model="deepseek-v4-flash:cloud",
        description="Ollama Local — custo zero, latência zero",
        tiers=["low"],
        tier_priority={"low": -1},
        cost_display="FREE",
        provider_slug="ollama-local",
    ),
    ProviderDef(
        key="ollama_cloud",
        name="OllamaCloud",
        model="deepseek-v4-flash",
        description="Ollama Cloud — grátis, via proxy local",
        tiers=["low", "medium"],
        tier_priority={"low": 0, "medium": -1},
        cost_display="FREE",
        provider_slug="ollama-launch",
        base_url="http://localhost:11434/v1",
    ),
    ProviderDef(
        key="nous",
        name="NousResearch",
        model="stepfun/step-3.7-flash:free",
        description="NousResearch Free — step-3.7-flash grátis",
        tiers=["low", "medium", "high"],
        tier_priority={"low": 2, "medium": 1, "high": 0},
        cost_display="FREE",
        provider_slug="nous",
    ),
    ProviderDef(
        key="openrouter",
        name="OpenRouter",
        model="qwen/qwen3-coder:free",
        description="OpenRouter Free",
        tiers=["low", "medium", "high"],
        tier_priority={"low": 3, "medium": 4, "high": 2},
        cost_display="FREE",
        provider_slug="openrouter",
    ),
    ProviderDef(
        key="nvidia",
        name="Nvidia",
        model="qwen/qwen3-coder-480b-a35b-instruct",
        description="Nvidia Free — qwen3-coder-480b",
        tiers=["medium"],
        tier_priority={"medium": 2},
        cost_display="FREE",
        provider_slug="nvidia",
    ),
    ProviderDef(
        key="deepseek",
        name="DeepSeek",
        model="deepseek-v4-flash",
        description="DeepSeek Paid — $0.00028/1K tokens",
        tiers=["high"],
        tier_priority={"high": 1},
        cost_display="$0.00028/1K",
        cost_per_1k=0.00028,
        provider_slug="deepseek",
    ),
]

# Ordered list of provider keys for display (dashboard / banner)
DISPLAY_ORDER = [
    "ollama", "ollama_cloud", "openrouter",
    "nvidia", "nous", "deepseek",
]

# Index by key
PROVIDER_MAP: dict[str, ProviderDef] = {p.key: p for p in ALL_PROVIDERS}


def get_providers_for_tier(tier: str, health_data: dict | None = None
                           ) -> list[ProviderDef]:
    """Get providers eligible for a tier, sorted by priority.
    
    If health_data is provided, only returns providers whose status
    allows routing (online, no_model, limited → usable; offline,
    no_key, rate_limited → excluded).
    """
    candidates = [
        p for p in ALL_PROVIDERS
        if tier in p.tiers
    ]
    
    if health_data:
        def _is_usable(key: str) -> bool:
            status = health_data.get(key, {}).get("status", "")
            return status in ("online", "no_model", "limited", "ready")
        
        candidates = [p for p in candidates if _is_usable(p.key)]
    
    candidates.sort(key=lambda p: p.tier_priority.get(tier, 99))
    return candidates


def get_best_for_tier(tier: str, health_data: dict | None = None
                      ) -> ProviderDef | None:
    """Get single best provider for a tier given current health."""
    pool = get_providers_for_tier(tier, health_data)
    return pool[0] if pool else None


def status_is_usable(status: str) -> bool:
    """Can this provider actually handle requests right now?"""
    return status in ("online", "ready")
