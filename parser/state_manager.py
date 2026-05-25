import asyncio
import time
import json
from pathlib import Path

from datetime import datetime, timedelta, timezone

from loguru import logger

from shared.models import Ticker, SpreadEvent
from parser.config import (
    OPEN_THRESHOLD, CLOSE_THRESHOLD, DEEPEN_TRIGGER, MIN_VOLUME_24H_USD,
    OPEN_DEBOUNCE, CLOSE_DEBOUNCE, DEEPEN_DEBOUNCE,
    SNAPSHOT_INTERVAL_SEC, STATE_FILE_PATH,  
)

def save_state(open_alerts: dict, daily_peaks: dict) -> None:
    state_path = Path(STATE_FILE_PATH)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        'open_alerts': open_alerts,
        'daily_peaks': daily_peaks,
    }
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    logger.info(
        "state snapshot saved ({} alerts, {} daily peaks)",
        len(open_alerts), len(daily_peaks),
    )        

def load_state() -> tuple[dict, dict]:
    state_path = Path(STATE_FILE_PATH)
    if not state_path.exists():
        logger.info("no state file found, starting fresh")
        return {}, {}
    with open(state_path, "r") as f:
        state = json.load(f)
    open_alerts = state.get("open_alerts", {})
    daily_peaks = state.get("daily_peaks", {})
    logger.info(
        "state loaded ({} alerts, {} daily peaks)",
        len(open_alerts), len(daily_peaks),
    )
    return open_alerts, daily_peaks

async def run_state_manager(in_queue: asyncio.Queue, out_queue: asyncio.Queue) -> None:
    last_prices: dict[tuple[str, str], float] = {}
    open_alerts, daily_peaks = load_state()
    pending_open: dict[str, int] = {}
    pending_close: dict[str, int] = {}
    pending_deepen: dict[str, int] = {}

    async def reset_daily_peaks() -> None:
        while True:
            now = datetime.now(timezone.utc)
            tomorrow = (now + timedelta(days=1)).date()
            midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
            seconds_until_midnight = (midnight - now).total_seconds()
            await asyncio.sleep(seconds_until_midnight)
            daily_peaks.clear()
            logger.info("daily_peaks reset at UTC midnight")

    async def periodic_snapshot() -> None:
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
            save_state(open_alerts, daily_peaks)

    
    reset_task = asyncio.create_task(reset_daily_peaks())
    snapshot_task = asyncio.create_task(periodic_snapshot())
    try:
        while True:
            ticker: Ticker = await in_queue.get()

            if ticker.volume_24h_usd < MIN_VOLUME_24H_USD:
                continue

            last_prices[(ticker.market, ticker.symbol)] = ticker.price

            if ('spot', ticker.symbol) not in last_prices or ('futures', ticker.symbol) not in last_prices:
                continue

            spot_price = last_prices[('spot', ticker.symbol)]
            fut_price = last_prices[('futures', ticker.symbol)]
            spread_pct = (fut_price - spot_price) / spot_price * 100
            symbol = ticker.symbol

            daily_peaks[symbol] = max(daily_peaks.get(symbol, 0), abs(spread_pct))

            if symbol not in open_alerts:
                if abs(spread_pct) >= OPEN_THRESHOLD:
                    pending_open[symbol] = pending_open.get(symbol, 0) + 1
                    if pending_open[symbol] >= OPEN_DEBOUNCE:
                        direction = 'LONG' if spread_pct > 0 else 'SHORT'
                        open_alerts[symbol] = {
                            'opened_at': time.time(),
                            'peak_pct': abs(spread_pct),
                            'direction': direction,
                        }
                        event = SpreadEvent(
                            event_type='open',
                            symbol=symbol,
                            direction=direction,
                            spot_price=spot_price,
                            fut_price=fut_price,
                            spread_pct=spread_pct,
                            daily_peak_pct=daily_peaks[symbol],
                            volume_24h_usd=ticker.volume_24h_usd,
                            duration_sec=None,
                            reply_to_message_id=None,
                        )
                        await out_queue.put(event)
                        del pending_open[symbol]
                        logger.info(f"OPEN  {symbol} {direction} spread={spread_pct:.2f}%")
                else:
                    if symbol in pending_open:
                        del pending_open[symbol]

            else:
                # 3a. CLOSE
                if abs(spread_pct) < CLOSE_THRESHOLD:
                    pending_close[symbol] = pending_close.get(symbol, 0) + 1
                    if pending_close[symbol] >= CLOSE_DEBOUNCE:
                        alert = open_alerts[symbol]
                        duration_sec = int(time.time() - alert['opened_at'])
                        event = SpreadEvent(
                            event_type='close',
                            symbol=symbol,
                            direction=alert['direction'],
                            spot_price=spot_price,
                            fut_price=fut_price,
                            spread_pct=spread_pct,
                            daily_peak_pct=daily_peaks[symbol],
                            volume_24h_usd=ticker.volume_24h_usd,
                            duration_sec=duration_sec,
                            reply_to_message_id=None,
                        )
                        await out_queue.put(event)
                        logger.info(f"CLOSE {symbol} {alert['direction']} spread={spread_pct:.2f}% duration={duration_sec}s")
                        del open_alerts[symbol]
                        del pending_close[symbol]
                        if symbol in pending_deepen:
                            del pending_deepen[symbol]
                        continue
                else:
                    if symbol in pending_close:
                        del pending_close[symbol]

                # 3b. DEEPEN
                if abs(spread_pct) >= open_alerts[symbol]['peak_pct'] * DEEPEN_TRIGGER:
                    pending_deepen[symbol] = pending_deepen.get(symbol, 0) + 1
                    if pending_deepen[symbol] >= DEEPEN_DEBOUNCE:
                        open_alerts[symbol]['peak_pct'] = abs(spread_pct)
                        direction = open_alerts[symbol]['direction']
                        event = SpreadEvent(
                            event_type='deepen',
                            symbol=symbol,
                            direction=direction,
                            spot_price=spot_price,
                            fut_price=fut_price,
                            spread_pct=spread_pct,
                            daily_peak_pct=daily_peaks[symbol],
                            volume_24h_usd=ticker.volume_24h_usd,
                            duration_sec=None,
                            reply_to_message_id=None,
                        )
                        await out_queue.put(event)
                        del pending_deepen[symbol]
                        logger.info(f"DEEPEN {symbol} {direction} spread={spread_pct:.2f}%")
                else:
                    if symbol in pending_deepen:
                        del pending_deepen[symbol]
    finally:
        reset_task.cancel()
