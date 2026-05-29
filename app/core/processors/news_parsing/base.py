from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NewsSource(str, Enum):
    INTERFAX = 'interfax'
    KOMMERSANT = 'kommersant'
    VEDOMOSTI = 'vedomosti'


class ParsedNewsArticle(BaseModel):
    """News article data"""

    model_config = ConfigDict(frozen=True)

    published_at: datetime
    topic: str | None = None
    text: str
    heading: str | None = None
    url: str
    source: NewsSource


class NewsParseResult(BaseModel):
    """Batch parse result"""

    model_config = ConfigDict(frozen=True)

    source: NewsSource
    start_date: date
    end_date: date
    articles: list[ParsedNewsArticle] = Field(default_factory=list)


def daterange(start_date: date, end_date: date) -> list[date]:
    """Return all dates in the inclusive range."""
    days = (end_date - start_date).days
    return [start_date + timedelta(days=i) for i in range(days + 1)]


def normalize_topic(topic: str | None) -> str | None:
    """Normalize topic names"""
    if topic == 'financies':
        return 'finance'
    return topic


class NewsParser(ABC):
    """Interface for news parsers"""

    source: NewsSource

    @abstractmethod
    async def parse(self, start_date: date, end_date: date) -> list[ParsedNewsArticle]:
        """Parse news articles for the given date range"""
