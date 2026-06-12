import asyncio

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.core.database import AssetCandleRepository, get_db_session
from app.core.processors.feature_generator import FeatureGenerator
from app.mlflow import configure_mlflow
from stocks_dl.constants import DEFAULT_EXPERIMENT_NAME
from stocks_dl.data.pipeline import load_features_bundle_multi
from stocks_dl.workflows.inference import (
    _prd_train_val_fallback,
    find_prd_run,
    load_prd_model,
    predict_from_dataframes,
)

TICKERS = ['SBER', 'GAZP', 'LKOH', 'ROSN', 'TCSG']
TICKERS_KEY = tuple(TICKERS)
EXPERIMENT_NAME = DEFAULT_EXPERIMENT_NAME
DB_CACHE_TTL = 3600
PREDICTION_CACHE_TTL = 3600
HISTORY_DAYS = 30


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


def _dataframe_fingerprint(df: pd.DataFrame) -> str:
    if df.empty:
        return 'empty'
    sorted_df = df.sort_values('begin')
    return f'{len(sorted_df)}:{sorted_df.iloc[-1]["begin"]}'


async def load_all_ticker_data(
    tickers: list[str],
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame] | None]:
    """Загружает свечи и признаки для всех тикеров в одном event loop."""
    raw_by_ticker: dict[str, pd.DataFrame] = {}

    async with get_db_session() as session:
        repo = AssetCandleRepository(session)
        for ticker in tickers:
            raw_df = await repo.get_dataframe(ticker, 1000)
            if not raw_df.empty:
                raw_by_ticker[ticker] = raw_df

    features_by_ticker = await load_features_bundle_multi(tickers)

    loaded: dict[str, tuple[pd.DataFrame, pd.DataFrame] | None] = {}
    for ticker in tickers:
        raw_df = raw_by_ticker.get(ticker)
        features_df = features_by_ticker.get(ticker)
        if raw_df is None or features_df is None or features_df.empty:
            loaded[ticker] = None
        else:
            loaded[ticker] = (raw_df, features_df)
    return loaded


@st.cache_data(ttl=DB_CACHE_TTL, show_spinner=False)
def load_all_ticker_data_cached(tickers: tuple[str, ...]) -> dict[str, tuple[pd.DataFrame, pd.DataFrame] | None]:
    return asyncio.run(load_all_ticker_data(list(tickers)))


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


def prepare_price_history(raw_df: pd.DataFrame, days: int = HISTORY_DAYS) -> pd.DataFrame:
    feature_gen = FeatureGenerator()
    processed_df = feature_gen.process(df=raw_df, include_original=True)
    if processed_df.empty:
        return processed_df

    processed_df = processed_df.copy()
    processed_df['begin'] = pd.to_datetime(processed_df['begin'])
    cutoff = processed_df['begin'].max() - pd.Timedelta(days=days)
    return (
        processed_df.loc[processed_df['begin'] >= cutoff, ['begin', 'close']]
        .sort_values('begin')
        .reset_index(drop=True)
    )


def build_ticker_prediction(
    ticker: str,
    raw_df: pd.DataFrame,
    features_df: pd.DataFrame,
) -> dict | None:
    """Строит прогноз по уже загруженным данным."""
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


@st.cache_data(ttl=PREDICTION_CACHE_TTL, show_spinner=False)
def build_ticker_prediction_cached(ticker: str, fingerprint: str) -> dict | None:
    loaded = load_all_ticker_data_cached(TICKERS_KEY)
    item = loaded.get(ticker)
    if item is None:
        return None
    raw_df, features_df = item
    return build_ticker_prediction(ticker, raw_df, features_df)


def fetch_all_predictions() -> tuple[dict[str, dict | None], dict[str, tuple[pd.DataFrame, pd.DataFrame] | None]]:
    results: dict[str, dict | None] = {}
    loaded_by_ticker: dict[str, tuple[pd.DataFrame, pd.DataFrame] | None] = {}

    with st.spinner('Загрузка данных...'):
        try:
            loaded_by_ticker = load_all_ticker_data_cached(TICKERS_KEY)
        except Exception as e:
            st.error(f'Ошибка загрузки данных: {e}')
            return dict.fromkeys(TICKERS), dict.fromkeys(TICKERS)

    with st.spinner('Прогнозирование...'):
        for ticker in TICKERS:
            loaded = loaded_by_ticker.get(ticker)
            if loaded is None:
                results[ticker] = None
                continue

            _, features_df = loaded
            fingerprint = _dataframe_fingerprint(features_df)

            try:
                results[ticker] = build_ticker_prediction_cached(ticker, fingerprint)
            except Exception as e:
                results[ticker] = None
                st.error(f'{ticker}: {e}')

    return results, loaded_by_ticker


def display_recommendation(price_change: float) -> None:
    if price_change > 1.0:
        st.success('Покупать')
    elif price_change < -1.0:
        st.error('Продавать')
    else:
        st.warning('Держать')


def render_price_chart(prediction: dict, history: pd.DataFrame) -> None:
    current_date = pd.to_datetime(prediction['current_date'])
    future_date = pd.to_datetime(prediction['future_date'])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history['begin'],
            y=history['close'],
            mode='lines',
            name='История',
            line={'color': '#2563eb', 'width': 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[current_date, future_date],
            y=[prediction['current_price'], prediction['predicted_price']],
            mode='lines+markers',
            name='Прогноз (+7 дн.)',
            line={'color': '#f97316', 'width': 2, 'dash': 'dash'},
            marker={'size': 8},
        )
    )
    fig.update_layout(
        height=320,
        margin={'l': 8, 'r': 8, 't': 32, 'b': 8},
        legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.02, 'xanchor': 'right', 'x': 1},
        xaxis={'title': None, 'showgrid': True, 'gridcolor': '#eef2f7'},
        yaxis={'title': 'Цена, ₽', 'showgrid': True, 'gridcolor': '#eef2f7', 'tickformat': '.2f'},
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
    )
    st.plotly_chart(fig, use_container_width=True)


def render_ticker_card(
    ticker: str,
    prediction: dict | None,
    raw_df: pd.DataFrame | None,
) -> None:
    st.subheader(ticker)

    if not prediction:
        st.warning('Нет данных')
        return

    if raw_df is None or raw_df.empty:
        st.warning('Нет истории цен')
        return

    history = prepare_price_history(raw_df)
    if history.empty:
        st.warning('Нет истории цен')
        return

    render_price_chart(prediction, history)

    col_current, col_forecast = st.columns(2)
    with col_current:
        st.metric(label='Текущая цена', value=f'{prediction["current_price"]:.2f} ₽')
    with col_forecast:
        future_label = pd.to_datetime(prediction['future_date']).strftime('%d.%m.%Y')
        st.metric(
            label=f'Прогноз на {future_label}',
            value=f'{prediction["predicted_price"]:.2f} ₽',
            delta=f'{prediction["predicted_price_change"]:.2f}%',
        )

    display_recommendation(prediction['predicted_price_change'])


def main():
    st.set_page_config(
        page_title='Финансовый советник',
        page_icon='📈',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Прогнозирование стоимости акций')
    st.markdown('### Прогноз на неделю')

    selected_ticker = st.sidebar.selectbox('Тикер', TICKERS, index=0)

    all_predictions, loaded_by_ticker = fetch_all_predictions()

    loaded = loaded_by_ticker.get(selected_ticker)
    raw_df = loaded[0] if loaded else None
    render_ticker_card(selected_ticker, all_predictions[selected_ticker], raw_df)


if __name__ == '__main__':
    main()
