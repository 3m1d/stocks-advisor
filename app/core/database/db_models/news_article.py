from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, BigInteger, Index, String, Text, UniqueConstraint, text as _text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.db_models.base import Base

if TYPE_CHECKING:
    from app.core.database.db_models.news_article_enrichment import NewsArticleEnrichment


class NewsSource(str, Enum):
    INTERFAX = 'interfax'
    KOMMERSANT = 'kommersant'
    VEDOMOSTI = 'vedomosti'


class NewsArticle(Base):
    """Новостная статья"""

    __tablename__ = 'news_article'

    # ID
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Дата и время публикации
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    # Тема
    topic: Mapped[str] = mapped_column(String(), nullable=False)

    # Текст статьи
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Заголовок статьи
    heading: Mapped[str] = mapped_column(Text, nullable=False)

    # URL статьи
    url: Mapped[str] = mapped_column(String(), nullable=False)

    # Источник новости
    source: Mapped[NewsSource] = mapped_column(String(), nullable=False)

    # Дата создания записи в БД
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=_text('CURRENT_TIMESTAMP'),
    )

    enrichments: Mapped[list[NewsArticleEnrichment]] = relationship(
        back_populates='article',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        Index('idx_news_article_source_published_at', 'source', 'published_at'),
        Index('idx_news_article_topic_published_at', 'topic', 'published_at'),
        Index('idx_news_article_published_at', 'published_at'),
        UniqueConstraint('url', 'published_at', name='unique_url_published_at'),
    )

    def __repr__(self) -> str:
        return f'<NewsArticle(id={self.id}, published_at={self.published_at}, topic={self.topic!r}, text={self.text!r}, heading={self.heading!r}, url={self.url!r}, source={self.source!r})>'
