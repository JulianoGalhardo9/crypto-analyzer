# Registro de ações

Diário do que foi feito, em ordem cronológica. Cada entrada diz **o que**, **por quê** e, quando houver, o **commit**. O que ainda não foi verificado é dito explicitamente.

## 2026-10-27

### Análise do CLAUDE.md
- Leitura crítica do `CLAUDE.md`, sem alterar arquivos.
- Pontos fortes: escopo fechado, núcleo funcional puro, regras de honestidade nos números.
- Riscos levantados: look-ahead bias nos regimes e no backtest, amostra pequena no backtest, fuso do "dia", casos de borda (BTC x BTC, dado velho), confusão entre `reports/` (código) e `reports/` (saída), escopo grande para a v1.

### Ajustes no CLAUDE.md e conexão com o GitHub
- `git init -b main` e `git remote add origin https://github.com/JulianoGalhardo9/crypto-analyzer.git`. Nenhum push foi feito.
- `CLAUDE.md` atualizado: seção **GitHub**, regras de **backtest**, regras **sem look-ahead** e **histerese**, seção **Decisões pendentes**, pasta de saída das planilhas renomeada para `output/`, definição de MVP (etapas 1 a 8), logging e Postgres no CI.
- Commit `a4f1928` — `docs: add project context and gitignore` (inclui o `.gitignore`).

### Etapa 1 — Base do projeto
- Commit `396b4c5` — `chore: scaffold package, tests and tooling`
  - Layout `src/crypto_analyzer/` (`core`, `pipeline`, `reports`, `infra`, `interfaces`), `tests/` (`unit`, `integration`, `dags`), `dags/`, `config/`, `docker/`.
  - `pyproject.toml` (hatchling), Python 3.12 fixado, dependências de desenvolvimento: pytest, pytest-cov, ruff, mypy, pandas-stubs.
  - Ruff, mypy (strict) e pytest configurados; um teste de fumaça do pacote.
- Commit `97e2480` — `ci: add GitHub Actions workflow with Postgres service`
  - Workflow: ruff, format, mypy, pytest com cobertura, Postgres 16 como service.
- Commit `ebe0b62` — `chore: add docker compose with Postgres and env example`
  - Postgres 16 com volume e healthcheck; `.env.example` sem segredos.
- Verificado localmente: `ruff check`, `ruff format --check`, `mypy src`, `pytest` (1 teste passando).
- **Não verificado:** o Postgres do compose não foi iniciado (Docker Desktop estava fechado; só a sintaxe foi validada com `docker compose config`) e o workflow do CI ainda não rodou no GitHub (falta o push).

### Documentação
- Criada a pasta `docs/` com este registro, `decisoes.md` e `arquitetura.md`.

## 2026-10-28

### Docker pelo terminal e fluxo GitHub autorizado
- `CLAUDE.md`: novas seções **Docker** (o Claude opera o Docker pelo terminal, sem apagar volumes) e autorização permanente para branches, commits, push de branches, PRs e merges, com limites (sem force push, sem mexer em configurações do repositório).
- `docker compose up -d`: Postgres 16 subiu e ficou `healthy`; `select version()` respondeu `PostgreSQL 16.15`. **Verificado.**
- Primeiro `git push -u origin main` (o remote estava vazio).
- `gh` (GitHub CLI) instalado com Homebrew para criar PRs e fazer merges. **Falta autenticar** (`gh auth login`), que é interativo.
- O CI ainda não foi conferido no GitHub.

### Etapa 2 — Cliente do Mercado Bitcoin (em andamento)
- PR #1 (`docs: authorize PR workflow and Docker via terminal`) mergeado com squash; **CI verde** (27s), primeira execução no GitHub.
- Lida a especificação OpenAPI oficial (`/docs/swagger.yaml`; a página `/docs` é só um visualizador que a carrega) e **medidos** na API pública os pontos que a documentação não cobre. Resultado em [api-mercado-bitcoin.md](api-mercado-bitcoin.md).
  - Rate limit documentado: 1 req/s. Sem limite de candles por requisição (medido: 42 mil candles horários de uma vez).
  - O User-Agent padrão do `urllib` recebe 403; `httpx` funciona.
  - Histórico diário: BTC desde 2013-06, ETH desde 2018-12, SOL desde 2021-11.
- Branch `feat/mercado-bitcoin-client`:
  - `httpx` adicionado como dependência.
  - `pipeline/market_data.py`: protocolo `MarketDataClient`, `RawCandles` e `MarketDataError`.
  - `infra/mercado_bitcoin.py`: cliente async com espaçamento de 1 req/s, retry com backoff exponencial (respeita `Retry-After`), User-Agent próprio.
  - 11 testes unitários com `httpx.MockTransport` e uma resposta real gravada como fixture (`tests/fixtures/candles_sol_brl_1d.json`). Passam localmente; **nenhum teste chama a API real**.
- **Ainda não feito nesta etapa:** gravar a bronze no Postgres (tabela, SQLAlchemy, Alembic) e coletar o histórico de verdade.

### Comentários em português e resumo ao final das respostas
- `CLAUDE.md`: comentários e docstrings passam a ser em **português**; nomes de código e commits continuam em inglês. Nova regra: toda resposta termina com a seção "O que mudou", em linguagem simples, citando os arquivos.
- Comentários e docstrings já existentes traduzidos em `pipeline/market_data.py`, `infra/mercado_bitcoin.py` e `tests/unit/test_mercado_bitcoin_client.py`. Nenhuma lógica foi alterada.

## Pendências abertas
- Etapa 2: persistir a bronze (SQLAlchemy + Alembic + tabela com JSONB) e coletar BTC, ETH e SOL.
- Decisão do "dia": a API entrega candles diários à 00:00 UTC; confirmar com o autor que o projeto fica em UTC.
