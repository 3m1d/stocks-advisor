import torch
from torch import nn
from typing import Optional


class StockLSTMRegressor(nn.Module):
    """
    LSTM регрессор для предсказания изменения стоимости акций
    """
    def __init__(self, input_size: int, hidden_size: int = 64,
                 num_layers: int = 1, dropout: float = 0.5):
        """
        :param input_size: количество числовых признаков
        :param hidden_size: размерность скрытого состояния
        :param num_layers: количество слоев LSTM
        :param dropout: dropout rate
        """
        super(StockLSTMRegressor, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
            bidirectional=False
        )
        
        self.dropout = nn.Dropout(dropout)
        self.regressor = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Forward pass через модель
        """
        if lengths is not None:
            packed_x = nn.utils.rnn.pack_padded_sequence(
                x, lengths.cpu(), batch_first=True, enforce_sorted=False
            )
            packed_output, (hidden, cell) = self.lstm(packed_x)
            output, _ = nn.utils.rnn.pad_packed_sequence(packed_output, batch_first=True)
        else:
            output, (hidden, cell) = self.lstm(x)
        
        hidden_last = hidden[-1]
        
        hidden_last = self.dropout(hidden_last)
        prediction = self.regressor(hidden_last)
        
        return prediction
    