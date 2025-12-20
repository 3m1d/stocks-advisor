from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.main import api_router
from app.config import get_settings, setup_logging
from app.core.database import engine
from app.web.middleware.request_logging import RequestLoggingMiddleware

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


# Middleware for saving requests history into database
app.add_middleware(RequestLoggingMiddleware)


app.include_router(api_router, prefix=settings.api.V1)
