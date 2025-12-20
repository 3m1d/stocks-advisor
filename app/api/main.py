from fastapi import APIRouter

from app.api.routes import auth, index, parse

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(index.router)
api_router.include_router(parse.router)
