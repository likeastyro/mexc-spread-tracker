import asyncio
import json
import time
from loguru import logger

import websockets

from parser.config import (
    FUT_WS_URL,
    FUT_TICKERS_CHANNEL,
    PING_INTERVAL_SEC,
    RECONNECT_DELAY_SEC,
    MIN_VOLUME_24H_USD,
    QUOTE,
)
from shared.models import Ticker

_QUOTE_SUFFIX = "_" + QUOTE  # "_USDT"


async def _heartbeat(ws) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_SEC)
        await ws.send(json.dumps({"method": "ping"}))


async def run_futures_ws(out_queue: asyncio.Queue) -> None:
    while True:
        ping_task = None
        try:
            async with websockets.connect(FUT_WS_URL) as ws:
                await ws.send(json.dumps({"method": FUT_TICKERS_CHANNEL, "param": {"gzip": False}}))
                ping_task = asyncio.create_task(_heartbeat(ws))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("channel") != "push.tickers":
                        continue
                    data = msg.get("data")
                    if not isinstance(data, list):
                        continue
                    now = time.time()
                    for t in data:
                        symbol = t.get("symbol", "")
                        if not symbol.endswith(_QUOTE_SUFFIX):
                            continue
                        volume = float(t.get("amount24", 0))
                        if volume < MIN_VOLUME_24H_USD:
                            continue
                        price = float(t.get("lastPrice", 0))
                        symbol_clean = symbol.removesuffix(_QUOTE_SUFFIX)
                        ticker = Ticker(
                            market="futures",
                            symbol=symbol_clean,
                            price=price,
                            volume_24h_usd=volume,
                            timestamp=now,
                        )
                        await out_queue.put(ticker)
        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            logger.warning("futures connection lost: {}, reconnect in {}s", e, RECONNECT_DELAY_SEC)
            await asyncio.sleep(RECONNECT_DELAY_SEC)
            continue
        finally:
            if ping_task is not None:
                ping_task.cancel()
