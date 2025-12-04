import logging
from abc import ABC, abstractmethod

from app.core.config import get_settings, setup_logging


class BaseDaemon(ABC):
    """Базовый класс для демонов"""

    def __init__(self):
        self.settings = get_settings()
        setup_logging(self.settings)

    @abstractmethod
    def run(self) -> None:
        pass
