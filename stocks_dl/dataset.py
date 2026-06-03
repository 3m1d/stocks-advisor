import torch
import pandas as pd
import numpy as np
from torch.utils.data import Dataset
from typing import Tuple


class StockDataset(Dataset):
    """
    Dataset для данных по акциям (только числовые фичи)
    """
    def __init__(self, X: pd.DataFrame, y: pd.Series, sequence_length: int = 7):
        """
        :param X: DataFrame с признаками (без даты и целевой переменной)
        :param y: Series с целевой переменной (процент изменения)
        :param sequence_length: длина последовательности для LSTM
        """
        self.sequence_length = sequence_length
        self.feature_names = X.columns.tolist()
        self.num_features = len(self.feature_names)
        
        self.X_mean = X.mean().values
        self.X_std = X.std().values
        self.X_std[self.X_std == 0] = 1
        
        X_normalized = (X.values - self.X_mean) / self.X_std
        y_values = y.values
        
        self.sequences = []
        self.targets = []
        
        for i in range(len(X) - sequence_length + 1):
            seq = X_normalized[i:i+sequence_length]
            target = y_values[i+sequence_length-1]
            self.sequences.append(seq)
            self.targets.append(target)
        
        self.sequences = np.array(self.sequences, dtype=np.float32)
        self.targets = np.array(self.targets, dtype=np.float32)
        
        print(f"Создано {len(self.sequences)} последовательностей длины {sequence_length}")
        print(f"Количество признаков: {self.num_features}")
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        features = torch.tensor(self.sequences[idx], dtype=torch.float32)
        target = torch.tensor(self.targets[idx], dtype=torch.float32)
        length = self.sequence_length
        
        return features, target, length
