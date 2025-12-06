from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings, setup_logging
from app.core.database import engine

# Setup logging before creating the app
settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)


@app.get('/')
async def root():
    return {'message': 'Hello World'}
