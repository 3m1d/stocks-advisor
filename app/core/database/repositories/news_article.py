from datetime import datetime
from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.news_article import NewsArticle, NewsSource


class NewsArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        published_at: datetime,
        topic: str,
        text: str,
        heading: str,
        url: str,
        source: NewsSource,
    ) -> NewsArticle:
        async with self.session.begin():
            article = NewsArticle(
                published_at=published_at,
                topic=topic,
                text=text,
                heading=heading,
                url=url,
                source=source,
            )
            self.session.add(article)
        return article

    async def bulk_add(self, articles: list[NewsArticle], batch_size: int = 1_000) -> int:
        if not articles:
            return 0
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than 0')

        payload = [
            {
                'published_at': a.published_at,
                'topic': a.topic,
                'text': a.text,
                'heading': a.heading,
                'url': a.url,
                'source': a.source,
            }
            for a in articles
        ]

        stmt = (
            insert(NewsArticle)
            .on_conflict_do_nothing(constraint='unique_url_published_at')
            .returning(NewsArticle.id)
            .execution_options(insertmanyvalues_page_size=batch_size)
        )

        async with self.session.begin():
            result = await self.session.execute(stmt, payload)
            return len(result.all())

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        source: NewsSource | None = None,
        topic: str | None = None,
    ) -> Sequence[NewsArticle]:
        q = select(NewsArticle).order_by(
            desc(NewsArticle.published_at),
            desc(NewsArticle.id),
        )

        if published_from is not None:
            q = q.where(NewsArticle.published_at >= published_from)
        if published_to is not None:
            q = q.where(NewsArticle.published_at <= published_to)
        if source is not None:
            q = q.where(NewsArticle.source == source)
        if topic is not None:
            q = q.where(NewsArticle.topic == topic)

        q = q.limit(limit).offset(offset)
        async with self.session.begin():
            result = await self.session.scalars(q)
            return result.all()
