# Switch Adapter Web Dashboard — Improvement Plan

## Executive Summary

**Objective**: Transform the existing FastAPI + WebSocket dashboard into a premium, mobile-first, professional web application with comprehensive token/cost analytics, organized model display, and visual excellence.

**Current State**: Functional but minimal — basic provider cards, Finbot/Codex/Tailscale sections, 10s WebSocket updates. No historical token tracking, no cost breakdown by model, no visual polish.

**Target State**: Premium dashboard with:
- Mobile-first responsive design (Vercel/Linear aesthetic)
- Historical token usage from creation → now (by model, provider, date)
- Total cost tracking for paid models with projections
- Organized model display with filtering, grouping, search
- Design token system (DESIGN.md) for consistency
- PWA support for mobile home-screen install

---

## Phase 1: Analysis & Documentation (Week 1)

### 1.1 Architecture Audit

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| Backend API | FastAPI 1.0, 6 endpoints | FastAPI + structured endpoints + query params | Add `/api/tokens`, `/api/costs/summary`, `/api/models` |
| Real-time | WebSocket 10s broadcast | WebSocket + HTTP fallback + reconnection strategy | Add exponential backoff, last-event-id |
| Frontend | Embedded HTML in Python | Separate files, design system, components | Extract to `web_static/` |
| Data Sources | 3 SQLite DBs + JSONL | Unified query layer with caching | Create `dashboard_data.py` service |
| Auth | None (local network) | Optional Tailscale IP allow | Keep simple, document Tailscale access |

### 1.2 Data Contracts

#### Provider Cost Summary (`/api/costs/summary`)
```json
{
  "period": { "start": "2026-05-01", "end": "2026-06-12" },
  "providers": [
    {
      "name": "deepseek",
      "model": "deepseek-chat",
      "is_paid": true,
      "calls_total": 142,
      "tokens_input": 452310,
      "tokens_output": 128940,
      "cost_usd_total": 0.0892,
      "cost_usd_7d": 0.0041,
      "cost_usd_30d": 0.0183,
      "monthly_projection": 0.078,
      "avg_latency_ms": 1240
    }
  ],
  "totals": {
    "calls": 2847,
    "tokens": 1204890,
    "cost_usd": 0.2341,
    "free_tokens": 987000,
    "paid_tokens": 217890
  }
}
```

#### Token Usage by Model (`/api/tokens/by-model`)
```json
{
  "models": [
    {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "display_name": "DeepSeek Chat",
      "is_paid": true,
      "cost_per_1k_input": 0.00007,
      "cost_per_1k_output": 0.00028,
      "daily": [
        { "date": "2026-06-10", "calls": 12, "input": 45210, "output": 12340, "cost": 0.0045 }
      ],
      "totals": { "calls": 142, "input": 452310, "output": 128940, "cost": 0.0892 }
    }
  ]
}
```

#### Model Registry (`/api/models`)
```json
{
  "categories": [
    {
      "name": "Free Local",
      "models": [
        { "key": "ollama", "name": "Ollama Local", "model_id": "deepseek-v4-flash:cloud", "provider_slug": "ollama-local", "cost": "FREE", "tier": "low", "status": "online" }
      ]
    },
    {
      "name": "Free Cloud/API",
      "models": [
        { "key": "ollama_cloud", "name": "Ollama Cloud", "model_id": "deepseek-v4-flash", "provider_slug": "ollama-launch", "cost": "FREE", "tier": "medium", "status": "online" },
        { "key": "nous", "name": "NousResearch", "model_id": "stepfun/step-3.7-flash:free", "provider_slug": "nous", "cost": "FREE", "tier": "high", "status": "online" },
        { "key": "openrouter", "name": "OpenRouter", "model_id": "qwen/qwen3-coder:free", "provider_slug": "openrouter", "cost": "FREE", "tier": "all", "status": "online" }
      ]
    },
    {
      "name": "Subscription",
      "models": [
        { "key": "opencode_go", "name": "OpenCode Go", "model_id": "deepseek-v4-flash", "provider_slug": "opencode-go", "cost": "$10/mo", "tier": "all", "status": "offline" }
      ]
    },
    {
      "name": "Paid APIs",
      "models": [
        { "key": "deepseek", "name": "DeepSeek", "model_id": "deepseek-v4-flash", "provider_slug": "deepseek", "cost": "$0.00028/1K", "tier": "high", "status": "online" },
        { "key": "nvidia", "name": "Nvidia", "model_id": "qwen/qwen3-coder-480b", "provider_slug": "nvidia", "cost": "FREE", "tier": "medium", "status": "offline" }
      ]
    }
  ]
}
```

### 1.3 Design System Specification

**Primary Reference**: `popular-web-designs` → Vercel + Linear + Stripe
- **Color**: Dark base (`#0d1117`), elevated (`#161b22`), border (`#30363d`), accent (`#58a6ff` / `#a371f7`), green (`#3fb950`), yellow (`#d29922`), red (`#f85149`)
- **Typography**: Space Grotesk (UI), JetBrains Mono (data)
- **Spacing**: 4px base unit, 8px/16px/24px/32px scale
- **Radius**: 8px (cards), 12px (modals), 4px (buttons)
- **Shadows**: 2-layer elevation system
- **Motion**: 150ms ease-out, `prefers-reduced-motion`

Create `DESIGN.md` in `/root/repositorio/switch-adapter/DESIGN.md`

### 1.4 Mobile-First Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| xs | < 480px | 1-col, stacked cards, bottom nav |
| sm | 480-768px | 1-col, condensed stats |
| md | 768-1024px | 2-col providers, side-by-side sections |
| lg | 1024-1440px | 3-col providers, full grid |
| xl | > 1440px | 4-col providers, expanded metrics |

---

## Phase 2: Viability & Technical Design (Week 1-2)

### 2.1 Backend Enhancements

#### New API Endpoints
```python
# web_dashboard.py additions

@app.get("/api/costs/summary")
async def get_cost_summary(days: int = 30):
    """Aggregated cost data across all providers."""
    
@app.get("/api/tokens/by-model")
async def get_tokens_by_model(days: int = 30):
    """Detailed token usage per model with daily breakdown."""
    
@app.get("/api/models")
async def get_model_registry():
    """Structured model catalog from provider_registry + health."""
    
@app.get("/api/health")
async def get_health():
    """Lightweight health check for load balancers/PWA."""
```

#### Data Service Layer
Create `dashboard_data.py`:
```python
class DashboardDataService:
    def __init__(self):
        self.costs_db = "/root/.hermes/provider-costs/costs.db"
        self.benchmarks_db = "/root/.hermes/provider-benchmarks/benchmarks.db"
        self.costs_jsonl = "/root/repositorio/switch-adapter/accounts/logs/costs.jsonl"
    
    def get_cost_summary(self, days: int) -> dict: ...
    def get_tokens_by_model(self, days: int) -> dict: ...
    def get_model_registry(self, health: dict) -> dict: ...
    def get_benchmarks(self, provider: str) -> dict: ...
```

#### Caching Strategy
- In-memory cache with 60s TTL for health endpoints
- SQLite indices on `timestamp`, `provider`, `status`
- Background refresh job for cost summaries (every 5min)

### 2.2 Frontend Architecture

#### File Structure
```
/root/repositorio/switch-adapter/
├── web_static/
│   ├── index.html              # Main entry
│   ├── css/
│   │   ├── design-tokens.css   # CSS custom properties from DESIGN.md
│   │   ├── components.css      # Card, table, modal, chart styles
│   │   ├── layout.css          # Grid, flex, responsive
│   │   └── themes.css          # Dark/light (system preference)
│   ├── js/
│   │   ├── app.js              # Main init, routing
│   │   ├── api.js              # Fetch + WebSocket client
│   │   ├── render.js           # DOM rendering functions
│   │   ├── charts.js           # Lightweight chart rendering (no deps)
│   │   ├── state.js            # Reactive state management
│   │   └── pwa.js              # Service worker registration
│   └── assets/
│       ├── favicon.svg
│       └── logo.svg
├── web_dashboard.py            # FastAPI backend
├── dashboard_data.py           # Data service
└── DESIGN.md                   # Design token spec
```

#### State Management
```javascript
// Minimal reactive store
const state = {
  providers: {},
  costs: { summary: null, byModel: null },
  benchmarks: {},
  ws: null,
  lastUpdate: null,
  filters: { tier: 'all', cost: 'all', search: '' }
};

// Actions trigger re-render
function setState(path, value) { ... }
function subscribe(path, callback) { ... }
```

#### Chart Rendering (Zero Dependencies)
- SVG-based sparklines for daily cost trends
- Bar charts for token comparison (flexbox + CSS variables)
- No Chart.js / D3 — keeps bundle < 50KB

### 2.3 PWA Configuration
```json
// web_static/manifest.json
{
  "name": "Switch Adapter Dashboard",
  "short_name": "Switch ADPT",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0d1117",
  "theme_color": "#58a6ff",
  "icons": [...]
}
```

```javascript
// web_static/js/pwa.js
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
```

---

## Phase 3: Implementation (Week 2-3)

### 3.1 Backend Implementation Order

1. **Create `DESIGN.md`** — Design token spec with WCAG-validated colors
2. **Create `dashboard_data.py`** — Unified data service
3. **Extend `web_dashboard.py`** — New endpoints + static file mount
4. **Extract frontend to `web_static/`** — HTML/CSS/JS separation
5. **Add PWA files** — manifest.json, sw.js, icons

### 3.2 Frontend Implementation Order

1. **Design Tokens CSS** — `:root` variables from DESIGN.md
2. **Layout System** — CSS Grid for dashboard, mobile-first
3. **Component Library** — Cards, tables, badges, charts, modals
4. **Provider Cards** — Organized by category, filterable, searchable
5. **Cost Analytics Section** — Summary cards, model breakdown table, sparklines
6. **Token Usage Section** — Daily bars, total costs, paid/free split
7. **Real-time Sync** — WebSocket with reconnection, manual refresh
7. **PWA Setup** — Service worker, manifest, install prompt

### 3.3 Key UI Components

#### Provider Card (Mobile-Optimized)
```
┌─────────────────────────────────────┐
│ 🟢 Ollama Local          [LOW] FREE │
│ deepseek-v4-flash:cloud             │
│ 0ms  ████████████ Online            │
│ [Details ▼]                         │
└─────────────────────────────────────┘
```
- Expandable for details (latency history, benchmarks, model info)
- Category badge (Free Local / Free Cloud / Subscription / Paid)
- Status dot with pulse animation

#### Cost Summary Row
```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Tasks   │ │ Free    │ │ Paid    │ │ Cost    │
│ 247     │ │ 198     │ │ 49      │ │ $0.0234 │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

#### Model Cost Breakdown Table
| Model | Provider | Type | Calls | Input Tokens | Output Tokens | Cost (30d) | Monthly Proj. |
|-------|----------|------|-------|--------------|---------------|------------|---------------|
| deepseek-chat | DeepSeek | Paid | 142 | 452K | 128K | $0.089 | $0.078 |
| deepseek-v4-flash | OpenRouter | Free | 89 | 234K | 67K | $0.000 | — |

#### Sparklines (CSS-only)
```css
.sparkline {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 32px;
}
.sparkline bar { width: 4px; background: var(--accent); }
```

---

## Phase 4: Testing & Polish (Week 3)

### 4.1 Visual Verification Checklist

- [ ] Desktop (1920px): Full 4-col grid, all sections visible
- [ ] Tablet (768px): 2-col providers, stacked sections
- [ ] Mobile (375px): 1-col, bottom nav, swipeable cards
- [ ] Dark mode: System preference respected
- [ ] Reduced motion: Animations disabled
- [ ] High contrast: WCAG AA on all text
- [ ] Tailscale access: Works from phone on mesh

### 4.2 Performance Targets

| Metric | Target |
|--------|--------|
| Initial HTML | < 50KB |
| CSS (gzipped) | < 15KB |
| JS (gzipped) | < 30KB |
| First paint | < 800ms |
| WebSocket connect | < 2s |
| PWA installable | Yes |

### 4.3 Accessibility

- Semantic HTML5 (header, main, section, article, aside)
- ARIA labels on interactive elements
- Focus visible outlines
- Color not sole information carrier
- Keyboard navigation for all controls

---

## Phase 5: Essential Improvements Not Yet Discussed

### 5.1 Alerting & Monitoring
- **Provider down webhook**: POST to Telegram/Discord on status change
- **Cost threshold alert**: Notify when daily cost > $X
- **Health check endpoint**: `/api/health` for uptime monitoring

### 5.2 Historical Comparison
- **Period-over-period**: Compare last 7d vs previous 7d
- **Trend indicators**: ✓ improving, ⚠ degrading, → stable
- **Anomaly detection**: Flag latency spikes > 2σ

### 5.3 Routing Intelligence Display
- **Actual vs Recommended**: Show what router chose vs what user forced
- **Fallback chain visualization**: Live view of fallback attempts
- **Cost savings calculator**: "Saved $X this month by using free providers"

### 5.4 Multi-Profile Support
- Profile selector (default, d5n, cronosbot, finbot, afiliate-bot)
- Per-profile provider config display
- Sync status with `sync_model.sh` cron

### 5.5 Export & Reporting
- **CSV export**: Token usage, costs, latency
- **PDF report**: Monthly summary with charts
- **API key**: Read-only token for external dashboards

---

## Deliverables & File Paths

| Deliverable | Path |
|-------------|------|
| Design Spec | `/root/repositorio/switch-adapter/DESIGN.md` |
| Data Service | `/root/repositorio/switch-adapter/dashboard_data.py` |
| Backend API | `/root/repositorio/switch-adapter/web_dashboard.py` |
| Frontend Entry | `/root/repositorio/switch-adapter/web_static/index.html` |
| Design Tokens CSS | `/root/repositorio/switch-adapter/web_static/css/design-tokens.css` |
| Components CSS | `/root/repositorio/switch-adapter/web_static/css/components.css` |
| Layout CSS | `/root/repositorio/switch-adapter/web_static/css/layout.css` |
| Main JS | `/root/repositorio/switch-adapter/web_static/js/app.js` |
| API Client | `/root/repositorio/switch-adapter/web_static/js/api.js` |
| Renderer | `/root/repositorio/switch-adapter/web_static/js/render.js` |
| Charts | `/root/repositorio/switch-adapter/web_static/js/charts.js` |
| State | `/root/repositorio/switch-adapter/web_static/js/state.js` |
| PWA | `/root/repositorio/switch-adapter/web_static/js/pwa.js` |
| Manifest | `/root/repositorio/switch-adapter/web_static/manifest.json` |
| Service Worker | `/root/repositorio/switch-adapter/web_static/sw.js` |
| Favicon | `/root/repositorio/switch-adapter/web_static/favicon.svg` |
| Logo | `/root/repositorio/switch-adapter/web_static/logo.svg` |

---

## Verification Commands

```bash
# Start dashboard
cd /root/repositorio/switch-adapter && python3 web_dashboard.py

# Test endpoints
curl http://localhost:8080/api/dashboard | jq .
curl http://localhost:8080/api/costs/summary | jq .
curl http://localhost:8080/api/tokens/by-model | jq .
curl http://localhost:8080/api/models | jq .

# Verify PWA
curl http://localhost:8080/manifest.json | jq .
curl http://localhost:8080/sw.js

# Test Tailscale access (from another device on tailnet)
curl http://100.91.103.8:8080/api/dashboard
```

---

## Next Steps

1. **Approve this plan** — confirm scope, priorities, timeline
2. **Create DESIGN.md** — establish design system (I'll use `design-md` skill)
3. **Implement backend** — data service + new endpoints
4. **Extract & redesign frontend** — mobile-first, premium visual
5. **Add PWA** — installable on mobile
6. **Test & iterate** — verify on desktop, tablet, phone via Tailscale

---

*Plan created following development flow: Analysis → Viability → Implementation. Documentation precedes code. All design decisions reference `popular-web-designs` (Vercel/Linear/Stripe) and use `claude-design` process for artifact creation.*