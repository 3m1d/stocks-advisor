import asyncio
import logging
from datetime import date, datetime, time
from random import uniform

import aiohttp
from bs4 import BeautifulSoup, Tag

from app.core.processors.news_parsing.base import NewsParser, NewsSource, ParsedNewsArticle, daterange, normalize_topic
from app.core.processors.news_parsing.fetch import DEFAULT_HEADERS, fetch_html

logger = logging.getLogger(__name__)

BASE_URL = 'https://www.kommersant.ru/archive/rubric'
DEFAULT_TOPICS = {
    3: 'economics',
    4: 'business',
    2: 'politics',
    40: 'financies',
}


class KommersantParser(NewsParser):
    """Парсер новостей с сайта Коммерсант"""

    source = NewsSource.KOMMERSANT

    def __init__(
        self,
        *,
        topics: dict[int, str] | None = None,
        max_concurrent_requests: int = 5,
        max_concurrent_articles: int = 5,
        request_timeout: int = 20,
        retry_count: int = 5,
        delay_between_articles: tuple[float, float] = (0.3, 0.5),
        delay_between_days: tuple[float, float] = (0.5, 1.5),
    ) -> None:
        self.topics = topics or DEFAULT_TOPICS
        self.max_concurrent_requests = max_concurrent_requests
        self.max_concurrent_articles = max_concurrent_articles
        self.request_timeout = request_timeout
        self.retry_count = retry_count
        self.delay_between_articles = delay_between_articles
        self.delay_between_days = delay_between_days

    async def parse(self, start_date: date, end_date: date) -> list[ParsedNewsArticle]:
        articles: list[ParsedNewsArticle] = []
        day_semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        article_semaphore = asyncio.Semaphore(self.max_concurrent_articles)

        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            for day in daterange(start_date, end_date):
                day_articles = await self._parse_day(session, day, day_semaphore, article_semaphore)
                articles.extend(day_articles)

        return articles

    async def _parse_day(
        self,
        session: aiohttp.ClientSession,
        day: date,
        day_semaphore: asyncio.Semaphore,
        article_semaphore: asyncio.Semaphore,
    ) -> list[ParsedNewsArticle]:
        async with day_semaphore:
            cards_by_topic: dict[str, list[Tag]] = {}
            for topic_id, topic_name in self.topics.items():
                url = f'{BASE_URL}/{topic_id}/day/{day.strftime("%Y-%m-%d")}'
                html = await fetch_html(session, url, retries=self.retry_count, timeout=self.request_timeout)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                cards_by_topic[topic_name] = self._get_article_cards(soup)
                await asyncio.sleep(uniform(*self.delay_between_days))

            tasks = [
                self._parse_article(session, day, card, topic_name, article_semaphore)
                for topic_name, cards in cards_by_topic.items()
                for card in cards
            ]
            results = await asyncio.gather(*tasks)
            return [article for article in results if article is not None]

    async def _parse_article(
        self,
        session: aiohttp.ClientSession,
        day: date,
        card: Tag,
        topic_name: str,
        article_semaphore: asyncio.Semaphore,
    ) -> ParsedNewsArticle | None:
        async with article_semaphore:
            url = card.get('data-article-url')
            heading = card.get('data-article-title', '').strip()
            if not url:
                return None

            await asyncio.sleep(uniform(*self.delay_between_articles))
            html = await fetch_html(session, url, retries=self.retry_count, timeout=self.request_timeout)
            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            text = self._parse_article_text(soup)
            if not text:
                return None

            published_at = self._extract_datetime(day, card)
            return ParsedNewsArticle(
                date=published_at or datetime.combine(day, time.min),
                topic=normalize_topic(topic_name),
                text=text,
                heading=heading or None,
                url=url,
                source=self.source,
            )

    @staticmethod
    def _get_article_cards(soup: BeautifulSoup) -> list[Tag]:
        cards: list[Tag] = []
        for lenta_tag in soup.find_all('div', class_='rubric_lenta'):
            cards.extend(lenta_tag.find_all('article'))
        return cards

    @staticmethod
    def _parse_article_text(soup: BeautifulSoup) -> str:
        parts = [paragraph.text.strip() for paragraph in soup.find_all('p', class_='doc__text')]
        return ' '.join(part for part in parts if part).strip()

    @staticmethod
    def _extract_datetime(day: date, card: Tag) -> datetime | None:
        timetag = card.find('p', class_='uho__tag rubric_lenta__item_tag hide_desktop')
        if not timetag:
            return None
        try:
            timetext = timetag.text.split(', ')[-1]
            hour, minute = map(int, timetext.split(':'))
            return datetime.combine(day, time(hour=hour, minute=minute))
        except (ValueError, IndexError):
            return None
