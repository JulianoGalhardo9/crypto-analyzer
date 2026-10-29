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

### Etapa 2 — Armazenamento da bronze (PR em andamento)
- Decisão do autor: o **"dia" é UTC** (registrada no CLAUDE.md).
- Descoberto: já existe um **Postgres instalado na máquina** (PID 1437) ocupando `localhost:5432`, que "escondia" o do Docker (erro `role "crypto" does not exist`). Solução: o container publica a porta **5433** no computador (continua 5432 por dentro e no CI). O Postgres local não foi tocado; os dados do volume Docker foram mantidos.
- Dependências: `sqlalchemy`, `psycopg[binary]`, `alembic`, `pydantic-settings`.
- `config.py` (`Settings` com `DATABASE_URL` do `.env`), `infra/db.py` (engine e sessões), `infra/tables.py` (tabela `bronze_candles_raw`, JSONB), `infra/repositories.py` (`save_raw_candles`).
- Alembic configurado (`alembic.ini`, `migrations/env.py` lendo a URL do `.env`); migration `0001` gerada, **lida antes de aplicar** e aplicada no Postgres do Docker (`\d bronze_candles_raw` conferido).
- Testes de integração (`tests/integration/`) gravam e leem a bronze no Postgres real. Total: 13 testes passando localmente. CI passou a definir `DATABASE_URL`.
- **Ainda não feito:** função de ingestão `pipeline/bronze.py` e a coleta real de BTC, ETH e SOL.

### Etapa 2 — Ingestão da bronze e primeira coleta real
- `config/assets.yaml` (BTC, ETH, SOL em BRL) e `config.py` com `load_assets()`; dependências `typer` e `pyyaml`.
- `pipeline/bronze.py`: `ingest_candles` busca cada par e grava a resposta crua; commit por par (se um falhar, o que já foi gravado fica). Chamadas sequenciais por causa do limite de 1 req/s.
- `interfaces/cli.py`: comando `crypto-analyzer coletar` (`--resolucao 1d|1h`, `--candles`).
- **Problema encontrado e corrigido:** os testes de integração apagavam a bronze do banco real. Agora usam um banco separado, `crypto_analyzer_test`, criado e migrado automaticamente. Duas linhas de teste (ids 11 e 12) tinham vazado para o banco real antes da correção; confirmei que eram lixo (fixture de 3 candles, `fetched_at` fixo) e as removi.
- **Coleta real (2026-10-29, 1d, `countback=100000`), medida no banco:**

| Par | Candles | Primeiro | Último | Tamanho do JSON no banco |
|---|---|---|---|---|
| BTC-BRL | 4.888 | 2013-06-12 | 2026-10-29 | 188 kB |
| ETH-BRL | 2.879 | 2018-12-12 | 2026-10-29 | 117 kB |
| SOL-BRL | 1.796 | 2021-11-29 | 2026-10-29 | 71 kB |

  As 3 chamadas levaram cerca de 3,4 s no total. O último candle de cada par é o do dia corrente (parcial).
- 16 testes passando (4 de integração no Postgres de teste). **Candles horários ainda não foram coletados**; fica para quando a etapa de volatilidade precisar.
- **Ainda não feito:** silver (limpeza), etapa 3.

### Etapa 3 — Silver e qualidade, PR A: funções puras com pandas
- Dependência: `pandas`. Novo `config/quality.yaml` (limite de outlier e idade máxima do último candle) e `load_quality_config()`.
- `pipeline/silver.py`: `parse_payload` (listas da API -> DataFrame com índice UTC e `float64`) e `build_silver` (junta várias respostas da bronze; em duplicatas vale a resposta mais recente; marca `is_partial`; guarda `source_bronze_id`).
- `pipeline/quality.py`: checagens de preço inválido, buracos (agrupados), outliers (mediana + MAD), dado velho e duplicatas.
- 30 testes passando (26 unitários novos com dados sintéticos).
- **Rodei as funções nos dados reais da bronze (só leitura), medido em 2026-10-29:** nenhum candle inválido, **nenhum buraco**, **nenhum dado velho**, **1 candle parcial por ativo** (o de hoje), 0 duplicatas (só há uma coleta).
- Outliers (limite 10): BTC 13, ETH 2, SOL 1. **São eventos reais** (ETH -38,8% em 2020-03-12; SOL -42,4% em 2022-11-09; BTC com oscilações de 20% a 49% em 2013), por isso a severidade é `info` e nenhum candle é removido.
- **Ainda não feito (PR B):** tabelas `silver_candles` e `quality_issues`, migration, gravação no banco e comando de CLI.

## Pendências abertas
- Etapa 2: persistir a bronze (SQLAlchemy + Alembic + tabela com JSONB) e coletar BTC, ETH e SOL.
- Etapa 3, PR B: persistir silver e qualidade no Postgres e rodar sobre os dados reais.
