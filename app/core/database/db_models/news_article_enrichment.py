from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, TIMESTAMP, BigInteger, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy import text as _text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.db_models.base import Base
from app.core.database.db_models.news_article import NewsArticle


class NewsSentiment(StrEnum):
    NEGATIVE = 'negative'
    NEUTRAL = 'neutral'
    POSITIVE = 'positive'


class NewsArticleEnrichment(Base):
    """Признаки для новостной статьи"""

    __tablename__ = 'news_article_enrichment'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    news_article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('news_article.id', ondelete='CASCADE'),
        nullable=False,
    )

    # Тикеры, про которых идет речь в новости
    tickers: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default=_text("'[]'"))
    # Сектор влияния новости
    sector: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Тональность новости
    sentiment: Mapped[NewsSentiment] = mapped_column(String(20), nullable=False)
    # Уверенность модели в предсказанной тональности
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=_text('CURRENT_TIMESTAMP'),
    )

    article: Mapped[NewsArticle] = relationship(back_populates='enrichments')

    __table_args__ = (UniqueConstraint('news_article_id', name='uq_news_article_enrichment_article_id'),)

    def __repr__(self) -> str:
        return (
            f'<NewsArticleEnrichment(id={self.id}, news_article_id={self.news_article_id}, '
            f'tickers={self.tickers!r}, sector={self.sector!r}, sentiment={self.sentiment!r}, '
            f'sentiment_score={self.sentiment_score:.4f})>'
        )
