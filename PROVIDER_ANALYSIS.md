# Switch Adapter — Provider & Model Analysis + Action Plan

**Data:** 2026-06-12
**Status:** Dashboard modernizado e funcional (web UI + API + WebSocket + PWA)

---

## 1. Panorama Atual dos Providers

| Provider | Tipo | Modelos Observados | Custo | Status Benchmark (Jun/26) |
|----------|------|-------------------|-------|---------------------------|
| **Ollama Local** | Free Local | `deepseek-v4-flash:cloud`, `gemma4:31b-cloud` | $0 | ✅ 503-674ms (latência total = TTFT) |
| **Ollama Cloud** | Free Cloud | `deepseek-v4-flash` | $0 | — (não benchmarkado recentemente) |
| **OpenRouter** | Free Cloud | `deepseek-v4-flash`, `qwen/qwen3-coder:free` | $0 | ✅ 1630ms / 1275ms TTFT |
| **NousResearch** | Free Cloud | `stepfun/step-3.7-flash:free` | $0 | — (não benchmarkado) |
| **Nvidia** | Free Cloud | `meta/llama-3.3-70b-instruct`, `qwen/qwen3-coder-480b` | $0 | ✅ 1086ms / 1086ms TTFT |
| **OpenCode Go** | **Subscription $10/mo (ATIVA — ver §4 atualizado)** | `deepseek-v4-flash`, `minimax-m3`, etc. | $10/mo fixo | ✅ 200 OK (com User-Agent header — ver §4) |
| **DeepSeek** | Paid API | `deepseek-chat` (`deepseek-v4-flash`) | ~$0.00028/1K out | ✅ 1701ms / 1701ms TTFT |

---

## 2. Análise de Benchmarks (Últimos dados — 07/06/2026)

```
┌─────────────────┬────────────┬────────────┬────────┐
│ Provider        │ Latência   │ TTFT       │ Modelo │
├─────────────────┼────────────┼────────────┼────────┤
│ Ollama (gemma)  │   674 ms   │   674 ms   │ local  │
│ Nvidia (Llama)  │  1086 ms   │  1086 ms   │ free   │
│ OpenRouter      │  1630 ms   │  1275 ms   │ free   │
│ DeepSeek (chat) │  1701 ms   │  1701 ms   │ paid   │
└─────────────────┴────────────┴────────────┴────────┘
```

**Insights:**
- **Ollama Local** = melhor latência (rede local, sem cold start)
- **Nvidia** = melhor entre cloud free (~1.1s)
- **DeepSeek paid** = mais lento e caro (só para tasks HIGH quando free indisponível)
- **OpenCode Go** = **EXPIRADA desde 05/06/2026** — 403 Forbidden em todos endpoints. Sub $10/mo não renovada. Remover do routing ou renovar.

---

## 3. Análise de Custos (SQLite + JSONL — últimos 30 dias)

| Provider | Chamadas | Custo Estimado | Tokens (approx) |
|----------|----------|----------------|-----------------|
| DeepSeek | ~12/dia  | **~$0.003/dia** (~$0.09/mês) | ~10-15K/dia |
| Nvidia   | ~8/dia   | $0 (free)      | ~8-12K/dia |
| Ollama   | ~5/dia   | $0 (local)     | — |
| OpenRouter| ~3/dia  | $0 (free)      | — |
| OpenCode Go| 0*     | **$0/mo (expirada)**  | — |

*OpenCode Go configurado mas **não usado** nos logs recentes — key pode não estar válida ou routing nunca seleciona.

**Economia atual:** ~95% tasks em free tier. DeepSeek só entra em HIGH tier quando free providers falham.

---

## 4. OpenCode Go — Status: **ATIVO** (diagnóstico atualizado 2026-06-15)

**Diagnóstico anterior (incorreto):** subscription expirada em 05/06/2026.

**Diagnóstico correto (verificado em 2026-06-15 20:38 UTC):**
- **Endpoint correto:** `https://opencode.ai/zen/go/v1` (com `zen` no path)
  - ❌ `https://opencode.ai/go/v1` → HTTP 404
  - ❌ `https://opencode.ai/zen/v1` → HTTP 200 mas modelos diferentes (zen regular)
  - ✅ `https://opencode.ai/zen/go/v1` → HTTP 200 com modelos Go
- **Base URL no auth.json:** `https://opencode.ai/zen/go/v1` ✓ (correto)
- **Key no credential_pool:** `sk-ZfrmmBe...kgc0` (status: `ok`, `last_status: ok`)
- **Testes anteriores (12/06):** `/models` → 403, `/chat/completions` → 403 (Forbidden)
- **Causa raiz:** Cloudflare Bot Protection (error 1010) — `urllib` Python sem `User-Agent` é bloqueado.
- **Teste correto (15/06) com `User-Agent: Mozilla/5.0...`:**
  - `GET /zen/go/v1/models` → HTTP 200, retorna `minimax-m3` e outros
  - `GET /zen/v1/models` → HTTP 200, retorna `claude-fable-5` e outros
- **Conclusão:** Subscription $10/mo **ATIVA**. O gateway do Hermes adiciona User-Agent automaticamente, por isso funciona em produção. O `dashboard.py:check_opencode_go` falhava por 2 motivos:
  1. Endpoint errado (`/go/v1` em vez de `/zen/go/v1`)
  2. Sem `User-Agent` header (Cloudflare block)
- **Ação:** Patch em `dashboard.py:check_opencode_go` corrige ambos (ver Camada 2 do plano de unificação).

---

## 5. Plano de Ação Priorizado

### 🔴 CRÍTICO (Esta semana)

| # | Ação | Detalhes | Owner |
|---|------|----------|-------|
| 1 | ~~**Remover OpenCode Go do routing**~~ FEITO com ressalva | `opencode_go` removido de `provider_registry.py` (não commitado, branch `fix/dashboard-endpoint-and-bridge-argv`). Sub $10/mo **ATIVA** — diagnóstico errado foi corrigido (ver §4). Gateway do Hermes usa direto via `auth.json`, sem depender do registry. | Você |
| 2 | **Adicionar benchmark cron** | Cron job diário 06h rodando `track-provider-costs.py --benchmark` | Cron |
| 3 | **Popular `provider-benchmarks.db`** | Incluir Ollama Cloud, Nous, Nvidia (qwen) | Script |

### 🟡 ALTO (Próximas 2 semanas)

| # | Ação | Detalhes |
|---|------|----------|
| 4 | **Model Registry completo** | Descobrir todos modelos OpenCode Go via CLI ou docs; atualizar `dashboard_data.py:MODEL_CATALOG` |
| 5 | **Cost tracking por modelo real** | JSONL não tem `input_tokens`/`output_tokens` — adicionar no `track-provider-costs.py` |
| 6 | **Alertas de custo** | Webhook Telegram se DeepSeek > $0.50/dia ou provider free OFFLINE > 10min |
| 7 | **Routing otimizado por benchmark** | `hermes_router.py` usar `latency_ms` + `cost` para score dinâmico (não só tier priority) |

### 🟢 MÉDIO (Mês)

| # | Ação | Detalhes |
|---|------|----------|
| 8 | **Histórico de custos exportável** | Endpoint `/api/costs/export?format=csv|parquet&days=90` |
| 9 | **A/B testing de modelos** | Flag para testar % de tráfego em modelo novo antes de promover |
| 10 | **Dashboard: aba "Otimização"** | Sugestões: "Mover X tasks de DeepSeek para Nvidia = economia $Y/mês" |
| 11 | **Provider health scoring** | Composite score: uptime% × (1/latency) × (1/cost) × success_rate |

### 🔵 BAIXO (Backlog)

| # | Ação | Detalhes |
|---|------|----------|
| 12 | **Multi-region latency** | Benchmark de diferentes endpoints (ex: OpenRouter US vs EU) |
| 13 | **Model capabilities matrix** | Tags: `coding`, `reasoning`, `long-context`, `portuguese` → routing semântico |
| 14 | **Finbot integration** | Mostrar custo por conversa Finbot no dashboard |
| 15 | **OpenCode Go model discovery** | Se API não expõe, scrapear docs ou usar CLI `opencode models list` |

---

## 6. Immediate Next Steps (Para Fazer Agora)

```bash
# 1. Remover OpenCode Go do provider_registry.py e DISPLAY_ORDER
cd /root/repositorio/switch-adapter
# Editar provider_registry.py: remover entry opencode_go de ALL_PROVIDERS e DISPLAY_ORDER

# 2. Testar regex do dashboard sem opencode_go
python3 -c "
from dashboard import build_dashboard
import json
data = build_dashboard()
print('Providers:', [k for k in data.keys() if k not in ['timestamp', 'costs', 'codex', 'finbot_usage', 'tailscale', 'models']])
"

# 3. Rodar benchmark manual de todos providers ativos
python3 -c "
from dashboard import build_dashboard
import json
data = build_dashboard()
print(json.dumps({k: v.get('elapsed') for k,v in data.items() if isinstance(v, dict) and 'elapsed' in v}, indent=2))
"

# 4. Verificar health check do dashboard
python3 -c "
from dashboard import check_opencode_go
print(check_opencode_go('deepseek-v4-flash'))
"
```

---

## 7. Dashboard — URLs de Teste

| Componente | URL |
|------------|-----|
| **Web UI** | `http://localhost:8080/` |
| **API Health** | `http://localhost:8080/api/health` |
| **Dashboard JSON** | `http://localhost:8080/api/dashboard` |
| **Models Registry** | `http://localhost:8080/api/models` |
| **Cost Summary (30d)** | `http://localhost:8080/api/costs/summary?days=30` |
| **Tokens by Model** | `http://localhost:8080/api/tokens/by-model?days=30` |
| **Benchmarks** | `http://localhost:8080/api/benchmarks` |
| **WebSocket** | `ws://localhost:8080/ws` |

---

## 8. Decisões de Arquitetura (Registradas)

1. **Cache 8s** no `web_dashboard.py` — `build_dashboard()` roda em background, endpoints servem cache (0ms)
2. **ThreadPoolExecutor(12)** — health checks paralelos (antes 8s sequencial → agora ~2s parede)
3. **Design System** — `DESIGN.md` validado (lint 0 erros), exportado para CSS/Tailwind/DTCG
4. **PWA ready** — `manifest.json`, `sw.js`, ícones 72-512px, shortcuts
5. **Model registry no WS** — `/api/dashboard` e WS incluem `models.categories` para aba Modelos

---

## 9. Próxima Sessão — Checklist

- [ ] Validar key OpenCode Go e listar modelos
- [ ] Criar cron de benchmark diário
- [ ] Implementar alerta de custo/offline via Telegram
- [ ] Adicionar `input_tokens`/`output_tokens` no JSONL logging
- [ ] Criar aba "Otimização" no dashboard com sugestões de economia

---

*Documento gerado automaticamente — atualize após cada iteração.*