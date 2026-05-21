import asyncio
from loguru import logger
from shared.models import SpreadEvent
from parser.spot_ws import run_spot_ws
from parser.futures_ws import run_futures_ws
from parser.state_manager import run_state_manager


async def printer(out_queue: asyncio.Queue) -> None:
    while True:
        event: SpreadEvent = await out_queue.get()
        if event.event_type == "open":
            logger.info(
                f"🟢 OPEN  {event.symbol} {event.direction} "
                f"spread={event.spread_pct:+.2f}% "
                f"spot={event.spot_price} fut={event.fut_price} "
                f"vol=${event.volume_24h_usd:,.0f}"
            )
        elif event.event_type == "deepen":
            logger.info(
                f"🔵 DEEPEN {event.symbol} {event.direction} "
                f"spread={event.spread_pct:+.2f}% "
                f"spot={event.spot_price} fut={event.fut_price}"
            )
        elif event.event_type == "close":
            logger.info(
                f"✅ CLOSE {event.symbol} {event.direction} "
                f"spread={event.spread_pct:+.2f}% "
                f"duration={event.duration_sec}s "
                f"daily_peak={event.daily_peak_pct:.2f}%"
            )


async def main():
    in_queue = asyncio.Queue()
    out_queue = asyncio.Queue()
    await asyncio.gather(
        run_spot_ws(in_queue),
        run_futures_ws(in_queue),
        run_state_manager(in_queue, out_queue),
        printer(out_queue),
    )


if __name__ == "__main__":
    asyncio.run(main())
