from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database.db_models.news_article import NewsArticle, NewsSource
from app.core.database.db_models.news_article_enrichment import NewsArticleEnrichment, NewsSentiment

NEWS_ARTICLE_DATAFRAME_COLUMNS = [
    'id',
    'published_at',
    'topic',
    'text',
    'heading',
    'url',
    'source',
]


def _normalize_topic(topic: str) -> str:
    return 'finance' if topic == 'financies' else topic


def news_articles_to_dataframe(articles: Sequence[NewsArticle]) -> pd.DataFrame:
    """Convert NewsArticle rows to a DataFrame compatible with run_news_pipeline."""
    if not articles:
        return pd.DataFrame(columns=NEWS_ARTICLE_DATAFRAME_COLUMNS)

    rows = [
        {
            'id': article.id,
            'published_at': article.published_at,
            'topic': _normalize_topic(article.topic),
            'text': article.text,
            'heading': article.heading,
            'url': article.url,
            'source': article.source.value if isinstance(article.source, NewsSource) else article.source,
        }
        for article in articles
    ]

    df = pd.DataFrame(rows, columns=NEWS_ARTICLE_DATAFRAME_COLUMNS)
    df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
    return df.sort_values(by='published_at', ascending=True).reset_index(drop=True)


NEWS_ARTICLE_ENRICHMENT_DATAFRAME_COLUMNS = [
    'id',
    'news_article_id',
    'published_at',
    'topic',
    'tickers',
    'sector',
    'sentiment',
    'sentiment_score',
]


def news_article_enrichments_to_dataframe(
    enrichments: Sequence[NewsArticleEnrichment],
) -> pd.DataFrame:
    """Convert NewsArticleEnrichment rows to a DataFrame."""
    if not enrichments:
        return pd.DataFrame(columns=NEWS_ARTICLE_ENRICHMENT_DATAFRAME_COLUMNS)

    rows = [
        {
            'id': enrichment.id,
            'news_article_id': enrichment.news_article_id,
            'published_at': enrichment.article.published_at,
            'topic': _normalize_topic(enrichment.article.topic),
            'tickers': enrichment.tickers,
            'sector': enrichment.sector,
            'sentiment': (
                enrichment.sentiment.value if isinstance(enrichment.sentiment, NewsSentiment) else enrichment.sentiment
            ),
            'sentiment_score': enrichment.sentiment_score,
        }
        for enrichment in enrichments
    ]

    df = pd.DataFrame(rows, columns=NEWS_ARTICLE_ENRICHMENT_DATAFRAME_COLUMNS)
    df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
    return df.sort_values(by=['published_at', 'id'], ascending=True).reset_index(drop=True)


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

    async def count(
        self,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        source: NewsSource | None = None,
        topic: str | None = None,
    ) -> int:
        q = select(func.count()).select_from(NewsArticle)

        if published_from is not None:
            q = q.where(NewsArticle.published_at >= published_from)
        if published_to is not None:
            q = q.where(NewsArticle.published_at <= published_to)
        if source is not None:
            q = q.where(NewsArticle.source == source)
        if topic is not None:
            q = q.where(NewsArticle.topic == topic)

        async with self.session.begin():
            return await self.session.scalar(q) or 0

    async def get_latest_published_date(self, source: NewsSource | None = None) -> date | None:
        q = select(func.max(cast(NewsArticle.published_at, Date)))
        if source is not None:
            q = q.where(NewsArticle.source == source)
        async with self.session.begin():
            return await self.session.scalar(q)

    async def get_latest_enriched_published_date(self, source: NewsSource | None = None) -> date | None:
        q = (
            select(func.max(cast(NewsArticle.published_at, Date)))
            .select_from(NewsArticleEnrichment)
            .join(NewsArticle, NewsArticle.id == NewsArticleEnrichment.news_article_id)
        )
        if source is not None:
            q = q.where(NewsArticle.source == source)
        async with self.session.begin():
            return await self.session.scalar(q)

    async def get_all_as_dataframe(
        self,
        limit: int = 100,
        offset: int = 0,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        source: NewsSource | None = None,
        topic: str | None = None,
    ) -> pd.DataFrame:
        articles = await self.get_all(
            limit=limit,
            offset=offset,
            published_from=published_from,
            published_to=published_to,
            source=source,
            topic=topic,
        )
        return news_articles_to_dataframe(articles)

    async def bulk_create_enrichments(
        self,
        enrichments: list[NewsArticleEnrichment],
        batch_size: int = 1_000,
    ) -> int:
        if not enrichments:
            return 0
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than 0')

        payload = [
            {
                'news_article_id': enrichment.news_article_id,
                'tickers': enrichment.tickers,
                'sector': enrichment.sector,
                'sentiment': (
                    enrichment.sentiment.value
                    if isinstance(enrichment.sentiment, NewsSentiment)
                    else enrichment.sentiment
                ),
                'sentiment_score': enrichment.sentiment_score,
            }
            for enrichment in enrichments
        ]

        stmt = insert(NewsArticleEnrichment)
        stmt = (
            stmt.on_conflict_do_update(
                constraint='uq_news_article_enrichment_article_id',
                set_={
                    'tickers': stmt.excluded.tickers,
                    'sector': stmt.excluded.sector,
                    'sentiment': stmt.excluded.sentiment,
                    'sentiment_score': stmt.excluded.sentiment_score,
                    'created_at': func.now(),
                },
            )
            .returning(NewsArticleEnrichment.id)
            .execution_options(insertmanyvalues_page_size=batch_size)
        )

        async with self.session.begin():
            result = await self.session.execute(stmt, payload)
            return len(result.all())

    async def get_all_enrichments(
        self,
        limit: int | None = None,
        offset: int = 0,
        news_article_id: int | None = None,
        ticker: str | None = None,
        sector: str | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> list[NewsArticleEnrichment]:
        q = select(NewsArticleEnrichment).options(joinedload(NewsArticleEnrichment.article))

        if news_article_id is not None:
            q = q.where(NewsArticleEnrichment.news_article_id == news_article_id)

        if ticker is not None:
            q = q.where(cast(NewsArticleEnrichment.tickers, JSONB).contains([ticker]))

        if sector is not None:
            q = q.where(NewsArticleEnrichment.sector == sector)

        if date_start is not None or date_end is not None:
            q = q.join(NewsArticleEnrichment.article)
            if date_start is not None:
                q = q.where(NewsArticle.published_at >= date_start)
            if date_end is not None:
                q = q.where(NewsArticle.published_at <= date_end)

        q = q.distinct(NewsArticleEnrichment.news_article_id).order_by(
            NewsArticleEnrichment.news_article_id,
            desc(NewsArticleEnrichment.created_at),
            desc(NewsArticleEnrichment.id),
        )

        if limit is not None:
            q = q.limit(limit)
        if offset is not None:
            q = q.offset(offset)
        async with self.session.begin():
            result = await self.session.scalars(q)
            return list(result.all())

    async def get_all_enrichments_as_dataframe(
        self,
        limit: int | None = None,
        offset: int = 0,
        news_article_id: int | None = None,
        ticker: str | None = None,
        sector: str | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> pd.DataFrame:
        enrichments = await self.get_all_enrichments(
            limit=limit,
            offset=offset,
            news_article_id=news_article_id,
            ticker=ticker,
            sector=sector,
            date_start=date_start,
            date_end=date_end,
        )
        return news_article_enrichments_to_dataframe(enrichments)

    async def get_latest_enrichment(self, news_article_id: int) -> NewsArticleEnrichment | None:
        q = (
            select(NewsArticleEnrichment)
            .where(NewsArticleEnrichment.news_article_id == news_article_id)
            .order_by(desc(NewsArticleEnrichment.created_at), desc(NewsArticleEnrichment.id))
            .limit(1)
        )
        async with self.session.begin():
            return await self.session.scalar(q)

    async def get_enrichments(self, news_article_id: int) -> list[NewsArticleEnrichment]:
        q = (
            select(NewsArticleEnrichment)
            .where(NewsArticleEnrichment.news_article_id == news_article_id)
            .order_by(desc(NewsArticleEnrichment.created_at), desc(NewsArticleEnrichment.id))
        )
        async with self.session.begin():
            result = await self.session.scalars(q)
            return list(result.all())
