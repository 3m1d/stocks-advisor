"""Package and run artifact paths (code vs generated outputs)."""

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PKG_ROOT.parent
DEFAULT_RUNS_DIR = 'stocks_dl_runs'


def get_runs_root(runs_dir: str | Path | None = None) -> Path:
    """Root for CSV/PNG/MLflow-adjacent outputs; default ``<repo>/stocks_dl_runs``."""
    name = DEFAULT_RUNS_DIR if runs_dir is None else runs_dir
    path = Path(name)
    return path if path.is_absolute() else REPO_ROOT / path


def runs_artifact_path(
    *parts: str,
    runs_dir: str | Path | None = None,
    mkdir: bool = True,
) -> Path:
    """Build path under runs root and optionally create parent directories."""
    target = get_runs_root(runs_dir).joinpath(*parts)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target
