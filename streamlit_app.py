import asyncio

import pandas as pd
import streamlit as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.core.database.repositories.asset_candle import AssetCandleRepository
from app.core.processors.feature_generator import FeatureGenerator
from app.core.processors.model_predictor import ModelPredictor

st.set_page_config(
    page_title='Советник по акциям',
    layout='wide',
    initial_sidebar_state='expanded',
)

TICKERS = ['SBER', 'GAZP', 'LKOH', 'ROSN']

settings = get_settings()


@st.cache_resource
def get_db_engine():
    return create_async_engine(
        settings.database.url_async,
        echo=False,
        poolclass=NullPool,
        pool_pre_ping=True,
    )


@st.cache_resource
def get_session_maker():
    """Create session maker"""
    engine = get_db_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_ticker_prediction(ticker: str) -> dict | None:
    """Получает последний прогноз для тикера"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            repo = AssetCandleRepository(session)

            # Fetch enough data for feature generation (need ~1000 hourly points for 200 2h-intervals after aggregation)
            raw_df = await repo.get_dataframe_by_ticker(ticker, 1000)

            if raw_df.empty:
                return None

            # Generate features
            feature_gen = FeatureGenerator()
            processed_df = feature_gen.process(df=raw_df, include_original=True)

            if processed_df.empty:
                return None

            # Make predictions on last row only
            last_row_df = processed_df.iloc[[-1]]
            model_predictor = ModelPredictor(ticker, 'app/core/processors/models')
            predictions = model_predictor.predict(last_row_df)

            if not predictions:
                return None

            prediction = predictions[0]  # Get first (and only) prediction

            # Get close price
            current_price = processed_df.iloc[-1]['close']
            current_date = processed_df.iloc[-1]['begin']

            # Calculate predicted price
            predicted_price_change = prediction['value']
            predicted_price = current_price * (1 + predicted_price_change / 100)
            future_date = pd.to_datetime(current_date) + pd.Timedelta(days=7)

            return {
                'ticker': ticker,
                'current_price': current_price,
                'current_date': current_date,
                'predicted_price': predicted_price,
                'predicted_price_change': predicted_price_change,
                'future_date': future_date,
            }
        finally:
            await session.close()


def get_recommendation(price_change: float) -> tuple[str, str]:
    """Возвращает рекомендацию и цвет на основе изменения цены"""
    if price_change > 1.0:
        return 'Покупать', 'success'
    elif price_change < -1.0:
        return 'Продавать', 'error'
    else:
        return 'Держать', 'warning'


# Main Streamlit app
st.title('Прогнозирование стоимости акций')
st.markdown('### Прогноз на неделю')


async def fetch_all_predictions():
    results = {}
    for ticker in TICKERS:
        try:
            prediction = await get_ticker_prediction(ticker)
            results[ticker] = (prediction, None)
        except Exception as e:
            results[ticker] = (None, str(e))
    return results


# Fetch data
all_predictions = asyncio.run(fetch_all_predictions())

# Display results
cols = st.columns(len(TICKERS))

for idx, ticker in enumerate(TICKERS):
    prediction, error = all_predictions[ticker]

    with cols[idx]:
        st.subheader(ticker)

        if error:
            st.error(f'Ошибка: {error}')
            continue

        if not prediction:
            st.warning('Нет данных')
            continue

        # Display current price
        st.metric(label='Текущая цена', value=f'{prediction["current_price"]:.2f} ₽')

        # Display predicted price with change
        st.metric(
            label='Прогноз цены',
            value=f'{prediction["predicted_price"]:.2f} ₽',
            delta=f'{prediction["predicted_price_change"]:.2f}%',
        )

        # Display recommendation
        recommendation, status = get_recommendation(prediction['predicted_price_change'])

        if status == 'success':
            st.success(recommendation)
        elif status == 'error':
            st.error(recommendation)
        else:
            st.warning(recommendation)
