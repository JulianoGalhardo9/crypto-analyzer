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

## Cliente da API

- **Protocolo `MarketDataClient` em `pipeline/`, implementação em `infra/`** — quem usa a interface (a bronze) é quem a define; `infra` apenas a implementa. `core/` continua sem importar nada disso. Existe só para permitir fakes nos testes.
- **Retry, backoff e espaçamento dentro do cliente, com `sleep` e `clock` injetáveis** — os testes verificam os tempos de espera sem esperar de verdade. Alternativa descartada: biblioteca de retry (`tenacity`), por ser uma dependência a mais para 30 linhas.
- **Só retenta 429 e 5xx e erros de rede** — um 403 ou 404 não melhora ao repetir, então falha logo.
- **`httpx.MockTransport` nos testes** — sem biblioteca extra de mock; o cliente recebe o `AsyncClient` por parâmetro.
- **Datas sempre com fuso** — o cliente recusa `datetime` sem timezone, alinhado à regra de UTC do CLAUDE.md.
- **Fixture real gravada** — o JSON de teste é uma resposta verdadeira da API (3 candles), não inventada.

## Banco e bronze

- **Bronze em uma tabela com `payload` JSONB** — guarda a resposta inteira, sem interpretar. Quando a API mudar de formato, o dado antigo continua intacto. Só recebe INSERT (imutável por convenção).
- **`fetched_at` (do cliente) e `ingested_at` (do Postgres)** — dois momentos distintos: quando recebemos e quando gravamos.
- **SQLAlchemy síncrono** — o gargalo é a API (1 req/s), não o banco; o cliente HTTP segue async. Alternativa descartada: driver async, que complicaria Alembic e testes sem ganho.
- **Alembic com a URL vinda do `.env`** — o `alembic.ini` é commitado, então não pode conter credenciais. As migrations autogeradas são lidas antes de aplicar.
- **Porta 5433 no host** — o Postgres local do autor já usa a 5432. Alternativa descartada: parar o Postgres local (não é nosso para mexer).
- **`DATABASE_URL` sem valor padrão no código** — obriga a configurar via `.env`/ambiente; o CI define a sua.

## Idioma

- **Comentários e docstrings em português; nomes de código e commits em inglês** — o projeto é de estudo e os comentários servem de explicação para o autor; o inglês nos nomes e commits mantém o padrão do mercado e do portfólio.

## Organização do repositório

- **Saída das planilhas em `output/`** — evita confusão com o pacote `src/crypto_analyzer/reports/`, que é código.
- **Nome do pacote `crypto-analyzer`** (com "z") — a pasta local `crypto-analyser` tem grafia diferente e não foi renomeada.
- **Nenhum push automático** — publicar no GitHub é decisão do autor a cada vez.

## Pendentes (ver CLAUDE.md, "Decisões pendentes")

Definição de "dia" (UTC ou BRT), janela do percentil de regime, amostra mínima do backtest, histerese, frequência do `intraday_refresh`, limite de "dado velho".
