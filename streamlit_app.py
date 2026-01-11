import asyncio

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.core.database.repositories.asset_candle import AssetCandleRepository
from app.core.processors.feature_generator import FeatureGenerator
from app.core.processors.model_predictor import ModelPredictor

st.set_page_config(
    page_title='Stocks advisor',
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


async def get_ticker_data(ticker: str, num_data_points: int) -> pd.DataFrame:
    """Получает данные и прогнозы для тикера"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            repo = AssetCandleRepository(session)

            # Fetch data
            raw_df = await repo.get_dataframe_by_ticker(ticker, num_data_points)

            if raw_df.empty:
                return pd.DataFrame()

            # Generate features
            feature_gen = FeatureGenerator()
            processed_df = feature_gen.process(df=raw_df, include_original=True)

            if processed_df.empty:
                return pd.DataFrame()

            # Make predictions
            model_predictor = ModelPredictor(ticker, 'app/core/processors/models')
            predictions = model_predictor.predict(processed_df)

            # Convert to df
            predictions_df = pd.DataFrame(predictions)
            predictions_df['begin'] = pd.to_datetime(predictions_df['datetime'])
            predictions_df.rename(columns={'value': 'predicted_price_change'}, inplace=True)

            # Merge with actual close prices
            result_df = predictions_df.merge(processed_df, on='begin', how='left')

            # Convert percentage change to actual predicted price
            # Formula: predicted_price = current_price * (1 + price_change / 100)
            result_df['predicted_value'] = result_df['close'] * (1 + result_df['predicted_price_change'] / 100)

            # Add 7 days to get the future date when the prediction applies
            result_df['future_date'] = result_df['begin'] + pd.Timedelta(days=7)

            result_df = result_df[['begin', 'close', 'future_date', 'predicted_price_change', 'predicted_value']]

            return result_df
        finally:
            # Ensure session is properly closed
            await session.close()


def create_price_chart(data_df: pd.DataFrame, ticker: str) -> go.Figure:
    fig = go.Figure()

    # Add actual prices
    if not data_df.empty:
        fig.add_trace(
            go.Scatter(
                x=data_df['begin'],
                y=data_df['close'],
                mode='lines',
                name='Цена акции',
                line=dict(color='green', width=2),
            )
        )

        # Add predicted future prices
        fig.add_trace(
            go.Scatter(
                x=data_df['future_date'],
                y=data_df['predicted_value'],
                mode='lines',
                name='Прогноз',
                line=dict(color='red', width=2),
                customdata=list(zip(data_df['begin'], data_df['close'], data_df['predicted_price_change'])),
                hovertemplate=(
                    '%{y:.2f}<br>'
                    'Прогноз основан на: %{customdata[1]:.2f} ₽ (%{customdata[0]})<br>'
                    'Прогнозируемое изменение: %{customdata[2]:.4f}%'
                ),
            )
        )

    fig.update_layout(
        title=f'{ticker}',
        xaxis_title='Дата',
        yaxis_title='Цена (RUB)',
        hovermode='x unified',
        template='plotly_white',
        height=700,
    )

    return fig


# Main Streamlit app
st.title('Прогнозирование стоимости акций')

NUM_DATA_POINTS = 3600  # 6 months of data


async def fetch_all_tickers_data(num_data_points: int):
    results = {}
    for ticker in TICKERS:
        try:
            data_df = await get_ticker_data(ticker, num_data_points)
            results[ticker] = (data_df, None)
        except Exception as e:
            results[ticker] = (pd.DataFrame(), str(e))
    return results


# Fetch data
all_data = asyncio.run(fetch_all_tickers_data(NUM_DATA_POINTS))

# Display results
for ticker in TICKERS:
    data_df, error = all_data[ticker]

    with st.spinner(f'Загрузка данных для {ticker}...'):
        if error:
            st.error(f'Ошибка загрузки данных для {ticker}: {error}')
            continue

        # Create chart
        if not data_df.empty:
            fig = create_price_chart(data_df, ticker)
            st.plotly_chart(fig, width='stretch')
        else:
            st.warning(f'Нет данных для {ticker}')
