import asyncio
import os

from dotenv import load_dotenv

from bot.bot_app import run_bot
from bot.consumer import fake_event_producer


async def main() -> None:
    load_dotenv()
    token = os.environ["BOT_TOKEN"]

    queue: asyncio.Queue = asyncio.Queue()

    producer_task = asyncio.create_task(
        fake_event_producer(queue, interval_seconds=2.0, repeat=True)
    )

    try:
        await run_bot(token=token, queue=queue)
    finally:
        producer_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
