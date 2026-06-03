from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from stocks_dl.constants import DEFAULT_TICKER
from stocks_dl.data.pipeline import TICKERS_WITH_NEWS
from stocks_dl.env_setup import REPO_ROOT
from stocks_dl.paths import PKG_ROOT


def resolve_tickers(cfg: DictConfig) -> list[str]:
    if cfg.get('ticker'):
        return [str(cfg.ticker).upper()]
    raw = cfg.get('tickers')
    if raw is None:
        return [DEFAULT_TICKER]
    if isinstance(raw, str):
        if raw.lower() == 'all':
            return list(TICKERS_WITH_NEWS)
        return [raw.upper()]
    tickers = [str(t).upper() for t in raw]
    if len(tickers) == 1 and tickers[0].lower() == 'all':
        return list(TICKERS_WITH_NEWS)
    return tickers


def pkg_path(template: str, ticker: str) -> Path:
    rel = template.format(ticker=ticker.lower())
    path = Path(rel)
    return path if path.is_absolute() else PKG_ROOT / rel


def repo_path(template: str, ticker: str) -> Path:
    rel = template.format(ticker=ticker.lower())
    path = Path(rel)
    return path if path.is_absolute() else REPO_ROOT / rel


def data_cfg(cfg: DictConfig) -> dict:
    return OmegaConf.to_container(cfg.data, resolve=True)  # type: ignore[return-value]


def training_cfg(cfg: DictConfig) -> dict:
    return OmegaConf.to_container(cfg.training, resolve=True)  # type: ignore[return-value]
