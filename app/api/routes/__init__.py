from .auth import router as auth_router
from .index import router as index_router
from .parse import router as parse_router
from .predict import router as predict_router  

__all__ = [
    "auth_router",
    "index_router", 
    "parse_router",
    "predict_router" 
]