# MEXC Spot/Futures Spread Bot

Telegram bot that monitors live MEXC spot and perpetual futures tickers, detects spread events, and sends alerts with direct market links.

## What it does

- Subscribes to the full MEXC spot mini-ticker feed and the full futures ticker feed
- Computes signed spread percentage as `(futures - spot) / spot * 100`
- Emits three event types:
  - `open` when a spread crosses the configured threshold
  - `deepen` when an open spread reaches a new significant peak
  - `close` when the spread collapses back below the close threshold
- Sends Telegram messages with:
  - direction and spread percentage
  - spot and futures prices
  - spot and futures 24h amount in USDT
  - inline buttons to open the MEXC spot and futures markets
- Supports an admin blacklist for hiding noisy symbols

## Architecture

The runtime is a single Python process started from [main.py](./main.py):

1. `parser/spot_ws.py` streams live spot tickers from MEXC
2. `parser/futures_ws.py` streams live futures tickers from MEXC
3. `parser/state_manager.py` joins both feeds, tracks open spreads, and emits `SpreadEvent`
4. `bot/bot_app.py` polls Telegram and consumes emitted spread events

Data flow:

```text
MEXC Spot WS ----\
                  > market_data_queue -> state_manager -> spread_event_queue -> Telegram bot
MEXC Futures WS -/
```

## Requirements

- Python 3.14 recommended
- A Telegram bot token from `@BotFather`

## Local setup

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Generate protobuf bindings:

```bash
python scripts/generate_proto.py
```

4. Create your local environment file:

```bash
cp .env.example .env
```

5. Fill in at least `BOT_TOKEN` inside `.env`

6. Start the bot:

```bash
python main.py
```

## Telegram usage

- `/start` subscribes the current chat to alerts
- `/stop` unsubscribes the current chat
- `/help` shows command help
- `/about` explains the project

Admin-only commands:

- `/admin`
- `/ban_token SYMBOL`
- `/unban_token SYMBOL`
- `/banned_tokens`

## Environment variables

See [.env.example](./.env.example) for the full list.

Required:

- `BOT_TOKEN`

Optional bot settings:

- `ADMIN_ONE_ID`
- `ADMIN_TWO_ID`
- `BLACKLIST_DB_PATH`

Optional parser and persistence settings:

- `STATE_FILE_PATH`
- `MIN_VOLUME_24H_USD`
- `OPEN_THRESHOLD`
- `CLOSE_THRESHOLD`
- `DEEPEN_TRIGGER`
- `OPEN_DEBOUNCE`
- `CLOSE_DEBOUNCE`
- `DEEPEN_DEBOUNCE`
- `PING_INTERVAL_SEC`
- `RECONNECT_DELAY_SEC`
- `SPOT_WS_URL`
- `FUT_WS_URL`
- `SPOT_TICKERS_CHANNEL`
- `FUT_TICKERS_CHANNEL`
- `QUOTE`
- `SNAPSHOT_INTERVAL_SEC`

## Persistence

The project stores:

- spread-state snapshots in `STATE_FILE_PATH`
- bot blacklist data in `BLACKLIST_DB_PATH`

For local development the defaults are:

- `data/state.json`
- `.bot_state/blacklist.sqlite3`

For cloud deployment you should point both paths to persistent storage.

## Render deployment

This repository includes [render.yaml](./render.yaml) for a Render background worker.

Build command:

- installs Python dependencies
- generates protobuf bindings from `parser/proto/*.proto`

Start command:

- `python main.py`

Recommended deployment notes:

- Render background workers require a paid instance type, so the included blueprint uses `starter`
- Deploy as a `worker`, not a web service
- Set `BOT_TOKEN` in the Render dashboard
- Keep a persistent disk attached if you want spread snapshots and blacklist state to survive restarts
- Point `STATE_FILE_PATH` and `BLACKLIST_DB_PATH` to the mounted disk

## Deployment notes for a pet project

For this repository, local execution is the primary supported mode.

Why:

- the bot is a long-running process that depends on continuous Telegram polling
- the parser maintains persistent websocket connections to MEXC
- the current persistence model uses local files for spread snapshots and a local SQLite file for the blacklist

Render's free web service tier is not a good fit for that architecture because:

- free web services spin down after idle time
- free web services do not support persistent disks
- the current bot is not designed as an HTTP web app

If you just want to keep this as a pet project, it is perfectly reasonable to run it locally and skip hosting for now.

If you later want a stable always-on deployment, the recommended Render setup is a paid background worker with persistent storage.

## Repository layout

```text
bot/           Telegram bot handlers, formatting, and event delivery
parser/        MEXC websocket readers and spread state manager
shared/        Shared dataclasses used across parser and bot
docs/          Technical notes and internal contracts
scripts/       Utility scripts, including protobuf generation
```

## Documentation

- [Parser/Bot Contract](./docs/contract_parser_bot.md)
- [MEXC WebSocket Notes](./docs/mexc_api_notes.md)

## Contributors

This project was built by two contributors:

- [Tenyokj](https://github.com/Tenyokj) — Telegram bot logic, message formatting, chat UX, and interface behavior
- [likeastyro](https://github.com/likeastyro) — parser implementation, MEXC API/WebSocket integration, and market data processing

## Known limitations

- Telegram polling allows only one running bot instance per token
- Spot and futures data arrive asynchronously, so alert payloads represent the latest matched values at event time, not a later browser snapshot
- Futures `volume24` is in contracts, not coins, so the bot intentionally reports 24h amount in USDT instead
