from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.core.database import NewsArticle, NewsSource


class ParsedNewsArticle(BaseModel):
    """News article data"""

    model_config = ConfigDict(frozen=True)

    published_at: datetime
    topic: str | None = None
    text: str
    heading: str | None = None
    url: str
    source: NewsSource

    def to_db_model(self) -> NewsArticle:
        return NewsArticle(
            published_at=self.published_at,
            topic=normalize_topic(self.topic) or '',
            text=self.text,
            heading=self.heading or '',
            url=self.url,
            source=self.source,
        )


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


def date_range_batches(start_date: date, end_date: date, batch_days: int = 30) -> list[tuple[date, date]]:
    """Split an inclusive date range into chunks of at most batch_days."""
    if batch_days <= 0:
        raise ValueError('batch_days must be greater than 0')

    batches: list[tuple[date, date]] = []
    current = start_date
    while current <= end_date:
        batch_end = min(current + timedelta(days=batch_days - 1), end_date)
        batches.append((current, batch_end))
        current = batch_end + timedelta(days=1)
    return batches


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
