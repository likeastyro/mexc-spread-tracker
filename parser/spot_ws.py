import asyncio
import json
import time
from loguru import logger

import websockets

from parser.proto import PushDataV3ApiWrapper_pb2
from parser.config import (
    SPOT_WS_URL,
    SPOT_TICKERS_CHANNEL,
    PING_INTERVAL_SEC,
    RECONNECT_DELAY_SEC,
    MIN_VOLUME_24H_USD,
    QUOTE,
)
from shared.models import Ticker


async def _heartbeat(ws) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_SEC)
        await ws.send(json.dumps({"method": "PING"}))


async def run_spot_ws(out_queue: asyncio.Queue) -> None:
    while True:
        ping_task = None
        try:
            async with websockets.connect(SPOT_WS_URL) as ws:
                await ws.send(json.dumps({"method": "SUBSCRIPTION", "params": [SPOT_TICKERS_CHANNEL]}))
                ping_task = asyncio.create_task(_heartbeat(ws))
                async for raw in ws:
                    if isinstance(raw, str):
                        if '"msg":"PONG"' in raw:
                            logger.debug("spot heartbeat acknowledged")
                        else:
                            logger.info("spot subscription confirmed: {}", raw)
                        continue
                    wrapper = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
                    wrapper.ParseFromString(raw)
                    now = time.time()
                    for t in wrapper.publicMiniTickers.items:
                        if not t.symbol.endswith(QUOTE):
                            continue
                        price = float(t.price)
                        volume = float(t.volume)
                        if volume < MIN_VOLUME_24H_USD:
                            continue
                        symbol = t.symbol.removesuffix(QUOTE)
                        ticker = Ticker(
                            market="spot",
                            symbol=symbol,
                            price=price,
                            volume_24h_usd=volume,
                            timestamp=now,
                        )
                        await out_queue.put(ticker)
        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            logger.warning("spot connection lost: {}, reconnect in {}s", e, RECONNECT_DELAY_SEC)
            await asyncio.sleep(RECONNECT_DELAY_SEC)
            continue
        finally:
            if ping_task is not None:
                ping_task.cancel()
