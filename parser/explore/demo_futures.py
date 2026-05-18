import asyncio
from parser.futures_ws import run_futures_ws


async def main():
    queue = asyncio.Queue()
    asyncio.create_task(run_futures_ws(queue))
    while True:
        ticker = await queue.get()
        print(ticker)


if __name__ == "__main__":
    asyncio.run(main())