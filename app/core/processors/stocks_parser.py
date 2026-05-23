from datetime import datetime, timedelta

import aiohttp
import pandas as pd

from app.core.clients.moex import Boards, Engines, Interval, Markets, MOEXClient, Ticker

DATE_START = datetime(2022, 5, 1)


class StocksParser:
    """Парсит данные из MOEX"""

    def __init__(
        self,
        date_start=DATE_START,
        date_end=None,
        interval=Interval.DAY_1,
    ) -> None:
        self.moex_client = MOEXClient()
        self.date_start = date_start
        self.date_end = date_end or datetime.now()
        self.interval = interval

    async def parse(self):
        """
        Парсит данные из MOEX, возвращает словарь {тикер -> df}.
        Для нефти объединяет несколько фьючерсов, чтобы получить непрервыную стоимость
        """
        stocks = await self.parse_stocks()
        currencies = await self.parse_currencies()
        imoex = await self.parse_imoex()
        gold = await self.parse_gold()
        brent = await self.parse_brent()
        return {**stocks, **currencies, **imoex, **gold, **brent}

    async def parse_stocks(self):
        return await self.moex_client.get_data(
            tickers=[Ticker.Gazprom, Ticker.Rosneft, Ticker.Lukoil, Ticker.Sber],
            engine=Engines.STOCK,
            market=Markets.SHARES,
            board=Boards.TQBR,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )

    async def parse_currencies(self):
        return await self.moex_client.get_data(
            tickers=[Ticker.USDRUBf, Ticker.EURRUBf, Ticker.CNYRUBf],
            engine=Engines.FUTURES,
            market=Markets.FORTS,
            board=Boards.RFUD,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )

    async def parse_imoex(self):
        return await self.moex_client.get_data(
            tickers=[Ticker.IMOEX],
            engine=Engines.STOCK,
            market=Markets.INDEX,
            board=Boards.RFUD,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )

    async def parse_gold(self):
        return await self.moex_client.get_data(
            tickers=[Ticker.GLDRUB],
            engine=Engines.CURRENCY,
            market=Markets.SELT,
            board=Boards.CETS,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )

    async def parse_brent(self):
        """Функция для парсинга цен на нефть Brent.
        Для Brent на MOEX нет вечного фьючерса, поэтому склеиваем цены фьючерсов, ограниченных по времени.
        """
        futures_meta = await self.get_brent_futures_metadata()

        tickers = futures_meta['ticker'].tolist()

        prices = await self.moex_client.get_data(
            tickers=tickers,
            engine=Engines.FUTURES,
            market=Markets.FORTS,
            board=Boards.RFUD,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )
        return await self.build_brent_continuous(self.date_start, self.date_end, prices, futures_meta, roll_window=5)

    async def get_brent_prices(self):
        futures_meta = await self.get_brent_futures_metadata()

        tickers = futures_meta['ticker'].tolist()

        return await self.moex_client.get_data(
            tickers=tickers,
            engine=Engines.FUTURES,
            market=Markets.FORTS,
            board=Boards.RFUD,
            start_date=self.date_start,
            end_date=self.date_end,
            interval=self.interval,
        )

    @staticmethod
    def generate_all_brent_tickers(start_year=2022, end_year=2026):
        month_codes = {
            1: 'F',
            2: 'G',
            3: 'H',
            4: 'J',
            5: 'K',
            6: 'M',
            7: 'N',
            8: 'Q',
            9: 'U',
            10: 'V',
            11: 'X',
            12: 'Z',
        }
        year_codes = {2022: '2', 2023: '3', 2024: '4', 2025: '5', 2026: '6', 2027: '7', 2028: '8', 2029: '9'}

        tickers = []
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                ticker = f'BR{month_codes[month]}{year_codes[year]}'
                expiry_date = pd.Timestamp(year=year, month=month, day=1)
                tickers.append({'ticker': ticker, 'expiry': expiry_date})

        return pd.DataFrame(tickers)

    async def get_brent_futures_metadata(self):
        url = 'https://iss.moex.com/iss/engines/futures/markets/forts/boards/RFUD/securities.json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()

        securities = data['securities']
        df_active = pd.DataFrame(securities['data'], columns=securities['columns'])
        df_active = df_active[df_active['SECID'].str.startswith('BR') & ~df_active['SECID'].str.startswith('BRM')]
        df_active['LASTTRADEDATE'] = pd.to_datetime(df_active['LASTTRADEDATE'])
        df_active = df_active[['SECID', 'LASTTRADEDATE']].rename(columns={'SECID': 'ticker', 'LASTTRADEDATE': 'expiry'})
        df_active = df_active.dropna()

        df_all = self.generate_all_brent_tickers(self.date_start.year, self.date_end.year)

        for idx, row in df_active.iterrows():
            mask = df_all['ticker'] == row['ticker']
            if mask.any():
                df_all.loc[mask, 'expiry'] = row['expiry']

        return df_all.sort_values('expiry').reset_index(drop=True)

    def count_trading_days(self, start_date, end_date):
        if pd.isna(start_date) or pd.isna(end_date):
            return 0
        if isinstance(start_date, pd.Timestamp):
            start_date = start_date.date()
        if isinstance(end_date, pd.Timestamp):
            end_date = end_date.date()

        trading_days = 0
        current = start_date
        while current < end_date:
            if current.weekday() < 5:
                trading_days += 1
            current += timedelta(days=1)
        return trading_days

    def select_contract(self, timestamp_t, futures_meta, all_data, roll_window=5):
        """
        Select the nearest-expiring futures contract for a given timestamp,
        subject to a minimum roll window in trading days.

        Parameters
        ----------
        timestamp_t : datetime-like
            The timestamp at which we want a contract (e.g. bar time).
        futures_meta : pd.DataFrame
            Must contain columns:
                - 'ticker' : str
                - 'expiry' : datetime64[ns] or convertible to datetime
            One row per contract.
        all_data : dict[str, pd.DataFrame]
            Mapping from ticker -> DataFrame with at least:
                - 'begin' : datetime64[ns] (bar start time)
        roll_window : int
            Minimum number of trading days to expiry to allow using this contract.

        Returns
        -------
        str | None
            Selected contract ticker, or None if no suitable contract has data
            at the given timestamp.
        """

        # Normalize timestamp
        timestamp_t = pd.Timestamp(timestamp_t)

        # Work in date space for roll logic
        date_t = timestamp_t.date()
        # Don't include contracts that expire more than 3 months from now
        date_t_max = date_t + timedelta(days=90)

        # Ensure expiry is proper datetime64[ns]
        futures_meta = futures_meta.copy()
        futures_meta['expiry'] = pd.to_datetime(futures_meta['expiry'])

        # Convert date_t and date_t_max to Timestamp so types match expiry (datetime64[ns])
        start_ts = pd.to_datetime(date_t)  # midnight of current date
        end_ts = pd.to_datetime(date_t_max)  # midnight of max date

        # Contracts whose expiry is strictly after current date and before date_t_max
        available = futures_meta.loc[(futures_meta['expiry'] > start_ts) & (futures_meta['expiry'] < end_ts)].copy()

        if available.empty:
            return None

        # Compute days to expiry for each contract using trading days
        # Here we go back to pure `date` for count_trading_days
        available['days_to_expiry'] = available['expiry'].dt.date.apply(lambda d: self.count_trading_days(date_t, d))

        # Keep only contracts that satisfy the roll_window constraint
        candidates = available.loc[available['days_to_expiry'] >= roll_window]
        if candidates.empty:
            return None

        # Sort so the nearest expiry (smallest days_to_expiry) is considered first
        candidates = candidates.sort_values(['days_to_expiry', 'expiry'])

        def has_bar_at_timestamp(ticker: str) -> bool:
            """Check that the given contract has data at timestamp_t."""
            df = all_data.get(ticker)
            if df is None or df.empty:
                return False
            return not df.loc[df['begin'] == timestamp_t].empty

        # Choose the nearest-expiring candidate that actually has a bar at this time
        for ticker in candidates['ticker']:
            if has_bar_at_timestamp(ticker):
                return ticker

        # No candidate contract had data at this timestamp
        return None

    async def build_brent_continuous(self, start_date, end_date, all_data, futures_meta, roll_window=5):
        print(f'\nBuilding continuous series (roll_window={roll_window})...')
        all_timestamps = pd.date_range(start=start_date, end=end_date, freq='H')
        trading_timestamps = [ts for ts in all_timestamps if ts.weekday() < 5]

        rows = []
        missing_data_count = 0

        for timestamp_t in trading_timestamps:
            ticker = self.select_contract(timestamp_t, futures_meta, all_data, roll_window)

            if ticker:
                contract_data = all_data[ticker]
                ts_data = contract_data[contract_data['begin'] == timestamp_t]
                row = ts_data.iloc[0]
                expiry = futures_meta[futures_meta['ticker'] == ticker]['expiry'].iloc[0]
                rows.append(
                    {
                        'begin': timestamp_t,
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row['volume'],
                        'value': row['value'],
                        'ticker': ticker,
                        'expiry': expiry,
                        'days_to_expiry': self.count_trading_days(timestamp_t.date(), expiry.date()),
                    }
                )
            else:
                missing_data_count += 1

        df = pd.DataFrame(rows)
        print(f'\n✓ Generated {len(df)} data points from {df["begin"].min()} to {df["begin"].max()}')
        if missing_data_count > 0:
            print(f'⚠ Missing {missing_data_count} timestamps (no contract had data)')
        return df
