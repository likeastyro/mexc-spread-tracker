# Parser to Bot Event Contract

Internal reference for the spread parser and Telegram bot integration.

## Overview

The parser runs continuously, watches all tracked MEXC spot and futures pairs, and pushes `SpreadEvent` objects into an `asyncio.Queue`.

The bot consumes those events and turns them into Telegram messages.

## Event lifecycle

The parser emits three event types:

| Event type | When it is emitted | Bot behavior |
| --- | --- | --- |
| `open` | A new spread crosses the open threshold | Send a fresh Telegram message and remember its `message_id` |
| `deepen` | The same spread reaches a new significant peak | Send a reply to the remembered `open` message |
| `close` | The spread collapses back below the close threshold | Send a reply to the remembered `open` message and forget that thread |

## `SpreadEvent` schema

| Field | Type | Description |
| --- | --- | --- |
| `event_type` | `"open" \| "deepen" \| "close"` | Spread lifecycle event |
| `symbol` | `str` | Base asset symbol, no `_USDT` suffix. Example: `PEPE` |
| `direction` | `"LONG" \| "SHORT"` | `LONG` means futures price is above spot. `SHORT` means futures price is below spot |
| `spot_price` | `float` | Latest matched spot price |
| `fut_price` | `float` | Latest matched futures price |
| `spread_pct` | `float` | Signed spread percentage. Positive for `LONG`, negative for `SHORT` |
| `daily_peak_pct` | `float` | Highest absolute spread observed for the symbol during the current UTC day |
| `volume_24h_usd` | `float` | Compatibility field. Current code fills it with `max(spot_amount, futures_amount)` |
| `spot_volume_24h_usd` | `float` | Spot 24h amount in quote currency (USDT) |
| `fut_volume_24h_usd` | `float` | Futures 24h amount in quote currency (USDT) |
| `duration_sec` | `int \| None` | Spread lifetime in seconds. Present for `close`, absent for `open` and `deepen` |
| `reply_to_message_id` | `int \| None` | Optional explicit reply target. The current bot mostly relies on its own in-memory thread mapping |

## Message expectations

### Open and deepen

The bot should show:

- direction and signed spread percent
- symbol
- daily peak
- spot price
- futures price
- spot 24h amount in USDT
- futures 24h amount in USDT
- inline buttons for Spot and Futures market pages

`deepen` messages use the same structure as `open`, but append `(deepened)` to the first line.

### Close

The bot should send a short threaded message:

```text
✅ #PEPE aligned in 12 min
```

No buttons are attached to `close` events.

## URL rules

The parser emits raw symbols such as `PEPE`.

The bot is responsible for building market URLs:

- Spot: `https://www.mexc.com/exchange/{symbol}_USDT`
- Futures: `https://futures.mexc.com/exchange/{symbol}_USDT`

## Current runtime wiring

The production entrypoint is [main.py](../main.py):

1. `run_spot_ws(market_data_queue)`
2. `run_futures_ws(market_data_queue)`
3. `run_state_manager(market_data_queue, spread_event_queue)`
4. `run_bot(token=..., queue=spread_event_queue)`

This means the bot now receives real parser output, not the legacy fake event producer.
