import pandas as pd
import numpy as np
from typing import Optional
import ta


class FeatureGenerator:
    """Feature generator for stock price data."""
    
    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all technical indicators from OHLCV data.
        
        Args:
            df: DataFrame with columns ['begin', 'open', 'high', 'low', 'close', 'volume']
                Must be sorted by 'begin'
        
        Returns:
            DataFrame with original data + generated features
        """
        if df.empty:
            return df
        
        # Создаем копию и конвертируем begin в datetime если это строка
        df_processed = df.copy()
        if df_processed['begin'].dtype == 'object':
            df_processed['begin'] = pd.to_datetime(df_processed['begin'])
        
        df_processed = df_processed.sort_values('begin')
        
        # ===== 1. MOVING AVERAGES =====
        df_processed['MA_20'] = df_processed['close'].rolling(window=20).mean()
        df_processed['MA_50'] = df_processed['close'].rolling(window=50).mean()
        df_processed['MA_90'] = df_processed['close'].rolling(window=90).mean()
        df_processed['MA_200'] = df_processed['close'].rolling(window=200).mean()
        
        df_processed['EMA_20'] = df_processed['close'].ewm(span=20).mean()
        df_processed['EMA_50'] = df_processed['close'].ewm(span=50).mean()
        df_processed['EMA_90'] = df_processed['close'].ewm(span=90).mean()
        df_processed['EMA_200'] = df_processed['close'].ewm(span=200).mean()
        
        df_processed['WMA_20'] = df_processed['close'].rolling(window=20).apply(
            lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True
        )
        df_processed['WMA_50'] = df_processed['close'].rolling(window=50).apply(
            lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True
        )
        df_processed['WMA_90'] = df_processed['close'].rolling(window=90).apply(
            lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True
        )
        df_processed['WMA_200'] = df_processed['close'].rolling(window=200).apply(
            lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True
        )
        
        # ===== 2. RSI =====
        df_processed['RSI_7'] = ta.momentum.RSIIndicator(df_processed['close'], window=7).rsi()
        df_processed['RSI_14'] = ta.momentum.RSIIndicator(df_processed['close'], window=14).rsi()
        df_processed['RSI_90'] = ta.momentum.RSIIndicator(df_processed['close'], window=90).rsi()
        
        # ===== 3. MOMENTUM =====
        df_processed['MOM_10'] = ta.momentum.ROCIndicator(df_processed['close'], window=5).roc()
        df_processed['MOM_20'] = ta.momentum.ROCIndicator(df_processed['close'], window=10).roc()
        df_processed['MOM_50'] = ta.momentum.ROCIndicator(df_processed['close'], window=20).roc()
        df_processed['MOM_200'] = ta.momentum.ROCIndicator(df_processed['close'], window=200).roc()
        
        # ===== 4. VOLATILITY =====
        returns = df_processed['close'].pct_change()
        df_processed['VOLATILITY_10'] = returns.rolling(window=10).std() * np.sqrt(252)
        df_processed['VOLATILITY_20'] = returns.rolling(window=20).std() * np.sqrt(252)
        df_processed['VOLATILITY_50'] = returns.rolling(window=50).std() * np.sqrt(252)
        df_processed['VOLATILITY_200'] = returns.rolling(window=200).std() * np.sqrt(252)
        
        # ===== 5. ATR =====
        df_processed['ATR_7'] = ta.volatility.AverageTrueRange(
            df_processed['high'], df_processed['low'], df_processed['close'], window=7
        ).average_true_range()
        df_processed['ATR_14'] = ta.volatility.AverageTrueRange(
            df_processed['high'], df_processed['low'], df_processed['close'], window=14
        ).average_true_range()
        df_processed['ATR_200'] = ta.volatility.AverageTrueRange(
            df_processed['high'], df_processed['low'], df_processed['close'], window=200
        ).average_true_range()
        
        # ===== 6. MACD =====
        macd = ta.trend.MACD(df_processed['close'])
        df_processed['MACD'] = macd.macd()
        df_processed['MACD_SIGNAL'] = macd.macd_signal()
        df_processed['MACD_HISTOGRAM'] = macd.macd_diff()
        
        # ===== 7. VOLUME =====
        df_processed['VOLUME_RATIO_20'] = (
            df_processed['volume'] / df_processed['volume'].rolling(window=20).mean()
        )
        df_processed['VOLUME_RATIO_50'] = (
            df_processed['volume'] / df_processed['volume'].rolling(window=50).mean()
        )
        df_processed['VOLUME_RATIO_200'] = (
            df_processed['volume'] / df_processed['volume'].rolling(window=200).mean()
        )
        
        # ===== 8. PRICE RETURNS =====
        df_processed['RETURN_1D'] = df_processed['close'].pct_change(5)
        df_processed['RETURN_1W'] = df_processed['close'].pct_change(20)
        df_processed['RETURN_1M'] = df_processed['close'].pct_change(40)
        
        # ===== 9. DERIVATIVE FEATURES =====
        # MA-EMA differences
        df_processed['MA_EMA_DIFF_20'] = df_processed['MA_20'] - df_processed['EMA_20']
        df_processed['MA_EMA_DIFF_50'] = df_processed['MA_50'] - df_processed['EMA_50']
        df_processed['MA_EMA_DIFF_90'] = df_processed['MA_90'] - df_processed['EMA_90']
        df_processed['MA_EMA_DIFF_200'] = df_processed['MA_200'] - df_processed['EMA_200']
        
        # MA-WMA differences
        df_processed['MA_WMA_DIFF_20'] = df_processed['MA_20'] - df_processed['WMA_20']
        df_processed['MA_WMA_DIFF_50'] = df_processed['MA_50'] - df_processed['WMA_50']
        df_processed['MA_WMA_DIFF_90'] = df_processed['MA_90'] - df_processed['WMA_90']
        df_processed['MA_WMA_DIFF_200'] = df_processed['MA_200'] - df_processed['WMA_200']
        
        # EMA-WMA differences
        df_processed['EMA_WMA_DIFF_20'] = df_processed['EMA_20'] - df_processed['WMA_20']
        df_processed['EMA_WMA_DIFF_50'] = df_processed['EMA_50'] - df_processed['WMA_50']
        df_processed['EMA_WMA_DIFF_90'] = df_processed['EMA_90'] - df_processed['WMA_90']
        df_processed['EMA_WMA_DIFF_200'] = df_processed['EMA_200'] - df_processed['WMA_200']
        
        # MA-EMA ratios
        df_processed['MA_EMA_RATIO_20'] = df_processed['MA_20'] / df_processed['EMA_20']
        df_processed['MA_EMA_RATIO_50'] = df_processed['MA_50'] / df_processed['EMA_50']
        df_processed['MA_EMA_RATIO_90'] = df_processed['MA_90'] / df_processed['EMA_90']
        df_processed['MA_EMA_RATIO_200'] = df_processed['MA_200'] / df_processed['EMA_200']
        
        # MA period differences
        df_processed['MA_DIFF_20_50'] = df_processed['MA_20'] - df_processed['MA_50']
        df_processed['MA_DIFF_20_90'] = df_processed['MA_20'] - df_processed['MA_90']
        df_processed['MA_DIFF_50_90'] = df_processed['MA_50'] - df_processed['MA_90']
        df_processed['MA_DIFF_20_200'] = df_processed['MA_20'] - df_processed['MA_200']
        df_processed['MA_DIFF_50_200'] = df_processed['MA_50'] - df_processed['MA_200']
        
        # EMA period differences
        df_processed['EMA_DIFF_20_50'] = df_processed['EMA_20'] - df_processed['EMA_50']
        df_processed['EMA_DIFF_20_90'] = df_processed['EMA_20'] - df_processed['EMA_90']
        df_processed['EMA_DIFF_50_90'] = df_processed['EMA_50'] - df_processed['EMA_90']
        df_processed['EMA_DIFF_20_200'] = df_processed['EMA_20'] - df_processed['EMA_200']
        df_processed['EMA_DIFF_50_200'] = df_processed['EMA_50'] - df_processed['EMA_200']
        
        # WMA period differences
        df_processed['WMA_DIFF_20_50'] = df_processed['WMA_20'] - df_processed['WMA_50']
        df_processed['WMA_DIFF_20_90'] = df_processed['WMA_20'] - df_processed['WMA_90']
        df_processed['WMA_DIFF_50_90'] = df_processed['WMA_50'] - df_processed['WMA_90']
        df_processed['WMA_DIFF_20_200'] = df_processed['WMA_20'] - df_processed['WMA_200']
        df_processed['WMA_DIFF_50_200'] = df_processed['WMA_50'] - df_processed['WMA_200']
        
        # MA period ratios
        df_processed['MA_RATIO_20_50'] = df_processed['MA_20'] / df_processed['MA_50']
        df_processed['MA_RATIO_20_90'] = df_processed['MA_20'] / df_processed['MA_90']
        df_processed['MA_RATIO_50_90'] = df_processed['MA_50'] / df_processed['MA_90']
        df_processed['MA_RATIO_20_200'] = df_processed['MA_20'] / df_processed['MA_200']
        df_processed['MA_RATIO_50_200'] = df_processed['MA_50'] / df_processed['MA_200']
        
        # Distance to moving averages
        df_processed['DISTANCE_MA_20'] = (df_processed['close'] - df_processed['MA_20']) / df_processed['MA_20']
        df_processed['DISTANCE_MA_50'] = (df_processed['close'] - df_processed['MA_50']) / df_processed['MA_50']
        df_processed['DISTANCE_MA_90'] = (df_processed['close'] - df_processed['MA_90']) / df_processed['MA_90']
        df_processed['DISTANCE_MA_200'] = (df_processed['close'] - df_processed['MA_200']) / df_processed['MA_200']
        
        df_processed['DISTANCE_EMA_20'] = (df_processed['close'] - df_processed['EMA_20']) / df_processed['EMA_20']
        df_processed['DISTANCE_EMA_50'] = (df_processed['close'] - df_processed['EMA_50']) / df_processed['EMA_50']
        df_processed['DISTANCE_EMA_90'] = (df_processed['close'] - df_processed['EMA_90']) / df_processed['EMA_90']
        df_processed['DISTANCE_EMA_200'] = (df_processed['close'] - df_processed['EMA_200']) / df_processed['EMA_200']
        
        df_processed['DISTANCE_WMA_20'] = (df_processed['close'] - df_processed['WMA_20']) / df_processed['WMA_20']
        df_processed['DISTANCE_WMA_50'] = (df_processed['close'] - df_processed['WMA_50']) / df_processed['WMA_50']
        df_processed['DISTANCE_WMA_90'] = (df_processed['close'] - df_processed['WMA_90']) / df_processed['WMA_90']
        df_processed['DISTANCE_WMA_200'] = (df_processed['close'] - df_processed['WMA_200']) / df_processed['WMA_200']
        
        return df_processed
    
    def add_targets(self, df: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
        """
        Add target variables for price prediction.
        
        Args:
            df: DataFrame with 'begin' and 'close' columns
            horizon_days: Prediction horizon in days
        
        Returns:
            DataFrame with added target columns
        """
        if df.empty:
            return df
        
        # Создаем копию и конвертируем begin в datetime если это строка
        df_sorted = df.copy()
        if df_sorted['begin'].dtype == 'object':
            df_sorted['begin'] = pd.to_datetime(df_sorted['begin'])
        
        df_sorted = df_sorted.sort_values('begin')
        
        # Create price dictionary for fast lookup
        price_dict = df_sorted.set_index('begin')['close'].to_dict()
        
        # Add future date
        df_sorted['future_date'] = df_sorted['begin'] + pd.Timedelta(days=horizon_days)
        
        # Map future price
        df_sorted['future_price'] = df_sorted['future_date'].map(price_dict)
        
        # Calculate target variables
        df_sorted['target_price_change'] = (
            (df_sorted['future_price'] / df_sorted['close'] - 1) * 100
        )
        
        df_sorted['target_class'] = df_sorted['target_price_change'].apply(
            lambda x: 'L' if x < -1 else ('H' if x > 1 else 'N')
        )
        
        # Remove helper columns
        df_sorted = df_sorted.drop(['future_date', 'future_price'], axis=1)
        
        return df_sorted
    
    def clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove rows with NaN values after feature generation.
        
        Args:
            df: DataFrame with possible NaN values
        
        Returns:
            Cleaned DataFrame without NaN rows
        """
        return df.dropna().copy()
    
    def process(
        self,
        df: pd.DataFrame,
        include_original: bool = False,
        add_targets: bool = False,
        horizon_days: int = 7,
        clean: bool = True
    ) -> pd.DataFrame:
        """
        Main processing pipeline with configurable options.
        
        Args:
            df: Input DataFrame with OHLCV data
            include_original: Include original OHLCV columns in output
            add_targets: Add target variables for prediction
            horizon_days: Prediction horizon if add_targets=True
            clean: Remove rows with NaN values
        
        Returns:
            Processed DataFrame with selected columns
        """
        # Generate all features
        result = self.generate(df)
        
        # Add targets if requested
        if add_targets:
            result = self.add_targets(result, horizon_days)
        
        # Clean NaN values if requested
        if clean:
            result = self.clean_features(result)
        
        # Select columns to return
        if not include_original:
            # Always keep 'begin', remove original OHLCV
            original_cols = ['open', 'high', 'low', 'close', 'volume', 'value', 'ticker']
            cols_to_keep = [col for col in result.columns if col not in original_cols]
            result = result[cols_to_keep]
        
        return result