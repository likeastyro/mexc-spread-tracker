# MEXC WebSocket Notes

Reference notes for the live market data feeds used by the parser.

## Quick comparison

| Topic | Spot | Futures |
| --- | --- | --- |
| Base URL | `wss://wbs-api.mexc.com/ws` | `wss://contract.mexc.com/edge` |
| Feed used in this project | `spot@public.miniTickers.v3.api.pb@UTC+8` | `sub.tickers` |
| Payload format | Protocol Buffers | JSON |
| Symbol format | `BTCUSDT` | `BTC_USDT` |
| Price field | `price` | `lastPrice` |
| 24h amount in USDT | `volume` | `amount24` |
| Non-USDT volume field | `quantity` in coins | `volume24` in contracts |
| Ping method | `{"method": "PING"}` | `{"method": "ping"}` |

## Spot feed notes

### Subscription

```json
{
  "method": "SUBSCRIPTION",
  "params": ["spot@public.miniTickers.v3.api.pb@UTC+8"]
}
```

### Important fields

| Field | Meaning |
| --- | --- |
| `symbol` | Pair symbol without underscore, such as `PEPEUSDT` |
| `price` | Latest trade price |
| `volume` | 24h amount in quote currency (USDT) |
| `quantity` | 24h volume in base asset units |

### Notes

- The feed is binary protobuf, not JSON
- The generated Python bindings are required before runtime
- `volume` and `quantity` are easy to confuse:
  - `volume` is the quote-denominated turnover
  - `quantity` is the base-asset amount

## Futures feed notes

### Subscription

```json
{
  "method": "sub.tickers",
  "param": {
    "gzip": false
  }
}
```

### Important fields

| Field | Meaning |
| --- | --- |
| `symbol` | Contract symbol such as `PEPE_USDT` |
| `lastPrice` | Latest trade price |
| `amount24` | 24h amount in quote currency (USDT) |
| `volume24` | 24h volume in contracts, not coins |

### Notes

- The project explicitly requests `gzip: false` to keep the feed in plain JSON
- `volume24` is not directly comparable with spot `quantity`
- For alert messages, the bot intentionally reports USDT-denominated 24h amount instead of unit-based volume

## Why the bot shows "24h amount (USDT)"

This is deliberate.

- Spot `volume` is quote turnover in USDT
- Futures `amount24` is quote turnover in USDT
- Spot `quantity` is in coins
- Futures `volume24` is in contracts

Because the non-USDT fields use different units, the bot formats:

- `Spot 24h amount (USDT)`
- `Futures 24h amount (USDT)`

This keeps both lines directly comparable.

## Protobuf generation

The repository stores `.proto` definitions under `parser/proto/`.

Generate the Python modules with:

```bash
python scripts/generate_proto.py
```

The build step for Render runs that command automatically.

## Known gotchas

1. Spot and futures use different websocket protocols and payload formats.
2. Spot symbols and futures symbols require different normalization rules.
3. Spot `quantity` and futures `volume24` do not use the same units.
4. A Telegram alert is a snapshot of values at event time, not a live-updating market card.
