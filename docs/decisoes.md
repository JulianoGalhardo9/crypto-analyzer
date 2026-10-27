# Decisões técnicas

Formato: decisão, motivo e alternativa descartada.

## Ferramentas e ambiente

- **`uv` + `pyproject.toml`** — gerenciador rápido, com lockfile (`uv.lock`) para o CI reproduzir o mesmo ambiente.
- **Python 3.12 fixado (`.python-version`)** — a máquina tem 3.14, mas o Airflow costuma demorar a suportar versões novas. Descartado: usar o 3.14 local.
- **Dependências de runtime entram só quando usadas** — cada `uv add` aparece no commit da etapa que precisa dela, o que torna o histórico explicável.
- **Layout `src/`** — impede importar o pacote sem instalá-lo, então os testes exercitam o pacote como ele será entregue.
- **Ruff com regra `PD`** — aponta maus hábitos de pandas (`inplace`, `.values`), alinhado ao objetivo de aprendizado.
- **mypy em modo `strict`** — o CLAUDE.md exige tipos em tudo; é mais barato começar estrito do que apertar depois.

## Infraestrutura

- **Postgres 16 no Docker Compose** — o mesmo banco no desenvolvimento e no CI. O CI usa `services:` do GitHub Actions em vez de Compose.
- **Credenciais `crypto/crypto` no compose** — apenas desenvolvimento local; valores reais ficam no `.env`, que é ignorado pelo git.

## Organização do repositório

- **Saída das planilhas em `output/`** — evita confusão com o pacote `src/crypto_analyzer/reports/`, que é código.
- **Nome do pacote `crypto-analyzer`** (com "z") — a pasta local `crypto-analyser` tem grafia diferente e não foi renomeada.
- **Nenhum push automático** — publicar no GitHub é decisão do autor a cada vez.

## Pendentes (ver CLAUDE.md, "Decisões pendentes")

Definição de "dia" (UTC ou BRT), janela do percentil de regime, amostra mínima do backtest, histerese, frequência do `intraday_refresh`, limite de "dado velho".
