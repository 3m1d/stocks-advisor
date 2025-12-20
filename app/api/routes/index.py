from fastapi import APIRouter

router = APIRouter(prefix='/index', tags=['Index'])


@router.get('/')
async def root():
    return {'message': 'Hello World'}
