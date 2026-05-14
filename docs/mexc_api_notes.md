# MEXC WebSocket API — справка для парсера

Собрано из публичной документации MEXC. Используется как референс при разработке спот↔фьюч спред-детектора.

---

## Краткая шпаргалка: спот vs фьюч

| | Спот | Фьюч |
|---|---|---|
| Base URL | `wss://wbs-api.mexc.com/ws` | `wss://contract.mexc.com/edge` |
| Канал «все тикеры» | `spot@public.miniTickers.v3.api.pb@24H` | `sub.tickers` |
| Формат входящих | Protocol Buffers (бинарь) | JSON (по умолчанию gzip!) |
| Частота пушей | каждые 3 сек | каждые 2 сек |
| Символ | `BTCUSDT` (без разделителя) | `BTC_USDT` (с подчёркиванием) |
| Объём в USDT — поле | `volume` | `amount24` |
| Ping | `{"method": "PING"}` | `{"method": "ping"}` |
| Лимит соединения | 24 часа max | не указан |
| Лимит подписок | 30 на одно WS | не указан |

> **Внимание:** регистр методов отличается — спот в UPPERCASE, фьюч в lowercase. Легко получить баг от копипасты.

---

## СПОТ

### Подключение

- **Base URL:** `wss://wbs-api.mexc.com/ws`
- **Время жизни соединения:** не более 24 часов — нужен проактивный reconnect примерно раз в 23 часа
- **Лимит подписок:** до 30 на одно WS-соединение
- **Auto-disconnect:**
  - 30 сек без валидной подписки → сервер сам отключит
  - 1 мин без потока данных → сервер сам отключит
  - Клиент может слать ping чтобы держать соединение
- **Символы** в названиях каналов всегда в UPPERCASE

### Канал MiniTickers (наш основной)

Стрим тикеров **по всем парам сразу** в указанной таймзоне. Push каждые 3 секунды.

**Допустимые таймзоны:** `24H, UTC-10, UTC-8, UTC-7, ..., UTC+13`
**Используем `24H`** — это rolling 24 часа от текущего момента (нужно подтвердить на боевом подключении).

**Подписка:**
```json
{
  "method": "SUBSCRIPTION",
  "params": ["spot@public.miniTickers.v3.api.pb@UTC+8"]
}
```

**Ответ** (Protocol Buffers → декодированный в JSON):
```json
{
  "channel": "spot@public.miniTickers.v3.api.pb@UTC+8",
  "sendTime": "1755076614201",
  "publicMiniTickers": {
    "items": [
      {
        "symbol": "METAUSDT",
        "price": "0.055",
        "rate": "-0.2361",
        "zonedRate": "-0.2361",
        "high": "0.119",
        "low": "0.053",
        "volume": "814864.474",
        "quantity": "10764997.16",
        "lastCloseRate": "-0.2567",
        "lastCloseZonedRate": "-0.2567",
        "lastCloseHigh": "0.119",
        "lastCloseLow": "0.053"
      }
    ]
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|---|---|---|
| `symbol` | string | Имя пары |
| `price` | string | Последняя цена |
| `rate` | string | % изменения цены (UTC+8) |
| `zonedRate` | string | % изменения (local timezone) |
| `high` / `low` | string | Roll high/low |
| `volume` | string | **Объём в quote (USDT) — это нам нужно** |
| `quantity` | string | Объём в base (монетах) |
| `lastClose*` | string | Аналоги по previous close |

> **Гочча:** `volume` (turnover) и `quantity` (volume в монетах) названы контринтуитивно. Для фильтра ликвидности `MIN_VOLUME_24H_USD` нужен `volume`.

### Канал MiniTicker (одиночный, нам НЕ подходит)

Тот же формат, но **на один указанный символ**. В подписке символ зашит в канал: `...@MXUSDT@UTC+8`. Не используем — из-за лимита 30 подписок на WS пришлось бы держать много соединений.

### Protocol Buffers — что это и зачем

**Спот стримит бинарь, не JSON.** Признак: в названии канала есть `.pb` (`spot@public.miniTickers.v3.api.pb@24H`).

Как работает:
1. У MEXC есть `.proto` файлы (схемы данных) — репо: https://github.com/mexcdevelop/websocket-proto
2. Через утилиту `protoc` компилируем их в Python-код — получаем сгенерированные классы вроде `PushDataV3ApiWrapper_pb2.py`
3. В рантайме: получили байты → распарсили в python-объект через сгенерированный класс

Команда генерации:
```bash
protoc *.proto --python_out=<путь>
```

Пример использования в Python:
```python
import PushDataV3ApiWrapper_pb2

result = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
result.ParseFromString(serializedData)
```

В коде парсера это будет отдельный модуль `proto_decoder.py` (или подобное), который превращает входящие байты в нормализованную структуру.

### Подписка / Отписка

**Subscribe:**
```json
{"method": "SUBSCRIPTION", "params": ["<channel>"]}
```

**Ответ на subscribe:**
```json
{"id": 0, "code": 0, "msg": "<channel>"}
```

**Unsubscribe:**
```json
{"method": "UNSUBSCRIPTION", "params": ["<channel>"]}
```

### Ping / Pong

**Запрос (клиент → сервер):**
```json
{"method": "PING"}
```

**Ответ (сервер → клиент):**
```json
{"id": 0, "code": 0, "msg": "PONG"}
```

---

## ФЬЮЧЕРС

### Подключение

- **Base URL:** `wss://contract.mexc.com/edge`
- **Формат:** JSON, **но по умолчанию сжат gzip!**
- **Disconnect:** если клиент не прислал ping в течение 1 минуты — сервер закроет соединение. Рекомендуется ping каждые 10–20 сек

### GZIP — критичная деталь

**По умолчанию сервер шлёт ответы сжатые gzip.** Если просто подписаться без флага — `json.loads()` упадёт на бинарных байтах.

Два решения:
- **Простое:** добавлять `"gzip": false` в каждую подписку → сервер шлёт plain text JSON
- **Правильное:** принимать gzip и разжимать через `gzip` либу Python

**Для проекта используем `gzip: false`** — нагрузка не та чтоб экономить трафик.

### Канал Tickers (наш основной)

Стрим тикеров **по всем перпам сразу**. Push каждые 2 секунды.

**Подписка:**
```json
{
  "method": "sub.tickers",
  "param": {},
  "gzip": false
}
```

**Unsubscribe:**
```json
{"method": "unsub.tickers", "param": {}}
```

**Ответ:**
```json
{
  "channel": "push.tickers",
  "data": [
    {
      "fairPrice": 183.01,
      "lastPrice": 183,
      "riseFallRate": -0.0708,
      "symbol": "BSV_USDT",
      "volume24": 200,
      "maxBidPrice": 7073.42,
      "minAskPrice": 6661.37
    }
  ]
}
```

**Описание полей:**

| Поле | Тип | Описание |
|---|---|---|
| `symbol` | string | Контракт (формат `BASE_QUOTE`) |
| `timestamp` | long | Trade time |
| `lastPrice` | decimal | Последняя цена |
| `volume24` | decimal | **Объём в контрактах — НЕ USDT!** |
| `amount24` | decimal | **Оборот в quote (USDT) — это нам нужно** |
| `riseFallRate` | decimal | % изменения |
| `fairPrice` | decimal | Fair price |
| `indexPrice` | decimal | Index price |
| `maxBidPrice` / `minAskPrice` | decimal | Max bid / Min ask |
| `lower24Price` / `high24Price` | decimal | 24h low / high |

> **Опасная гочча:** `volume24` — это **количество контрактов**, не USDT. В перпах 1 контракт ≠ 1 монета (у каждого свой contract size). Для фильтра ликвидности использовать **`amount24`**.
> **Проблема:** в примере ответа `amount24` не показан. Возможно приходит не всегда. **Проверить на боевом подключении в первую очередь.**

### Канал Ticker (одиночный, нам НЕ подходит)

Аналог по структуре, но на один символ:
```json
{"method": "sub.ticker", "param": {"symbol": "BTC_USDT"}}
```

Не используем — нам нужны все пары сразу.

### Ping / Pong

**Запрос:**
```json
{"method": "ping"}
```

**Ответ:**
```json
{"channel": "pong", "data": 1587453241453}
```

Рекомендация MEXC: ping каждые 10–20 сек. Если ping от клиента не пришёл за минуту — сервер закроет соединение.

---

## Сводка известных проблемных мест («гочч»)

1. **Спот → бинарный Protocol Buffers, фьюч → JSON.** Два разных пути декодинга в коде.
2. **Фьюч JSON по умолчанию сжат gzip.** Передавать `"gzip": false` в каждой подписке.
3. **Разные регистры методов:** спот `PING` / `SUBSCRIPTION`, фьюч `ping` / `sub.tickers`.
4. **Разный формат символов:** `BTCUSDT` (спот) vs `BTC_USDT` (фьюч). Понадобится нормализация в матчинге пар.
5. **Названия полей объёма противоречат интуиции.** Спот: `volume` (USDT) / `quantity` (монеты). Фьюч: `amount24` (USDT) / `volume24` (контракты).
6. **Спот: 24-часовой лимит на соединение.** Нужен проактивный reconnect.
7. **Спот: лимит 30 подписок на WS.** Нам это не критично т.к. подписываемся на один канал «все пары».
8. **Спот: проверить что `24H` в подписке MiniTickers действительно даёт rolling 24h** (а не суточный сброс).
9. **Фьюч: проверить что `amount24` реально приходит в каждом push.** В примере его нет.

---

## Источники

- MEXC Spot API v3 docs: https://www.mexc.com/api-docs/spot-v3/introduction
- MEXC Spot WebSocket Market Streams: https://www.mexc.com/api-docs/spot-v3/websocket-market-streams
- MEXC Futures API docs: https://www.mexc.com/api-docs/futures/update-log
- MEXC Protobuf schemas: https://github.com/mexcdevelop/websocket-proto
