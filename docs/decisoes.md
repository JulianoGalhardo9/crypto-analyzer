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
- **Testes de integração em banco separado (`<banco>_test`)** — os testes apagam tabelas; no mesmo banco dos dados reais isso destruiria o histórico (e deixou lixo nele uma vez). O banco de teste é criado sozinho pela fixture.
- **Commit por par na ingestão** — um erro no ETH não descarta o BTC já gravado; a falha sobe para quem chamou decidir (Airflow fará retry só do que faltou).
- **`DATABASE_URL` sem valor padrão no código** — obriga a configurar via `.env`/ambiente; o CI define a sua.

## Silver e qualidade

- **Funções puras primeiro, banco depois** — `build_silver` e as checagens recebem e devolvem DataFrames, então são testadas com dados sintéticos, sem Postgres.
- **Duplicata: vale a resposta mais recente** — o candle do dia corrente chega incompleto numa coleta e completo na seguinte; a nova substitui a antiga. `source_bronze_id` mantém a rastreabilidade.
- **Candle parcial é marcado, não removido** — `is_partial` deixa quem consome decidir (indicadores devem ignorá-lo).
- **Outlier por mediana e MAD, não por média e desvio padrão** — o próprio outlier infla o desvio padrão e se esconde; mediana e MAD não são distorcidas por ele.
- **Outlier é `info`, nunca motivo de remoção** — medido nos dados reais: os "outliers" são crashes e picos verdadeiros. Apagar seria falsificar o histórico.
- **Retornos que atravessam um buraco não entram na checagem** — não são de um único passo, então não são comparáveis.
- **Parâmetros em `config/quality.yaml`** — limite de outlier e idade máxima por resolução, nunca fixos no código.
- **Upsert com chave composta (par, resolução, ts)** — o `ON CONFLICT DO UPDATE` do Postgres torna o reprocessamento seguro (backfill e retry do Airflow); o `updated_at` mostra quando cada candle foi tocado pela última vez.
- **Preços como `Numeric(24,8)`, não `float`** — a API entrega 8 casas decimais; `float` no banco acumularia erros de arredondamento. No pandas usamos `float64`, que basta para os indicadores.
- **Problemas de qualidade são reescritos a cada processamento do par** — o resultado reflete o estado atual da silver, sem acumular histórico de avisos repetidos.
- **Uma transação por par** — falha no ETH não desfaz o BTC.
- **Silver só padroniza; quem sinaliza problemas é `quality.py`** — ajuste em relação ao texto original do CLAUDE.md, que falava em "outliers tratados" na silver.

## Indicadores

- **`pandas-ta-classic` como gabarito, não `pandas-ta`** — a original não instala com pandas 3 (conflito de `numpy` via `numba`). O fork é só dependência de desenvolvimento, nunca de runtime, como o CLAUDE.md pede.
- **Média exponencial semeada com a SMA** — convenção clássica (Wilder, TradingView) e a do gabarito. Começar do primeiro preço dá números diferentes no início que só convergem devagar; medido: diferença de 17 pontos no RSI no começo e 0,03 ainda depois de 100 candles.
- **Sem loops** — a semente (SMA) é colocada na posição N e o `ewm` do pandas segue a recursão; fica vetorizado.
- **NaN no aquecimento, nunca preenchido** — os primeiros `window - 1` valores não existem; inventar um número seria fingir precisão.
- **RSI com preço parado é NaN; só altas dá exatamente 100** — consequência natural da fórmula, documentada e testada.
- **True range do primeiro candle é NaN** — sem fechamento anterior não dá para medir o salto. Convenção da TA-Lib e do gabarito; evita um primeiro valor que seria inconsistente com os demais. O ATR começa no candle `window` (igual ao RSI).
- **MACD devolve um DataFrame (`macd`, `signal`, `histogram`)** — as três séries nascem juntas e compartilham o mesmo índice; mais simples de persistir e de colocar na planilha.
- **O sinal do MACD também é semeado com a SMA** — mesma convenção das outras médias; assim bate com o gabarito.
- **Validação também em dados reais** — além dos testes sintéticos, comparei com o gabarito nos candles reais dos 3 ativos (diferença máxima ~5e-10).
- **Bollinger com desvio populacional (`ddof=0`)** — convenção de Bollinger, do TradingView e do gabarito. O padrão do pandas é `ddof=1`; sem passar `ddof=0` as bandas saem mais largas.
- **Correlação sobre retornos logarítmicos, não sobre preços** — preços de séries em tendência quase sempre parecem correlacionados; os retornos medem se os movimentos coincidem.
- **Correlação só nas datas em comum** — a janela é de datas presentes nas duas séries (a SOL começou em 2021, o BTC em 2013), e não de dias corridos.
- **`window` da correlação é obrigatório** — é uma escolha do projeto, não uma convenção do mercado; será definida em configuração.
- **Rótulos de correlação por percentil, não por corte fixo** — medido: ETH e SOL têm correlação de 90 dias com o BTC sempre alta (mínimos 0,54 e 0,50; medianas 0,82 e 0,74). Um corte fixo diria "anda junto" quase todo dia.
- **Teste de "sem look-ahead"** — alterar valores futuros não pode mudar os indicadores já calculados.

## Regimes de volatilidade

- **Decisões delegadas pelo autor e tomadas medindo** — as tabelas de medição estão no registro de ações (2026-10-29).
- **Percentil em janela móvel de 365 dias, não crescente** — a volatilidade das criptos caiu com o tempo; com o histórico inteiro, a SOL ficava 57% do tempo em "calma". A janela móvel deu a distribuição mais equilibrada nos 3 ativos.
- **Mínimo de 180 valores de volatilidade** — abaixo disso o regime é NaN ("sem histórico suficiente"), alinhado à regra de não fingir precisão.
- **Volatilidade realizada de 30 dias** — desvio padrão dos retornos logarítmicos diários; reaproveita `log_returns`. Os candles horários não entram agora.
- **Cortes 33/66 e `<=` na calma** — percentil até 33 é calma, acima de 66 é alta. Os cortes vêm do YAML.
- **Histerese de 5 dias** — sem ela o regime trocava ~24 vezes por ano (mediana de 5 a 8 dias por regime), ruído demais para alertar; com 5, ~11 trocas por ano. Custo: o sinal chega até 5 dias depois.
- **Histerese é um laço, não vetorizada** — é uma máquina de estados (hoje depende de ontem). Único laço do núcleo, justificado e testado.
- **Rótulo é relativo ao próprio histórico** — "calma" significa calma para aquele ativo na janela de 365 dias, não calma em absoluto. O texto ao usuário deve dizer isso (etapa 7).
- **`Regime` como `StrEnum` em `core/models.py`** — os valores `calm`/`normal`/`high` são os que vão para o banco; a tradução para o português é só na exibição.

## Idioma

- **Comentários e docstrings em português; nomes de código e commits em inglês** — o projeto é de estudo e os comentários servem de explicação para o autor; o inglês nos nomes e commits mantém o padrão do mercado e do portfólio.

## Organização do repositório

- **Saída das planilhas em `output/`** — evita confusão com o pacote `src/crypto_analyzer/reports/`, que é código.
- **Nome do pacote `crypto-analyzer`** (com "z") — a pasta local `crypto-analyser` tem grafia diferente e não foi renomeada.
- **Nenhum push automático** — publicar no GitHub é decisão do autor a cada vez.

## Pendentes (ver CLAUDE.md, "Decisões pendentes")

Definição de "dia" (UTC ou BRT), janela do percentil de regime, amostra mínima do backtest, histerese, frequência do `intraday_refresh`, limite de "dado velho".
