import asyncio
from enum import IntEnum, StrEnum

import aiohttp
import pandas as pd
from aiomoex import get_board_candles
from pandas.core.frame import DataFrame


class Interval(IntEnum):
    """MOEX API candle intervals"""

    MINUTE_1 = 1
    MINUTE_10 = 10
    HOUR_1 = 60
    DAY_1 = 24
    WEEK_1 = 7
    MONTH_1 = 31


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
        interval: int,
        start_date: str,
        end_date: str,
    ) -> dict[str, pd.DataFrame]:
        """
        Извлекает свечи по тикеру

        Args:
            session: aiohttp client session
            ticker: Тикер
            interval: Интервал
            start_date: Начальная дата в формате "YYYY-MM-DD"
            end_date: Конечная дата в формате "YYYY-MM-DD"

        Returns:
            {<ticker>: <candles DataFrame>}
        """
        try:
            res = await get_board_candles(session, ticker, interval, start_date, end_date)
            if res:
                df = pd.DataFrame(res)

                if 'end' in df.columns:
                    df = df.drop('end', axis=1)

                df['begin'] = pd.to_datetime(df['begin'])

                # Normalize datetime for daily, weekly, monthly intervals
                if interval in [Interval.DAY_1, Interval.WEEK_1, Interval.MONTH_1]:
                    df['begin'] = df['begin'].dt.normalize()

                # Reorder columns: begin first
                if 'begin' in df.columns:
                    cols = ['begin'] + [col for col in df.columns if col != 'begin']
                    df: DataFrame = df[cols]

                df['ticker'] = ticker
                return {ticker: df}
            else:
                return {ticker: pd.DataFrame()}
        except Exception as e:
            print(f'Ошибка парсинга. Не удалось получить данные для {ticker}: {e}')
            return {ticker: pd.DataFrame()}

    async def get_data(
        self,
        tickers: list[Ticker],
        start_date: str,
        end_date: str,
        interval: int = Interval.DAY_1,
    ) -> dict[str, pd.DataFrame]:
        """
        Извлекает свечи из MOEX сразу по нескольку тикеров.

        Args:
            tickers: Список тикеров
            start_date: Начальная дата в формате "YYYY-MM-DD"
            end_date: Конечная дата в формате "YYYY-MM-DD"
            interval: Интервал

        Returns:
            Словарь тикер -> свечи
        """
        if interval not in list(Interval):
            raise ValueError(f'Неверный интервал. Допустимые значения: {[i.value for i in Interval]}')

        async with aiohttp.ClientSession() as session:
            coros = [self._fetch_ticker_data(session, ticker, interval, start_date, end_date) for ticker in tickers]
            stock_data = await asyncio.gather(*coros)

        stock_data_dict = {k: v for d in stock_data for k, v in d.items()}
        return stock_data_dict
