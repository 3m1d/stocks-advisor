from fastapi import FastAPI

from app.core.config import get_settings, setup_logging

# Setup logging before creating the app
settings = get_settings()
setup_logging(settings)

app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
)


@app.get('/')
async def root():
    return {'message': 'Hello World'}
