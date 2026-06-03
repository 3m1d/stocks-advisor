"""Structured error analysis, baseline and robustness checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from stocks_dl.constants import TARGET_COLUMN
from stocks_dl.paths import PKG_ROOT
from stocks_dl.training.dataset import build_predictions_df, evaluate_model, make_loaders, set_seed
from stocks_dl.training.train import calculate_metrics
from stocks_dl.viz.plotting import save_direction_confusion_matrix, save_prediction_plot

LOW_AMPLITUDE_THRESHOLD = 0.5
LARGE_MOVE_THRESHOLD = 3.0


def _direction_label(value: float, flat_threshold: float = 0.25) -> str:
    if value > flat_threshold:
        return 'up'
    if value < -flat_threshold:
        return 'down'
    return 'flat'


def classify_error_row(row: pd.Series, sentiment_cols: list[str]) -> tuple[str, str]:
    target = float(row[TARGET_COLUMN])
    pred = float(row['predict'])
    abs_target = abs(target)
    categories = []

    if abs_target < LOW_AMPLITUDE_THRESHOLD:
        categories.append('low_amplitude')
    if abs_target >= LARGE_MOVE_THRESHOLD:
        categories.append('large_move')
    if not bool(row.get('direction_match', np.sign(pred) == np.sign(target))):
        categories.append('direction_flip')

    sentiment_vals = [row.get(c, 0) for c in sentiment_cols]
    if sentiment_cols and all((pd.isna(v) or float(v) == 0) for v in sentiment_vals):
        categories.append('sentiment_missing')

    if not categories:
        categories.append('residual_noise')

    category = categories[0]
    explanations = {
        'low_amplitude': (
            'Движение цены мало (шум); модель и baseline плохо различают знак. '
            'Корректировка ограничена — нужны более длинные горизонты или фильтр по амплитуде.'
        ),
        'large_move': (
            'Резкое движение, вероятно вне распределения обучающей выборки или из-за новостей. '
            'Без полного новостного контекста ошибку сложно устранить только LSTM.'
        ),
        'direction_flip': (
            'Неверно предсказано направление при заметной амплитуде. '
            'Возможны лаг тональности или недостаточные признаки; улучшение — сбор новостей и лагов.'
        ),
        'sentiment_missing': (
            'Тональность в окне отсутствует или нулевая; модель опирается на технические признаки. '
            'Можно улучшить пайплайн новостей, но не в рамках весов LSTM.'
        ),
        'residual_noise': (
            'Остаточная ошибка при типичных условиях; частично объясняется шумом целевой переменной.'
        ),
    }
    return category, explanations.get(category, 'Ошибка предсказания.')


def enrich_top_errors(
    predictions_df: pd.DataFrame,
    test_df: pd.DataFrame,
    enrichments_df: pd.DataFrame | None,
    top_n: int = 20,
) -> pd.DataFrame:
    sentiment_cols = [c for c in test_df.columns if 'sentiment' in c.lower()]
    feature_cols = [c for c in test_df.columns if c not in (TARGET_COLUMN,)]
    merged = predictions_df.merge(
        test_df[feature_cols],
        on='begin',
        how='left',
    )
    top_errors = merged.sort_values('abs_error', ascending=False).head(top_n).copy()

    news_excerpts = []
    for _, row in top_errors.iterrows():
        excerpt = ''
        if enrichments_df is not None and not enrichments_df.empty:
            ts = pd.to_datetime(row['begin'])
            window = enrichments_df[
                (pd.to_datetime(enrichments_df['date']) <= ts)
                & (pd.to_datetime(enrichments_df['date']) >= ts - pd.Timedelta(hours=72))
            ]
            if not window.empty and 'topic' in window.columns:
                topics = window['topic'].dropna().astype(str).head(3).tolist()
                excerpt = '; '.join(topics)
            elif not window.empty and 'sentiment' in window.columns:
                excerpt = f"sentiment mix: {window['sentiment'].value_counts().head(2).to_dict()}"
        if not excerpt:
            sent_vals = [row.get(c) for c in sentiment_cols[:3]]
            excerpt = f'sentiment features: {sent_vals}'
        news_excerpts.append(str(excerpt)[:200])

    categories = []
    explanations = []
    for _, row in top_errors.iterrows():
        cat, expl = classify_error_row(row, sentiment_cols)
        categories.append(cat)
        explanations.append(expl)

    top_errors['news_excerpt'] = news_excerpts
    top_errors['error_category'] = categories
    top_errors['explanation'] = explanations
    return top_errors.reset_index(drop=True)


def build_error_analysis_markdown(
    top_errors_df: pd.DataFrame,
    error_summary_df: pd.DataFrame,
    robustness_df: pd.DataFrame,
    ticker: str,
) -> str:
    cat_counts = top_errors_df['error_category'].value_counts().to_dict()
    lines = [
        f'# Error analysis — {ticker}',
        '',
        '## Сводка метрик (test)',
        error_summary_df.to_csv(index=False),
        '',
        '## Категории ошибок (top-N)',
    ]
    for cat, cnt in cat_counts.items():
        lines.append(f'- **{cat}**: {cnt}')
    lines.extend(['', '## Разобранные примеры', ''])
    for i, row in top_errors_df.head(5).iterrows():
        lines.append(f"### Пример {i + 1} — {row['begin']}")
        lines.append(f"- target: {row[TARGET_COLUMN]:.4f}%, predict: {row['predict']:.4f}%")
        lines.append(f"- abs_error: {row['abs_error']:.4f}, category: {row['error_category']}")
        lines.append(f"- news: {row.get('news_excerpt', '')}")
        lines.append(f"- {row.get('explanation', '')}")
        lines.append('')
    lines.extend(['## Robustness', '', robustness_df.to_csv(index=False)])
    return '\n'.join(lines)


def run_robustness_checks(
    model,
    prd_train_df: pd.DataFrame,
    prd_val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    sequence_length: int,
    batch_size: int,
    seed: int,
) -> pd.DataFrame:
    set_seed(seed)
    sentiment_cols = [col for col in test_df.columns if 'sentiment' in col]
    robust_variants = {
        'zero_sentiment': lambda frame: frame.assign(**{col: 0 for col in sentiment_cols}),
        'shifted_sentiment': lambda frame: frame.assign(
            **{col: frame[col].shift(1).fillna(0) for col in sentiment_cols}
        ),
        'noise_sentiment': lambda frame: frame.assign(
            **{
                col: frame[col] + np.random.normal(0, 0.05, size=len(frame))
                for col in sentiment_cols
            }
        ),
    }
    rows = []
    for variant_name, transform in robust_variants.items():
        variant_test_df = transform(test_df.copy())
        _, _, _, _, _, variant_loader = make_loaders(
            prd_train_df, prd_val_df, variant_test_df, sequence_length, batch_size
        )
        variant_metrics, _, _ = evaluate_model(model, variant_loader)
        rows.append(
            {
                'variant': variant_name,
                'mae': float(variant_metrics['mae']),
                'rmse': float(variant_metrics['rmse']),
                'r2': float(variant_metrics['r2']),
                'direction_accuracy': float(variant_metrics['direction_accuracy']),
            }
        )
    return pd.DataFrame(rows)


def run_error_analysis(
    prd_run_id: str,
    prd_run_summary: dict,
    prd_train_df: pd.DataFrame,
    prd_val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    ticker: str,
    enrichments_df: pd.DataFrame | None = None,
    experiment_name: str | None = None,
) -> dict:
    import mlflow.pytorch

    analysis_model = mlflow.pytorch.load_model(f'runs:/{prd_run_id}/model')
    seq_len = int(prd_run_summary['sequence_length'])
    batch_size = int(prd_run_summary['batch_size'])

    _, _, _, _, _, test_loader = make_loaders(
        prd_train_df, prd_val_df, test_df, seq_len, batch_size
    )
    prd_test_metrics, y_true, y_pred = evaluate_model(analysis_model, test_loader)
    predictions_df = build_predictions_df(test_df, y_true, y_pred, seq_len)

    baseline_metrics = calculate_metrics(y_true, np.zeros_like(y_true))
    baseline_df = pd.DataFrame(
        [
            {
                'model': 'zero_baseline',
                'mae': float(baseline_metrics['mae']),
                'rmse': float(baseline_metrics['rmse']),
                'r2': float(baseline_metrics['r2']),
                'direction_accuracy': float(baseline_metrics['direction_accuracy']),
            }
        ]
    )
    error_summary_df = pd.DataFrame(
        [
            {
                'model_mae': float(prd_test_metrics['mae']),
                'model_rmse': float(prd_test_metrics['rmse']),
                'model_r2': float(prd_test_metrics['r2']),
                'model_direction_accuracy': float(prd_test_metrics['direction_accuracy']),
                'baseline_mae': float(baseline_metrics['mae']),
                'baseline_rmse': float(baseline_metrics['rmse']),
                'baseline_r2': float(baseline_metrics['r2']),
                'baseline_direction_accuracy': float(baseline_metrics['direction_accuracy']),
            }
        ]
    )
    top_errors_df = enrich_top_errors(predictions_df, test_df, enrichments_df, top_n=20)
    robustness_df = run_robustness_checks(
        analysis_model,
        prd_train_df,
        prd_val_df,
        test_df,
        seq_len,
        batch_size,
        int(prd_run_summary.get('seed', 42)),
    )
    analysis_md = build_error_analysis_markdown(
        top_errors_df, error_summary_df, robustness_df, ticker
    )

    save_prediction_plot(predictions_df, PKG_ROOT / 'prd_predictions.png', f'{ticker} PRD predictions')

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        predictions_df.to_csv(tmpdir / 'prd_predictions.csv', index=False)
        top_errors_df.to_csv(tmpdir / 'top_errors.csv', index=False)
        baseline_df.to_csv(tmpdir / 'baseline_comparison.csv', index=False)
        error_summary_df.to_csv(tmpdir / 'error_summary.csv', index=False)
        robustness_df.to_csv(tmpdir / 'robustness.csv', index=False)
        (tmpdir / 'error_analysis.md').write_text(analysis_md, encoding='utf-8')
        save_prediction_plot(predictions_df, tmpdir / 'prd_predictions.png', f'{ticker} PRD predictions')
        save_direction_confusion_matrix(y_true, y_pred, tmpdir / 'direction_confusion_matrix.png')

        if experiment_name:
            mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=f'{ticker}_analysis') as _:
            mlflow.set_tags(
                {
                    'ticker': ticker,
                    'stage': 'analysis',
                    'source_prd_run_id': prd_run_id,
                }
            )
            mlflow.log_metrics(
                {
                    'prd_mae': float(prd_test_metrics['mae']),
                    'prd_rmse': float(prd_test_metrics['rmse']),
                    'prd_r2': float(prd_test_metrics['r2']),
                    'prd_direction_accuracy': float(prd_test_metrics['direction_accuracy']),
                    'baseline_mae': float(baseline_metrics['mae']),
                    'baseline_rmse': float(baseline_metrics['rmse']),
                    'baseline_r2': float(baseline_metrics['r2']),
                    'baseline_direction_accuracy': float(baseline_metrics['direction_accuracy']),
                }
            )
            mlflow.log_artifacts(str(tmpdir))

    return {
        'predictions_df': predictions_df,
        'top_errors_df': top_errors_df,
        'baseline_df': baseline_df,
        'error_summary_df': error_summary_df,
        'robustness_df': robustness_df,
        'error_analysis_md': analysis_md,
    }
