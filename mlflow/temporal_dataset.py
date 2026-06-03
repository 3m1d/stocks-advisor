"""Temporal LSTM dataset, splits and evaluation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from train import calculate_metrics

from constants import TARGET_COLUMN


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def split_train_test(
    df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    test_size: float = 0.2,
    val_size: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.sort_values('begin').reset_index(drop=True)
    test_idx = int(len(df) * (1 - test_size))
    train_val_df = df.iloc[:test_idx].copy()
    test_df = df.iloc[test_idx:].copy()
    val_idx = int(len(train_val_df) * (1 - val_size))
    train_df = train_val_df.iloc[:val_idx].copy()
    val_df = train_val_df.iloc[val_idx:].copy()
    return train_df, val_df, test_df


def split_train_val(
    df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    val_size: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values('begin').reset_index(drop=True)
    val_idx = int(len(df) * (1 - val_size))
    train_df = df.iloc[:val_idx].copy()
    val_df = df.iloc[val_idx:].copy()
    return train_df, val_df


class TemporalStockDataset(Dataset):
    def __init__(self, X: pd.DataFrame, y: pd.Series, sequence_length: int, mean=None, std=None):
        if len(X) < sequence_length:
            raise ValueError('Not enough rows for the selected sequence_length')
        self.sequence_length = sequence_length
        self.feature_names = X.columns.tolist()
        self.num_features = len(self.feature_names)
        self.X_mean = np.asarray(X.mean().values if mean is None else mean)
        self.X_std = np.asarray(X.std().values if std is None else std)
        self.X_std[self.X_std == 0] = 1
        X_normalized = (X.values - self.X_mean) / self.X_std
        y_values = y.values
        self.sequences = []
        self.targets = []
        for i in range(len(X) - sequence_length + 1):
            self.sequences.append(X_normalized[i : i + sequence_length])
            self.targets.append(y_values[i + sequence_length - 1])
        self.sequences = np.asarray(self.sequences, dtype=np.float32)
        self.targets = np.asarray(self.targets, dtype=np.float32)

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int):
        features = torch.tensor(self.sequences[idx], dtype=torch.float32)
        target = torch.tensor(self.targets[idx], dtype=torch.float32)
        length = self.sequence_length
        return features, target, length


def make_loaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    sequence_length: int,
    batch_size: int,
    target_column: str = TARGET_COLUMN,
):
    train_X = train_df.drop(columns=['begin', target_column])
    train_y = train_df[target_column]
    val_X = val_df.drop(columns=['begin', target_column])
    val_y = val_df[target_column]
    test_X = test_df.drop(columns=['begin', target_column])
    test_y = test_df[target_column]
    train_dataset = TemporalStockDataset(train_X, train_y, sequence_length)
    val_dataset = TemporalStockDataset(
        val_X, val_y, sequence_length, mean=train_dataset.X_mean, std=train_dataset.X_std
    )
    test_dataset = TemporalStockDataset(
        test_X, test_y, sequence_length, mean=train_dataset.X_mean, std=train_dataset.X_std
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    return train_dataset, val_dataset, test_dataset, train_loader, val_loader, test_loader


@torch.no_grad()
def evaluate_model(model, loader) -> tuple[dict, np.ndarray, np.ndarray]:
    device = next(model.parameters()).device
    all_predictions = []
    all_targets = []
    model.eval()
    for features, targets, lengths in loader:
        features = features.to(device)
        targets = targets.to(device).float().view(-1, 1)
        lengths = lengths.to(device)
        predictions = model(features, lengths)
        all_predictions.extend(predictions.cpu().numpy().reshape(-1))
        all_targets.extend(targets.cpu().numpy().reshape(-1))
    all_predictions = np.asarray(all_predictions).reshape(-1)
    all_targets = np.asarray(all_targets).reshape(-1)
    metrics = calculate_metrics(all_targets, all_predictions)
    return metrics, all_targets, all_predictions


def build_predictions_df(
    test_df: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sequence_length: int,
    target_column: str = TARGET_COLUMN,
) -> pd.DataFrame:
    test_dates = (
        test_df.sort_values('begin')
        .reset_index(drop=True)
        .iloc[sequence_length - 1 :]['begin']
        .reset_index(drop=True)
    )
    n = min(len(test_dates), len(y_pred), len(y_true))
    predictions_df = pd.DataFrame(
        {
            'begin': test_dates.iloc[:n].values,
            target_column: y_true[:n],
            'predict': y_pred[:n],
        }
    )
    predictions_df['error'] = predictions_df['predict'] - predictions_df[target_column]
    predictions_df['abs_error'] = predictions_df['error'].abs()
    predictions_df['direction_match'] = np.sign(predictions_df['predict']) == np.sign(
        predictions_df[target_column]
    )
    return predictions_df
