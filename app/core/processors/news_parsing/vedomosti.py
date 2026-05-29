import asyncio
import logging
import re
from datetime import date, datetime, time
from functools import lru_cache
from random import uniform

import aiohttp
from bs4 import BeautifulSoup
from trafilatura import extract, fetch_url
from trafilatura.metadata import extract_metadata

from app.core.database.db_models.news_article import NewsSource
from app.core.processors.news_parsing.base import NewsParser, ParsedNewsArticle, normalize_topic
from app.core.processors.news_parsing.fetch import DEFAULT_HEADERS, fetch_html

logger = logging.getLogger(__name__)

SITEMAP_URL = 'https://www.vedomosti.ru/sitemap_news3.xml'
URL_DATE_PATTERN = re.compile(r'/(\w+)/news/(\d{4})/(\d{2})/(\d{2})/')
VEDOMOSTI_HEADERS = {
    **DEFAULT_HEADERS,
    'Referer': 'https://www.vedomosti.ru/',
}


class VedomostiParser(NewsParser):
    """
    Парсер новостей с сайта Ведомости.

    На сайте есть API, предоставляющее список новостей со ссылками за определенный период времени.
    """

    source = NewsSource.VEDOMOSTI

    def __init__(
        self,
        *,
        sitemap_url: str = SITEMAP_URL,
        max_concurrent_articles: int = 3,
        delay_between_articles: tuple[float, float] = (0.2, 0.5),
        request_timeout: int = 20,
        retry_count: int = 5,
    ) -> None:
        self.sitemap_url = sitemap_url
        self.max_concurrent_articles = max_concurrent_articles
        self.delay_between_articles = delay_between_articles
        self.request_timeout = request_timeout
        self.retry_count = retry_count

    async def parse(self, start_date: date, end_date: date) -> list[ParsedNewsArticle]:
        candidates = await asyncio.to_thread(self._collect_candidates, start_date, end_date)
        if not candidates:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrent_articles)
        connector = aiohttp.TCPConnector(limit_per_host=self.max_concurrent_articles)
        async with aiohttp.ClientSession(headers=VEDOMOSTI_HEADERS, connector=connector) as session:
            tasks = [self._parse_candidate(session, candidate, semaphore) for candidate in candidates]
            results = await asyncio.gather(*tasks)
        return [article for article in results if article is not None]

    def _collect_candidates(self, start_date: date, end_date: date) -> list[dict]:
        candidates: list[dict] = []
        for url, topic, article_date, lastmod in _load_sitemap_entries_cached(self.sitemap_url):
            if article_date < start_date or article_date > end_date:
                continue

            candidates.append(
                {
                    'url': url,
                    'topic': topic,
                    'date': lastmod or datetime.combine(article_date, time.min),
                }
            )

        candidates.sort(key=lambda item: item['date'])
        return candidates

    async def _parse_candidate(
        self,
        session: aiohttp.ClientSession,
        candidate: dict,
        semaphore: asyncio.Semaphore,
    ) -> ParsedNewsArticle | None:
        async with semaphore:
            await asyncio.sleep(uniform(*self.delay_between_articles))
            return await self._fetch_article(session, candidate)

    async def _fetch_article(
        self,
        session: aiohttp.ClientSession,
        candidate: dict,
    ) -> ParsedNewsArticle | None:
        url = candidate['url']
        try:
            html = await fetch_html(session, url, retries=self.retry_count, timeout=self.request_timeout)
            if not html:
                return None

            text = extract(html)
            if not text:
                return None

            metadata = extract_metadata(html)
            heading = metadata.title if metadata and metadata.title else None
            published_at = candidate['date']
            if metadata and metadata.date:
                try:
                    published_at = datetime.fromisoformat(metadata.date)
                except ValueError:
                    pass

            return ParsedNewsArticle(
                published_at=published_at,
                topic=normalize_topic(candidate['topic']),
                text=text,
                heading=heading,
                url=url,
                source=NewsSource.VEDOMOSTI,
            )
        except Exception as exc:
            logger.warning('Failed to parse article %s: %s', url, exc)
            return None


SitemapEntry = tuple[str, str, date, datetime | None]


@lru_cache(maxsize=4)
def _load_sitemap_entries_cached(sitemap_url: str) -> tuple[SitemapEntry, ...]:
    """Download and parse the sitemap once per process (shared across date batches)."""
    downloaded = fetch_url(sitemap_url)
    if not downloaded:
        return ()

    soup = BeautifulSoup(downloaded, 'xml')
    entries: list[SitemapEntry] = []
    for url_tag in soup.find_all('url'):
        loc_tag = url_tag.find('loc')
        if loc_tag is None or not loc_tag.text:
            continue

        loc = loc_tag.text.strip()
        match = URL_DATE_PATTERN.search(loc)
        if not match:
            continue

        topic, year, month, day = match.groups()
        article_date = date(int(year), int(month), int(day))

        lastmod: datetime | None = None
        lastmod_tag = url_tag.find('lastmod')
        if lastmod_tag is not None and lastmod_tag.text:
            try:
                lastmod = datetime.fromisoformat(lastmod_tag.text.strip().replace('Z', '+00:00'))
            except ValueError:
                pass

        entries.append((loc, topic, article_date, lastmod))

    return tuple(entries)
