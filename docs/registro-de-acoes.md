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

## Pendências abertas
- Subir o Postgres (`docker compose up -d`) e conferir o status `healthy`.
- Primeiro `git push -u origin main` (decisão do autor) e conferir o CI.
- Próxima etapa: **2 — cliente do Mercado Bitcoin + bronze**, começando pela leitura da documentação oficial da API.
