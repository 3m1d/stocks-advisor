from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import cached, TTLCache

from app.core.database.session import DBSession
from app.core.database.repositories.asset_candle import AssetCandleRepository
from app.core.processors.feature_generator import FeatureGenerator
from app.core.processors.model_predictor import ModelPredictor

router = APIRouter(prefix='/predict', tags=['Predict'])


@cached(cache=TTLCache(maxsize=100, ttl=600))
async def fetch_and_process_candles(ticker: str, num_records: int, session: AsyncSession):
    repo = AssetCandleRepository(session)
    df = await repo.get_dataframe_by_ticker(ticker, num_records+200)
    
    if df.empty:
        raise HTTPException(404, f"No data found for ticker '{ticker}'")
    
    feature_gen = FeatureGenerator()
    processed_df = feature_gen.process(
        df=df,
        include_original=False,
        add_targets=False,
        clean=True
    )
    
    if processed_df.empty:
        raise HTTPException(400, "Not enough data for feature generation")
    
    return processed_df


@router.post('/forward')
async def forward_inference(ticker: str, num_records: int, session: DBSession):
    """ML inference for stock price prediction."""
    try:
        processed_df = await fetch_and_process_candles(ticker, num_records, session)
        model_predictor = ModelPredictor(ticker, "app/core/processors/models")
        predictions = model_predictor.predict(processed_df)
        return predictions
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, f"Model not found for ticker '{ticker}'")
    except Exception as e:
        raise HTTPException(500, f"Prediction failed: {str(e)}")