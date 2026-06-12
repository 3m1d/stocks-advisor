import asyncio
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.core.database import AssetCandleRepository, get_db_session
from app.core.processors.feature_generator import FeatureGenerator
from app.mlflow import configure_mlflow
from app.utils.disk_cache import DiskCache
from stocks_dl.constants import (
    CATBOOST_EXPERIMENT_NAME,
    DEFAULT_EXPERIMENT_NAME,
    LSTM_EXPERIMENT_NAME,
)
from stocks_dl.data.pipeline import (
    NEWS_HORIZONS_HOURS,
    load_features_bundle_multi,
    merge_tonality_with_prices,
)
from stocks_dl.workflows.catboost_inference import (
    find_catboost_run,
    load_catboost_model,
    predict_catboost_latest,
)
from stocks_dl.workflows.inference import (
    _prd_train_val_fallback,
    find_prd_run,
    load_prd_model,
    predict_from_dataframes,
)

TICKERS = ['SBER', 'GAZP', 'LKOH', 'ROSN', 'T']
TICKER_OPTIONS = ['Все', *TICKERS]
TICKERS_KEY = tuple(TICKERS)
CATBOOST_TICKERS = frozenset({'SBER', 'GAZP'})
# T — новый тикер Т-Банка; PRD-модель и новости обучались на TCSG
MODEL_TICKER_BY_DATA_TICKER: dict[str, str] = {'T': 'TCSG'}
DB_CACHE_TTL = 3600
PREDICTION_CACHE_TTL = 3600
HISTORY_PERIOD_OPTIONS: dict[str, int] = {
    '2 недели': 14,
    '1 месяц': 30,
    '3 месяца': 90,
    '6 месяцев': 180,
}
DEFAULT_HISTORY_PERIOD = '1 месяц'
MAX_CANDLES_LIMIT = max(HISTORY_PERIOD_OPTIONS.values()) * 12
PREDICTION_DISK_CACHE = DiskCache(
    Path('.cache/streamlit/predictions'),
    ttl_seconds=PREDICTION_CACHE_TTL,
)


def resolve_model_ticker(data_ticker: str) -> str:
    return MODEL_TICKER_BY_DATA_TICKER.get(data_ticker, data_ticker)


def uses_catboost(data_ticker: str) -> bool:
    return data_ticker in CATBOOST_TICKERS


@st.cache_resource
def init_mlflow() -> bool:
    configure_mlflow(DEFAULT_EXPERIMENT_NAME)
    return True


@st.cache_resource
def load_lstm_model_from_mlflow(ticker: str):
    init_mlflow()
    prd_run_id, prd_summary = find_prd_run(ticker, LSTM_EXPERIMENT_NAME)
    model, checkpoint = load_prd_model(prd_run_id)
    return model, checkpoint, prd_summary, prd_run_id


@st.cache_resource
def load_catboost_model_from_mlflow(ticker: str):
    init_mlflow()
    run_id, summary = find_catboost_run(ticker, CATBOOST_EXPERIMENT_NAME)
    model = load_catboost_model(run_id)
    return model, summary, run_id


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
            raw_df = await repo.get_dataframe(ticker, MAX_CANDLES_LIMIT)
            if not raw_df.empty:
                raw_by_ticker[ticker] = raw_df

    features_by_ticker = await load_features_bundle_multi(tickers)
    enrichments = features_by_ticker['_enrichments']

    loaded: dict[str, tuple[pd.DataFrame, pd.DataFrame] | None] = {}
    for ticker in tickers:
        raw_df = raw_by_ticker.get(ticker)
        features_df = features_by_ticker.get(ticker)
        if raw_df is None or features_df is None or features_df.empty:
            loaded[ticker] = None
            continue

        if ticker in MODEL_TICKER_BY_DATA_TICKER:
            news_ticker = MODEL_TICKER_BY_DATA_TICKER[ticker]
            features_df = merge_tonality_with_prices(
                news_ticker,
                features_df,
                enrichments,
                NEWS_HORIZONS_HOURS,
            ).fillna(0)

        loaded[ticker] = (raw_df, features_df)
    return loaded


@st.cache_data(ttl=DB_CACHE_TTL, show_spinner=False)
def load_all_ticker_data_cached(tickers: tuple[str, ...]) -> dict[str, tuple[pd.DataFrame, pd.DataFrame] | None]:
    return asyncio.run(load_all_ticker_data(list(tickers)))


def predict_latest_price_change(data_ticker: str, features_df: pd.DataFrame) -> float:
    """Прогноз изменения цены (%) на последней доступной точке."""
    if uses_catboost(data_ticker):
        model, _, _ = load_catboost_model_from_mlflow(data_ticker)
        return predict_catboost_latest(model, features_df)

    model_ticker = resolve_model_ticker(data_ticker)
    model, checkpoint, prd_summary, _ = load_lstm_model_from_mlflow(model_ticker)
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


def prepare_price_history(raw_df: pd.DataFrame, days: int) -> pd.DataFrame:
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


def _prediction_cache_key(ticker: str, fingerprint: str) -> str:
    model_family = 'catboost' if uses_catboost(ticker) else 'lstm'
    return f'{model_family}:{ticker}:{fingerprint}'


def get_ticker_prediction_cached(
    ticker: str,
    fingerprint: str,
    raw_df: pd.DataFrame,
    features_df: pd.DataFrame,
) -> dict | None:
    cache_key = _prediction_cache_key(ticker, fingerprint)
    cached = PREDICTION_DISK_CACHE.get(cache_key)
    if cached is not None:
        return cached

    result = build_ticker_prediction(ticker, raw_df, features_df)
    if result is not None:
        PREDICTION_DISK_CACHE.set(cache_key, result)
    return result


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

            raw_df, features_df = loaded
            fingerprint = _dataframe_fingerprint(features_df)

            try:
                results[ticker] = get_ticker_prediction_cached(ticker, fingerprint, raw_df, features_df)
            except Exception as e:
                results[ticker] = None
                st.error(f'{ticker}: {e}')

    return results, loaded_by_ticker


def recommendation_label(price_change: float) -> str:
    if price_change > 1.0:
        return 'Покупать'
    if price_change < -1.0:
        return 'Продавать'
    return 'Держать'


def display_recommendation(price_change: float) -> None:
    label = recommendation_label(price_change)
    if price_change > 1.0:
        st.success(label)
    elif price_change < -1.0:
        st.error(label)
    else:
        st.warning(label)


def render_price_chart(
    prediction: dict,
    history: pd.DataFrame,
    *,
    height: int = 320,
    compact: bool = False,
) -> None:
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
        template='streamlit',
        height=height,
        margin={
            'l': 4,
            'r': 4,
            't': 8 if compact else 16,
            'b': 4 if compact else 48,
        },
        showlegend=not compact,
        legend={
            'orientation': 'h',
            'yanchor': 'top',
            'y': -0.25,
            'xanchor': 'center',
            'x': 0.5,
        },
        xaxis={'title': None, 'showgrid': True, 'showticklabels': not compact},
        yaxis={
            'title': None if compact else 'Цена, ₽',
            'showgrid': True,
            'tickformat': '.2f',
        },
        hovermode='x unified',
    )
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': not compact})


def render_ticker_card(
    ticker: str,
    prediction: dict | None,
    raw_df: pd.DataFrame | None,
    history_days: int,
) -> None:
    st.subheader(ticker)

    if not prediction:
        st.warning('Нет данных')
        return

    if raw_df is None or raw_df.empty:
        st.warning('Нет истории цен')
        return

    history = prepare_price_history(raw_df, history_days)
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


def render_ticker_compact(
    ticker: str,
    prediction: dict | None,
    raw_df: pd.DataFrame | None,
    history_days: int,
) -> None:
    st.markdown(f'**{ticker}**')

    if not prediction:
        st.caption('Нет данных')
        return

    if raw_df is None or raw_df.empty:
        st.caption('Нет истории цен')
        return

    history = prepare_price_history(raw_df, history_days)
    if history.empty:
        st.caption('Нет истории цен')
        return

    render_price_chart(prediction, history, height=160, compact=True)

    change = prediction['predicted_price_change']
    st.caption(f'{prediction["current_price"]:.2f} ₽ → {prediction["predicted_price"]:.2f} ₽ ({change:+.2f}%)')
    display_recommendation(change)


def render_all_tickers(
    all_predictions: dict[str, dict | None],
    loaded_by_ticker: dict[str, tuple[pd.DataFrame, pd.DataFrame] | None],
    history_days: int,
) -> None:
    cols_per_row = 3
    for row_start in range(0, len(TICKERS), cols_per_row):
        row_tickers = TICKERS[row_start : row_start + cols_per_row]
        columns = st.columns(len(row_tickers))
        for column, ticker in zip(columns, row_tickers, strict=True):
            loaded = loaded_by_ticker.get(ticker)
            raw_df = loaded[0] if loaded else None
            with column:
                render_ticker_compact(ticker, all_predictions[ticker], raw_df, history_days)


def main():
    st.set_page_config(
        page_title='Финансовый советник',
        page_icon='📈',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Прогнозирование стоимости акций')
    st.markdown('### Прогноз на неделю')

    selected_ticker = st.sidebar.pills(
        'Тикер',
        TICKER_OPTIONS,
        default='Все',
        selection_mode='single',
    ) or 'Все'
    selected_period = st.sidebar.selectbox(
        'Период графика',
        list(HISTORY_PERIOD_OPTIONS.keys()),
        index=list(HISTORY_PERIOD_OPTIONS.keys()).index(DEFAULT_HISTORY_PERIOD),
    )
    history_days = HISTORY_PERIOD_OPTIONS[selected_period]

    all_predictions, loaded_by_ticker = fetch_all_predictions()

    if selected_ticker == 'Все':
        render_all_tickers(all_predictions, loaded_by_ticker, history_days)
    else:
        loaded = loaded_by_ticker.get(selected_ticker)
        raw_df = loaded[0] if loaded else None
        render_ticker_card(selected_ticker, all_predictions[selected_ticker], raw_df, history_days)


if __name__ == '__main__':
    main()
