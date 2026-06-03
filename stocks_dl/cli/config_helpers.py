"""Resolve Hydra DictConfig into paths and ticker lists for DL CLIs."""

from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from stocks_dl.constants import DEFAULT_TICKER
from stocks_dl.data.pipeline import TICKERS_WITH_NEWS
from stocks_dl.paths import get_runs_root, runs_artifact_path


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


def runs_root(cfg: DictConfig) -> Path:
    return get_runs_root(cfg.paths.get('runs_dir'))


def artifact_path(cfg: DictConfig, template: str, ticker: str) -> Path:
    """Path under ``paths.runs_dir`` from a template with ``{ticker}`` placeholder."""
    rel = template.format(ticker=ticker.lower())
    return runs_artifact_path(rel, runs_dir=cfg.paths.get('runs_dir'))


def data_cfg(cfg: DictConfig) -> dict:
    return OmegaConf.to_container(cfg.data, resolve=True)  # type: ignore[return-value]


def training_cfg(cfg: DictConfig) -> dict:
    return OmegaConf.to_container(cfg.training, resolve=True)  # type: ignore[return-value]
