### stock_price

Цены активов с MOEX

Структура таблицы:

```sql
CREATE TABLE stock_price (
    "id" BIGSERIAL PRIMARY KEY,
    "ticker" VARCHAR(20) NOT NULL,
    "begin" TIMESTAMP NOT NULL,
    "end" TIMESTAMP NOT NULL,
    "open" NUMERIC(18, 4) NOT NULL,
    "close" NUMERIC(18, 4) NOT NULL,
    "high" NUMERIC(18, 4) NOT NULL,
    "low" NUMERIC(18, 4) NOT NULL,
    "value" NUMERIC(18, 2),
    "volume" BIGINT NOT NULL,
    "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_ticker_begin UNIQUE ("ticker", "begin")
);

CREATE INDEX idx_stock_price_ticker ON stock_price("ticker");
CREATE INDEX idx_stock_price_begin ON stock_price("begin");
```

Описание полей:

Поле|Описание
---|---
id | ID
ticker | Тикер бумаги на MOEX
begin | Начало свечи
end | Окончание свечи
open | Цена открытия за период (в рублях)
close | Цена закрытия за период (в рублях)
high | Максимальная цена за период (в рублях)
low | Минимальная цена за период (в рублях)
value | Общая стоимость сделок за период (оборот в рублях)
volume | Объем торгов за период (количество ценных бумаг)
created_at | Время создания записи в БД
