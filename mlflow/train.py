import torch
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from typing import List, Optional, Any, Dict
from torch import nn
from torch.utils.data import DataLoader
from IPython.display import clear_output
from tqdm import tqdm
from sklearn.metrics import mean_absolute_error, r2_score
from model import StockLSTMRegressor


sns.set_style('whitegrid')
plt.rcParams.update({'font.size': 12})


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Рассчитывает метрики для регрессии"""
    mae = mean_absolute_error(y_true, y_pred)
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_true, y_pred)
    direction_accuracy = np.mean((y_true > 0) == (y_pred > 0))
    
    return {
        'mae': mae,
        'rmse': rmse,
        'r2': r2,
        'direction_accuracy': direction_accuracy
    }


def plot_metrics(train_losses: List[float], val_losses: List[float], 
                 val_metrics: Dict[str, List[float]]):
    """Отображение метрик для регрессии"""
    clear_output()
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    
    axs[0, 0].plot(range(1, len(train_losses) + 1), train_losses, label='train', linewidth=2)
    axs[0, 0].plot(range(1, len(val_losses) + 1), val_losses, label='val', linewidth=2)
    axs[0, 0].set_ylabel('MSE Loss')
    axs[0, 0].set_xlabel('Epoch')
    axs[0, 0].set_title('Training and Validation Loss')
    axs[0, 0].legend()
    axs[0, 0].grid(True, alpha=0.3)
    
    axs[0, 1].plot(range(1, len(val_metrics['mae']) + 1), val_metrics['mae'], 
                   color='orange', linewidth=2)
    axs[0, 1].set_ylabel('MAE (%)')
    axs[0, 1].set_xlabel('Epoch')
    axs[0, 1].set_title('Mean Absolute Error')
    axs[0, 1].grid(True, alpha=0.3)
    
    axs[1, 0].plot(range(1, len(val_metrics['rmse']) + 1), val_metrics['rmse'], 
                   color='green', linewidth=2)
    axs[1, 0].set_ylabel('RMSE (%)')
    axs[1, 0].set_xlabel('Epoch')
    axs[1, 0].set_title('Root Mean Square Error')
    axs[1, 0].grid(True, alpha=0.3)
    
    axs[1, 1].plot(range(1, len(val_metrics['r2']) + 1), val_metrics['r2'], 
                   label='R²', color='purple', linewidth=2)
    axs[1, 1].plot(range(1, len(val_metrics['direction_accuracy']) + 1), 
                   val_metrics['direction_accuracy'], label='Direction Accuracy', 
                   color='red', linewidth=2)
    axs[1, 1].set_ylabel('Score')
    axs[1, 1].set_xlabel('Epoch')
    axs[1, 1].set_title('R² and Direction Accuracy')
    axs[1, 1].legend()
    axs[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def training_epoch(model: StockLSTMRegressor, optimizer: torch.optim.Optimizer, 
                   criterion: nn.Module, loader: DataLoader, tqdm_desc: str) -> float:
    """Одна эпоха обучения"""
    device = next(model.parameters()).device
    train_loss = 0.0
    
    model.train()
    for features, targets, lengths in tqdm(loader, desc=tqdm_desc):
        features = features.to(device)
        targets = targets.to(device).float().view(-1, 1)
        lengths = lengths.to(device)
        
        predictions = model(features, lengths)
        loss = criterion(predictions, targets)
        
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        
        train_loss += loss.item() * features.size(0)
    
    train_loss /= len(loader.dataset)
    return train_loss


@torch.no_grad()
def validation_epoch(model: StockLSTMRegressor, criterion: nn.Module,
                     loader: DataLoader, tqdm_desc: str) -> tuple:
    """Одна эпоха валидации"""
    device = next(model.parameters()).device
    val_loss = 0.0
    all_predictions = []
    all_targets = []
    
    model.eval()
    for features, targets, lengths in tqdm(loader, desc=tqdm_desc):
        features = features.to(device)
        targets = targets.to(device).float().view(-1, 1)
        lengths = lengths.to(device)
        
        predictions = model(features, lengths)
        loss = criterion(predictions, targets)
        
        val_loss += loss.item() * features.size(0)
        all_predictions.extend(predictions.cpu().numpy())
        all_targets.extend(targets.cpu().numpy())
    
    val_loss /= len(loader.dataset)
    
    all_predictions = np.array(all_predictions).flatten()
    all_targets = np.array(all_targets).flatten()
    
    metrics = calculate_metrics(all_targets, all_predictions)
    
    return val_loss, metrics, all_predictions, all_targets


def train(model: StockLSTMRegressor, optimizer: torch.optim.Optimizer,
          scheduler: Optional[Any], train_loader: DataLoader,
          val_loader: DataLoader, num_epochs: int, show_plots: bool = True):
    """Обучение регрессора"""
    train_losses, val_losses = [], []
    val_metrics = {
        'mae': [], 'rmse': [], 'r2': [], 'direction_accuracy': []
    }
    criterion = nn.MSELoss()
    
    for epoch in range(1, num_epochs + 1):
        train_loss = training_epoch(
            model, optimizer, criterion, train_loader,
            tqdm_desc=f'Training {epoch}/{num_epochs}'
        )
        
        val_loss, metrics, val_preds, val_targets = validation_epoch(
            model, criterion, val_loader,
            tqdm_desc=f'Validating {epoch}/{num_epochs}'
        )
        
        if scheduler is not None:
            if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_loss)
            else:
                scheduler.step()
        
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        for key in val_metrics:
            val_metrics[key].append(metrics[key])
        
        if show_plots:
            plot_metrics(train_losses, val_losses, val_metrics)
            print(f'\nEpoch {epoch}/{num_epochs}:')
            print(f'  Train Loss: {train_loss:.6f}')
            print(f'  Val Loss:   {val_loss:.6f}')
            print(f'  MAE:  {metrics["mae"]:.4f}%')
            print(f'  RMSE: {metrics["rmse"]:.4f}%')
            print(f'  R²:   {metrics["r2"]:.4f}')
            print(f'  Dir Acc: {metrics["direction_accuracy"]:.4f}')
        else:
            print(
                f'Epoch {epoch}/{num_epochs}: train={train_loss:.6f} val={val_loss:.6f} '
                f'mae={metrics["mae"]:.4f}% dir_acc={metrics["direction_accuracy"]:.4f}'
            )
    
    return train_losses, val_losses, val_metrics
