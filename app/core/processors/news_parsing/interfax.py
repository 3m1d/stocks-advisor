import asyncio
import logging
import re
from datetime import date, datetime, time
from random import uniform

import aiohttp
from bs4 import BeautifulSoup

from app.core.database.db_models.news_article import NewsSource
from app.core.processors.news_parsing.base import NewsParser, ParsedNewsArticle, daterange, normalize_topic
from app.core.processors.news_parsing.fetch import DEFAULT_HEADERS, fetch_html

logger = logging.getLogger(__name__)

ARCHIVE_URL = 'https://www.interfax.ru/business/news/{date_str}'
INTERFAX_TOPIC = 'business'
MIN_TITLE_LENGTH = 10


class InterfaxParser(NewsParser):
    """
    Парсер новостей с Интерфакс

    Логика работы:
    - Скачиваем страницу со списком новостей за определенный день, парсим URL новостных страниц
    - Проходимся по каждой странице и извлекаем тело новости
    """

    source = NewsSource.INTERFAX

    def __init__(
        self,
        *,
        request_timeout: int = 20,
        retry_count: int = 5,
        delay_between_days: tuple[float, float] = (0.5, 1.0),
        delay_between_articles: float = 0.01,
    ) -> None:
        self.request_timeout = request_timeout
        self.retry_count = retry_count
        self.delay_between_days = delay_between_days
        self.delay_between_articles = delay_between_articles

    async def parse(self, start_date: date, end_date: date) -> list[ParsedNewsArticle]:
        articles: list[ParsedNewsArticle] = []
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            for day in daterange(start_date, end_date):
                day_articles = await self._parse_day(session, day)
                articles.extend(day_articles)
                await asyncio.sleep(uniform(*self.delay_between_days))
        return articles

    async def _parse_day(self, session: aiohttp.ClientSession, day: date) -> list[ParsedNewsArticle]:
        url = ARCHIVE_URL.format(date_str=day.strftime('%Y/%m/%d'))
        html = await fetch_html(session, url, retries=self.retry_count, timeout=self.request_timeout)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        news_block = soup.find('div', class_='an')
        if not news_block:
            return []

        full_text = news_block.get_text()
        all_times = re.findall(r'\d{2}:\d{2}', full_text)
        links = news_block.find_all('a', href=True)

        articles: list[ParsedNewsArticle] = []
        time_index = 0

        for link in links:
            heading = link.get_text(strip=True)
            href = link.get('href')
            if not heading or len(heading) <= MIN_TITLE_LENGTH or not href:
                continue

            time_str = all_times[time_index] if time_index < len(all_times) else '00:00'
            time_index += 1

            hour, minute = map(int, time_str.split(':'))
            published_at = datetime.combine(day, time(hour=hour, minute=minute))
            full_url = f'https://www.interfax.ru{href}' if href.startswith('/') else href

            try:
                text = await self._parse_article_text(session, full_url)
                if not text:
                    continue

                articles.append(
                    ParsedNewsArticle(
                        published_at=published_at,
                        topic=normalize_topic(INTERFAX_TOPIC),
                        text=text,
                        heading=heading,
                        url=full_url,
                        source=self.source,
                    )
                )
            except Exception as exc:
                logger.warning('Failed to parse article %s: %s', full_url, exc)
                continue

            await asyncio.sleep(self.delay_between_articles)

        return articles

    async def _parse_article_text(self, session: aiohttp.ClientSession, url: str) -> str:
        html = await fetch_html(session, url, retries=self.retry_count, timeout=self.request_timeout)
        if not html:
            return ''

        soup = BeautifulSoup(html, 'html.parser')
        article_elem = (
            soup.find('article')
            or soup.find('div', {'itemprop': 'articleBody'})
            or soup.find('div', class_='text')
            or soup.find('div', class_='at')
        )
        if not article_elem:
            return ''

        for elem in article_elem.find_all(['script', 'style', 'iframe', 'div', 'span']):
            elem.decompose()

        return article_elem.get_text('\n', strip=True)
