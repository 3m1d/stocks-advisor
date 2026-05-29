import asyncio
import logging
import random
from random import uniform

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_CHARSET = 'cp1251'

DEFAULT_USER_AGENTS = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'),
    (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 '
        '(KHTML, like Gecko) Version/16.3 Safari/605.1.15'
    ),
    'Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/120.0',
]

DEFAULT_HEADERS = {
    'User-Agent': random.choice(DEFAULT_USER_AGENTS),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru,en;q=0.9',
    # Avoid "br" unless brotli is installed — otherwise aiohttp can fail while reading the body.
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

RETRYABLE_STATUS_CODES = frozenset({403, 429, 502, 503, 504})


def _response_encoding(charset: str | None) -> str:
    if not charset:
        return DEFAULT_CHARSET
    normalized = charset.strip().lower()
    if normalized in {'windows-1251', 'win-1251', 'x-cp1251'}:
        return DEFAULT_CHARSET
    return normalized


def decode_response_body(body: bytes, url: str, charset: str | None) -> str:
    encoding = _response_encoding(charset)
    try:
        return body.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        if encoding != DEFAULT_CHARSET:
            try:
                return body.decode(DEFAULT_CHARSET)
            except UnicodeDecodeError:
                pass
        logger.warning('Could not decode %s as %s, using lossy utf-8', url, encoding)
        return body.decode('utf-8', errors='replace')


async def fetch_html(
    session: aiohttp.ClientSession,
    url: str,
    *,
    retries: int = 5,
    timeout: int = 20,
) -> str:
    """Fetch HTML page with retries."""
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    body = await response.read()
                    return decode_response_body(body, url, response.charset)
                if response.status in RETRYABLE_STATUS_CODES:
                    wait = 2**attempt + uniform(0.5, 1.5)
                    logger.warning('HTTP %s while fetching %s, retry in %.1fs', response.status, url, wait)
                    await asyncio.sleep(wait)
                    continue
                logger.warning('HTTP %s while fetching %s', response.status, url)
                return ''
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            wait = 2**attempt + uniform(0.5, 1.5)
            status = getattr(exc, 'status', None)
            if status is not None:
                logger.warning('HTTP %s while fetching %s, retry in %.1fs', status, url, wait)
            else:
                logger.warning('%s while fetching %s, retry in %.1fs', type(exc).__name__, url, wait)
            await asyncio.sleep(wait)
    logger.error('Failed to fetch %s after %s attempts', url, retries)
    return ''
