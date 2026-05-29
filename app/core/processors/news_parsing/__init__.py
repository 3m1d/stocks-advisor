from datetime import date
import logging

from app.core.processors.news_parsing.base import (
    NewsParser,
    NewsParseResult,
    NewsSource,
    ParsedNewsArticle,
    daterange,
    normalize_topic,
)
from app.core.processors.news_parsing.interfax import InterfaxParser
from app.core.processors.news_parsing.kommersant import KommersantParser
from app.core.processors.news_parsing.vedomosti import VedomostiParser

logger = logging.getLogger(__name__)

NEWS_PARSERS: dict[NewsSource, type[NewsParser]] = {
    NewsSource.INTERFAX: InterfaxParser,
    NewsSource.KOMMERSANT: KommersantParser,
    NewsSource.VEDOMOSTI: VedomostiParser,
}


async def parse_all_news(start_date: date, end_date: date) -> list[ParsedNewsArticle]:
    articles: list[ParsedNewsArticle] = []
    for parser in NEWS_PARSERS.values():
        logger.info(f'Parsing news from {parser.source} for {start_date} to {end_date}')
        articles.extend(await parser().parse(start_date, end_date))
    return articles


__all__ = [
    'InterfaxParser',
    'KommersantParser',
    'NewsParseResult',
    'NewsParser',
    'NewsSource',
    'ParsedNewsArticle',
    'VedomostiParser',
    'daterange',
    'normalize_topic',
    'NEWS_PARSERS',
]
