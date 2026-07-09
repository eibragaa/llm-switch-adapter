/**
 * Switch Adapter Dashboard — Main Application
 * Mobile-first, PWA-ready, WebSocket-driven real-time updates
 */

// ─── Configuration ────────────────────────────────────────────────────────

const CONFIG = {
  apiBase: '',
  wsPath: '/ws',
  refreshInterval: 10000,
  maxReconnectAttempts: 10,
  chartColors: [
    '#58a6ff', '#a371f7', '#3fb950', '#d29922',
    '#f85149', '#39c5cf', '#f97583', '#ffa657'
  ],
  tierLabels: {
    low: 'LOW (grátis local)',
    medium: 'MEDIUM (API grátis)',
    high: 'HIGH (pago)',
  },
  tierColors: {
    low: 'var(--color-green)',
    medium: 'var(--color-yellow)',
    high: 'var(--color-red)',
  },
  statusLabels: {
    online: 'Online',
    offline: 'Offline',
    limited: 'Limitado',
    no_model: 'Sem modelo',
    no_key: 'Sem key',
    rate_limited: 'Rate limited',
    unreachable: 'Inacessível',
    ready: 'Pronto',
    exhausted: 'Exhausted',
  }
};

// ─── Icons ────────────────────────────────────────────────────────────────

const ICONS = {
  ollama: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>',
  ollama_cloud: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>',
  openrouter: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.95 2.25z"/></svg>',
  nous: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
  nvidia: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M13.5.6c-.4 0-.8.1-1.1.4L.2 8.4c-.5.4-.5 1.1 0 1.5l12.2 10.6c.3.3.7.4 1.1.4.4 0 .8-.1 1.1-.4l12.2-10.6c.5-.4.5-1.1 0-1.5L14.7.2c-.3-.3-.7-.4-1.1-.4zM12 2.7l9.1 7.9-9.1 7.9-9.1-7.9 9.1-7.9zM12 17.9c-2.3 0-4.2-1.3-5.1-3.1l4.2-3.6c.4.8 1.2 1.4 2.2 1.4 1 0 1.8-.6 2.1-1.5l.1-.4.1.4c.3.9 1.1 1.5 2.1 1.5 1 0 1.8-.6 2.2-1.4l4.2 3.6c-.9 1.8-2.8 3.1-5.1 3.1z"/></svg>',
  deepseek: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
  opencode_go: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M14.7 3.3c-.3-.3-.7-.4-1.1-.4H10.4c-.4 0-.8.1-1.1.4L.2 9.2c-.5.4-.5 1.1 0 1.5l12.2 10.6c.3.3.7.4 1.1.4h3.2c.4 0 .8-.1 1.1-.4l12.2-10.6c.5-.4.5-1.1 0-1.5L14.7 3.3zM12 17.9c-2.3 0-4.2-1.3-5.1-3.1l4.2-3.6c.4.8 1.2 1.4 2.2 1.4 1 0 1.8-.6 2.1-1.5l.1-.4.1.4c.3.9 1.1 1.5 2.1 1.5 1 0 1.8-.6 2.2-1.4l4.2 3.6c-.9 1.8-2.8 3.1-5.1 3.1z"/></svg>',
  finbot: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.95 2.25z"/></svg>',
  codex: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>',
  tailscale: '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-12.5v9h2v-9zm4 9v-9h2v9h-2zM6.5 12.5v-9h2v9h-2z"/></svg>',
  provider_default: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg>',
};

// Category order for display
const CATEGORY_ORDER = [
  'Free Local',
  'Free Cloud/API',
  'Subscription',
  'Paid APIs',
];

// ─── State ────────────────────────────────────────────────────────────────

let ws = null;
let reconnectAttempts = 0;
let charts = {};
let currentTab = 'overview';

// ─── DOM Elements (initialized in init()) ─────────────────────────────────

let elements = {};
let allModelsData = null; // Cache for models tab filtering

// ─── Utility Functions ────────────────────────────────────────────────────

function formatTime(date = new Date()) {
  return date.toLocaleTimeString('pt-BR', { hour12: false });
}

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}

function formatCost(n) {
  if (n >= 1) return '$' + n.toFixed(4);
  if (n >= 0.01) return '$' + n.toFixed(4);
  if (n >= 0.0001) return '$' + n.toFixed(6);
  return '$' + n.toFixed(8);
}

function formatLatency(ms) {
  if (ms < 1000) return ms.toFixed(0) + 'ms';
  return (ms / 1000).toFixed(2) + 's';
}

function statusClass(status) {
  const online = ['online', 'ready'];
  const limited = ['limited', 'no_model', 'rate_limited'];
  if (online.includes(status)) return 'status-online';
  if (limited.includes(status)) return 'status-limited';
  return 'status-offline';
}

function statusLabel(status) {
  return CONFIG.statusLabels[status] || status;
}

function getIcon(key) {
  return ICONS[key] || ICONS.provider_default;
}

// ─── API Helpers ──────────────────────────────────────────────────────────

async function fetchAPI(path, options = {}) {
  const res = await fetch(`${CONFIG.apiBase}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ─── Chart Rendering (using Chart.js) ────────────────────────────────────

function initCharts() {
  if (typeof Chart === 'undefined') {
    // Chart.js not loaded yet
    return;
  }

  Chart.defaults.font.family = "'Space Grotesk', sans-serif";
  Chart.defaults.color = '#8b949e';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.backgroundColor = '#161b22';
  Chart.defaults.plugins.tooltip.titleColor = '#e6edf3';
  Chart.defaults.plugins.tooltip.bodyColor = '#8b949e';
  Chart.defaults.plugins.tooltip.borderColor = '#30363d';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.displayColors = false;
  Chart.defaults.plugins.tooltip.padding = 12;

  // Cost Trend Chart
  const costCtx = document.getElementById('chartCostTrend');
  if (costCtx) {
    charts.costTrend = new Chart(costCtx, {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: '#21262d' }, ticks: { color: '#6e7681' } },
          y: { grid: { color: '#21262d' }, ticks: { color: '#6e7681' }, beginAtZero: true },
        },
        plugins: { legend: { position: 'top' } },
      },
    });
  }

  // Provider Comparison Chart
  const compCtx = document.getElementById('chartProviderComparison');
  if (compCtx) {
    charts.providerComparison = new Chart(compCtx, {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { grid: { color: '#21262d' }, ticks: { color: '#6e7681' }, beginAtZero: true },
          y: { grid: { display: false }, ticks: { color: '#e6edf3' } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Latency Chart
  const latCtx = document.getElementById('chartLatency');
  if (latCtx) {
    charts.latency = new Chart(latCtx, {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { grid: { color: '#21262d' }, ticks: { color: '#6e7681' }, beginAtZero: true },
          y: { grid: { display: false }, ticks: { color: '#e6edf3' } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }
}

function updateCostTrendChart(data) {
  if (!charts.costTrend) return;

  // Build daily cost data from models
  const dailyCosts = {};
  data.models?.forEach(model => {
    model.daily?.forEach(d => {
      if (!dailyCosts[d.date]) dailyCosts[d.date] = 0;
      dailyCosts[d.date] += d.cost;
    });
  });

  const labels = Object.keys(dailyCosts).sort();
  const values = labels.map(d => dailyCosts[d]);

  charts.costTrend.data.labels = labels;
  charts.costTrend.data.datasets = [{
    label: 'Custo Diário (USD)',
    data: values,
    borderColor: '#58a6ff',
    backgroundColor: 'rgba(88, 166, 255, 0.1)',
    fill: true,
    tension: 0.3,
    pointRadius: 0,
    pointHoverRadius: 4,
  }];
  charts.costTrend.update('none');
}

function updateProviderComparisonChart(data) {
  if (!charts.providerComparison) return;

  const providers = data.providers || [];
  const labels = providers.map(p => p.display_name);
  const costs = providers.map(p => p.cost_usd_30d || 0);
  const calls = providers.map(p => p.calls_total || 0);
  const latencies = providers.map(p => p.avg_latency_ms || 0);

  // Cost chart
  charts.providerComparison.data.labels = labels;
  charts.providerComparison.data.datasets = [{
    label: 'Custo 30d (USD)',
    data: costs,
    backgroundColor: providers.map((p, i) => CONFIG.chartColors[i % CONFIG.chartColors.length]),
    borderRadius: 4,
  }];
  charts.providerComparison.update('none');
}

function updateLatencyChart(data) {
  if (!charts.latency) return;

  const providers = data.providers || [];
  const labels = providers.map(p => p.display_name);
  const latencies = providers.map(p => p.avg_latency_ms || 0);

  charts.latency.data.labels = labels;
  charts.latency.data.datasets = [{
    label: 'Latência Média (ms)',
    data: latencies,
    backgroundColor: latencies.map(l => 
      l < 1000 ? '#3fb950' : l < 3000 ? '#d29922' : '#f85149'
    ),
    borderRadius: 4,
  }];
  charts.latency.update('none');
}

// ─── Render Functions ─────────────────────────────────────────────────────

function renderHeader() {
  elements.lastUpdate.textContent = formatTime();
}

function renderRouteSuggestion(data) {
  const rec = computeRouteSuggestion(data);
  if (!rec) {
    elements.routeSuggestion.classList.add('hidden');
    return;
  }

  elements.routeTier.textContent = CONFIG.tierLabels[rec.tier] || rec.tier;
  elements.routeTier.style.color = CONFIG.tierColors[rec.tier] || 'var(--color-fg)';
  elements.routeProvider.textContent = rec.provider;
  elements.routeCost.textContent = rec.cost;
  elements.routeSuggestion.classList.remove('hidden');
}

function computeRouteSuggestion(data) {
  const providers = data.providers || [];
  const online = providers.filter(p => {
    // Check health from models data
    return true; // We'll compute from health data
  });

  // Use the routing from dashboard data
  const health = data.health || {};
  
  if (health.ollama?.status === 'online' || health.ollama_cloud?.status === 'online' || health.openrouter?.status === 'online' || health.nous?.status === 'online') {
    return { tier: 'low', provider: 'Ollama Local / OpenRouter', cost: 'FREE' };
  }
  if (health.opencode_go?.status === 'online') {
    return { tier: 'medium', provider: 'OpenCode Go', cost: '$10/mo sub' };
  }
  if (health.deepseek?.status === 'online') {
    return { tier: 'high', provider: 'DeepSeek', cost: '~$0.14/1K' };
  }
  if (health.nvidia?.status === 'online') {
    return { tier: 'high', provider: 'Nvidia', cost: 'FREE' };
  }
  return null;
}

function renderStats(costs) {
  const total = costs.totals?.calls || 0;
  const freeTokens = costs.totals?.free_tokens || 0;
  const paidTokens = costs.totals?.paid_tokens || 0;
  const cost = costs.totals?.cost_usd || 0;

  elements.statTasks.textContent = formatNumber(total);
  elements.statFree.textContent = formatNumber(freeTokens) + ' tok';
  elements.statPaid.textContent = formatNumber(paidTokens) + ' tok';
  elements.statCost.textContent = formatCost(cost);
}

function renderProviders(categories) {
  if (!elements.providersGrid) return;

  let html = '';
  
  CATEGORY_ORDER.forEach((catName, catIndex) => {
    const category = categories.find(c => c.name === catName);
    if (!category || category.models.length === 0) return;

    html += `
      <section class="provider-category" data-category="${catName.replace(/\s+/g, '-').toLowerCase()}" style="${catIndex > 0 ? 'margin-top: var(--space-xl);' : ''}">
        <header class="flex items-center justify-between mb-3">
          <h3 class="text-label-lg text-[var(--color-fg-muted)]">${catName}</h3>
          <span class="text-body-xs text-[var(--color-fg-subtle)]">${category.models.length} modelos</span>
        </header>
        <div class="providers-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-md);">
          ${category.models.map(m => renderProviderCard(m)).join('')}
        </div>
      </section>
    `;
  });

  elements.providersGrid.innerHTML = html || '<p class="text-[var(--color-fg-muted)] text-center py-8">Nenhum provedor configurado</p>';
}

function renderProviderCard(model) {
  const icon = getIcon(model.key);
  const status = model.status || 'offline';
  const isPaid = model.is_paid;
  const cost = model.cost;
  
  return `
    <article class="card-provider provider-card" data-provider="${model.key}">
      <header class="flex items-start gap-3 mb-3">
        <div class="w-10 h-10 rounded-lg bg-[var(--color-border)]/50 flex items-center justify-center text-[var(--color-accent)] flex-shrink-0">
          ${icon}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <h4 class="font-semibold truncate">${model.display_name || model.name}</h4>
            <span class="status-dot ${statusClass(status)}" title="${statusLabel(status)}"></span>
            <span class="${isPaid ? 'badge badge-paid' : 'badge badge-free'}">${cost}</span>
          </div>
          <p class="text-body-sm text-[var(--color-fg-muted)] mono truncate mt-1">${model.model_id || model.model}</p>
        </div>
      </header>
      
      <div class="space-y-2 border-t border-[var(--color-border-muted)] pt-3">
        <div class="grid grid-cols-3 gap-3 text-center">
          <div class="p-2 rounded-lg bg-[var(--color-bg-hover)]">
            <p class="text-mono-lg text-[var(--color-fg)]">${model.cost_usd_total !== undefined ? formatCost(model.cost_usd_total) : '-'}</p>
            <p class="text-label-sm text-[var(--color-fg-muted)]">Custo 30d</p>
          </div>
          <div class="p-2 rounded-lg bg-[var(--color-bg-hover)]">
            <p class="text-mono-lg text-[var(--color-fg)]">${model.calls_total !== undefined ? formatNumber(model.calls_total) : '-'}</p>
            <p class="text-label-sm text-[var(--color-fg-muted)]">Chamadas</p>
          </div>
          <div class="p-2 rounded-lg bg-[var(--color-bg-hover)]">
            <p class="text-mono-lg" style="color: ${model.avg_latency_ms < 1000 ? 'var(--color-green)' : model.avg_latency_ms < 3000 ? 'var(--color-yellow)' : 'var(--color-red)'}">${model.avg_latency_ms ? formatLatency(model.avg_latency_ms) : '-'}</p>
            <p class="text-label-sm text-[var(--color-fg-muted)]">Latência</p>
          </div>
        </div>
        
        <details class="details mt-2">
          <summary class="flex items-center justify-between text-body-sm text-[var(--color-fg-muted)]">
            <span>Detalhes</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </summary>
          <div class="space-y-2 text-body-sm">
            <div class="flex justify-between">
              <span class="text-[var(--color-fg-muted)]">Categoria</span>
              <span>${model.category}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--color-fg-muted)]">Tier</span>
              <span class="text-[${CONFIG.tierColors[model.tier] || 'var(--color-fg)'}]">${model.tier?.toUpperCase()}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--color-fg-muted)]">Provedor</span>
              <span class="mono">${model.provider_slug}</span>
            </div>
            ${model.cost_per_1k_input !== undefined && model.cost_per_1k_input > 0 ? `
            <div class="flex justify-between">
              <span class="text-[var(--color-fg-muted)]">Entrada / 1K</span>
              <span class="mono">${formatCost(model.cost_per_1k_input)}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--color-fg-muted)]">Saída / 1K</span>
              <span class="mono">${formatCost(model.cost_per_1k_output)}</span>
            </div>
            ` : ''}
          </div>
        </details>
      </div>
    </article>
  `;
}

function renderCostSummary(costs) {
  const providers = costs.providers || [];
  const totals = costs.totals || {};
  
  let html = `
    <div class="card-section mb-6">
      <header class="flex items-center justify-between mb-4">
        <h2 class="text-h3">Resumo de Custos (30 dias)</h2>
        <span class="badge badge-free">${formatCost(totals.cost_usd)} total</span>
      </header>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="card-stat">
          <p class="text-label-md text-[var(--color-fg-muted)]">Chamadas Totais</p>
          <p class="text-mono-xl text-[var(--color-fg)] mt-1">${formatNumber(totals.calls)}</p>
        </div>
        <div class="card-stat">
          <p class="text-label-md text-[var(--color-fg-muted)]">Tokens Grátis</p>
          <p class="text-mono-xl text-[var(--color-green)] mt-1">${formatNumber(totals.free_tokens)}</p>
        </div>
        <div class="card-stat">
          <p class="text-label-md text-[var(--color-fg-muted)]">Tokens Pagos</p>
          <p class="text-mono-xl text-[var(--color-yellow)] mt-1">${formatNumber(totals.paid_tokens)}</p>
        </div>
        <div class="card-stat">
          <p class="text-label-md text-[var(--color-fg-muted)]">Custo Estimado</p>
          <p class="text-mono-xl text-[var(--color-red)] mt-1">${formatCost(totals.cost_usd)}</p>
        </div>
      </div>
    </div>

    <div class="card-section mb-6">
      <h3 class="text-h4 mb-4">Custo por Provedor (30d)</h3>
      <div class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>Provedor</th>
              <th class="text-right">Modelo</th>
              <th class="text-right">Chamadas</th>
              <th class="text-right">Custo 7d</th>
              <th class="text-right">Custo 30d</th>
              <th class="text-right">Proj. Mensal</th>
              <th class="text-right">Lat. Média</th>
            </tr>
          </thead>
          <tbody>
  `;

  providers.forEach(p => {
    const costColor = p.is_paid ? 'var(--color-yellow)' : 'var(--color-green)';
    html += `
      <tr>
        <td>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full" style="background: ${p.is_paid ? 'var(--color-yellow)' : 'var(--color-green)'}"></span>
            <span class="font-medium">${p.display_name}</span>
          </div>
        </td>
        <td class="text-right mono text-[var(--color-fg-muted)]">${p.model}</td>
        <td class="text-right mono">${formatNumber(p.calls_total)}</td>
        <td class="text-right mono" style="color: ${costColor}">${formatCost(p.cost_usd_7d)}</td>
        <td class="text-right mono" style="color: ${costColor}">${formatCost(p.cost_usd_30d)}</td>
        <td class="text-right mono" style="color: ${costColor}">${formatCost(p.monthly_projection)}/mês</td>
        <td class="text-right mono" style="color: ${p.avg_latency_ms < 1000 ? 'var(--color-green)' : p.avg_latency_ms < 3000 ? 'var(--color-yellow)' : 'var(--color-red)'}">${formatLatency(p.avg_latency_ms)}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  return html;
}

function renderTokensByModel(tokensData) {
  const models = tokensData.models || [];
  
  let html = `
    <div class="card-section mb-6">
      <header class="flex items-center justify-between mb-4">
        <h2 class="text-h3">Uso por Modelo</h2>
        <span class="text-body-sm text-[var(--color-fg-muted)]">${models.length} modelos ativos</span>
      </header>
      <div class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>Modelo</th>
              <th class="text-right">Provedor</th>
              <th class="text-right">Chamadas</th>
              <th class="text-right">Custo 30d</th>
              <th class="text-right">Dias Ativos</th>
            </tr>
          </thead>
          <tbody>
  `;

  models.forEach(m => {
    const costColor = m.is_paid ? 'var(--color-yellow)' : 'var(--color-green)';
    const activeDays = m.daily?.length || 0;
    html += `
      <tr>
        <td>
          <div class="flex items-center gap-2">
            <span class="${m.is_paid ? 'badge badge-paid' : 'badge badge-free'}">${m.display_name}</span>
          </div>
        </td>
        <td class="text-right mono text-[var(--color-fg-muted)]">${m.provider}</td>
        <td class="text-right mono">${formatNumber(m.totals?.calls || 0)}</td>
        <td class="text-right mono" style="color: ${costColor}">${formatCost(m.totals?.cost || 0)}</td>
        <td class="text-right text-[var(--color-fg-muted)]">${activeDays} dias</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  return html;
}

function renderBenchmarks(benchmarks) {
  const providers = Object.entries(benchmarks);
  
  if (providers.length === 0) {
    return '<div class="card-section"><p class="text-[var(--color-fg-muted)] text-center py-8">Nenhum benchmark disponível</p></div>';
  }

  let html = `
    <div class="card-section mb-6">
      <h2 class="text-h3 mb-4">Benchmarks Recentes (Latência / TTFT)</h2>
      <div class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>Provedor</th>
              <th class="text-right">Modelo</th>
              <th class="text-right">Latência (ms)</th>
              <th class="text-right">TTFT (ms)</th>
              <th class="text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody>
  `;

  providers.forEach(([key, b]) => {
    const lat = b.latency_ms || 0;
    const ttft = b.ttft_ms || 0;
    const latColor = lat < 1000 ? 'var(--color-green)' : lat < 3000 ? 'var(--color-yellow)' : 'var(--color-red)';
    const date = b.timestamp ? new Date(b.timestamp).toLocaleString('pt-BR') : '—';
    
    html += `
      <tr>
        <td><span class="font-medium">${key}</span></td>
        <td class="text-right mono text-[var(--color-fg-muted)]">${b.model || '—'}</td>
        <td class="text-right mono" style="color: ${latColor}">${lat.toFixed(1)}</td>
        <td class="text-right mono" style="color: ${latColor}">${ttft.toFixed(1)}</td>
        <td class="text-right text-[var(--color-fg-muted)]">${date}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  return html;
}

function renderChartsSection(costsData, tokensData) {
  return `
    <div class="card-section mb-6" id="chartsSection">
      <header class="flex items-center justify-between mb-4">
        <h2 class="text-h3">Análise Visual</h2>
        <div class="flex gap-2">
          <button class="btn btn-ghost text-body-xs" data-chart="cost">Custo</button>
          <button class="btn btn-ghost text-body-xs" data-chart="latency">Latência</button>
          <button class="btn btn-ghost text-body-xs" data-chart="calls">Chamadas</button>
        </div>
      </header>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6" style="display: none;" id="chartsGrid">
        <div style="height: 300px;">
          <canvas id="chartCostTrend"></canvas>
        </div>
        <div style="height: 300px;">
          <canvas id="chartProviderComparison"></canvas>
        </div>
        <div style="height: 300px;">
          <canvas id="chartLatency"></canvas>
        </div>
      </div>
      <p class="text-body-sm text-[var(--color-fg-muted)] text-center py-8" id="chartsLoading">Carregando gráficos...</p>
    </div>
  `;
}

// ─── Tab Navigation ───────────────────────────────────────────────────────

function initTabs() {
  const tabs = document.querySelectorAll('[data-tab]');
  const panels = document.querySelectorAll('[data-tab-panel]');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab;
      
      tabs.forEach(t => t.classList.remove('active', 'text-[var(--color-accent)]', 'border-[var(--color-accent)]'));
      tab.classList.add('active', 'text-[var(--color-accent)]', 'border-[var(--color-accent)]');
      
      panels.forEach(p => {
        if (p.dataset.tabPanel === tabName) {
          p.classList.remove('hidden');
          p.classList.add('visible');
        } else {
          p.classList.add('hidden');
          p.classList.remove('visible');
        }
      });
      
      currentTab = tabName;
      
      // Lazy load charts when analytics tab is shown
      if (tabName === 'analytics' && !charts.costTrend) {
        initCharts();
        setTimeout(() => {
          document.getElementById('chartsGrid')?.style.removeProperty('display');
          document.getElementById('chartsLoading')?.remove();
        }, 100);
      }
    });
  });
}

// ─── WebSocket ────────────────────────────────────────────────────────────

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}${CONFIG.wsPath}`;

  console.log('Connecting to WebSocket:', wsUrl);
  
  elements.websocketStatus.textContent = 'WebSocket: Conectando...';
  elements.websocketStatus.style.color = 'var(--color-yellow)';
  
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.error('WebSocket constructor error:', e);
    elements.websocketStatus.textContent = 'WebSocket: Erro ao criar conexão';
    elements.websocketStatus.style.color = 'var(--color-red)';
    return;
  }

  ws.onopen = () => {
    console.log('WebSocket connected successfully');
    elements.websocketStatus.textContent = 'WebSocket: Conectado ✓';
    elements.websocketStatus.style.color = 'var(--color-green)';
    if (elements.websocketStatusFooter) {
      elements.websocketStatusFooter.textContent = 'WebSocket: Conectado ✓';
      elements.websocketStatusFooter.style.color = 'var(--color-green)';
    }
    reconnectAttempts = 0;
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('WebSocket message received:', Object.keys(data));
      renderDashboard(data);
    } catch (e) {
      console.error('WS parse error:', e);
    }
  };

  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    elements.websocketStatus.textContent = 'WebSocket: Reconectando...';
    elements.websocketStatus.style.color = 'var(--color-yellow)';
    if (reconnectAttempts < CONFIG.maxReconnectAttempts) {
      reconnectAttempts++;
      const delay = Math.min(1000 * reconnectAttempts, 10000);
      console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
      setTimeout(connectWebSocket, delay);
    } else {
      elements.websocketStatus.textContent = 'WebSocket: Desconectado';
      elements.websocketStatus.style.color = 'var(--color-red)';
    }
  };

  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
    // Don't update status here - onclose will handle it
  };
}

// ─── Main Render ──────────────────────────────────────────────────────────

async function renderDashboard(data) {
  // Update header
  elements.lastUpdate.textContent = formatTime();

  // Route suggestion
  renderRouteSuggestion(data);

  // Stats
  if (data.costs) {
    renderStats(data.costs);
  }

  // Providers (from /api/models)
  if (data.models) {
    renderProviders(data.models.categories);
    
    // Render models tab if active
    if (currentTab === 'models') {
      allModelsData = data.models;
      renderModels(data.models.categories, elements.modelFilter?.value || 'all', elements.modelSearch?.value || '');
    }
  }

  // Render analytics panels if on that tab
  if (currentTab === 'analytics') {
    if (data.costs) {
      elements.costsPanel.innerHTML = renderCostSummary(data.costs);
      updateProviderComparisonChart(data.costs);
    }
    if (data.tokens) {
      elements.tokensPanel.innerHTML = renderTokensByModel(data.tokens);
    }
    if (data.benchmarks) {
      elements.benchmarksPanel.innerHTML = renderBenchmarks(data.benchmarks);
      updateLatencyChart(data.benchmarks);
    }
    if (data.costs || data.tokens) {
      updateCostTrendChart({ models: data.tokens?.models || [] });
    }
  }

  // Extra sections (Finbot, Codex, Tailscale)
  renderExtras(data);
}

function renderExtras(data) {
  const sections = [];
  
  if (data.finbot_usage) {
    sections.push(renderFinbot(data.finbot_usage));
  }
  if (data.codex) {
    sections.push(renderCodex(data.codex));
  }
  if (data.tailscale) {
    sections.push(renderTailscale(data.tailscale));
  }

  if (elements.extraSections) {
    elements.extraSections.innerHTML = sections.join('') || '';
  }
}

function renderFinbot(data) {
  if (!data || data.status !== 'ok') {
    return `
      <article class="card-section">
        <h3 class="text-h4 mb-3 flex items-center gap-2">${ICONS.finbot} Finbot (RPi3)</h3>
        <p class="text-[var(--color-fg-muted)] text-sm">${data?.detail || 'Não disponível'}</p>
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
      <div class="p-3 rounded-lg bg-[var(--color-bg-hover)] border border-[var(--color-border)] mb-2">
        <div class="flex items-center justify-between mb-1">
          <span class="font-medium text-sm">${(prov.provider || key).toUpperCase()}</span>
          <span class="text-body-xs text-[var(--color-fg-muted)] mono">${prov.model || ''}</span>
        </div>
        ${reqs > 0 ? `
          <div class="grid grid-cols-2 gap-2 text-body-xs">
            <div><span class="text-[var(--color-fg-muted)]">Hoje:</span> <span class="mono">${reqs} reqs</span></div>
            <div><span class="text-[var(--color-fg-muted)]">Tokens:</span> <span class="mono">${formatNumber(tokens)}</span></div>
            <div class="col-span-2"><span class="text-[var(--color-fg-muted)]">Total:</span> <span class="mono">${formatNumber(tTokens)} tokens</span></div>
          </div>
        ` : `<p class="text-body-xs text-[var(--color-fg-muted)]">Aguardando requisições</p>`}
      </div>
    `;
  }

  return `
    <article class="card-section">
      <h3 class="text-h4 mb-3 flex items-center gap-2">${ICONS.finbot} Finbot (RPi3)</h3>
      <div class="space-y-1">${providersHtml || '<p class="text-[var(--color-fg-muted)] text-sm">Nenhum provedor ativo</p>'}</div>
    </article>
  `;
}

function renderCodex(accounts) {
  let accountsHtml = '';
  for (const acc of accounts || []) {
    const isActive = acc.active;
    const status = acc.status || 'unknown';
    const statusColors = {
      ready: 'var(--color-green)',
      rate_limited: 'var(--color-red)',
      exhausted: 'var(--color-red)',
    };
    const color = statusColors[status] || 'var(--color-fg-muted)';

    accountsHtml += `
      <div class="flex items-center justify-between p-2 rounded-lg ${isActive ? 'bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30' : 'bg-[var(--color-bg-hover)] border border-[var(--color-border)]'}">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full" style="background: ${color}"></span>
          <div>
            <p class="font-medium text-sm">${acc.name} ${isActive ? '<span class="text-[var(--color-accent)] text-body-xs ml-1">ATIVA</span>' : ''}</p>
            <p class="text-body-xs text-[var(--color-fg-muted)] mono">${acc.email}</p>
          </div>
        </div>
        <span class="text-body-xs mono" style="color: ${color}">${status}</span>
      </div>
    `;
  }

  return `
    <article class="card-section">
      <h3 class="text-h4 mb-3 flex items-center gap-2">${ICONS.codex} Codex Accounts</h3>
      <div class="space-y-1">${accountsHtml || '<p class="text-[var(--color-fg-muted)] text-sm">Nenhuma conta</p>'}</div>
    </article>
  `;
}

function renderTailscale(data) {
  if (!data || data.status === 'error' || data.status === 'not_installed') {
    return `
      <article class="card-section">
        <h3 class="text-h4 mb-3 flex items-center gap-2">${ICONS.tailscale} Tailscale Mesh</h3>
        <p class="text-[var(--color-fg-muted)] text-sm">${data?.detail || 'Tailscale não disponível'}</p>
      </article>
    `;
  }

  const statusColors = {
    connected: 'var(--color-green)',
    no_peers: 'var(--color-yellow)',
    timeout: 'var(--color-red)',
  };
  const statusColor = statusColors[data.status] || 'var(--color-fg-muted)';
  const statusText = data.status.charAt(0).toUpperCase() + data.status.slice(1).replace('_', ' ');

  let peersHtml = '';
  for (const peer of data.peers || []) {
    const peerColor = peer.online ? 'var(--color-green)' : 'var(--color-red)';
    peersHtml += `
      <div class="flex items-center justify-between p-2 rounded-lg bg-[var(--color-bg-hover)] border border-[var(--color-border)]">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full" style="background: ${peerColor}"></span>
          <div>
            <p class="font-medium text-sm">${peer.dns_name || 'unnamed'}</p>
            <p class="text-body-xs text-[var(--color-fg-muted)] mono">${peer.tailscale_ip}</p>
          </div>
        </div>
        <span class="text-body-xs" style="color: ${peerColor}">${peer.online ? 'Online' : 'Offline'}</span>
      </div>
    `;
  }

  return `
    <article class="card-section">
      <h3 class="text-h4 mb-3 flex items-center gap-2">${ICONS.tailscale} Tailscale Mesh</h3>
      <div class="space-y-2 mb-3">
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div><span class="text-[var(--color-fg-muted)]">Status:</span> <span class="mono ml-2" style="color: ${statusColor}">${statusText}</span></div>
          <div><span class="text-[var(--color-fg-muted)]">Seu IP:</span> <span class="mono ml-2">${data.local_ip}</span></div>
          <div class="col-span-2"><span class="text-[var(--color-fg-muted)]">Peers:</span> <span class="mono ml-2">${data.online_count} / ${data.total_count} online</span></div>
        </div>
        <a href="${data.dashboard_url}" target="_blank" class="inline-block px-3 py-1.5 text-body-xs font-medium text-[var(--color-fg)] bg-[var(--color-accent)]/20 border border-[var(--color-accent)]/30 rounded-lg hover:bg-[var(--color-accent)]/30 transition-colors">Abrir Dashboard via Tailscale →</a>
      </div>
      <div class="space-y-1 max-h-60 overflow-y-auto">${peersHtml || '<p class="text-[var(--color-fg-muted)] text-sm">Nenhum peer encontrado</p>'}</div>
    </article>
  `;
}

/**
 * Render Models tab with filtering and search
 */
function renderModels(categories, filterCategory = 'all', searchQuery = '') {
  if (!elements.modelsGrid) return;
  
  if (!categories) {
    elements.modelsGrid.innerHTML = '<p class="text-[var(--color-fg-muted)] text-center py-8">Carregando modelos...</p>';
    return;
  }
  
  const query = searchQuery.toLowerCase().trim();
  
  let html = '';
  let totalModels = 0;
  let visibleModels = 0;
  
  CATEGORY_ORDER.forEach((catName, catIndex) => {
    if (filterCategory !== 'all' && filterCategory !== catName) return;
    
    const category = categories.find(c => c.name === catName);
    if (!category || category.models.length === 0) return;
    
    // Filter models by search query
    const filteredModels = category.models.filter(m => 
      m.name.toLowerCase().includes(query) ||
      m.model_id.toLowerCase().includes(query) ||
      m.provider_slug.toLowerCase().includes(query) ||
      m.key.toLowerCase().includes(query)
    );
    
    if (filteredModels.length === 0) return;
    
    totalModels += category.models.length;
    visibleModels += filteredModels.length;
    
    html += `
      <section class="provider-category" data-category="${catName.replace(/\s+/g, '-').toLowerCase()}" style="${catIndex > 0 ? 'margin-top: var(--space-xl);' : ''}">
        <header class="flex items-center justify-between mb-3">
          <h3 class="text-label-lg text-[var(--color-fg-muted)]">${catName}</h3>
          <span class="text-body-xs text-[var(--color-fg-subtle)]">${filteredModels.length} de ${category.models.length} modelos</span>
        </header>
        <div class="providers-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-md);">
          ${filteredModels.map(m => renderProviderCard(m)).join('')}
        </div>
      </section>
    `;
  });
  
  if (html === '') {
    html = `<p class="text-[var(--color-fg-muted)] text-center py-8">Nenhum modelo encontrado${query ? ` para "${searchQuery}"` : ''}${filterCategory !== 'all' ? ` na categoria ${filterCategory}` : ''}</p>`;
  }
  
  elements.modelsGrid.innerHTML = html;
  
  // Update filter count if needed
  const countEl = document.getElementById('modelsCount');
  if (countEl) {
    countEl.textContent = `${visibleModels} de ${totalModels} modelos`;
  }
}

// ─── Manual Refresh ───────────────────────────────────────────────────────

async function manualRefresh() {
  elements.refreshBtn.disabled = true;
  elements.refreshBtn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizando...';

  try {
    const data = await fetchAPI('/api/dashboard');
    renderDashboard(data);
    // Also fetch analytics data
    loadAnalyticsData();
  } catch (e) {
    console.error('Refresh failed:', e);
  } finally {
    elements.refreshBtn.disabled = false;
    elements.refreshBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizar';
  }
}

async function loadAnalyticsData() {
  try {
    const [costs, tokens, benchmarks, models] = await Promise.all([
      fetchAPI('/api/costs/summary?days=30'),
      fetchAPI('/api/tokens/by-model?days=30'),
      fetchAPI('/api/benchmarks'),
      fetchAPI('/api/models'),
    ]);

    if (currentTab === 'analytics') {
      elements.costsPanel.innerHTML = renderCostSummary(costs);
      elements.tokensPanel.innerHTML = renderTokensByModel(tokens);
      elements.benchmarksPanel.innerHTML = renderBenchmarks(benchmarks);
      
      updateProviderComparisonChart(costs);
      updateLatencyChart(benchmarks);
      updateCostTrendChart({ models: tokens.models || [] });
    }
  } catch (e) {
    console.error('Analytics load failed:', e);
  }
}

async function loadModelsData() {
  try {
    const data = await fetchAPI('/api/models');
    allModelsData = data;
    if (currentTab === 'models') {
      renderModels(data.categories, elements.modelFilter?.value || 'all', elements.modelSearch?.value || '');
    }
  } catch (e) {
    console.error('Models load failed:', e);
  }
}

// ─── Initialization ───────────────────────────────────────────────────────

function initElements() {
  elements = {
    // Header
    lastUpdate: document.getElementById('lastUpdate'),
    websocketStatus: document.getElementById('websocketStatus'),
    refreshBtn: document.getElementById('refreshBtn'),
    routeSuggestion: document.getElementById('routeSuggestion'),
    routeTier: document.getElementById('routeTier'),
    routeProvider: document.getElementById('routeProvider'),
    routeCost: document.getElementById('routeCost'),
    
    // Stats
    statTasks: document.getElementById('statTasks'),
    statFree: document.getElementById('statFree'),
    statPaid: document.getElementById('statPaid'),
    statCost: document.getElementById('statCost'),
    
    // Main content
    providersGrid: document.getElementById('providersGrid'),
    extraSections: document.getElementById('extraSections'),
    
    // Analytics panels
    costsPanel: document.getElementById('costsPanel'),
    tokensPanel: document.getElementById('tokensPanel'),
    benchmarksPanel: document.getElementById('benchmarksPanel'),
    
    // Models tab
    modelsGrid: document.getElementById('modelsGrid'),
    modelFilter: document.getElementById('modelFilter'),
    modelSearch: document.getElementById('modelSearch'),
    
    // Footer websocket status
    websocketStatusFooter: document.getElementById('websocketStatusFooter'),
  };
}

async function init() {
  initElements();
  initTabs();
  
  // Event listeners
  elements.refreshBtn?.addEventListener('click', manualRefresh);
  elements.modelFilter?.addEventListener('change', (e) => {
    if (allModelsData) {
      renderModels(allModelsData.categories, e.target.value, elements.modelSearch?.value || '');
    }
  });
  elements.modelSearch?.addEventListener('input', (e) => {
    if (allModelsData) {
      renderModels(allModelsData.categories, elements.modelFilter?.value || 'all', e.target.value);
    }
  });
  
  // Initial load
  try {
    console.log('Fetching initial dashboard data...');
    const data = await fetchAPI('/api/dashboard');
    console.log('Initial data received:', Object.keys(data));
    renderDashboard(data);
  } catch (e) {
    console.error('Initial load failed:', e);
    // Show error in UI
    const providersGrid = document.getElementById('providersGrid');
    if (providersGrid) {
      providersGrid.innerHTML = `
        <div class="col-span-full card-section text-center py-12">
          <svg class="w-16 h-16 mx-auto text-[var(--color-red)] mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          <p class="text-[var(--color-fg-muted)]">Falha ao carregar dados: ${e.message}</p>
          <button onclick="location.reload()" class="btn btn-primary mt-4">Tentar Novamente</button>
        </div>
      `;
    }
  }
  
  // Load analytics and models data in background
  loadAnalyticsData();
  loadModelsData();
  
  // Connect WebSocket
  connectWebSocket();
  
  // Register PWA
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(console.error);
  }
}

// ─── Boot ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);