import asyncio

import pandas as pd
import streamlit as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.core.database.repositories.asset_candle import AssetCandleRepository
from app.core.processors.feature_generator import FeatureGenerator
from app.mlflow import configure_mlflow
from stocks_dl.constants import DEFAULT_EXPERIMENT_NAME
from stocks_dl.data.pipeline import load_features_bundle
from stocks_dl.workflows.inference import (
    _prd_train_val_fallback,
    find_prd_run,
    load_prd_model,
    predict_from_dataframes,
)

TICKERS = ['SBER', 'GAZP', 'LKOH', 'ROSN']
EXPERIMENT_NAME = DEFAULT_EXPERIMENT_NAME

settings = get_settings()


@st.cache_resource
def init_mlflow() -> bool:
    configure_mlflow(EXPERIMENT_NAME)
    return True


@st.cache_resource
def load_best_prd_model_from_mlflow(ticker: str):
    """Загружает PRD-модель из MLflow (лучший search → PRD run), как в DL_Demonstration."""
    init_mlflow()
    prd_run_id, prd_summary = find_prd_run(ticker, EXPERIMENT_NAME)
    model, checkpoint = load_prd_model(prd_run_id)
    return model, checkpoint, prd_summary, prd_run_id


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


def predict_latest_price_change(ticker: str, features_df: pd.DataFrame) -> float:
    """Прогноз изменения цены (%) на последней доступной точке."""
    model, checkpoint, prd_summary, _ = load_best_prd_model_from_mlflow(ticker)
    seq_len = int(prd_summary['sequence_length'])
    batch_size = int(prd_summary['batch_size'])

    inference_df = features_df.sort_values('begin').tail(max(seq_len, 32)).copy()
    train_df, val_df = _prd_train_val_fallback(
        features_df,
        checkpoint,
        test_size=0.2,
        val_size=0.2,
        final_val_size=0.15,
    )
    predictions_df, _ = predict_from_dataframes(
        model,
        inference_df,
        seq_len,
        batch_size,
        checkpoint=checkpoint,
        train_df=train_df,
        val_df=val_df,
    )
    return float(predictions_df.iloc[-1]['predict'])


async def get_ticker_prediction(ticker: str) -> dict | None:
    """Получает прогноз для тикера"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            repo = AssetCandleRepository(session)

            raw_df = await repo.get_dataframe(ticker, 1000)
            if raw_df.empty:
                return None

            features_df, _ = await load_features_bundle(ticker)
            if features_df.empty:
                return None

            predicted_price_change = predict_latest_price_change(ticker, features_df)

            feature_gen = FeatureGenerator()
            processed_df = feature_gen.process(df=raw_df, include_original=True)
            if processed_df.empty:
                return None

            current_price = processed_df.iloc[-1]['close']
            current_date = processed_df.iloc[-1]['begin']
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


def display_recommendation(price_change: float) -> None:
    if price_change > 1.0:
        st.success('Покупать')
    elif price_change < -1.0:
        st.error('Продавать')
    else:
        st.warning('Держать')


async def fetch_all_predictions():
    results = {}
    for ticker in TICKERS:
        try:
            prediction = await get_ticker_prediction(ticker)
            results[ticker] = prediction
        except Exception as e:
            st.error(f'Ошибка: {e}')
    return results


def main():
    # Main Streamlit app
    st.set_page_config(
        page_title='Финансовый советник',
        page_icon='📈',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Прогнозирование стоимости акций')
    st.markdown('### Прогноз на неделю')

    # Fetch data
    all_predictions = asyncio.run(fetch_all_predictions())

    # Display results
    cols = st.columns(len(TICKERS))

    for idx, ticker in enumerate(TICKERS):
        prediction = all_predictions[ticker]

        with cols[idx]:
            st.subheader(ticker)

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
            display_recommendation(prediction['predicted_price_change'])


if __name__ == '__main__':
    main()
