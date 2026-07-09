#!/usr/bin/env python3
"""
Switch Adapter Web Dashboard — FastAPI backend + WebSocket for real-time updates.
Serves data from dashboard.py and provides a modern web UI.
"""

import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Add local modules (once!)
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dashboard import build_dashboard, render_json, get_cost_stats
from dashboard_data import get_data_service

# Thread pool for blocking operations
_executor = ThreadPoolExecutor(max_workers=4)

# Cache for dashboard data
_dashboard_cache = {"data": None, "last_update": 0, "lock": asyncio.Lock()}
_cache_ttl = 8  # seconds

# Cache auth.json in memory
_auth_cache = {"data": None, "mtime": 0}


async def get_cached_dashboard() -> dict:
    """Get dashboard data from cache or build fresh."""
    now = time.time()
    async with _dashboard_cache["lock"]:
        if _dashboard_cache["data"] is not None and (now - _dashboard_cache["last_update"]) < _cache_ttl:
            return _dashboard_cache["data"]
        
        # Cache miss or expired, build fresh
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, build_dashboard)
        _dashboard_cache["data"] = data
        _dashboard_cache["last_update"] = now
        return data


async def refresh_dashboard_cache():
    """Background task to refresh dashboard cache."""
    while True:
        try:
            await asyncio.sleep(_cache_ttl)
            async with _dashboard_cache["lock"]:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(_executor, build_dashboard)
                _dashboard_cache["data"] = data
                _dashboard_cache["last_update"] = time.time()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Cache refresh error: {e}")


# ── WebSocket Connection Manager ──────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ── Background Data Updater ───────────────────────────────────────────────

async def periodic_broadcast():
    """Broadcast cached dashboard data to all WebSocket clients every 5s."""
    while True:
        try:
            data = await get_cached_dashboard()
            json_data = render_json(data)
            await manager.broadcast(json_data)
        except Exception as e:
            print(f"Broadcast error: {e}")
        await asyncio.sleep(5)  # More frequent broadcasts from cache


# ── FastAPI App ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background tasks
    cache_task = asyncio.create_task(refresh_dashboard_cache())
    broadcast_task = asyncio.create_task(periodic_broadcast())
    yield
    # Shutdown
    for task in (cache_task, broadcast_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Switch Adapter Dashboard",
    description="Real-time provider status, cost tracking, and routing for LLM Switch Adapter",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web_static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── API Routes ────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def get_dashboard():
    """Get current dashboard data as JSON (from cache)."""
    data = await get_cached_dashboard()
    import json
    return json.loads(render_json(data))


@app.get("/api/dashboard/full")
async def get_dashboard_full():
    """Get full dashboard data with all details (from cache)."""
    return await get_cached_dashboard()


@app.get("/api/costs")
async def get_costs(days: int = 1):
    """Get cost summary."""
    from dashboard import get_cost_stats
    return get_cost_stats(days)


@app.get("/api/providers")
async def get_providers():
    """Get provider registry info."""
    from provider_registry import PROVIDER_MAP, ALL_PROVIDERS, DISPLAY_ORDER, status_is_usable
    result = {}
    for key in DISPLAY_ORDER:
        prov = PROVIDER_MAP.get(key)
        if prov:
            result[key] = {
                "name": prov.name,
                "model": prov.model,
                "cost_per_1k": prov.cost_per_1k,
                "tier": prov.tiers[0] if prov.tiers else "unknown",
                "description": prov.description,
            }
    return result


# ── New Analytics Endpoints ───────────────────────────────────────────────

@app.get("/api/costs/summary")
async def get_cost_summary(days: int = 30):
    """Aggregated cost data across all providers with historical breakdown."""
    loop = asyncio.get_event_loop()
    service = get_data_service()
    return await loop.run_in_executor(_executor, service.get_cost_summary, days)


@app.get("/api/tokens/by-model")
async def get_tokens_by_model(days: int = 30):
    """Detailed token usage per model with daily breakdown."""
    loop = asyncio.get_event_loop()
    service = get_data_service()
    return await loop.run_in_executor(_executor, service.get_tokens_by_model, days)


@app.get("/api/models")
async def get_model_registry():
    """Structured model catalog from provider_registry + health."""
    # Get health data from dashboard
    loop = asyncio.get_event_loop()
    dashboard_data = await loop.run_in_executor(_executor, build_dashboard)
    
    # Extract health status for each provider key
    health = {}
    for key, data in dashboard_data.items():
        if isinstance(data, dict) and "status" in data:
            health[key] = {"status": data["status"]}
    
    service = get_data_service()
    return await loop.run_in_executor(_executor, service.get_model_registry, health)


@app.get("/api/benchmarks")
async def get_benchmarks():
    """Latest benchmark results for all providers."""
    loop = asyncio.get_event_loop()
    service = get_data_service()
    return await loop.run_in_executor(_executor, service.get_all_benchmarks)


@app.get("/api/health")
async def health_check():
    """Lightweight health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial data immediately (async)
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, build_dashboard)
        await websocket.send_text(render_json(data))
        # Keep connection alive, ignore incoming messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ── Web UI ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard_ui():
    """Serve the main dashboard HTML."""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content=_default_html(), status_code=200)


def _default_html() -> str:
    """Fallback HTML if static file not found."""
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Switch Adapter Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #0d1117;
                --bg-elevated: #161b22;
                --border: #30363d;
                --fg: #e6edf3;
                --fg-muted: #8b949e;
                --accent: #58a6ff;
                --accent-dim: #1f6feb;
                --green: #3fb950;
                --yellow: #d29922;
                --red: #f85149;
                --purple: #a371f7;
                --cyan: #39c5cf;
            }
            * { font-family: 'Space Grotesk', sans-serif; }
            .mono { font-family: 'JetBrains Mono', monospace; }
            .provider-card { transition: transform 0.15s ease, box-shadow 0.15s ease; }
            .provider-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
            .status-dot { width: 10px; height: 10px; border-radius: 50%; animation: pulse 2s infinite; }
            .status-online { background: var(--green); box-shadow: 0 0 8px var(--green); }
            .status-limited { background: var(--yellow); box-shadow: 0 0 8px var(--yellow); }
            .status-offline { background: var(--red); box-shadow: 0 0 8px var(--red); }
            .status-no_key { background: var(--fg-muted); }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .progress-bar { height: 6px; border-radius: 3px; background: var(--border); overflow: hidden; }
            .progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
            .providers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
            @media (max-width: 640px) { .providers-grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body class="bg-[var(--bg)] text-[var(--fg)] min-h-screen">
        <!-- Header -->
        <header class="border-b border-[var(--border)] bg-[var(--bg-elevated)]/80 backdrop-blur-sm sticky top-0 z-10">
            <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--purple)] flex items-center justify-center">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold tracking-tight">Switch Adapter</h1>
                        <p class="text-xs text-[var(--fg-muted)] mono">Multi-provider LLM Router</p>
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <div class="text-right hidden sm:block">
                        <p class="text-xs text-[var(--fg-muted)]">Última atualização</p>
                        <p id="lastUpdate" class="mono text-sm font-medium">--:--:--</p>
                    </div>
                    <button id="refreshBtn" class="px-3 py-1.5 text-sm font-medium text-[var(--fg)] bg-[var(--border)] rounded-lg hover:bg-[var(--accent-dim)] transition-colors flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                        Atualizar
                    </button>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-7xl mx-auto px-4 py-6">
            <!-- Route Suggestion Banner -->
            <section id="routeSuggestion" class="mb-6 p-4 rounded-xl bg-gradient-to-r from-[var(--accent-dim)]/20 to-[var(--purple)]/20 border border-[var(--accent)]/30 hidden">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <div class="w-2 h-2 rounded-full bg-[var(--green)]" id="routePulse"></div>
                        <span class="font-medium">Melhor rota para tarefas <span id="routeTier" class="font-mono text-[var(--accent)]"></span>:</span>
                        <span id="routeProvider" class="font-bold mono text-[var(--fg)]"></span>
                        <span class="text-[var(--fg-muted)] text-sm">(<span id="routeCost" class="font-mono"></span>)</span>
                    </div>
                    <span class="text-xs text-[var(--fg-muted)] mono">Atualiza a cada 10s via WebSocket</span>
                </div>
            </section>

            <!-- Stats Row -->
            <section class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6" id="statsRow">
                <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                    <p class="text-xs text-[var(--fg-muted)] uppercase tracking-wider">Tarefas Hoje</p>
                    <p id="statTasks" class="text-3xl font-bold mono mt-1">--</p>
                </article>
                <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                    <p class="text-xs text-[var(--fg-muted)] uppercase tracking-wider">Free</p>
                    <p id="statFree" class="text-3xl font-bold mono text-[var(--green)] mt-1">--</p>
                </article>
                <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                    <p class="text-xs text-[var(--fg-muted)] uppercase tracking-wider">Pago</p>
                    <p id="statPaid" class="text-3xl font-bold mono text-[var(--yellow)] mt-1">--</p>
                </article>
                <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                    <p class="text-xs text-[var(--fg-muted)] uppercase tracking-wider">Custo Estimado</p>
                    <p id="statCost" class="text-3xl font-bold mono text-[var(--red)] mt-1">$0.0000</p>
                </article>
            </section>

            <!-- Providers Grid -->
            <section>
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold flex items-center gap-2">
                        <svg class="w-5 h-5 text-[var(--accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>
                        Providers
                    </h2>
                    <div class="flex items-center gap-2 text-xs text-[var(--fg-muted)]">
                        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[var(--green)]"></span>Online</span>
                        <span class="flex items-center gap-1 ml-3"><span class="w-2 h-2 rounded-full bg-[var(--yellow)]"></span>Limitado</span>
                        <span class="flex items-center gap-1 ml-3"><span class="w-2 h-2 rounded-full bg-[var(--red)]"></span>Offline</span>
                    </div>
                </div>
                <div class="providers-grid" id="providersGrid">
                    <!-- Populated by JS -->
                </div>
            </section>

            <!-- Finbot & Codex Sections -->
            <section class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8" id="extraSections">
                <!-- Populated by JS -->
            </section>
        </main>

        <!-- Footer -->
        <footer class="border-t border-[var(--border)] py-4 mt-10">
            <div class="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--fg-muted)]">
                <span>Switch Adapter Dashboard • <a href="https://github.com/seuusuario/switch-adapter" class="text-[var(--accent)] hover:underline" target="_blank">GitHub</a></span>
                <span class="mono" id="websocketStatus">WebSocket: Conectando...</span>
            </div>
        </footer>

        <script>
            // ── State ──
            let ws = null;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 10;

            // ── DOM Elements ──
            const providersGrid = document.getElementById('providersGrid');
            const extraSections = document.getElementById('extraSections');
            const routeSuggestion = document.getElementById('routeSuggestion');
            const routeTier = document.getElementById('routeTier');
            const routeProvider = document.getElementById('routeProvider');
            const routeCost = document.getElementById('routeCost');
            const lastUpdateEl = document.getElementById('lastUpdate');
            const websocketStatus = document.getElementById('websocketStatus');
            const refreshBtn = document.getElementById('refreshBtn');

            // ── Icons ──
            const icons = {
                ollama: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>',
                openrouter: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.95 2.25z"/></svg>',
                nvidia: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M13.5.6c-.4 0-.8.1-1.1.4L.2 8.4c-.5.4-.5 1.1 0 1.5l12.2 10.6c.3.3.7.4 1.1.4.4 0 .8-.1 1.1-.4l12.2-10.6c.5-.4.5-1.1 0-1.5L14.7.2c-.3-.3-.7-.4-1.1-.4zM12 2.7l9.1 7.9-9.1 7.9-9.1-7.9 9.1-7.9zM12 17.9c-2.3 0-4.2-1.3-5.1-3.1l4.2-3.6c.4.8 1.2 1.4 2.2 1.4 1 0 1.8-.6 2.1-1.5l.1-.4.1.4c.3.9 1.1 1.5 2.1 1.5 1 0 1.8-.6 2.2-1.4l4.2 3.6c-.9 1.8-2.8 3.1-5.1 3.1z"/></svg>',
                deepseek: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
                opencode: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M14.7 3.3c-.3-.3-.7-.4-1.1-.4H10.4c-.4 0-.8.1-1.1.4L.2 9.2c-.5.4-.5 1.1 0 1.5l12.2 10.6c.3.3.7.4 1.1.4h3.2c.4 0 .8-.1 1.1-.4l12.2-10.6c.5-.4.5-1.1 0-1.5L14.7 3.3zM12 17.9c-2.3 0-4.2-1.3-5.1-3.1l4.2-3.6c.4.8 1.2 1.4 2.2 1.4 1 0 1.8-.6 2.1-1.5l.1-.4.1.4c.3.9 1.1 1.5 2.1 1.5 1 0 1.8-.6 2.2-1.4l4.2 3.6c-.9 1.8-2.8 3.1-5.1 3.1z"/></svg>',
                nous: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
                finbot: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.95 2.25z"/></svg>',
                codex: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>',
                tailscale: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-12.5v9h2v-9zm4 9v-9h2v9h-2zM6.5 12.5v-9h2v9h-2z"/></svg>',
            };

            const tierColors = {
                low: 'var(--green)',
                medium: 'var(--yellow)',
                high: 'var(--red)',
            };

            const tierLabels = {
                low: 'LOW (grátis local)',
                medium: 'MEDIUM (API grátis)',
                high: 'HIGH (pago)',
            };

            // ── Helpers ──
            function formatTime(date = new Date()) {
                return date.toLocaleTimeString('pt-BR', { hour12: false });
            }

            function statusClass(status) {
                if (['online', 'ready'].includes(status)) return 'status-online';
                if (['limited', 'no_model', 'rate_limited'].includes(status)) return 'status-limited';
                if (['offline', 'unreachable', 'error', 'no_key'].includes(status)) return 'status-offline';
                return 'status-offline';
            }

            function statusLabel(status) {
                const labels = {
                    online: 'Online',
                    offline: 'Offline',
                    limited: 'Limitado',
                    no_model: 'Sem modelo',
                    no_key: 'Sem key',
                    rate_limited: 'Rate limited',
                    unreachable: 'Inacessível',
                    ready: 'Pronto',
                    exhausted: 'Exhausted',
                };
                return labels[status] || status;
            }

            function formatNumber(n) {
                if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
                if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
                return n.toString();
            }

            // ── Render Provider Card ──
            function renderProviderCard(key, data) {
                const icon = icons[key] || '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>';
                const status = data.status || 'offline';
                const elapsed = data.latency_ms || data.elapsed || 0;
                const model = data.model || '—';
                const detail = data.detail || '';

                const latencyColor = elapsed < 1000 ? 'var(--green)' : elapsed < 3000 ? 'var(--yellow)' : 'var(--red)';

                return `
                    <article class="provider-card bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                        <div class="flex items-start gap-3">
                            <div class="w-10 h-10 rounded-lg bg-[var(--border)]/50 flex items-center justify-center text-[var(--accent)] flex-shrink-0">
                                ${icon}
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <h3 class="font-semibold truncate">${key}</h3>
                                    <span class="status-dot ${statusClass(status)}"></span>
                                </div>
                                <p class="text-xs text-[var(--fg-muted)] mono truncate">${model}</p>
                                ${detail ? `<p class="text-xs text-[var(--fg-muted)] mt-1 truncate">${detail}</p>` : ''}
                                <div class="flex items-center gap-3 mt-3 pt-2 border-t border-[var(--border)]">
                                    <span class="text-xs text-[var(--fg-muted)] mono" style="color: ${latencyColor}">${elapsed < 1000 ? (elapsed * 1000).toFixed(0) + 'ms' : (elapsed / 1000).toFixed(2) + 's'}</span>
                                    <span class="text-xs text-[var(--fg-muted)]">${statusLabel(status)}</span>
                                </div>
                            </div>
                        </div>
                    </article>
                `;
            }

            // ── Render Finbot ──
            function renderFinbot(data) {
                if (!data || data.status !== 'ok') {
                    return `
                        <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                            <h3 class="font-semibold mb-3 flex items-center gap-2">
                                ${icons.finbot} Finbot (RPi3)
                            </h3>
                            <p class="text-[var(--fg-muted)] text-sm">${data?.detail || 'Não disponível'}</p>
                        </article>
                    `;
                }

                let providersHtml = '';
                for (const [key, prov] of Object.entries(data.providers || {})) {
                    const today = prov.today || {};
                    const total = prov.total || {};
                    const reqs = today.requests || 0;
                    const tokens = today.total_tokens || 0;
                    const tTokens = total.total_tokens || 0;

                    providersHtml += `
                        <div class="mb-3 last:mb-0 p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                            <div class="flex items-center justify-between mb-1">
                                <span class="font-medium text-sm">${prov.provider?.toUpperCase() || key}</span>
                                <span class="text-xs text-[var(--fg-muted)] mono">${prov.model || ''}</span>
                            </div>
                            ${reqs > 0 ? `
                                <div class="grid grid-cols-2 gap-2 text-xs">
                                    <div><span class="text-[var(--fg-muted)]">Hoje:</span> <span class="mono">${reqs} reqs</span></div>
                                    <div><span class="text-[var(--fg-muted)]">Tokens:</span> <span class="mono">${formatNumber(tokens)}</span></div>
                                    <div class="col-span-2"><span class="text-[var(--fg-muted)]">Total:</span> <span class="mono">${formatNumber(tTokens)} tokens</span></div>
                                </div>
                            ` : `
                                <p class="text-xs text-[var(--fg-muted)]">Aguardando requisições</p>
                            `}
                        </div>
                    `;
                }

                return `
                    <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                        <h3 class="font-semibold mb-3 flex items-center gap-2">
                            ${icons.finbot} Finbot (RPi3)
                        </h3>
                        <div class="space-y-2">${providersHtml}</div>
                    </article>
                `;
            }

            // ── Render Codex ──
            function renderCodex(accounts) {
                let accountsHtml = '';
                for (const acc of accounts || []) {
                    const isActive = acc.active;
                    const status = acc.status || 'unknown';
                    const statusColors = {
                        ready: 'var(--green)',
                        'rate_limited': 'var(--red)',
                        exhausted: 'var(--red)',
                    };
                    const color = statusColors[status] || 'var(--fg-muted)';

                    accountsHtml += `
                        <div class="flex items-center justify-between p-2 rounded-lg ${isActive ? 'bg-[var(--accent)]/10 border border-[var(--accent)]/30' : 'bg-[var(--bg)] border border-[var(--border)]'}">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full" style="background: ${color}"></span>
                                <div>
                                    <p class="font-medium text-sm">${acc.name} ${isActive ? '<span class="text-[var(--accent)] text-xs ml-1">ATIVA</span>' : ''}</p>
                                    <p class="text-xs text-[var(--fg-muted)] mono">${acc.email}</p>
                                </div>
                            </div>
                            <span class="text-xs mono" style="color: ${color}">${status}</span>
                        </div>
                    `;
                }

                return `
                    <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                        <h3 class="font-semibold mb-3 flex items-center gap-2">
                            ${icons.codex} Codex Accounts
                        </h3>
                        <div class="space-y-1">${accountsHtml || '<p class="text-[var(--fg-muted)] text-sm">Nenhuma conta</p>'}</div>
                    </article>
                `;
            }

            // ── Render Tailscale ──
            function renderTailscale(data) {
                if (!data || data.status === 'error' || data.status === 'not_installed') {
                    return `
                        <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                            <h3 class="font-semibold mb-3 flex items-center gap-2">
                                ${icons.tailscale} Tailscale Mesh
                            </h3>
                            <p class="text-[var(--fg-muted)] text-sm">${data?.detail || 'Tailscale não disponível'}</p>
                        </article>
                    `;
                }

                const statusColors = {
                    connected: 'var(--green)',
                    no_peers: 'var(--yellow)',
                    timeout: 'var(--red)',
                };
                const statusColor = statusColors[data.status] || 'var(--fg-muted)';
                const statusText = data.status.charAt(0).toUpperCase() + data.status.slice(1).replace('_', ' ');

                let peersHtml = '';
                for (const peer of data.peers || []) {
                    const peerColor = peer.online ? 'var(--green)' : 'var(--red)';
                    peersHtml += `
                        <div class="flex items-center justify-between p-2 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full" style="background: ${peerColor}"></span>
                                <div>
                                    <p class="font-medium text-sm">${peer.dns_name || 'unnamed'}</p>
                                    <p class="text-xs text-[var(--fg-muted)] mono">${peer.tailscale_ip}</p>
                                </div>
                            </div>
                            <span class="text-xs" style="color: ${peerColor}">${peer.online ? 'Online' : 'Offline'}</span>
                        </div>
                    `;
                }

                return `
                    <article class="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-4">
                        <h3 class="font-semibold mb-3 flex items-center gap-2">
                            ${icons.tailscale} Tailscale Mesh
                        </h3>
                        <div class="space-y-2 mb-3">
                            <div class="grid grid-cols-2 gap-2 text-sm">
                                <div>
                                    <span class="text-[var(--fg-muted)]">Status:</span>
                                    <span class="mono ml-2" style="color: ${statusColor}">${statusText}</span>
                                </div>
                                <div>
                                    <span class="text-[var(--fg-muted)]">Seu IP:</span>
                                    <span class="mono ml-2">${data.local_ip}</span>
                                </div>
                                <div class="col-span-2">
                                    <span class="text-[var(--fg-muted)]">Peers:</span>
                                    <span class="mono ml-2">${data.online_count} / ${data.total_count} online</span>
                                </div>
                            </div>
                            <a href="${data.dashboard_url}" target="_blank" class="inline-block px-3 py-1.5 text-xs font-medium text-[var(--fg)] bg-[var(--accent)]/20 border border-[var(--accent)]/30 rounded-lg hover:bg-[var(--accent)]/30 transition-colors">
                                Abrir Dashboard via Tailscale →
                            </a>
                        </div>
                        <div class="space-y-1 max-h-60 overflow-y-auto">
                            ${peersHtml || '<p class="text-[var(--fg-muted)] text-sm">Nenhum peer encontrado</p>'}
                        </div>
                    </article>
                `;
            }

            // ── Render Route Suggestion ──
            function renderRouteSuggestion(rec) {
                if (!rec) return;

                let hasAvailable = false;
                for (const tier of ['low', 'medium', 'high']) {
                    if (rec[tier]?.available) {
                        routeTier.textContent = tierLabels[tier];
                        routeTier.style.color = tierColors[tier];
                        routeProvider.textContent = rec[tier].provider;
                        routeCost.textContent = rec[tier].cost;
                        hasAvailable = true;
                        break;
                    }
                }
                routeSuggestion.classList.toggle('hidden', !hasAvailable);
            }

            // ── Render Stats ──
            function renderStats(costs) {
                const total = costs.today_tasks || 0;
                const free = costs.today_free || 0;
                const paid = costs.today_paid || 0;
                const cost = costs.estimated_cost_usd || 0;

                document.getElementById('statTasks').textContent = total;
                document.getElementById('statFree').textContent = free;
                document.getElementById('statPaid').textContent = paid;
                document.getElementById('statCost').textContent = '$' + cost.toFixed(4);
            }

            // ── Main Render ──
            function renderDashboard(data) {
                // Providers
                const providerKeys = ['ollama', 'ollama_cloud', 'openrouter', 'nous', 'nvidia', 'opencode_go', 'deepseek'];
                providersGrid.innerHTML = providerKeys.map(key => renderProviderCard(key, data[key])).join('');

                // Stats
                renderStats(data.costs || {});

                // Route suggestion
                if (data.costs) {
                    // We need to compute route suggestion from data
                    // For now, show based on what's online
                    const lowAvailable = ['ollama', 'ollama_cloud', 'openrouter', 'nous'].some(k => data[k]?.status === 'online');
                    const medAvailable = ['opencode_go'].some(k => data[k]?.status === 'online');
                    const highAvailable = ['deepseek', 'nvidia'].some(k => data[k]?.status === 'online');

                    const rec = {
                        low: { available: lowAvailable, provider: 'Ollama', cost: 'FREE' },
                        medium: { available: medAvailable, provider: 'OpenCode Go', cost: '$10/mo sub' },
                        high: { available: highAvailable, provider: 'DeepSeek', cost: '~$0.14/1K' },
                    };
                    renderRouteSuggestion(rec);
                }

                // Extra sections (Finbot + Codex + Tailscale)
                extraSections.innerHTML = `
                    ${renderFinbot(data.finbot_usage)}
                    ${renderCodex(data.codex)}
                    ${renderTailscale(data.tailscale)}
                `;

                // Last update
                lastUpdateEl.textContent = formatTime();
            }

            // ── WebSocket ──
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;

                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    websocketStatus.textContent = 'WebSocket: Conectado ✓';
                    websocketStatus.style.color = 'var(--green)';
                    reconnectAttempts = 0;
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        renderDashboard(data);
                    } catch (e) {
                        console.error('WS parse error:', e);
                    }
                };

                ws.onclose = () => {
                    websocketStatus.textContent = 'WebSocket: Reconectando...';
                    websocketStatus.style.color = 'var(--yellow)';
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        setTimeout(connectWebSocket, Math.min(1000 * reconnectAttempts, 10000));
                    } else {
                        websocketStatus.textContent = 'WebSocket: Desconectado';
                        websocketStatus.style.color = 'var(--red)';
                    }
                };

                ws.onerror = (err) => {
                    console.error('WebSocket error:', err);
                };
            }

            // ── Manual Refresh ──
            async function manualRefresh() {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizando...';

                try {
                    const res = await fetch('/api/dashboard');
                    const data = await res.json();
                    renderDashboard(data);
                } catch (e) {
                    console.error('Refresh failed:', e);
                } finally {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizar';
                }
            }

            refreshBtn.addEventListener('click', manualRefresh);

            // ── Init ──
            connectWebSocket();
            manualRefresh(); // Initial load via HTTP
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)