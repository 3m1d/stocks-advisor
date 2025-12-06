import asyncio
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, setup_logging
from app.core.database import get_db_session


class BaseDaemon(ABC):
    """Базовый класс для демонов"""

    def __init__(self):
        self.settings = get_settings()
        setup_logging(self.settings)

    @abstractmethod
    async def execute(self, session: AsyncSession) -> None:
        """Implement daemon logic here"""
        pass

    def run(self) -> None:
        asyncio.run(self._run_with_session())

    async def _run_with_session(self) -> None:
        async with get_db_session() as session:
            await self.execute(session)
