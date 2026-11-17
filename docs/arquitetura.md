# Arquitetura (estado atual)

Descreve o que **existe hoje** no repositório. O desenho completo planejado está no `CLAUDE.md`.

```
src/crypto_analyzer/
  __init__.py        # __version__
  config.py          # Settings (DATABASE_URL via .env)
  core/              # funções puras: indicadores, regime, backtest, explainer
    models.py        # Regime, Trend, CorrelationLevel, Analysis
    explainer.py     # números -> texto simples (explain, explain_details)
    trend.py         # classify_trend
    regime.py        # volatilidade realizada, percentil, classificação, histerese, mudanças novas
    refresh.py       # refresh_due: hora de atualizar os candles de 1h?
    indicators.py    # sma, ema, rsi, macd, true_range, atr, bollinger, log_returns, rolling_correlation
  pipeline/          # bronze -> silver -> gold, qualidade
    bronze.py        # ingest_candles: API -> bronze
    build_analysis.py  # build_analysis: banco -> Analysis
    build_report.py  # build_report_data: banco -> ReportData (dados da planilha)
    analysis.py      # assemble_analysis: gold -> Analysis (puro)
    gold.py          # compute_indicators, compute_gold (puro, pandas)
    process_gold.py  # process_gold: silver -> gold (orquestra)
    process.py       # process_silver: bronze -> silver + qualidade (orquestra)
    silver.py        # parse_payload, build_silver (puro, pandas)
    quality.py       # checagens de qualidade (puro, pandas)
    intraday.py      # symbols_due_for_refresh e refresh_hourly (candles de 1h)
    alerts.py        # regime_alert_messages (textos dos alertas de regime)
    market_data.py   # MarketDataClient (Protocol), RawCandles, MarketDataError
  reports/           # montagem e escrita da planilha
    frames.py        # um DataFrame por aba (puro)
    excel.py         # write_report: escreve o .xlsx (formatos, cores, filtros, gráficos)
  infra/             # API do Mercado Bitcoin, banco, Telegram
    mercado_bitcoin.py  # cliente httpx async (implementa MarketDataClient)
    db.py            # engine e sessões SQLAlchemy
    tables.py        # bronze, silver, quality_issues, dim_ativo, fact_indicador, fact_regime
    repositories.py  # leitura/escrita (bronze, silver em upsert, qualidade)
  interfaces/        # CLI, bot, API
    airflow_callbacks.py  # on_failure_callback das DAGs (não importa o Airflow)
    cli.py           # `crypto-analyzer coletar`, `processar`, `calcular` e `analisar`
tests/
  unit/              # test_package, test_mercado_bitcoin_client, test_silver, test_quality, test_indicators, test_regime, test_gold, test_explainer, test_analysis, test_trend_and_levels, test_cli, test_report_frames, test_report_excel (report_data.py: dados sintéticos compartilhados)
  fixtures/          # respostas reais gravadas da API
  conftest.py        # backend asyncio para os testes async
  integration/       # banco real (Postgres do Docker); API sempre simulada
  dags/              # integridade das DAGs com DagBag (conftest aponta AIRFLOW_HOME para pasta temporária)
dags/
  intraday_refresh.py  # aos 5 min de cada hora: short-circuit decide quem atualiza (1h/3h/6h pelo regime) -> candles 1h
  daily_report.py  # roda após cada atualização do gold (Asset crypto_gold): gera o .xlsx em output/
  daily_pipeline.py  # 00:15 UTC: coleta (mapeada, 1 por vez) -> silver (mapeada) -> gold -> alerta de regime
config/              # assets.yaml (com nomes e benchmark), quality.yaml, regimes.yaml, report.yaml
docker/
  airflow/
    Dockerfile       # apache/airflow:3.4.0-python3.12 + crypto-analyzer (editável)
    compose.yaml     # Airflow 3.4 (LocalExecutor), perfil "airflow", incluído pelo docker-compose.yml
airflow/             # logs e airflow.cfg gerados pelo Airflow (no .gitignore)
docs/                # esta documentação
.github/workflows/ci.yml
migrations/          # Alembic (0001 bronze, 0002 silver e qualidade, 0003 gold)
alembic.ini
docker-compose.yml   # Postgres 16 do projeto (porta 5433 no host) + include do Airflow
.dockerignore        # a imagem só recebe pyproject, README, src/ e config/
```

## Regras que valem desde já
- `core/` nunca importa de `infra/`, `pipeline/`, `reports/`, `interfaces/` ou `dags/`.
- Airflow só orquestra: a lógica roda sem ele.
- Testes nunca chamam a API real.

## Fluxo de dados (planejado, ainda não implementado)
Mercado Bitcoin API → **bronze** (resposta bruta) → **silver** (limpo, UTC, deduplicado) → **gold** (indicadores, regimes, backtests) → CLI / bot / planilha.
