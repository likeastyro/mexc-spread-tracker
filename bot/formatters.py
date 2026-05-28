from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping

from bot.keyboards import market_links_keyboard


EventLike = Mapping[str, Any] | Any

LONG_EMOJI = '<tg-emoji emoji-id="5429463966432643712">🤑</tg-emoji>'
SHORT_EMOJI = '<tg-emoji emoji-id="5429165728198576891">😡</tg-emoji>'
CHECK_EMOJI = '<tg-emoji emoji-id="5472123673265590913">✅</tg-emoji>'
VOLUME_EMOJI = '<tg-emoji emoji-id="5409048419211682843">💵</tg-emoji>'
PRICE_EMOJI = '<tg-emoji emoji-id="5332722143077613679">▶️</tg-emoji>'


def format_event_message(event: EventLike) -> tuple[str, object | None]:
    event_type = _event_type(event)

    if event_type == "deepen":
        text = _format_deepen(event)
        keyboard = market_links_keyboard(symbol=_symbol(event))
    elif event_type == "close":
        text = _format_close(event)
        keyboard = None
    else:
        text = _format_open(event)
        keyboard = market_links_keyboard(symbol=_symbol(event))
    return text, keyboard


def event_thread_key(event: EventLike) -> str:
    return str(
        _value(
            event,
            "spread_id",
            "event_id",
            "id",
            "key",
            "symbol",
            "pair",
            default="unknown",
        )
    )


def _format_open(event: EventLike) -> str:
    emoji, direction = _direction_style(event)
    daily_peak = _daily_peak_line(event)
    lines = [
        f"{emoji} <b>{direction}</b> <b>#{escape(_symbol(event))}</b> spread "
        f"<b>{_signed_percent(event, 'spread_pct', 'spread_percent', 'spread')}</b> detected",
    ]
    if daily_peak:
        lines.append(daily_peak)
    lines.extend(
        [
            "",
            f"{PRICE_EMOJI} Spot <code>{_usd(event, 'spot_price')}</code>",
            f"{PRICE_EMOJI} Futures <code>{_usd(event, 'fut_price', 'futures_price', 'future_price')}</code>",
            "",
            f"{VOLUME_EMOJI} Spot 24h amount (USDT) <code>{_compact_usd(event, 'spot_volume_24h_usd', 'volume_24h_usd')}</code>",
            f"{VOLUME_EMOJI} Futures 24h amount (USDT) <code>{_compact_usd(event, 'fut_volume_24h_usd', 'volume_24h_usd')}</code>",
        ]
    )
    return "\n".join(lines)


def _format_deepen(event: EventLike) -> str:
    emoji, direction = _direction_style(event)
    daily_peak = _daily_peak_line(event)
    lines = [
        f"{emoji} <b>{direction}</b> <b>#{escape(_symbol(event))}</b> spread "
        f"<b>{_signed_percent(event, 'spread_pct', 'spread_percent', 'spread')}</b> detected (deepened)",
    ]
    if daily_peak:
        lines.append(daily_peak)
    lines.extend(
        [
            "",
            f"{PRICE_EMOJI} Spot <code>{_usd(event, 'spot_price')}</code>",
            f"{PRICE_EMOJI} Futures <code>{_usd(event, 'fut_price', 'futures_price', 'future_price')}</code>",
            "",
            f"{VOLUME_EMOJI} Spot 24h amount (USDT) <code>{_compact_usd(event, 'spot_volume_24h_usd', 'volume_24h_usd')}</code>",
            f"{VOLUME_EMOJI} Futures 24h amount (USDT) <code>{_compact_usd(event, 'fut_volume_24h_usd', 'volume_24h_usd')}</code>",
        ]
    )
    return "\n".join(lines)


def _format_close(event: EventLike) -> str:
    return (
        f"{CHECK_EMOJI} <b>#{escape(_symbol(event))}</b> aligned in "
        f"<b>{escape(_format_duration(_value(event, 'duration_sec', default=None)))}</b>"
    )


def _event_type(event: EventLike) -> str:
    raw_value = str(_value(event, "event_type", "type", "action", "status", default="open"))
    raw_value = raw_value.strip().lower()
    if raw_value in {"deepen", "deepen_spread", "update"}:
        return "deepen"
    if raw_value in {"close", "closed", "close_spread"}:
        return "close"
    return "open"


def _symbol(event: EventLike) -> str:
    return str(_value(event, "symbol", "pair", "instrument", default="UNKNOWN"))


def _timestamp(event: EventLike) -> str:
    raw = _value(event, "timestamp", "created_at", "detected_at", default=None)
    if raw is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    return str(raw)


def _percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _signed_percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _absolute_percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{abs(float(value)):.1f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _daily_peak_line(event: EventLike) -> str:
    value = _value(event, "daily_peak_pct", default=None)
    if value is None:
        return ""
    try:
        peak_value = abs(float(value))
    except (TypeError, ValueError):
        return f"daily peak was <b>{escape(str(value))}</b>"

    direction = str(_value(event, "direction", default="LONG")).strip().upper()
    if direction == "SHORT":
        peak_value = -peak_value

    return f"daily peak was <b>{peak_value:+.2f}%</b>"


def _number(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.8f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return escape(str(value))


def _usd(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return escape(str(value))


def _compact_usd(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return escape(str(value))

    abs_amount = abs(amount)
    if abs_amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if abs_amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if abs_amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:.0f}"


def _format_duration(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return str(value)

    if seconds < 60:
        return f"{seconds} sec"

    minutes, rem_seconds = divmod(seconds, 60)
    if minutes < 60:
        if rem_seconds == 0:
            return f"{minutes} min"
        return f"{minutes} min {rem_seconds} sec"

    hours, rem_minutes = divmod(minutes, 60)
    if rem_minutes == 0:
        return f"{hours} h"
    return f"{hours} h {rem_minutes} min"


def _direction_style(event: EventLike) -> tuple[str, str]:
    direction = str(_value(event, "direction", default="LONG")).strip().upper()
    if direction == "SHORT":
        return SHORT_EMOJI, "SHORT"
    return LONG_EMOJI, "LONG"


def _value(event: EventLike, *names: str, default: Any = None) -> Any:
    data = _to_mapping(event)
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return default


def _to_mapping(event: EventLike) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)
    if is_dataclass(event):
        return asdict(event)
    if hasattr(event, "__dict__"):
        return vars(event)
    return {}
