# Arquitetura (estado atual)

Descreve o que **existe hoje** no repositório. O desenho completo planejado está no `CLAUDE.md`.

```
src/crypto_analyzer/
  __init__.py        # __version__
  config.py          # Settings (DATABASE_URL via .env)
  core/              # (vazio) funções puras: indicadores, regime, backtest, explainer
  pipeline/          # bronze -> silver -> gold, qualidade
    bronze.py        # ingest_candles: API -> bronze
    market_data.py   # MarketDataClient (Protocol), RawCandles, MarketDataError
  reports/           # (vazio) montagem e escrita da planilha
  infra/             # API do Mercado Bitcoin, banco, Telegram
    mercado_bitcoin.py  # cliente httpx async (implementa MarketDataClient)
    db.py            # engine e sessões SQLAlchemy
    tables.py        # tabelas (hoje: bronze_candles_raw)
    repositories.py  # leitura/escrita (hoje: save_raw_candles)
  interfaces/        # CLI, bot, API
    cli.py           # `crypto-analyzer coletar`
tests/
  unit/              # test_package.py, test_mercado_bitcoin_client.py
  fixtures/          # respostas reais gravadas da API
  conftest.py        # backend asyncio para os testes async
  integration/       # banco real (Postgres do Docker); API sempre simulada
  dags/              # (vazio) integridade das DAGs
dags/                # (vazio) DAGs do Airflow
config/              # assets.yaml (regimes.yaml virá na etapa 5)
docker/              # (vazio)
docs/                # esta documentação
.github/workflows/ci.yml
migrations/          # Alembic (0001: bronze_candles_raw)
alembic.ini
docker-compose.yml   # Postgres 16 (porta 5433 no host)
```

## Regras que valem desde já
- `core/` nunca importa de `infra/`, `pipeline/`, `reports/`, `interfaces/` ou `dags/`.
- Airflow só orquestra: a lógica roda sem ele.
- Testes nunca chamam a API real.

## Fluxo de dados (planejado, ainda não implementado)
Mercado Bitcoin API → **bronze** (resposta bruta) → **silver** (limpo, UTC, deduplicado) → **gold** (indicadores, regimes, backtests) → CLI / bot / planilha.
