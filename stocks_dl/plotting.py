"""Plot helpers for experiments and analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def save_learning_curves(train_losses, val_losses, val_metrics, path: Path | str) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    axs[0, 0].plot(range(1, len(train_losses) + 1), train_losses, label='train', linewidth=2)
    axs[0, 0].plot(range(1, len(val_losses) + 1), val_losses, label='val', linewidth=2)
    axs[0, 0].set_ylabel('MSE Loss')
    axs[0, 0].set_xlabel('Epoch')
    axs[0, 0].set_title('Training and Validation Loss')
    axs[0, 0].legend()
    axs[0, 0].grid(True, alpha=0.3)
    axs[0, 1].plot(range(1, len(val_metrics['mae']) + 1), val_metrics['mae'], color='orange', linewidth=2)
    axs[0, 1].set_ylabel('MAE (%)')
    axs[0, 1].set_xlabel('Epoch')
    axs[0, 1].set_title('Mean Absolute Error')
    axs[0, 1].grid(True, alpha=0.3)
    axs[1, 0].plot(range(1, len(val_metrics['rmse']) + 1), val_metrics['rmse'], color='green', linewidth=2)
    axs[1, 0].set_ylabel('RMSE (%)')
    axs[1, 0].set_xlabel('Epoch')
    axs[1, 0].set_title('Root Mean Square Error')
    axs[1, 0].grid(True, alpha=0.3)
    axs[1, 1].plot(range(1, len(val_metrics['r2']) + 1), val_metrics['r2'], label='R²', color='purple', linewidth=2)
    axs[1, 1].plot(
        range(1, len(val_metrics['direction_accuracy']) + 1),
        val_metrics['direction_accuracy'],
        label='Direction Accuracy',
        color='red',
        linewidth=2,
    )
    axs[1, 1].set_ylabel('Score')
    axs[1, 1].set_xlabel('Epoch')
    axs[1, 1].set_title('R² and Direction Accuracy')
    axs[1, 1].legend()
    axs[1, 1].grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def save_prediction_plot(results_df: pd.DataFrame, path: Path | str, title: str) -> None:
    df = results_df.copy()
    if df['begin'].dtype == 'object':
        df['begin'] = pd.to_datetime(df['begin'])
    df = df.sort_values('begin')
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.plot(
        df['begin'],
        df['target_price_change'],
        linewidth=2,
        color='#2E8B57',
        label='Реальное изменение',
        marker='o',
        markersize=3,
        alpha=0.8,
    )
    ax.plot(
        df['begin'],
        df['predict'],
        linewidth=2,
        color='#DC143C',
        label='Предсказанное изменение',
        marker='s',
        markersize=3,
        alpha=0.8,
    )
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylabel('Изменение цены (%)', fontsize=12)
    ax.set_xlabel('Дата', fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def save_direction_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    path: Path | str,
    flat_threshold: float = 0.25,
) -> None:
    def to_label(values: np.ndarray) -> np.ndarray:
        labels = np.zeros(len(values), dtype=int)
        labels[values > flat_threshold] = 1
        labels[values < -flat_threshold] = -1
        return labels

    true_lbl = to_label(y_true)
    pred_lbl = to_label(y_pred)
    label_names = ['down', 'flat', 'up']
    label_order = [-1, 0, 1]
    matrix = np.zeros((3, 3), dtype=int)
    idx_map = {-1: 0, 0: 1, 1: 2}
    for t, p in zip(true_lbl, pred_lbl):
        matrix[idx_map[t], idx_map[p]] += 1
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        matrix,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=label_names,
        yticklabels=label_names,
        ax=ax,
    )
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title('Direction confusion matrix')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def visualize_predictions_comparison(
    results_df: pd.DataFrame,
    title: str = 'Сравнение реальных и предсказанных изменений',
) -> None:
    df = results_df.copy()
    if df['begin'].dtype == 'object':
        df['begin'] = pd.to_datetime(df['begin'])
    df = df.sort_values('begin')
    plt.figure(figsize=(16, 8))
    plt.plot(
        df['begin'],
        df['target_price_change'],
        linewidth=2,
        color='#2E8B57',
        label='Реальное изменение',
        marker='o',
        markersize=3,
        alpha=0.8,
    )
    plt.plot(
        df['begin'],
        df['predict'],
        linewidth=2,
        color='#DC143C',
        label='Предсказанное изменение',
        marker='s',
        markersize=3,
        alpha=0.8,
    )
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylabel('Изменение цены (%)', fontsize=12)
    plt.xlabel('Дата', fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()
