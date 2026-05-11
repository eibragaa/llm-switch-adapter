# LLM Switch Adapter

Roteador multi-conta e multi-provider para ferramentas de codificação AI. Alterna automaticamente entre contas Codex quando há rate-limit e escolhe o provider mais barato por complexidade da tarefa.

## Stack
- Python 3.10+ (stdlib only — zero dependencies)
- Symlink-based account switching (~/.codex → snapshot)
- Regex-based complexity classifier + rate-limit detection

## Como Instalar

```bash
cd /root/switch-adapter
ln -sf $(pwd)/switch-adapter /usr/local/bin/switch-adapter
```

## Comandos

### Codex Account Manager

```bash
# Adicionar nova conta (faça login no codex antes!)
switch-adapter codex add conta2 jean.braga23@gmail.com

# Listar contas com status
switch-adapter codex list

# Trocar manualmente
switch-adapter codex switch conta2

# Auto-detectar rate-limit e trocar
switch-adapter codex next

# Status detalhado
switch-adapter codex status
```

### Hermes Router

```bash
# Classificar complexidade (sem executar)
switch-adapter route "fix typo in main.py"
# → Complexity: LOW → OpenRouter Free

switch-adapter route "debug memory leak in production"
# → Complexity: HIGH → DeepSeek v4 Flash

# Classificar E executar
switch-adapter route --exec "add a test for login"
```

### Custos

```bash
switch-adapter cost
switch-adapter cost --days 30
```

## Fluxo para Adicionar Conta Codex

1. `codex logout` (se estiver logado)
2. `codex login` (nova conta)
3. `switch-adapter codex add conta2 email@gmail.com`

O symlink `~/.codex` aponta para o snapshot da conta ativa. Trocar de conta é instantâneo.

## Rate-Limit Detection

O parser detecta automaticamente:
- `You've hit your usage limit`
- `rate limit` / `quota exceeded`
- Timeout de execução
- Extrai horário de reset: `try again at 5:02 AM`

## Estratégia de Roteamento

| Complexidade | Provider | Modelo | Custo |
|-------------|----------|--------|-------|
| LOW | OpenRouter | qwen/qwen3-coder:free | $0 |
| MEDIUM | Nvidia | qwen3-coder-480b | $0 |
| HIGH | DeepSeek | deepseek-v4-flash | $0.28/M |

## URLs
- Repo: /root/switch-adapter/
- Symlink: ~/.codex → accounts/data/codex_<active>/
- Logs: accounts/logs/switch.log
- Custos: accounts/logs/costs.jsonl
