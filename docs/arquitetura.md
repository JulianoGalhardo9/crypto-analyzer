# Arquitetura (estado atual)

Descreve o que **existe hoje** no repositório. O desenho completo planejado está no `CLAUDE.md`.

```
src/crypto_analyzer/
  __init__.py        # __version__
  config.py          # Settings (DATABASE_URL via .env)
  core/              # funções puras: indicadores, regime, backtest, explainer
    models.py        # Regime (StrEnum)
    regime.py        # volatilidade realizada, percentil, classificação, histerese
    indicators.py    # sma, ema, rsi, macd, true_range, atr, bollinger, log_returns, rolling_correlation
  pipeline/          # bronze -> silver -> gold, qualidade
    bronze.py        # ingest_candles: API -> bronze
    process.py       # process_silver: bronze -> silver + qualidade (orquestra)
    silver.py        # parse_payload, build_silver (puro, pandas)
    quality.py       # checagens de qualidade (puro, pandas)
    market_data.py   # MarketDataClient (Protocol), RawCandles, MarketDataError
  reports/           # (vazio) montagem e escrita da planilha
  infra/             # API do Mercado Bitcoin, banco, Telegram
    mercado_bitcoin.py  # cliente httpx async (implementa MarketDataClient)
    db.py            # engine e sessões SQLAlchemy
    tables.py        # bronze_candles_raw, silver_candles, quality_issues
    repositories.py  # leitura/escrita (bronze, silver em upsert, qualidade)
  interfaces/        # CLI, bot, API
    cli.py           # `crypto-analyzer coletar` e `processar`
tests/
  unit/              # test_package, test_mercado_bitcoin_client, test_silver, test_quality, test_indicators, test_regime
  fixtures/          # respostas reais gravadas da API
  conftest.py        # backend asyncio para os testes async
  integration/       # banco real (Postgres do Docker); API sempre simulada
  dags/              # (vazio) integridade das DAGs
dags/                # (vazio) DAGs do Airflow
config/              # assets.yaml, quality.yaml, regimes.yaml
docker/              # (vazio)
docs/                # esta documentação
.github/workflows/ci.yml
migrations/          # Alembic (0001 bronze, 0002 silver e qualidade)
alembic.ini
docker-compose.yml   # Postgres 16 (porta 5433 no host)
```

## Regras que valem desde já
- `core/` nunca importa de `infra/`, `pipeline/`, `reports/`, `interfaces/` ou `dags/`.
- Airflow só orquestra: a lógica roda sem ele.
- Testes nunca chamam a API real.

## Fluxo de dados (planejado, ainda não implementado)
Mercado Bitcoin API → **bronze** (resposta bruta) → **silver** (limpo, UTC, deduplicado) → **gold** (indicadores, regimes, backtests) → CLI / bot / planilha.
