from fastapi import APIRouter, HTTPException
from sqlalchemy import select, desc
import pandas as pd

from app.core.database.session import DBSession
from app.core.database.db_models.asset_candle import AssetCandle
from app.core.processors.feature_generator import FeatureGenerator
from app.core.processors.model_predictor import ModelPredictor

router = APIRouter(prefix='/predict', tags=['Predict'])


@router.post('/forward')
async def forward_inference(ticker: str, num_records: int, session: DBSession):
    """ML inference for stock price prediction."""
    # Get data from database
    query = (
        select(AssetCandle)
        .where(AssetCandle.ticker == ticker)
        .order_by(desc(AssetCandle.begin))
        .limit(num_records)
    )
    
    result = await session.execute(query)
    candles = result.scalars().all()
    
    if not candles:
        raise HTTPException(404, f"No data found for ticker '{ticker}'")
    
    # Convert to DataFrame
    data = []
    for candle in reversed(candles):
        data.append({
            'begin': candle.begin,
            'open': float(candle.open),
            'high': float(candle.high),
            'low': float(candle.low),
            'close': float(candle.close),
            'volume': float(candle.volume),
            'value': float(candle.value) if candle.value else None,
            'ticker': candle.ticker
        })
    
    df = pd.DataFrame(data)
    
    # Generate features
    feature_gen = FeatureGenerator()
    processed_df = feature_gen.process(
        df=df,
        include_original=False,
        add_targets=False,
        clean=True
    )
    
    if processed_df.empty:
        raise HTTPException(400, "Not enough data for feature generation")
    
    # Run ML inference
    model_predictor = ModelPredictor(ticker, "app/core/processors/models")
    predictions = model_predictor.predict(processed_df)
    
    return predictions