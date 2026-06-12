import pickle
import time
from pathlib import Path
from typing import TypeVar

T = TypeVar('T')


class DiskCache:
    """Простой файловый кэш с TTL (pickle)."""

    def __init__(self, cache_dir: Path, ttl_seconds: int) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, key: str) -> Path:
        safe_key = key.replace(':', '_').replace('/', '_')
        return self.cache_dir / f'{safe_key}.pkl'

    def get(self, key: str) -> T | None:
        path = self._entry_path(key)
        if not path.exists():
            return None

        try:
            with path.open('rb') as file:
                entry = pickle.load(file)
        except (OSError, EOFError, pickle.PickleError):
            path.unlink(missing_ok=True)
            return None

        cached_at = entry.get('cached_at')
        if cached_at is None or time.time() - float(cached_at) > self.ttl_seconds:
            path.unlink(missing_ok=True)
            return None

        return entry.get('value')

    def set(self, key: str, value: T) -> None:
        path = self._entry_path(key)
        entry = {'cached_at': time.time(), 'value': value}
        with path.open('wb') as file:
            pickle.dump(entry, file)
