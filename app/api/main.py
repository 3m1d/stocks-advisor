from fastapi import APIRouter

from app.api.routes import auth, history, index, parse, predict

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(index.router)
api_router.include_router(parse.router)
api_router.include_router(history.router)
api_router.include_router(predict.router)
