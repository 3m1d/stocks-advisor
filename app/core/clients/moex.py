import asyncio
from datetime import datetime
from enum import IntEnum, StrEnum

import aiohttp
import pandas as pd
from aiomoex import get_board_candles


class Interval(IntEnum):
    """MOEX API candle intervals"""

    MINUTE_1 = 1
    MINUTE_10 = 10
    HOUR_1 = 60
    DAY_1 = 24
    WEEK_1 = 7
    MONTH_1 = 31


class Engines(StrEnum):
    """https://iss.moex.com/iss/engines"""

    STOCK = 'stock'  # Фондовый рынок и рынок депозитов
    STATE = 'state'  # Рынок ГЦБ (размещение)
    CURRENCY = 'currency'  # Валютный рынок
    FUTURES = 'futures'  # Срочный рынок
    COMMODITY = 'commodity'  # Товарный рынок
    INTERVENTIONS = 'interventions'  # Товарные интервенции
    OFFBOARD = 'offboard'  # ОТС-система
    AGR = 'agro'  # Агро
    OTC = 'otc'  # ОТС с ЦК
    QUOTES = 'quotes'  # Квоты
    MONEY = 'money'  # Денежный рынок


class Markets(StrEnum):
    """https://iss.moex.com/iss/engines/<engine>/markets"""

    # engine=stock
    SHARES = 'shares'  # Акции
    BONDS = 'bonds'  # Облигации

    # engine=currency
    OTCINDICES = 'otcindices'  # Внебиржевые индексы
    SELT = 'selt'  # Биржевые сделки с ЦК
    FUTURES = 'futures'  # Поставочные фьючерсы
    INDEX = 'index'  # Валютный фиксинг
    OTC = 'otc'  # Внебиржевой

    # engine=futures
    FORTS = 'forts'  # Фьючерсы
    OPTIONS = 'options'  # Опционы
    FORTSIQS = 'fortsiqs'  # Фьючерсы IQS
    OPTIONSIQS = 'optionsiqs'  # Опционы IQS
    MAIN = 'main'  # Срочные инструменты


class Boards(StrEnum):
    """https://iss.moex.com/iss/engines/<engine>/markets/<market>/boards"""

    # engine=currency, market=selt
    TQBR = 'TQBR'  # Фондовый рынок
    AUCB = 'AUCB'  # Аукцион ЦБР - адрес.
    CETS = 'CETS'  # Системные сделки - безадрес.
    CNGD = 'CNGD'  # Внесистемные сделки- адрес.
    CURR = 'CURR'  # Дневная сессия
    FIXN = 'FIXN'  # Фиксинг внесистемный- адрес.
    FIXS = 'FIXS'  # Фиксинг системный - безадрес.
    LICU = 'LICU'  # Внесистемные сделки урегулирования - безадрес.
    SDBP = 'SDBP'  # Крупные сделки - безадрес.
    SPEC = 'SPEC'  # Поставка - безадресные
    WAPN = 'WAPN'  # Внесистемные средневзвешенные - адрес.
    WAPS = 'WAPS'  # Системные средневзвешенные - безадрес.

    # engine=futures, market=forts
    RFUD = 'RFUD'  # Фьючерсы


# объявим аннотацию для удобства
StockData = list[dict[str, str | int | float]]


INTERVAL_DESCRIPTIONS: dict[Interval, str] = {
    Interval.MINUTE_1: '1 минута',
    Interval.MINUTE_10: '10 минут',
    Interval.HOUR_1: '1 час',
    Interval.DAY_1: '1 день',
    Interval.WEEK_1: '1 неделя',
    Interval.MONTH_1: '1 месяц',
}


class Ticker(StrEnum):
    Sber = 'SBER'
    Yandex = 'YDEX'
    YandexOld = 'YNDX'
    Gazprom = 'GAZP'
    Lukoil = 'LKOH'
    Rosneft = 'ROSN'
    VTB = 'VTBR'
    Tatneft = 'TATN'
    NorNickel = 'GMKN'


class MOEXClient:
    """Асинхронный клиент MOEX (Московская Биржа)"""

    async def _fetch_ticker_data(
        self,
        session: aiohttp.ClientSession,
        ticker: Ticker | str,
        board: Boards,
        engine: Engines,
        market: Markets,
        start_date: str,
        end_date: str,
        interval: int,
    ) -> dict[str, pd.DataFrame]:
        """
        Парсит свечи по тикеру из MOEX

        Args:
            session: aiohttp client session
            ticker: Тикер
            engine: Engine
            market: Market
            board: Board
            start_date: Дата начала парсинга
            end_date: Дата окончания парсинга
            interval: Интервал

        Returns:
            Словарь тикер -> свечи
        """
        try:
            # получаем данные по переданному тикеру за указанный период
            res = await get_board_candles(
                session,
                ticker,
                interval,
                start_date,
                end_date,
                board=board.value,
                market=market.value,
                engine=engine.value,
            )
            if res:
                df = pd.DataFrame(res)

                df['begin'] = pd.to_datetime(df['begin'])
                df['end'] = pd.to_datetime(df['end'])
                df['ticker'] = ticker
                return {ticker: df}
            else:
                return {ticker: pd.DataFrame()}
        except Exception as e:
            print(f'Ошибка парсинга. Не удалось получить данные для {ticker}, {e}')
            return {ticker: pd.DataFrame()}

    async def get_data(
        self,
        tickers: list[Ticker],
        engine: Engines,
        market: Markets,
        board: Boards,
        start_date: datetime,
        end_date: datetime | None = None,
        interval: int = Interval.DAY_1,
    ) -> dict[str, pd.DataFrame]:
        """
        Парсит свечи из MOEX сразу по нескольку тикеров.

        Args:
            tickers: Список тикеров
            engine: Engine
            market: Market
            board: Board
            start_date: Дата начала парсинга
            end_date: Дата окончания парсинга (по умолчанию - текущее время)
            interval: Интервал

        Returns:
            Словарь тикер -> свечи
        """
        if end_date is None:
            end_date = datetime.now()

        if interval not in Interval:
            raise ValueError(f'Неверный интервал. Допустимые значения: {Interval}')

        end_date_formatted = end_date.strftime('%Y-%m-%d %H:%M:%S')
        start_date_formatted = start_date.strftime('%Y-%m-%d %H:%M:%S')

        # Увеличиваем таймауты для MOEX API
        timeout = aiohttp.ClientTimeout(
            connect=30,  # время подключения
            sock_read=60,  # время чтения данных
            total=120,  # общий таймаут
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            coros = [
                self._fetch_ticker_data(
                    session,
                    ticker,
                    board,
                    engine,
                    market,
                    start_date_formatted,
                    end_date_formatted,
                    interval,
                )
                for ticker in tickers
            ]
            stock_data = await asyncio.gather(*coros)

        # разворачиваем список словарей в один словарь
        stock_data = {ticker: data for element in stock_data for ticker, data in element.items()}
        return stock_data
