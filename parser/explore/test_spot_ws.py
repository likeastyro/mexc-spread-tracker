import asyncio
import json
import websockets
from parser.proto import PushDataV3ApiWrapper_pb2

URL = "wss://wbs-api.mexc.com/ws"
SUBSCRIBE_MSG = json.dumps({
    "method": "SUBSCRIPTION",
    "params": ["spot@public.miniTickers.v3.api.pb@UTC+8"]
})


async def heartbeat(ws):
    while True:
        await asyncio.sleep(15)
        await ws.send(json.dumps({"method": "PING"}))


async def main():
    while True:
        ping_task = None
        try:
            async with websockets.connect(URL) as ws:
                await ws.send(SUBSCRIBE_MSG)
                ping_task = asyncio.create_task(heartbeat(ws))

                async for raw in ws:
                    if isinstance(raw, str):
                        print("[service]", raw)
                        continue

                    wrapper = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
                    wrapper.ParseFromString(raw)
                    tickers = wrapper.publicMiniTickers.items
                    btc = next((t for t in tickers if t.symbol == "BTCUSDT"), None)
                    if btc is None:
                        continue

                    price = float(btc.price)
                    volume = float(btc.volume)
                    print(f"BTCUSDT  price={price}  volume={volume:,.0f}")

            print("[connection closed, reconnecting in 5s...]")
        except (websockets.exceptions.ConnectionClosed, OSError) as e:
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
