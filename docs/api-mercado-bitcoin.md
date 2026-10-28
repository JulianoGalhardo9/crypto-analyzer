# API do Mercado Bitcoin (v4) — o que foi lido e medido

Fonte: especificação OpenAPI oficial (`https://api.mercadobitcoin.net/api/v4/docs/swagger.yaml`, a página `/docs` é só um visualizador Redoc que carrega esse arquivo) e medições feitas em 2026-10-28 contra a API pública. Itens marcados **(medido)** não estão na documentação.

## Endpoint de candles
`GET /api/v4/candles` — público, sem autenticação.

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `symbol` | sim | formato `BASE-QUOTE`, ex.: `SOL-BRL` |
| `resolution` | sim | `1m`, `15m`, `1h`, `3h`, `1d`, `1w`, `1M` |
| `to` | sim | Unix timestamp (UTC) do último candle; pode estar no futuro (devolve o mais recente) |
| `from` | não | Unix timestamp (UTC) do primeiro candle |
| `countback` | não | número de candles a partir de `to`; **tem prioridade sobre `from`** |

Resposta: objeto com **listas paralelas** `t` (início do candle, Unix UTC, inteiro), `o`, `h`, `l`, `c`, `v` (strings decimais, ex.: `"541.77000000"`).

## Limites
- **Rate limit: 1 requisição por segundo** por endpoint (documentado). O cliente espaça as chamadas.
- **Candles por requisição:** a documentação não diz. **(medido)** `countback=100000` devolveu o histórico inteiro de uma vez (ex.: 42.268 candles horários de SOL), sem erro.
- **User-Agent:** **(medido)** o User-Agent padrão do `urllib` (`Python-urllib/x`) recebe **403**; `curl`, `python-httpx` e um User-Agent próprio recebem 200. O cliente envia `crypto-analyzer/<versão>`.

## Profundidade do histórico (candles diários, medido em 2026-10-28)

| Par | Primeiro candle | Candles |
|---|---|---|
| BTC-BRL | 2013-06-12 | 4.887 |
| ETH-BRL | 2018-12-12 | 2.878 |
| SOL-BRL | 2021-11-29 | 1.795 |

SOL horário começa em 2021-11-29 13:00 UTC. A SOL tem cerca de 5 anos de histórico: isso limita percentis, correlação e backtest (registrar no README).

## Observações que afetam o projeto
- Os candles diários começam à **00:00 UTC**. A API já "pensa" em dias UTC.
- **O último candle é parcial:** o candle do dia corrente ainda está em formação. A silver precisa sinalizá-lo para os indicadores não tratarem como fechado.
- Valores vêm como **strings**; a conversão para número é feita na silver, e a bronze guarda a resposta crua.
- Outros endpoints públicos: `/symbols`, `/tickers`, `/{symbol}/orderbook`, `/{symbol}/trades`. Só `/candles` é usado na v1.
