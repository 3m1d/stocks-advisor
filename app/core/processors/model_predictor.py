import pickle
import pandas as pd
from typing import List, Dict


class ModelPredictor:
    """ML model for stock price prediction."""

    def __init__(self, ticker: str, model_dir: str) -> None:
        """
        Initialize the predictor with a trained model for specific ticker.

        Args:
            ticker: Stock ticker symbol ('SBER', 'TCSG', 'GAZP', 'LKOH', 'ROSN')
            model_dir: Directory containing model files
        """
        self.ticker = ticker
        model_path = f"{model_dir}/{ticker}_model.pkl"

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

    def predict(self, processed_data: pd.DataFrame) -> List[Dict]:
        """
        Make predictions on processed data.

        Args:
            processed_data: DataFrame with technical indicators and 'begin' column

        Returns:
            List of prediction dictionaries in format [{"datetime": ..., "value": ...}]
        """
        # Remove timestamp column for prediction
        features = processed_data.drop(columns = ['begin'])

        # Generate predictions
        predictions = self.model.predict(features)

        # Format results for API response
        return [
            {"datetime": ts, "value": float(pred)}
            for ts, pred in zip(processed_data['begin'], predictions)
        ]