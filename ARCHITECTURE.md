# Arquitetura — LLM Switch Adapter

## Componentes

```
switch-adapter/
├── account_manager.py    # Snapshot + Symlink engine
├── codex_switcher.py     # Codex rate-limit detection + switching
├── hermes_router.py      # Complexity classifier + provider routing
├── cli.py                # CLI interface (argparse)
├── switch-adapter        # Entry point
├── accounts/
│   ├── accounts.json     # Registry de contas
│   ├── data/             # Snapshots (codex_conta1/, codex_conta2/)
│   └── logs/             # switch.log, costs.jsonl
├── README.md
└── ARCHITECTURE.md
```

## Fluxo de Dados

```
Usuário (CLI/Telegram)
        │
        ▼
   switch-adapter
        │
   ┌────┴────┐
   ▼         ▼
 codex     route
   │         │
   ▼         ▼
symlink   classify()
 switch    │
   │    ┌──┴──┐
   │   LOW  MED  HIGH
   │    │    │    │
   │  Open  Nvidia DeepSeek
   │  Router Free  Paid
   │
   ▼
~/.codex → accounts/data/codex_<active>/
```

## Design Patterns

### Symlink Switching
- `~/.codex` é um symlink → `accounts/data/codex_<name>/`
- Troca é instantânea (sem cópia)
- Estado (histórico, cache) é preservado por conta
- Snapshot inicial é lightweight (auth.json + config.toml apenas)

### Rate-Limit Detection
- Executa `codex exec 'true'` (mínimo custo se ativa)
- Faz parse do stderr via regex
- Timeout de 10s (assume rate-limited se travar)

### Complexity Classifier
- Regras regex hierárquicas (sem LLM para classificar)
- HIGH checked first (padrões mais específicos)
- Falls back to MEDIUM como safe default
- Length-based thresholds: <150 chars LOW, <800 MEDIUM, >800 HIGH

### Provider Routing
- LOW → OpenRouter `qwen/qwen3-coder:free` ($0)
- MEDIUM → Nvidia `qwen3-coder-480b` ($0) com fallback para glm4/minimax
- HIGH → DeepSeek `v4-flash` ($0.28/M tokens)

## Providers / Fallbacks

| Provider | Papel | Fallback |
|----------|-------|----------|
| OpenRouter free | Tarefas LOW | N/A |
| Nvidia free | Tarefas MEDIUM | glm4.7 → minimax-m2.7 → OpenRouter |
| DeepSeek paid | Tarefas HIGH | Hermes fallback chain nativa |
| Codex OAuth | Codificação | Conta 2 se rate-limited |

## Decisões de Design (ADR)

### ADR-001: Symlink vs Cópia para Account Switching
**Decisão:** Symlink
**Motivo:** Troca instantânea, estado preservado, sem duplicação de disco

### ADR-002: Snapshot Lightweight vs Full
**Decisão:** Lightweight (auth + config apenas)
**Motivo:** Codex logs_2.sqlite tem 52MB. Só precisamos das credenciais.

### ADR-003: Classificador Regex vs LLM
**Decisão:** Regex rules
**Motivo:** Usar um LLM para classificar tarefas (que depois vai pra outro LLM) é contraproducente para redução de custos.
