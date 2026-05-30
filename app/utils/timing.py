import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f'{seconds:.1f}s'
    minutes, secs = divmod(seconds, 60)
    return f'{int(minutes)}m {secs:.0f}s'


@dataclass
class Elapsed:
    seconds: float = 0.0


@contextmanager
def timed():
    """Measure wall-clock time; yields Elapsed with `.seconds` set on exit."""
    elapsed = Elapsed()
    start = time.perf_counter()
    try:
        yield elapsed
    finally:
        elapsed.seconds = time.perf_counter() - start


@contextmanager
def log_timed(label: str, *, count: int | None = None, logger: logging.Logger | None = None):
    """Like timed(), but logs start and completion."""
    log = logger or logging.getLogger(__name__)
    log.info('%s started', label)
    with timed() as elapsed:
        yield elapsed
    duration = format_duration(elapsed.seconds)
    if count is not None:
        rate = count / elapsed.seconds if elapsed.seconds else 0.0
        log.info('%s done: %s in %s (%.2f/s)', label, count, duration, rate)
    else:
        log.info('%s done in %s', label, duration)
