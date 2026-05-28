import asyncio
import contextlib
import os

from dotenv import load_dotenv

from bot.bot_app import run_bot
from parser.futures_ws import run_futures_ws
from parser.spot_ws import run_spot_ws
from parser.state_manager import run_state_manager


async def main() -> None:
    load_dotenv()
    token = os.environ["BOT_TOKEN"]

    ticker_queue: asyncio.Queue = asyncio.Queue()
    event_queue: asyncio.Queue = asyncio.Queue()

    spot_task = asyncio.create_task(run_spot_ws(ticker_queue))
    futures_task = asyncio.create_task(run_futures_ws(ticker_queue))
    state_manager_task = asyncio.create_task(run_state_manager(ticker_queue, event_queue))

    parser_tasks = [spot_task, futures_task, state_manager_task]

    try:
        await run_bot(token=token, queue=event_queue)
    finally:
        for task in parser_tasks:
            task.cancel()
        for task in parser_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
