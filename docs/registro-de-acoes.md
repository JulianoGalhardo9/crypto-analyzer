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

### Etapa 3 — Silver e qualidade, PR B: persistência e execução real
- Migration `0002` (gerada, **lida antes de aplicar** e aplicada): `silver_candles` (PK `symbol, resolution, ts`; preços `Numeric(24,8)`; FK para a bronze) e `quality_issues`.
- `infra/repositories.py`: `load_bronze_responses`, `upsert_silver_candles` (`INSERT ... ON CONFLICT DO UPDATE`) e `replace_quality_issues`.
- `pipeline/process.py`: `process_silver`, uma transação por par.
- CLI: `crypto-analyzer processar`.
- 34 testes passando (4 de integração novos: gravação com decimais exatos, idempotência, atualização do candle aberto por uma coleta mais nova, par sem dados).
- **Execução real (2026-10-29), medida no banco:**

| Par | Candles na silver | Parciais | Avisos (outlier, `info`) |
|---|---|---|---|
| BTC-BRL | 4.888 | 1 | 13 |
| ETH-BRL | 2.879 | 1 | 2 |
| SOL-BRL | 1.796 | 1 | 1 |

- **Idempotência verificada:** rodei `processar` duas vezes; o total ficou em 9.563 candles e 16 avisos nas duas.
- Nenhum buraco, preço inválido ou dado velho nos dados reais.
- **Etapa 3 concluída.** Ainda não feito: candles horários (não coletados) e a etapa 4 (indicadores).

### Etapa 4 — Indicadores, PR 1: médias móveis e RSI
- `pandas-ta` **não instala**: depende de `numba==0.61.2`, que exige `numpy<2.3`, e o projeto usa pandas 3 (numpy >= 2.3.3). Usei o fork mantido **`pandas-ta-classic`** (0.9.0), só como dependência de desenvolvimento, para ser o gabarito dos testes.
- `core/indicators.py`: `sma`, `ema` e `rsi` (Wilder) como funções puras sobre `pd.Series`, sem loops.
- **Medido antes de escrever:** a SMA do pandas bate exatamente com o gabarito; a EMA e o RSI com a semente "primeiro preço" divergiam no começo (diferença de 17 pontos no RSI e ainda 0,03 depois de 100 candles). O gabarito inicia a média com a SMA dos primeiros N valores (convenção clássica de Wilder); adotei a mesma e passou a bater exatamente.
- 21 testes novos: comparação com o gabarito (tolerância 1e-9, várias janelas), valores calculados à mão, propriedades (RSI sempre entre 0 e 100; 100 só com altas; NaN com preço parado), série curta e **ausência de look-ahead** (alterar o futuro não muda o que já foi calculado). Total: 55 testes.
- **Ainda não feito:** MACD, ATR, Bollinger e correlação (próximos PRs da etapa 4); persistência dos indicadores é da etapa 6.

### Etapa 4 — Indicadores, PR 2: MACD e ATR
- `core/indicators.py`: `macd` (colunas `macd`, `signal`, `histogram`), `true_range` e `atr` (Wilder), puras e sem loops.
- **Medido antes de escrever:** o MACD com EMAs semeadas por SMA já batia com o gabarito (diferença ~1e-14). No ATR havia diferença de ~0,03: o gabarito deixa o *true range* do **primeiro candle vazio** (não há fechamento anterior), e o ATR começa um candle depois. Adotei isso (mesma convenção da TA-Lib) em vez de usar `máxima - mínima` no primeiro candle.
- 13 testes novos (total 68): comparação com o gabarito em várias janelas, true range e ATR calculados à mão (incluindo um gap de alta), aquecimento do MACD (25 e 33 NaN), histograma = macd - signal, MACD zero com preço constante e positivo em tendência de alta, ATR nunca negativo e sem look-ahead. Um teste meu falhou por usar `.all()` num DataFrame; corrigido.
- **Validação em dados reais (só leitura, candles fechados da silver, 1d):** comparei SMA(200), EMA(50), RSI(14), MACD e ATR(14) com o gabarito em BTC (4.887 candles), ETH (2.878) e SOL (1.795). Diferença máxima: 0 em SMA, EMA e ATR; ≤ 2,8e-14 no RSI; ≤ 4,7e-10 no MACD (em preços de até R$ 435 mil).
- **Ainda não feito:** Bandas de Bollinger e correlação com o BTC (próximo PR). Os indicadores continuam sem persistência (etapa 6).

### Etapa 4 — Indicadores, PR 3: Bollinger e correlação (etapa 4 concluída)
- `core/indicators.py`: `bollinger` (`lower`, `middle`, `upper`), `log_returns` e `rolling_correlation`.
- **Medido antes de escrever:** o gabarito usa desvio padrão **populacional** (`ddof=0`, diferença de 1,9e-12); o padrão do pandas é o amostral (`ddof=1`), que erraria em 0,3. Passo `ddof=0` explicitamente.
- A correlação não tem gabarito na `pandas-ta`; validei contra `numpy.corrcoef` **em cada janela** e com casos conhecidos (+1 para os mesmos movimentos, -1 para opostos, datas em comum, sem look-ahead).
- 11 testes novos (total 79). O mypy reclamou de `Any` vindo do `np.log` (corrigido com tipo explícito); a primeira hipótese que testei, a de `rolling().corr`, estava errada.
- **Em dados reais (só leitura, candles fechados da silver, 1d):**
  - Bollinger(20, 2) vs gabarito: diferença máxima 3,0e-7 (BTC, preços de ~R$ 400 mil), 2,5e-9 (ETH), 8,0e-11 (SOL).
  - Correlação de 90 dias com o BTC (iguala `numpy` na última janela): ETH, 2.788 pontos, mín 0,54, mediana 0,82, máx 0,95; SOL, 1.705 pontos, mín 0,50, mediana 0,74, máx 0,93.
- **Consequência para a etapa 7:** como a correlação com o BTC é quase sempre alta, um corte fixo rotularia quase todo dia igual. O rótulo "anda junto" deve vir de percentil do histórico do próprio ativo (regra do CLAUDE.md), não de um número fixo.
- **Etapa 4 concluída:** SMA, EMA, RSI, MACD, ATR, Bollinger e correlação. Ainda sem persistência (etapa 6).

### Etapa 5 — Volatilidade e regimes (funções puras e configuração)
- O autor delegou as decisões pendentes ("faça como achar melhor"); decidi **medindo os dados reais** (só leitura, candles fechados da silver, 1d).
- **Janela do percentil.** Distribuição calma/normal/alta com cortes 33/66:

| Variante | BTC | ETH | SOL |
|---|---|---|---|
| crescente (todo o passado) | 46/34/20 | 41/33/25 | **57**/28/15 |
| móvel 730 dias | 40/33/27 | 36/30/34 | 46/35/19 |
| móvel 1095 dias | 42/33/25 | 36/32/32 | 53/32/15 |
| **móvel 365 dias** | 41/29/31 | 39/29/32 | 41/34/25 |

  O percentil crescente inclina para "calma" (a volatilidade caiu com a maturidade do mercado). A janela de 365 dias é a mais equilibrada e a que menos varia de ano para ano. Escolhida: **365 dias, mínimo de 180 valores**.
- **Histerese.** Trocas de regime por ano (confirmação de N dias seguidos):

| N | BTC | ETH | SOL | duração mediana de um regime |
|---|---|---|---|---|
| 1 (sem histerese) | 22,3 | 24,8 | 24,2 | 5 a 8 dias |
| 3 | 14,0 | 13,5 | 14,7 | 18 a 20 dias |
| **5** | 11,9 | 10,0 | 10,8 | 22 a 30 dias |
| 7 | 10,0 | 8,9 | 10,4 | 28 a 32 dias |
| 10 | 7,8 | 8,2 | 9,4 | 31 a 37 dias |

  Escolhido **N = 5**: cerca de uma troca por mês por ativo; acima disso o ganho é pequeno e o atraso do sinal cresce.
- `config/regimes.yaml` (janelas, cortes 33/66, histerese), `RegimeConfig`/`load_regime_config`, `core/models.py` (`Regime`), `core/regime.py`: `realized_volatility`, `volatility_percentile`, `classify`, `apply_hysteresis` e `compute_regimes`.
- 15 testes novos (total 94): contas à mão, fronteiras, histerese (ruído solto descartado, contagem reinicia ao trocar de candidato), espera pelo histórico mínimo, e **sem look-ahead**.
- **Erro de teste meu, instrutivo:** assumi que um período calmo seria todo "calma"; mas o percentil é relativo ao histórico, então num mercado igualmente estável os dias se espalham pelos 3 rótulos. Isso é por design e agora está num teste. Em surtos longos o percentil também desce um pouco (97 → 77) mas fica acima do corte de "alta".
- **Resultado real em 2026-10-28** (config oficial): BTC, ETH e SOL em **calma** (percentis 31, 15 e 18; o BTC está perto da fronteira de 33). Trocas de regime nos últimos 365 dias: BTC 15, ETH 10, SOL 13. Distribuição histórica BTC 41/26/33, ETH 39/28/34, SOL 40/34/25 (calma/normal/alta).
- **Não feito:** candles horários (a volatilidade usa só os diários; horários ficam para a etapa 10, onde o `intraday_refresh` precisa), frequências de atualização por regime no YAML (também etapa 10, para não ter configuração sem uso) e persistência (etapa 6).

### Etapa 6 — Gold e modelagem
- Migration `0003` (gerada, lida antes de aplicar e aplicada): `dim_ativo` (id, símbolo único, base, cotação, nome), `fact_indicador` (14 indicadores, formato largo) e `fact_regime` (volatilidade, percentil, regime cru e com histerese). Chave composta `(ativo_id, ts)` nas duas fatos.
- `config/assets.yaml` agora tem o nome de cada ativo e o `benchmark` (BTC); `AssetsConfig` ganhou `benchmark_symbol`.
- `pipeline/gold.py` (puro): `compute_indicators` e `compute_gold`. `pipeline/process_gold.py`: lê os candles fechados da silver, calcula, grava com upsert numa transação. `infra/repositories.py`: o upsert foi extraído para `_upsert_frame` (silver e gold usam o mesmo código); novas `load_closed_candles`, `upsert_ativos`, `upsert_gold`.
- CLI: `crypto-analyzer calcular`.
- **Bug pego pelos testes antes de gravar qualquer dado:** `compute_regimes` devolve a coluna `percentile`, mas a tabela usa `volatility_percentile`. Corrigido com um `rename` na montagem do gold. Um segundo teste falhou por erro meu (`between` antes de `dropna`).
- 103 testes passando (9 novos de integração e unitários para o gold, incluindo: só candles fechados, NaN vira NULL, o BTC não tem correlação consigo mesmo, idempotência e erro claro quando falta a silver).
- **Execução real (2026-10-29), medida no banco:**

| Par | Dias no gold | Primeiro | Último | Com SMA 200 | Com correlação |
|---|---|---|---|---|---|
| BTC-BRL | 4.887 | 2013-06-12 | 2026-10-28 | 4.688 | 0 (é o benchmark) |
| ETH-BRL | 2.878 | 2018-12-12 | 2026-10-28 | 2.679 | 2.788 |
| SOL-BRL | 1.795 | 2021-11-29 | 2026-10-28 | 1.596 | 1.705 |

- **Idempotência verificada:** `calcular` rodado 2x; 3 ativos, 9.560 linhas de indicadores e 9.560 de regimes nas duas vezes.
- **Conferência cruzada** com os scripts independentes das etapas 4 e 5, no último candle fechado (2026-10-28): RSI 60,1 / 51,2 / 51,2, ATR 13.811,46 / 510,82 / 26,45, correlação ETH 0,883 e SOL 0,828, percentis 31 / 15 / 18, regime `calm` nos 3. Tudo igual.
- **Etapa 6 concluída.** `fact_backtest` fica para a etapa 11. Candles horários seguem não coletados.

### Etapa 7 — Explainer e análise, PR A: peças puras
- Decisões tomadas por delegação do autor (registradas no CLAUDE.md): **"últimas 24h" = último dia fechado** (sem candles horários, uma janela móvel de 24h seria fingir precisão) e **dado velho** reaproveita `max_age_hours` de `config/quality.yaml` (48 h).
- `core/models.py`: `Analysis` (todos os números de um ativo), `Trend`, `CorrelationLevel`. `core/trend.py`: `classify_trend` (preço > média 50 > média 200 = subindo; o inverso = caindo; qualquer outra ordem = de lado; sem média 200 = sem conclusão). `core/regime.py`: `latest_percentile`. `core/indicators.py`: `recent_extremes` (mínima e máxima recentes como suporte e resistência, definição simples de canal de Donchian).
- `core/explainer.py`: `explain` (resposta padrão: 4 linhas + explicação), `explain_details` (números técnicos) e `unsupported_asset_message`. Números em formato brasileiro (`R$ 435.668,00`, `+3,2%`). RSI só é mencionado nos extremos (70 e 30, convenção de Wilder) e sempre explicado.
- `pipeline/analysis.py`: `assemble_analysis` junta candles e gold no objeto `Analysis` (puro, sem banco).
- **A frase sobre "variações comuns" vem dos dados:** mediana e percentil 90 do movimento diário no último ano, não de um texto fixo.
- **Correlação com o BTC:** como medimos que é sempre alta (mínimo 0,50), o texto diz o fato ("anda junto") **e** se hoje está mais ou menos colada que o normal, por percentil do próprio histórico (mesmos cortes 33/66).
- 101 testes novos (total 198): as regras do CLAUDE.md valem em **todas as 64 combinações** de tendência, agitação e correlação (nunca "compre/venda", nunca previsão, sempre o aviso, no máximo 4 linhas de informação, nenhum NaN vazando); histórico insuficiente e dado velho avisados; BTC sem linha de correlação; números calculados à mão.
- **Dois erros meus nos testes, corrigidos:** o teste de "dado velho" usava candles sintéticos que já terminavam 15 dias antes do `now`, então até o caso "fresco" era velho; e um `product` do itertools precisava virar lista para o pytest.
- **Ainda não feito (PR B):** ler o gold do banco, o comando `analisar` e a execução real. O backtest aparece como "ainda não disponível" nos detalhes até a etapa 11.

### Etapa 7 — Explainer e análise, PR B: banco, comando `analisar` e execução real (etapa 7 concluída)
- `infra/repositories.py`: `load_fact_frame` e `load_last_candle_ts`. `pipeline/build_analysis.py`: `build_analysis` (lê candles e gold e devolve o `Analysis`) e `NoDataError`. CLI: `crypto-analyzer analisar <ATIVO> [--detalhes]`; ativo fora de BTC, ETH e SOL recebe a mensagem amigável (código de saída 1) antes de qualquer acesso ao banco.
- **Execução real em 2026-11-03.** Os dados eram da coleta de 29/10, então o aviso de dado velho apareceu de verdade ("6 dias atrás"). Respostas reais (candles até 28/10): BTC em alta e calmo; ETH e SOL de lado e calmos; os 3 "andam junto" do BTC.
- **A API do Mercado Bitcoin estava fora do ar** (HTTP 302 para "Página indisponível", em todos os endpoints, também com `curl`). Nada foi gravado pela metade (conferi a bronze: 1 resposta por ativo, de 29/10). **A atualização dos dados não pôde ser feita**; fica pendente até a API voltar.
- **Defeito meu encontrado nessa falha:** o erro chegava ao usuário como um traceback com HTML dentro. Agora o cliente diz "a API redirecionou em vez de responder (provavelmente fora do ar ou em manutenção)" e o `coletar` mostra uma mensagem curta, mantém o que já estava gravado e sai com código 1.
- **BUG SÉRIO, encontrado lendo as respostas reais:** a silver marcava `is_partial` comparando com a hora do **processamento**. O candle de 29/10 foi coletado às 21:05 UTC do próprio dia (incompleto), mas, ao reprocessar em 03/11, passou a valer como fechado, e o RSI, a volatilidade e o regime "de ontem" eram calculados sobre um retrato parcial. **Correção:** o candle só é fechado se a coleta que o trouxe aconteceu depois do fim dele (`build_silver` não recebe mais `now`). Tem testes que reproduzem o caso real e o caso em que uma coleta posterior o completa. O gold agora apaga as linhas posteriores ao último candle fechado.
- **Reparo dos dados reais:** reprocessei a silver e recalculei o gold. Verificado no banco: o candle de 29/10 voltou a `is_partial = true` nos 3 ativos e o gold voltou a 4.887, 2.878 e 1.795 dias (os mesmos números da etapa 6), terminando em 28/10.
- **Concordância de gênero:** o texto dizia "para a BTC" e "bem calma" para o BTC. `config/assets.yaml` ganhou `article` (o BTC, o ETH, a SOL); o texto usa o artigo e concorda os adjetivos ("bem calmo", "agitado", "do ETH", "da SOL").
- 213 testes passando (15 novos nesta parte): montagem a partir do banco (candle parcial fora, mas contado na idade do dado), BTC sem correlação, dado velho com "7 dias atrás", erro sem dados, ativo fora do escopo, API fora do ar no CLI, regra do candle parcial, limpeza do gold e concordância de gênero.
- **Pendente:** atualizar os dados (`coletar`, `processar`, `calcular`) quando a API voltar; o backtest aparece como "ainda não disponível" até a etapa 11.

### Etapa 8 — Planilha Excel, PR A: os DataFrames de cada aba
- Dependências: `xlsxwriter` (escrita) e `openpyxl` (só dev, para os testes lerem o arquivo). `config/report.yaml` (`window_days: 365`) e `load_report_config()`.
- `reports/frames.py` (puro): `ReportData` e um construtor por aba: `summary_frame` (Resumo), `candles_frame`, `indicators_frame`, `regimes_frame`, `regime_changes_frame` (Mudanças), `quality_frame` (Qualidade) e `about_frame` (Sobre).
- **Formato longo** (coluna `Ativo` + uma linha por dia, ordenado por ativo e data) para filtrar, ordenar e criar tabelas dinâmicas. Cabeçalhos e rótulos em português ("Calma", "Subindo"...). Datas são datas de verdade, **sem fuso** (o Excel não aceita fuso; a aba Sobre diz que são dias em UTC).
- 17 testes novos (total 230): janela de 365 dias por ativo e ordem, datas sem fuso, colunas numéricas como `float64`, só os vazios esperados (correlação do BTC), mudanças de regime calculadas à mão (datas e dias de duração), tradução, resumo com "Sem histórico", Qualidade vazia e Sobre com aviso de dado velho.
- **Dois erros meus nos testes:** a SOL sintética tinha 500 dias, menos que 365 + 199 do aquecimento da média de 200 dias, o que deixava vazios na janela (os dados reais têm 1.795 dias); e uma asserção terminava em `or True`, que nunca falha. Corrigidos.
- **Ainda não feito (PR B):** o arquivo `.xlsx` em si (formatação, cores, gráficos), a leitura do banco e o comando `planilha`. A aba `Backtest` entra na etapa 11.

### Etapa 8 — Planilha Excel, PR B: o arquivo `.xlsx` e o comando `planilha` (etapa 8 concluída)
- PR #16. Commits `48b5272` (dados sintéticos compartilhados entre os testes da planilha), `499ab04` (`reports/excel.py`) e `47931b3` (leitura do banco e comando).
- `reports/excel.py`: `write_report` e `default_report_path` (`output/crypto_report_AAAA-MM-DD.xlsx`, data em UTC). Abas `Resumo`, `Candles`, `Indicadores`, `Regimes`, `Mudanças`, `Qualidade`, `Gráficos` e `Sobre`. Cabeçalho congelado (mais as colunas Ativo e Data nas abas diárias), filtros, larguras, formatos R$ / % / data, cores por regime (verde, amarelo, vermelho) e por sinal (+ verde, − vermelho), e 2 gráficos nativos por ativo. Sem macros e sem links externos.
- `pipeline/build_report.py`: `build_report_data` lê candles, gold e os problemas de qualidade **diários** do banco e reaproveita `build_analysis` para o `Resumo`. `infra/repositories.py`: `load_quality_issues`. CLI: `crypto-analyzer planilha [--pasta output]`; sem gold, mostra o que rodar e não grava arquivo.
- **Erro meu nos dados de teste, pego pelo teste do `.xlsx`:** o BTC e a SOL sintéticos começavam no mesmo dia e tinham tamanhos diferentes, então a SOL "continuava" 100 dias depois do BTC acabar e a correlação ficava vazia. Nos dados reais é o contrário (começam em datas diferentes e terminam no mesmo dia); os sintéticos agora terminam juntos.
- 16 testes novos (total 246): o `.xlsx` é aberto com `openpyxl` e conferido (abas e ordem, cabeçalhos e número de linhas iguais aos frames, datas como datas, preços como números, formatos R$/%/data, nenhum vazio fora da correlação do BTC, painéis congelados, filtros, formatação condicional, 6 gráficos, nada de macro ou link externo, aviso na aba Sobre); integração com o Postgres (leitura do banco, só qualidade diária, candle parcial fora, erro sem gold); CLI (nome do arquivo com data e mensagem sem dados).
- **Execução real em 2026-11-17 (UTC):** `planilha` gerou `crypto_report_2026-11-17.xlsx` (379 KB, ~1,4 s). Conferido com `openpyxl`: 1.095 linhas por aba diária (365 por ativo, de 29/10/2025 a 28/10/2026), 275 mudanças de regime no histórico (BTC 150, ETH 77, SOL 48), 19 problemas de qualidade, 6 gráficos. Resumo igual ao das etapas 6 e 7 (BTC R$ 435.668,00, RSI 60,1 / 51,2 / 51,2, percentis 31 / 15 / 18, correlações 0,883 e 0,828, tudo "Calma"). A aba Sobre avisa "o candle mais recente tem 19 dias".
- **API bloqueada de novo, por outro motivo:** `coletar --candles 30` recebeu **HTTP 403 do Cloudflare** ("Attention Required!") em todos os endpoints, também com `curl`. Parece bloqueio do IP/rede, não manutenção. Não tentei contornar. A planilha real usa os dados de 29/10.
- **Não verificado:** a aparência dos gráficos e das cores **num Excel de verdade** (não há Excel nem LibreOffice nesta máquina; conferi só a estrutura do arquivo). A aba `Qualidade` mostra a idade do dado medida no último `processar` (141,8 h, em 03/11), não a de hoje; e os detalhes das checagens usam ponto decimal (`+32.5%`), diferente do resto em formato brasileiro.

### Etapa 9 — Airflow, primeiro contato
- PR #17. Commits `f5e47d5` (SQLAlchemy 2.0.x, igual ao Airflow), `4624884` (`collect_candles`, usado pelo CLI e pela DAG), `ec48826` (Airflow no Docker Compose) e `e9dad1b` (DAG `bronze_ingestion`).
- **Versão:** Airflow **3.4.0** (estável mais recente, lançada em 06/11/2026), imagem `apache/airflow:3.4.0-python3.12`. Li a documentação dessa versão antes de escrever qualquer coisa: guia do Docker Compose, tutorial do TaskFlow, timetables, execuções de DAG, variáveis de contexto, LocalExecutor e referência de configuração. Três diferenças em relação ao Airflow 2 apareceram no código: imports de `airflow.sdk`; cron agendado = `CronTriggerTimetable` (data lógica = horário agendado); `retry_exponential_backoff` agora é multiplicador (`2.0`), não `True`.
- **Compatibilidade conferida antes de construir a imagem:** as constraints do Airflow 3.4.0 (Python 3.12) fixam exatamente as versões que o projeto usa (pandas 3.1.0, alembic 1.20.1, httpx 0.28.1, psycopg 3.3.6, pydantic-settings 2.16.2, typer 0.27.3), exceto o SQLAlchemy (2.0.55 contra o nosso `>=2.1.6`). Rodei a suíte inteira e o mypy com o 2.0.55: tudo passou; o requisito virou `>=2.0.50,<2.1`.
- **Subido e verificado (2026-11-17):** `docker compose --profile airflow up -d` → `airflow-init` saiu com código 0 (banco de metadados migrado, usuário criado); api-server, scheduler, dag-processor e os dois Postgres `healthy`. Memória em repouso medida com `docker stats`: api-server 267 MiB, scheduler 233, dag-processor 208, Postgres do Airflow 48, Postgres do projeto 69 (≈ 825 MiB). Interface em `http://localhost:8080` (HTTP 200) e API REST autenticando com `airflow/airflow`.
- **DAG:** `airflow dags list-import-errors` sem erros; `bronze_ingestion` listada, pausada, tarefa `ingest`, agendamento `15 0 * * *`. Dentro do contêiner, o pacote acha os YAMLs e lê o banco do projeto (3 respostas na bronze, última de 29/10).
- **Execução com `airflow dags test`:** a API continua com **HTTP 403 do Cloudflare** (também de dentro do contêiner). Tentativa 1 às 00:14:08 falhou e ficou `up_for_retry`; tentativa 2 às 00:19:24, **5 min depois**, falhou de novo. Interrompi o teste a pedido do autor antes da tentativa 3 e marquei a execução como `failed` pela API REST (ao sair, o `dags test` a tinha marcado como `success`, o que seria enganoso). Nada foi gravado na bronze.
- **Não verificado:** uma coleta com sucesso pelo Airflow (API bloqueada); a espera crescente das tentativas 3 e 4 (10 e 20 min); uma execução disparada pelo scheduler (a DAG ficou pausada); o teste de integridade com `DagBag` no CI (etapa 10). O CI não instala o Airflow.

### Etapa 10 — DAGs completas, PR A: `daily_pipeline`, alertas e integridade das DAGs
- Decisões do autor (2026-11-17, registradas no CLAUDE.md): `intraday_refresh` checa de hora em hora (aos 5 min) com intervalos por regime de 1h/3h/6h; **o alerta de mudança de regime sai da `daily_pipeline`**; Telegram com fakes até existir um bot.
- PR #18. Commits `969e26c`, `e9f786a`, `63e9534`, `9f0628a`, `1d04e2d`, `5bde5d3`: detecção de mudança de regime + texto do alerta + envio ao Telegram; correção do log do Alembic; `process_gold` devolvendo as mudanças novas; `session_factory_from_settings`; callback de falha; DAG `daily_pipeline` + testes de integridade.
- `core/regime.py`: `regime_changes_after` (só trocas depois do último dia já avaliado). `core/explainer.py`: `regime_change_message`. `infra/telegram.py`: `send_message` e `notify` (sem token = só log; erros nunca repetem o token). `pipeline/alerts.py`: `regime_alert_messages`. `interfaces/airflow_callbacks.py`: `notify_task_failure`.
- **DAG `daily_pipeline`** (substitui a `bronze_ingestion`): `list_symbols` → `ingest` mapeada (uma por vez, `max_active_tis_per_dagrun=1`) → `silver` mapeada → `gold` → `alert_regime_changes`. Retries 3× (5/10/20 min), timeout de 10 min, callback de falha em todas as tarefas.
- **Defeito encontrado por um teste novo:** o `migrations/env.py` chamava `fileConfig` com o padrão `disable_existing_loggers=True`, o que desligava os loggers de `pipeline/` e `infra/` em qualquer processo que rodasse as migrations (nos testes, os de integração rodam antes). Corrigido.
- **Mudanças do Airflow 3.4 encontradas lendo a API instalada:** `DagBag` saiu de `airflow.models` para `airflow.dag_processing.dagbag` e não aceita mais `include_examples` (vem da configuração).
- **Testes:** 23 novos (total 269): mudanças de regime à mão (só as novas, várias de uma vez, repetir não realerta, primeira carga não alerta, "sem histórico" não conta), texto do alerta, Telegram com `httpx.MockTransport` (URL, corte em 4096, 401 e erro de rede sem vazar o token, sem configuração vai para o log), callback (mensagem, índice do mapeamento, nunca levanta), integração do `process_gold` (apagando 120 dias do gold, só as trocas desses dias voltam; repetir não realerta), e **integridade das DAGs com `DagBag`** (sem erros de importação, retries e callback em todas as tarefas, ordem das etapas, coleta uma por vez). O `~/airflow` não é criado pelos testes.
- **Verificado no Airflow rodando (2026-11-17):** `list-import-errors` vazio; `daily_pipeline` com as 5 tarefas. `airflow tasks test daily_pipeline gold` rodou de verdade (3 ativos calculados, nenhuma mudança nova: os dados continuam até 28/10). `airflow dags test daily_pipeline`: `list_symbols` ok, `ingest` expandida em 3 instâncias (`map_index` 0, 1 e 2) que rodaram **uma depois da outra** (início da 2ª às 23,255 s, depois do fim da 1ª às 23,222 s) e falharam com **HTTP 403** (API bloqueada para este IP). Interrompi o teste; ao morrer, o `dags test` marcou a execução como `success`, e eu a corrigi para `failed` pela API REST.
- **Não verificado:** silver, gold e alerta rodando *dentro* de uma execução completa (dependem da coleta, bloqueada); a silver mapeada isolada não roda com `tasks test` (falta o XCom de `list_symbols`, esperado); envio real ao Telegram (sem bot); o callback de falha disparando no Airflow (só acontece após a última tentativa, e o teste foi interrompido antes). A `bronze_ingestion` continua listada no banco de metadados até o Airflow desativá-la.

### Etapa 10 — DAGs completas, PR B: `daily_report` por Asset
- Commit `45ee26c`. A tarefa `gold` da `daily_pipeline` declara o Asset `crypto_gold` (`x-crypto-analyzer://gold`) como saída; a DAG `daily_report` tem `schedule=[GOLD]` e gera a planilha em `output/` (montada no contêiner; `OUTPUT_DIR` no compose, `Settings.output_dir`).
- **Erro pego pelo teste de integridade antes de subir:** `Asset(uri, name=...)` falha na 3.4 (o 1º argumento posicional é `name`). Corrigido para argumentos nomeados.
- 1 teste novo (total 270): a `gold` emite o Asset e a `daily_report` é disparada por ele.
- **Verificado de ponta a ponta no Airflow (2026-11-17):** contêineres recriados (todos `healthy`), as duas DAGs sem erros de importação. Despausei a `daily_report` e criei um evento do Asset pela API REST (`POST /api/v2/assets/events`, o mesmo efeito da tarefa `gold`); o scheduler criou sozinho a execução `asset_triggered__2026-11-17T00:44:36…`, que terminou com `success` e regravou `output/crypto_report_2026-11-17.xlsx` (8 abas, 3 ativos, 1.095 linhas de candles, "Gerado em" 00:44:40 UTC). Depois **pausei de novo** a `daily_report` (estado padrão).
- **Não verificado:** o evento emitido pela própria tarefa `gold` dentro de uma execução completa da `daily_pipeline` (a coleta continua bloqueada pelo 403).

## Pendências abertas
- Etapa 2: persistir a bronze (SQLAlchemy + Alembic + tabela com JSONB) e coletar BTC, ETH e SOL.
- Quando a API do Mercado Bitcoin liberar o acesso (403 do Cloudflare em 17/11): `coletar --candles 30`, `processar` e `calcular` (ou despausar a `daily_pipeline`) para atualizar os dados (a última coleta é de 29/10).
- Abrir a planilha num Excel/LibreOffice e conferir gráficos e cores.
