import asyncio
import json
import websockets

URL = "wss://contract.mexc.com/edge"
SUB = {"method": "sub.tickers", "param": {}, "gzip": False}


async def heartbeat(ws):
    while True:
        await asyncio.sleep(15)
        await ws.send(json.dumps({"method": "ping"}))
        print("[ping sent]")


async def main():
    while True:
        ping_task = None
        try:
            async with websockets.connect(URL) as ws:
                await ws.send(json.dumps(SUB))
                ping_task = asyncio.create_task(heartbeat(ws))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("channel") == "pong":
                        print("[pong received]")
                        continue
                    if msg.get("channel") != "push.tickers":
                        continue
                    data = msg.get("data", [])
                    btc = next((t for t in data if t.get("symbol") == "BTC_USDT"), None)
                    if not btc:
                        continue
                    vol = btc.get("amount24", "N/A")
                    print(f"[BTC_USDT] price={btc['lastPrice']} vol=${vol}")
            print("[connection closed, reconnecting in 5s...]")
        except Exception as e:
            print(f"[connection error: {e}, reconnecting in 5s...]")
        finally:
            if ping_task is not None:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
        await asyncio.sleep(5)


asyncio.run(main())
