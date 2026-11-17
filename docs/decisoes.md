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

## Gold e modelagem

- **`fact_candle` é a `silver_candles`** — criar outra tabela com os mesmos candles só duplicaria dados. A silver já tem a chave `(par, resolução, ts)`.
- **`fact_indicador` em formato largo** — uma linha por ativo e dia, uma coluna por indicador. É o formato mais simples de consultar em SQL e de virar a aba da planilha. Alternativa descartada: formato longo (uma linha por indicador), que exigiria pivotar sempre.
- **Parâmetros no nome da coluna (`sma_20`, `rsi_14`, `corr_btc_90`)** — o nome é honesto sobre o que a coluna contém; mudar um parâmetro é uma mudança de esquema (migration), não uma troca silenciosa de significado. Por isso esses parâmetros ficam como constantes em `pipeline/gold.py`, e não em YAML.
- **Só candles fechados no gold** — o candle parcial de hoje não gera indicador; senão o RSI de "hoje" mudaria a cada coleta.
- **NaN vira NULL** — aquecimento e "não se aplica" (correlação do BTC com ele mesmo) ficam nulos; nada é preenchido com zero ou valor inventado.
- **`dim_ativo` populada a partir de `assets.yaml`** — com nome amigável ("Solana") para a resposta e a planilha; o `benchmark` também é configuração.
- **Chaves por `ativo_id` nas fatos, `symbol` na bronze e na silver** — a dimensão entra onde o dado vira consumo; as camadas de ingestão continuam falando a língua da API.
- **Upsert compartilhado (`_upsert_frame`)** — silver e gold usam a mesma lógica de `ON CONFLICT DO UPDATE`; o reprocessamento é seguro para backfill e retry.
- **Tudo em uma transação** — se algo falhar no meio, o gold não fica pela metade.

## Explainer

- **"Últimas 24h" é o último dia fechado, com a data** — sem candles horários não há janela móvel de 24h; mostrar "24h" seria fingir precisão. Muda quando os horários entrarem.
- **Dado velho usa o mesmo limite da qualidade** (`max_age_hours`, 48 h) — uma única definição de "atrasado" no projeto.
- **Tendência por alinhamento, não por número fixo** — preço > média 50 > média 200 é subindo; o inverso, caindo; o resto, de lado. É uma regra estrutural (ordem), sem corte arbitrário.
- **Sem a média de 200 dias, "sem conclusão"** — em vez de usar uma média mais curta e fingir a mesma confiança.
- **RSI só aparece nos extremos (70 e 30)** — são os limites clássicos de Wilder, não cortes inventados; no meio do caminho o RSI não diz nada de útil e só aumentaria a resposta.
- **Frases com números vêm dos dados** — "variou cerca de X% por dia e, em 1 de cada 10 dias, mais de Y%" usa a mediana e o percentil 90 do último ano daquele ativo.
- **Correlação: fato + comparação com o normal** — "anda junto" é verdade quase sempre (medido); a informação nova é se hoje está mais ou menos colada que o normal do próprio ativo.
- **Cortes 0,7 e 0,4 para a força da correlação** — convenção usual da estatística; é só a palavra ("junto", "parcialmente", "independente"). O que diferencia os dias é o percentil.
- **Suporte e resistência = mínima e máxima de 30 e 90 dias** — definição simples (canal de Donchian), explicitamente rotulada como "mínima e máxima recentes".
- **Nenhuma previsão no texto** — o RSI alto diz que "subiu muito rápido", nunca que "vai cair". Há teste para isso.
- **`is_partial` pela hora da coleta, não do processamento** — um candle é fechado só se a coleta que o trouxe ocorreu depois do fim dele. Pela hora do processamento, reprocessar dias depois "fechava" um retrato incompleto (bug real, 2026-11-03).
- **O gold apaga linhas posteriores ao último candle fechado** — um dia que antes contava como fechado pode voltar a ser parcial; guardar indicadores dele seria guardar números sobre dado incompleto.
- **Artigo e concordância por ativo na configuração** — "o BTC, o ETH, a SOL": o gênero não se deduz do nome, então fica em `assets.yaml`.
- **Erro de API explicado, sem traceback** — falhas esperadas da fonte de dados viram mensagem curta e código de saída 1; o que já estava gravado é mantido.
- **Texto puro, sem formatação de terminal** — o mesmo texto serve para o CLI e, na etapa 12, para o bot do Telegram.
- **O explainer não calcula nada** — recebe o `Analysis` pronto; os números vêm do pandas, nunca do texto (regra do CLAUDE.md sobre LLM e cálculo vale aqui também).

## Planilha

- **Formato longo (coluna `Ativo` + uma linha por dia)** — é o que permite filtrar, ordenar e criar tabelas dinâmicas. Uma aba por ativo impediria comparar ativos num filtro só.
- **Janela de 365 dias nas abas diárias, em `config/report.yaml`** — o histórico completo teria ~9.500 linhas por aba e pouca utilidade; os indicadores continuam calculados sobre todo o histórico, então a janela não tem vazios de aquecimento.
- **Datas sem fuso** — o XlsxWriter/Excel não aceita datas com fuso; escrevo o dia UTC como data comum e a aba Sobre avisa.
- **Aba `Mudanças` além das listadas no CLAUDE.md** — a lista de datas em que o regime mudou é pedida na aba `Regimes`, mas misturá-la com a série diária quebraria o filtro e as tabelas dinâmicas.
- **Aba `Backtest` só na etapa 11** — não faria sentido uma aba vazia; o teste de abas a incluirá quando existir.
- **Cabeçalhos e rótulos em português** — a planilha é para o usuário final, diferente do código.
- **Valores vazios só onde fazem sentido** — correlação do BTC (é a referência) e datas de verificações que não têm data (ex.: duplicatas). Nenhum "—" em coluna numérica, que a transformaria em texto.
- **Aba `Gráficos` separada** — os gráficos (preço com médias de 20/50/200 dias e volatilidade, um par por ativo) ficam numa aba própria em vez de flutuar sobre as tabelas, que continuam livres para filtrar e ordenar. Os gráficos leem os dados das abas `Indicadores` e `Regimes`, então não há cópia dos números.
- **Cores por formatação condicional, não por célula** — o Excel recalcula a cor se o usuário editar ou filtrar; pintar célula a célula deixaria a cor "presa" ao valor antigo.
- **A planilha reaproveita `build_analysis`** — o `Resumo` usa exatamente a mesma análise do comando `analisar`, então os dois nunca discordam. O custo é ler os candles duas vezes do banco (poucos milhares de linhas, ~1 s no total).
- **Frames puros, escrita separada** — `frames.py` monta DataFrames testáveis sem Excel; `excel.py` só formata e escreve.

## Airflow

- **Airflow 3.4.0 (estável mais recente em 2026-11-17, lançada em 06/11), imagem `python3.12`** — o CLAUDE.md pede a mais recente e a documentação dela foi lida antes (compose, TaskFlow, timetables, LocalExecutor, referência de configuração). Descartado: a 3.3.2, mais antiga sem motivo concreto.
- **Compose a partir do oficial, enxugado** — LocalExecutor no lugar do Celery (sem Redis, worker e flower), sem triggerer (só serve para tarefas *deferrable*, que não usamos), sem exemplos carregados. Medido em repouso: ~825 MB para os 5 contêineres (api-server 267, scheduler 233, dag-processor 208, os dois Postgres 117). O oficial pede ≥ 4 GB para o Docker; aqui há 3,8 GiB e sobra folga.
- **`AIRFLOW__CORE__PARALLELISM=4`** — a documentação do LocalExecutor diz que, no Linux (modo *fork*), ele abre `parallelism` processos de uma vez; o padrão (32) gasta memória à toa num projeto com no máximo 3 tarefas paralelas.
- **Perfil `airflow` e arquivo próprio (`docker/airflow/compose.yaml`, incluído pelo `docker-compose.yml`)** — `docker compose up -d` continua subindo só o Postgres do projeto (testes e CLI não precisam do Airflow); `--profile airflow` sobe o resto. Descartado: tudo sempre ligado, gastando ~800 MB sem necessidade.
- **Banco de metadados separado (`airflow-postgres`)** — exigência do CLAUDE.md: apagar ou recriar o Airflow nunca toca no histórico coletado.
- **Imagem própria com o pacote instalado em modo editável em `/opt/crypto-analyzer`** — o `config.py` acha os YAMLs a partir do próprio arquivo; num `pip install` comum o código iria para `site-packages` e o caminho quebraria. Com `src/` e `config/` montados por cima, mudar o código não exige reconstruir a imagem. O `pip install` usa o arquivo de *constraints* do Airflow para não trocar versões das dependências dele. Descartado: `_PIP_ADDITIONAL_REQUIREMENTS` (a documentação desaconselha: reinstala a cada partida).
- **SQLAlchemy `>=2.0.50,<2.1`** — o Airflow 3.4 fixa 2.0.55; o projeto pedia `>=2.1.6` sem usar nada da 2.1 (suíte inteira e mypy passaram na 2.0.55). Assim o ambiente local é igual ao do contêiner.
- **DAG fina, imports dentro da tarefa** — o dag-processor relê o arquivo a cada 30 s; importar pandas/SQLAlchemy no topo deixaria cada leitura lenta. A lógica (`collect_candles`) é a mesma do `coletar`.
- **Agendamento `15 0 * * *` (00:15 UTC)** — o candle diário fecha às 00:00 UTC. No Airflow 3 um cron usa por padrão o `CronTriggerTimetable`: a data lógica é o próprio horário agendado (`data_interval_start == data_interval_end`), diferente do Airflow 2, em que era o início do intervalo. `catchup=False` (já é o padrão na 3.x).
- **Retries: 3, começando em 5 min, `retry_exponential_backoff=2.0`** — na 3.4 esse parâmetro é um multiplicador (era `True/False` no Airflow 2); 2.0 dá 5, 10 e 20 min, o suficiente para uma instabilidade curta da API.
- **30 dias por coleta** — cobre dias em que a coleta falhou sem precisar de backfill. A bronze guarda cada resposta como um evento imutável (repetir a DAG acrescenta uma resposta); quem não pode duplicar é a silver, que já deduplica por ativo + timestamp.

## Airflow: DAGs completas (etapa 10)

- **Alerta de regime na `daily_pipeline`, não no `intraday_refresh`** (decisão do autor, 2026-11-17) — o regime vem do candle diário e só muda após 5 dias seguidos; recalculá-lo a cada hora repetiria o mesmo valor, e usar o candle do dia em andamento seria fingir precisão.
- **O que é "mudança nova"** — antes de recalcular, o `process_gold` lê o último dia que o gold já tinha; só trocas posteriores a ele viram alerta. Reexecutar o mesmo dia não repete a mensagem; depois de dias sem coleta, todas as trocas do período chegam; a primeira carga (gold vazio) não alerta o histórico inteiro. Alternativa descartada: tabela de "alertas enviados" (mais uma tabela para o mesmo resultado).
- **Mapeamento por ativo só na coleta e na silver** — o gold precisa do BTC para a correlação e leva ~1 s para os 3 ativos, então é uma tarefa só. Cada etapa mapeada espera todas as instâncias da anterior, o que garante que o gold veja a silver do BTC atualizada.
- **`max_active_tis_per_dagrun=1` na coleta** — as 3 coletas rodam uma por vez (limite de 1 req/s da API); a silver, que só usa o banco, roda em paralelo.
- **Lista de ativos numa tarefa (`list_symbols`)** — o YAML é lido na execução, não a cada leitura do arquivo pelo dag-processor; é isso que torna o mapeamento "dinâmico".
- **Alerta numa tarefa separada do gold** — se o Telegram falhar, o retry não recalcula o gold. O gold devolve só textos (XCom pequeno), nunca DataFrames.
- **Callback de falha em `interfaces/airflow_callbacks.py`, sem importar o Airflow** — recebe o contexto como dicionário, então é testável sem o Airflow. Nunca levanta exceção (um erro no callback só aparece no log do dag-processor e esconderia a falha original).
- **Telegram com `httpx` direto (só `sendMessage`)** — já é dependência; o `python-telegram-bot` entra na etapa 12, para o bot. O token faz parte da URL, então os erros são reescritos sem a mensagem original do httpx. Sem token, o alerta vai para o log.
- **`daily_report` agendada pelo Asset do gold, não por horário** — roda logo depois de cada gold bem-sucedido; se a pipeline atrasar ou falhar, a planilha não sai com dados velhos. Identificador `x-crypto-analyzer://gold` (o prefixo `x-` é o indicado pela documentação para nomes próprios) definido uma vez em `interfaces/airflow_callbacks.py`, sem importar o Airflow. Na 3.4 o primeiro argumento posicional de `Asset` é `name`; por isso `Asset(name=..., uri=...)`.
- **Planilha não é enviada ao Telegram (por enquanto)** — o envio de arquivo é "opcional" no CLAUDE.md e não poderia ser verificado sem bot; o `/planilha` do bot (etapa 12) cobre isso.
- **`bronze_ingestion` removida** — era o "primeiro contato" da etapa 9; a `daily_pipeline` faz a mesma coleta e mais.
- **Airflow instalado no grupo `airflow` do `uv` (padrão junto com `dev`)** — o teste de integridade usa o `DagBag` de verdade, na mesma versão da imagem (3.4.0). O `conftest.py` aponta o `AIRFLOW_HOME` para uma pasta temporária: importar o Airflow cria `~/airflow` sozinho.

## Idioma

- **Comentários e docstrings em português; nomes de código e commits em inglês** — o projeto é de estudo e os comentários servem de explicação para o autor; o inglês nos nomes e commits mantém o padrão do mercado e do portfólio.

## Organização do repositório

- **Saída das planilhas em `output/`** — evita confusão com o pacote `src/crypto_analyzer/reports/`, que é código.
- **Nome do pacote `crypto-analyzer`** (com "z") — a pasta local `crypto-analyser` tem grafia diferente e não foi renomeada.
- **Nenhum push automático** — publicar no GitHub é decisão do autor a cada vez.

## Pendentes (ver CLAUDE.md, "Decisões pendentes")

Definição de "dia" (UTC ou BRT), janela do percentil de regime, amostra mínima do backtest, histerese, frequência do `intraday_refresh`, limite de "dado velho".
