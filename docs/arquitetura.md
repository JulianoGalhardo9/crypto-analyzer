# Arquitetura (estado atual)

Descreve o que **existe hoje** no repositório. O desenho completo planejado está no `CLAUDE.md`.

```
src/crypto_analyzer/
  __init__.py        # __version__
  core/              # (vazio) funções puras: indicadores, regime, backtest, explainer
  pipeline/          # (vazio) bronze -> silver -> gold, qualidade
  reports/           # (vazio) montagem e escrita da planilha
  infra/             # (vazio) API do Mercado Bitcoin, banco, Telegram
  interfaces/        # (vazio) CLI, bot, API
tests/
  unit/              # test_package.py (teste de fumaça)
  integration/       # (vazio) banco real; API sempre simulada
  dags/              # (vazio) integridade das DAGs
dags/                # (vazio) DAGs do Airflow
config/              # (vazio) assets.yaml, regimes.yaml
docker/              # (vazio)
docs/                # esta documentação
.github/workflows/ci.yml
docker-compose.yml   # Postgres 16
```

## Regras que valem desde já
- `core/` nunca importa de `infra/`, `pipeline/`, `reports/`, `interfaces/` ou `dags/`.
- Airflow só orquestra: a lógica roda sem ele.
- Testes nunca chamam a API real.

## Fluxo de dados (planejado, ainda não implementado)
Mercado Bitcoin API → **bronze** (resposta bruta) → **silver** (limpo, UTC, deduplicado) → **gold** (indicadores, regimes, backtests) → CLI / bot / planilha.
