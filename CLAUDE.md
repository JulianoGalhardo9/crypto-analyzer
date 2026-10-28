# CLAUDE.md

Contexto do projeto para o Claude Code. Leia este arquivo inteiro antes de qualquer tarefa.

## O que é este projeto

**crypto-analyzer** (nome provisório) é uma plataforma de dados em Python que responde a uma pergunta simples:

> "Me fala sobre a SOL."

O usuário pede a análise de uma criptomoeda e recebe, por padrão, uma **resposta curta e fácil de entender**. Por trás existe um pipeline de dados completo: coleta de uma API, camadas bronze/silver/gold, modelagem, indicadores técnicos, **relatório em planilha Excel gerado com pandas** e **orquestração com Apache Airflow**. Quem quiser mais profundidade pede `--detalhes` e vê os números técnicos.

Este projeto é a evolução do antigo CryptoArbitrage (.NET + Angular), que apenas monitorava spreads. Aqui o foco muda de "monitor" para **plataforma de dados com uma funcionalidade clara**.

### Objetivos de aprendizado do autor

- Pandas aplicado a dados reais (limpeza, séries temporais, indicadores, exportação)
- Apache Airflow na prática (DAGs, agendamento, retries, task mapping, branching, alertas)
- Engenharia de software aplicada a dados (testes, camadas, CI, Docker)

## Escopo fechado (decisões do autor)

- **Apenas 3 ativos:** BTC, ETH e SOL, cotados em BRL
- **Apenas 1 fonte de dados:** Mercado Bitcoin (API pública v4, endpoints públicos de dados de mercado)
- **Sem comparação entre exchanges** e sem divergência de preço
- Ativos fora dessa lista recebem uma mensagem amigável ("por enquanto acompanho apenas BTC, ETH e SOL"), sem ingestão sob demanda

Não expandir esse escopo sem o autor pedir. Mais ativos ou exchanges são evoluções futuras, não parte da v1.

## Entregas ao usuário

1. **Resposta simples** no CLI e no bot de Telegram
2. **Planilha Excel** com a análise completa (gerada sob demanda e automaticamente por uma DAG)

### Resposta padrão (simples)

```
> analisar SOL

SOL (Solana) está em alta, mas agitada.

📈 Tendência:    subindo nas últimas semanas
🌊 Agitação:     ALTA (o preço está oscilando mais que o normal)
🔗 Com o BTC:    anda junto (quando o BTC cai, a SOL costuma cair também)
🕐 Últimas 24h:  +3,2%

O que isso significa:
O preço vem subindo, mas com movimentos bruscos. Em fases assim,
variações de 5% a 10% em um dia são comuns.

⚠️ Informativo, não é recomendação de investimento.
```

Os números do exemplo são ilustrativos. Os reais vêm sempre dos dados coletados.

`analisar SOL --detalhes` mostra os cálculos por trás: médias móveis, RSI, MACD, ATR, Bandas de Bollinger, percentil de volatilidade, correlações exatas, suportes/resistências e o resultado do backtest dos sinais.

### Regras da resposta simples

- Máximo de 4 a 5 linhas de informação + uma explicação curta em linguagem comum
- **Sem jargão** na resposta padrão; se um termo técnico aparecer, explicar na hora
- **Nunca** dizer "compre" ou "venda". O sistema **descreve** a situação, não manda agir
- Rótulos (calma / normal / alta) vêm de **percentis do histórico do próprio ativo**, nunca de números fixos chutados
- Sempre incluir o aviso de que é informativo e não é recomendação de investimento
- Se não há histórico suficiente para uma conclusão confiável, **dizer isso** em vez de fingir precisão
- Frases com números ("variações de 5% a 10% são comuns") **saem dos percentis reais do ativo**, nunca de texto fixo no template
- Se o último dado coletado estiver velho (acima do limite em `config/`), a resposta avisa "dados de X horas atrás"
- Para o **BTC**, a linha "Com o BTC" não se aplica e é omitida

Tradução do técnico para o simples:

| Cálculo por trás | O que o usuário vê |
|---|---|
| Médias móveis de 20/50/200 dias | Tendência: subindo, de lado ou caindo |
| Volatilidade em percentil do histórico | Agitação: calma, normal ou alta |
| RSI | "Subiu muito rápido recentemente" / "caiu muito rápido recentemente" |
| Correlação com BTC | "Anda junto com o BTC" / "se move de forma independente" |
| Variação das últimas 24h | Percentual simples |

### Planilha Excel (relatório)

Sistema de planilhas gerado com **pandas** (`pd.ExcelWriter` com engine XlsxWriter). Uma pasta de trabalho `.xlsx` com abas:

- `Resumo`: uma linha por ativo (preço em R$, variação 24h/7d/30d, tendência, regime de volatilidade, correlação com BTC)
- `Candles`: candles diários recentes
- `Indicadores`: médias, RSI, MACD, ATR, Bollinger por data
- `Regimes`: histórico de regimes e datas das mudanças
- `Backtest`: resultado dos sinais, **sempre com o número de ocorrências**
- `Qualidade`: resultado das checagens de qualidade de dados (buracos, outliers, atrasos)
- `Sobre`: data de geração, fonte dos dados, janela usada e o aviso de que não é recomendação de investimento

Requisitos de qualidade da planilha:
- Valores gravados como **números e datas reais**, nunca texto, para o usuário poder filtrar, ordenar e criar tabelas dinâmicas
- Cabeçalho congelado, filtros nas colunas, larguras ajustadas, formatos numéricos (R$, %)
- Formatação condicional (ex.: cores por regime e por variação positiva/negativa)
- Gráficos nativos do Excel via XlsxWriter (preço com médias móveis; volatilidade ao longo do tempo)
- Sem macros e sem dependência de links externos
- Nome do arquivo com data (ex.: `crypto_report_2026-10-27.xlsx`), salvo em `output/` (não confundir com o pacote `src/crypto_analyzer/reports/`, que é código)
- Gerada por `crypto-analyzer planilha` (sob demanda) e pela DAG diária; o bot pode enviá-la via `/planilha`
- Teste: abrir o `.xlsx` gerado com `openpyxl` e verificar abas, colunas, tipos e que não há células vazias onde não deveria

## O que o sistema NÃO faz

- Não executa ordens, não tem integração de trading. Usar **apenas endpoints públicos**, nenhuma chave com permissão de trading
- Não dá recomendação de investimento nem promete retorno
- Não prevê preço. Indicadores técnicos **descrevem o passado**; o sistema mostra, com backtest, o quanto cada sinal realmente funcionou nos dados
- Não usa LLM para calcular nada. (Opcional no futuro: LLM apenas para **redigir** o texto a partir de números já calculados; os números nunca vêm do LLM.)

## Funcionalidades

1. **Análise sob demanda** de BTC, ETH ou SOL via CLI e bot de Telegram (API REST opcional)
2. **Relatório em planilha Excel**, sob demanda e automático
3. **Automação baseada em volatilidade (Airflow):** o regime do ativo (calmo / normal / alta agitação) define a frequência de atualização dos dados recentes, e a **mudança de regime dispara alerta** no Telegram
4. **Validação dos indicadores (backtest simples):** ex.: "nas últimas N vezes em que o RSI passou de 70 neste ativo, o preço 7 dias depois estava em média X% acima/abaixo". Se o sinal não funciona, isso aparece (e vai para o README). Com amostra pequena, avisar
5. **Qualidade de dados:** checagem de candles faltando, preços absurdos, duplicatas e atrasos de coleta

## Arquitetura

**Monólito modular em camadas, com núcleo funcional puro** (*functional core, imperative shell*). Decisão consciente: arquitetura hexagonal completa compensa quando há várias fontes e bancos. Aqui há **uma fonte e um banco**, então mantemos só o que traz valor:

1. **Núcleo puro e testável:** indicadores, regime, backtest e texto explicativo são **funções puras** (entram Series/DataFrames ou números, saem Series/DataFrames, números ou texto), sem I/O
2. **Camadas de dados (medallion):** bronze → silver → gold
3. **Uma única interface pequena** para a fonte de dados (`MarketDataClient`), existente **só para permitir fakes nos testes**
4. **Airflow só orquestra.** A lógica vive em `core/`, `pipeline/` e `reports/` e **roda sem Airflow** (pelo CLI e pelos testes). As DAGs são finas: apenas chamam essas funções. Isso evita acoplar o código ao Airflow e deixa tudo testável

```
src/crypto_analyzer/
  core/               # PURO, sem I/O
    models.py         # Candle, Asset, Regime, Analysis
    indicators.py     # médias, RSI, MACD, ATR, Bollinger, correlação (sobre pandas Series)
    regime.py         # classificação por percentil
    backtest.py       # validação dos sinais
    explainer.py      # números -> texto simples
  pipeline/           # orquestra leitura/escrita entre camadas
    bronze.py         # ingestão bruta
    silver.py         # limpeza e padronização
    gold.py           # indicadores, regimes, backtests persistidos
    quality.py        # checagens de qualidade
  reports/
    frames.py         # monta os DataFrames de cada aba (puro)
    excel.py          # escreve o .xlsx (formatação, gráficos)
  infra/
    mercado_bitcoin.py  # cliente httpx da API v4 (implementa MarketDataClient)
    db.py               # engine/sessões SQLAlchemy
    repositories.py     # leitura/escrita das tabelas
    telegram.py         # envio de mensagens e arquivos
  interfaces/
    cli.py            # Typer + Rich
    bot.py            # Telegram
    api.py            # FastAPI (opcional)
  config.py           # pydantic-settings
dags/                 # DAGs do Airflow (finas, só chamam pipeline/ e reports/)
config/               # assets.yaml, regimes.yaml
tests/
  unit/               # core/ e reports/frames com dados sintéticos
  integration/        # banco real no Docker; API do Mercado Bitcoin sempre simulada
  dags/               # testes de integridade das DAGs
docker/
output/               # planilhas geradas (no .gitignore)
```

Princípios:
- `core/` **nunca** importa de `infra/`, `pipeline/`, `reports/`, `interfaces/` ou `dags/`
- Funções pequenas, tipadas, com nomes claros
- O `explainer` recebe os números e devolve o texto; testar com casos como "dado RSI 72 e tendência de alta, o texto deve dizer X"
- Testes **nunca** dependem da API real: usar respostas gravadas (fixtures) ou fakes

## Stack

- **Python 3.12+**, gerenciado com `uv` (`pyproject.toml`)
- **Coleta:** `httpx` (async) direto na API v4 do Mercado Bitcoin, **sem ccxt**. Retry com backoff exponencial, respeitando rate limits
- **Processamento:** **pandas** (limpeza, séries temporais, indicadores, montagem das abas)
- **Planilhas:** XlsxWriter (escrita, formatação, gráficos) e openpyxl (leitura nos testes)
- **Orquestração:** **Apache Airflow** (ver seção própria)
- **Banco do projeto:** PostgreSQL via SQLAlchemy 2.x + Alembic. Sem TimescaleDB: o volume é pequeno
- **CLI:** Typer + Rich
- **Bot:** python-telegram-bot
- **API (opcional):** FastAPI + Pydantic v2
- **Configuração:** pydantic-settings + YAML (ativos, cortes de regime, frequências por regime)
- **Qualidade:** pytest (+ cov), Ruff, mypy (+ pandas-stubs)
- **Infra:** Docker Compose, GitHub Actions (lint, tipos, testes; Postgres no CI via `services:` do workflow)
- **Logging:** módulo `logging` da biblioteca padrão, com logs estruturados mínimos (ativo, etapa, duração) nas camadas `pipeline/` e `infra/`; `core/` não loga

Indicadores (RSI, MACD, ATR, Bollinger, médias, correlação): **implementar como funções puras próprias sobre pandas**, para aprender e facilitar testes. Nos testes, validar contra valores de referência conhecidos (ex.: `pandas-ta` usada **apenas como oráculo nos testes**, não como dependência de runtime).

Pandas: usar timestamps em UTC, índices temporais, operações vetorizadas (evitar loops linha a linha) e tipos explícitos.

## Airflow

Objetivo duplo: **entregar a automação** e **dar ao autor contato real com Airflow**.

- Usar a **versão estável mais recente** do Apache Airflow e **ler a documentação oficial dessa versão** antes de escrever DAGs. A API mudou bastante entre versões maiores; **não copiar exemplos antigos de memória**
- Rodar com **Docker Compose** (executor local, sem Celery/Kubernetes) partindo do compose oficial da documentação da versão escolhida. O banco de metadados do Airflow fica **separado** do banco de dados do projeto
- Airflow consome bastante memória; se a máquina do autor sofrer, avisar e simplificar a configuração
- Usar **TaskFlow API** (`@dag` e `@task`)
- Segredos (token do Telegram etc.) via variáveis de ambiente/Connections do Airflow, nunca no código
- **Não passar DataFrames por XCom.** Persistir no banco e passar apenas identificadores (ativo, intervalo de datas)
- **Idempotência:** reexecutar uma DAG para a mesma data não pode duplicar dados (upsert por ativo + timestamp). Isso permite `backfill` e retry seguros

### DAGs planejadas

1. **`daily_pipeline`** (diária): bronze → silver → qualidade → gold. Usar **dynamic task mapping** (`.expand()`) para processar cada ativo em paralelo. Retries com backoff
2. **`intraday_refresh`** (frequente, ex.: a cada poucos minutos): uma task de decisão (`short_circuit` ou `branch`) lê o regime atual de cada ativo e decide se já é hora de atualizar os dados recentes, conforme as frequências definidas em `config/regimes.yaml`. Se atualizou, recalcula o regime e **alerta no Telegram quando o regime mudou** (com histerese/confirmação mínima para não alertar repetidamente na fronteira)
3. **`daily_report`**: gera a planilha Excel após o gold estar pronto (dependência entre DAGs via agendamento orientado a dados, "Assets"/"Datasets" conforme o nome na versão usada) e opcionalmente envia ao Telegram
4. **Falhas:** callback de falha que avisa no Telegram

Conceitos que o autor quer praticar: DAG/task, agendamento e `catchup`, retries, task mapping, branching/short-circuit, dependência entre DAGs, callbacks, idempotência, backfill.

### Testes das DAGs

- Teste de integridade: todas as DAGs importam sem erro (carregar via `DagBag`)
- A lógica das tasks é testada como funções comuns em `tests/unit` e `tests/integration` (por isso as DAGs ficam finas)
- Nunca chamar a API real nos testes

## Fonte de dados: Mercado Bitcoin

- API pública v4, gratuita, documentação em `https://api.mercadobitcoin.net/api/v4/docs`
- Endpoint de candles: `GET https://api.mercadobitcoin.net/api/v4/candles`
- **Antes de implementar o cliente, ler a documentação oficial** e confirmar: símbolos dos pares (ex.: formato `BTC-BRL`), parâmetros e resoluções aceitas, limite de candles por requisição, **rate limits** e **até onde vai o histórico disponível**. Não assumir nada disso de memória
- Ter uma resolução diária (indicadores de tendência) e uma horária (volatilidade recente), se a API suportar
- A profundidade do histórico limita o backtest e o cálculo de percentis; registrar isso no README

## Camadas de dados

- **Bronze:** respostas exatamente como vieram da API, com metadados de coleta (timestamp de ingestão, parâmetros). Imutável
- **Silver:** candles limpos e padronizados (UTC, tipos corretos, deduplicados, buracos sinalizados, outliers **sinalizados** e nunca removidos em silêncio). A silver só marca; `pipeline/quality.py` decide e reporta o que é problema (buracos, preços absurdos, atrasos) e grava o resultado para a aba `Qualidade`
- Indicadores sobre janelas com candles faltando: não preencher em silêncio; o resultado daquela janela fica nulo ou sinalizado
- **Gold:** indicadores, volatilidade, regime, correlação com BTC e backtests, prontos para consumo (CLI, bot, planilha)

### Modelagem

Simples e proporcional ao tamanho do projeto:
- `dim_ativo`
- `fact_candle`, `fact_indicador`, `fact_regime`, `fact_backtest`

## Volatilidade e regimes

- Volatilidade realizada: desvio padrão dos retornos em janela móvel (e/ou ATR, EWMA)
- Regime por **percentil do histórico do próprio ativo** (ex.: abaixo do percentil 33 = calma, entre 33 e 66 = normal, acima = alta). Cortes em `config/regimes.yaml`
- Frequências de atualização por regime também em configuração, nunca hardcoded
- **Sem look-ahead:** o regime de uma data só pode usar dados até aquela data (percentil *expanding* ou em janela móvel). Isso vale para a aba `Regimes`, para o backtest e para a detecção de mudança. O percentil sobre o histórico completo só é válido para descrever o "agora"
- **Histerese:** um regime só muda após N leituras consecutivas no novo estado, com N e a margem em pontos de percentil definidos em `config/regimes.yaml`

## Backtest: regras de honestidade

- Sinais consecutivos se sobrepõem (ex.: retorno a 7 dias do mesmo evento); contar ocorrências **independentes** (ex.: agrupar sinais dentro da janela de avaliação) e reportar também o total bruto
- Definir uma **amostra mínima** em configuração; abaixo dela o sistema diz "amostra pequena demais para concluir" em vez de mostrar média
- Reportar o resultado do sinal ao lado de uma linha de base (retorno médio em qualquer dia), senão "+X%" não significa nada
- O sistema descreve o que aconteceu no passado; nunca apresenta o resultado como previsão

## Decisões pendentes

Resolver na etapa indicada, registrar a decisão aqui e **perguntar ao autor antes de assumir**:

- **Definição de "dia":** candle diário em UTC ou em horário de Brasília? "Últimas 24h" é janela móvel ou o candle do dia? (etapa 2, depois de ler a doc da API)
- **Janela do percentil de regime:** expanding ou móvel, e de quantos dias? (etapa 5)
- **Amostra mínima do backtest:** quantas ocorrências independentes? (etapa 11)
- **Histerese:** valor de N e da margem (etapa 10)
- **Frequência do `intraday_refresh`:** compatível com o rate limit da API e com a resolução horária (etapa 10)
- **Limite de "dado velho"** para o aviso na resposta (etapa 7)

## Segurança e configuração

- Tokens **nunca** no código nem commitados: variáveis de ambiente / `.env` (no `.gitignore`) e `.env.example` documentado
- Parâmetros que mudam (ativos, regimes, frequências) ficam em YAML

## GitHub

- Repositório: `https://github.com/JulianoGalhardo9/crypto-analyzer` (remote `origin`, branch principal `main`)
- Nome oficial do projeto/pacote: `crypto-analyzer` (com "z"). A pasta local `crypto-analyser` tem grafia diferente; não renomear sem o autor pedir
- Fluxo: uma branch curta por tarefa (`feat/...`, `fix/...`, `docs/...`), Pull Request para `main` com CI verde. Não commitar direto na `main` depois que o CI existir
- **Autorização permanente do autor:** o Claude pode, por conta própria, criar branches, fazer commits, `git push` de branches, abrir PRs e fazer merge deles (via `gh`), seguindo o fluxo acima. Antes do merge: CI verde (quando existir) e `git diff` conferido. Preferir *squash merge* com título em Conventional Commits e apagar a branch depois
- **Continua proibido sem pedido explícito:** `--force`/`--force-with-lease`, reescrever histórico já publicado, apagar branches ou tags que não sejam as do próprio fluxo, alterar configurações do repositório (proteção de branch, secrets, visibilidade), fechar PRs/issues de terceiros
- Cada PR descreve o que mudou, por quê e como foi verificado (e o que **não** foi verificado). Registrar o PR em `docs/registro-de-acoes.md`
- Commits em inglês, Conventional Commits, um assunto por commit
- Nunca commitar: `.env`, `output/`, dados baixados, credenciais. Conferir `git status` e `git diff --staged` antes de cada commit
- O histórico faz parte do portfólio: sem commits do tipo "wip" ou "fix fix"; reescrever só em branch local, nunca em histórico já publicado
- Issues: todo TODO no código precisa de uma issue associada (referenciar `#número`)
- O repositório precisa de `LICENSE` antes do lançamento (etapa 14)

## Docker

- O Claude opera o Docker **pelo terminal** (`docker compose up -d`, `ps`, `logs`, `down`, `exec`), sem pedir ao autor para rodar os comandos. Se o Docker Desktop estiver fechado, abri-lo com `open -a Docker` e esperar o daemon subir
- Verificar o resultado (`docker compose ps` com `healthy`, logs) antes de dizer que funcionou
- **Não apagar volumes nem dados** (`down -v`, `docker volume rm`, `system prune`) sem o autor pedir, porque o histórico coletado tem valor
- Registrar em `docs/registro-de-acoes.md` o que foi subido e verificado

## Documentação (`docs/`)

- Manter `docs/` atualizado a cada etapa, em **português (pt-BR)**: `registro-de-acoes.md` (diário do que foi feito, com hashes dos commits e o que **não** foi verificado), `decisoes.md` (decisão + motivo + alternativa descartada) e `arquitetura.md` (estado atual das pastas)
- Atualizar a documentação no mesmo commit ou logo após a mudança que a motivou; nunca registrar algo que não foi feito ou testado

## Padrões de código

- Type hints em tudo; `mypy` e `ruff` limpos antes de commitar
- Teste junto com cada funcionalidade
- Commits no estilo Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`)
- Sem código morto, sem TODO solto sem issue associada
- Comentários e docstrings em **português**, curtos e só onde o "porquê" não é óbvio (nomes de código continuam em inglês)

## Como trabalhar com o autor

- Juliano é estudante de Engenharia de Software e estagiário de engenharia de dados. Domina C#/.NET e SQL Server; **está usando Python, pandas e Airflow para aprender**
- **Explique brevemente decisões não óbvias** (por que esta função do pandas, por que este operador do Airflow) em vez de só despejar código
- Trabalhe em **passos pequenos**, com commits pequenos e frequentes. O histórico do GitHub faz parte do portfólio
- Se algo estiver ambíguo, **pergunte antes de assumir**
- Conversar em **português (pt-BR)**. Código, nomes de variáveis/funções e commits em **inglês**; **comentários e docstrings em português (pt-BR)**
- **No final de cada resposta**, incluir uma seção curta "O que mudou" explicando em **linguagem simples** (sem jargão, como se fosse para um iniciante) o que foi alterado e **em quais arquivos**, um item por arquivo ou grupo de arquivos. Se nada foi alterado, dizer isso
- **Nunca invente resultados, benchmarks ou números.** Qualquer métrica que vá para o README deve vir de medição ou execução real

## Comandos úteis

```bash
uv sync                                   # instalar dependências
docker compose up -d                      # subir Postgres e Airflow
uv run alembic upgrade head               # migrations
uv run pytest                             # testes
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run crypto-analyzer analisar SOL
uv run crypto-analyzer analisar SOL --detalhes
uv run crypto-analyzer planilha           # gera o .xlsx em output/
```

(Ajustar esta seção conforme os arquivos forem sendo criados, incluindo os comandos do Airflow da versão usada.)

## Ordem de construção

Cada etapa termina com algo funcionando e testado. A lógica nasce como Python comum, chamável pelo CLI, e só depois é envolvida pelo Airflow.

**MVP demonstrável = etapas 1 a 8** (CLI e planilha funcionando com dados reais). Se o tempo apertar, cortar nesta ordem: API FastAPI (13), depois bot (12). Airflow (9–10) é objetivo de aprendizado e não é cortado.

1. **Base do projeto:** estrutura de pastas, `pyproject.toml`, Ruff, mypy, pytest, CI básico, Docker Compose com Postgres
2. **Cliente do Mercado Bitcoin + bronze:** ler a documentação, implementar o cliente atrás de `MarketDataClient`, coletar o histórico de BTC, ETH e SOL e gravar bruto
3. **Silver + qualidade:** pandas para padronização, deduplicação, buracos e outliers, com testes
4. **Indicadores:** funções puras sobre pandas, validadas contra valores de referência
5. **Volatilidade e regimes:** cálculo por percentil e classificação
6. **Gold e modelagem:** tabelas, migrations, persistência dos indicadores e regimes
7. **Explainer + CLI:** resposta simples por padrão e `--detalhes`
8. **Planilha Excel:** `frames.py` + `excel.py`, comando `planilha`, testes lendo o `.xlsx` gerado
9. **Airflow, primeiro contato:** subir o ambiente via Docker Compose e criar uma DAG simples de ingestão que chama `pipeline/bronze.py`
10. **DAGs completas:** `daily_pipeline` (task mapping por ativo), `intraday_refresh` (decisão por regime + alerta de mudança), `daily_report`, callbacks de falha, teste de integridade das DAGs
11. **Backtest dos sinais:** validação do que os indicadores realmente indicaram nos dados; incluir na planilha
12. **Bot de Telegram:** `/analisar sol` e `/planilha`
13. **Opcional:** API FastAPI
14. **Lançamento:** README (problema, demo em 30 segundos, diagrama de arquitetura, exemplo da planilha, instalação, limitações), CONTRIBUTING, CHANGELOG, descobertas reais dos dados

**Dica:** deixar a coleta rodando o quanto antes (VPS barato ou máquina própria) depois da etapa 10, porque o valor do projeto cresce com o histórico acumulado.

## Definição de pronto (v0.1.0)

- `analisar BTC|ETH|SOL` devolve a resposta simples e `--detalhes` devolve os números
- `planilha` gera um `.xlsx` bem formatado, com gráficos e todas as abas
- Airflow roda as DAGs sozinho, atualiza os dados conforme o regime e alerta mudanças de regime
- Testes unitários, de integração e de integridade das DAGs passando no CI, sem depender da API real
- Bot de Telegram respondendo `/analisar sol` e `/planilha`
- README permite que um estranho rode o projeto sem ajuda, com limitações descritas com honestidade
- Nenhum segredo no repositório
