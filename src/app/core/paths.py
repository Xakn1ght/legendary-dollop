"""
Single source of truth for repository and app-package filesystem locations.

Supports both legacy layout (repo/app/...) and src layout (repo/src/app/...).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Directory containing config/alembic.ini, alembic/, src/ or app/, etc."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "config" / "alembic.ini").is_file():
            return p
    raise RuntimeError("Cannot find repository root (missing config/alembic.ini)")


@lru_cache(maxsize=1)
def app_pkg_root() -> Path:
    """Directory of the importable `app` package (contains core/, handlers/, ...)."""
    r = repo_root()
    src_app = r / "src" / "app"
    flat_app = r / "app"
    if src_app.is_dir() and (src_app / "core").is_dir():
        return src_app
    if flat_app.is_dir() and (flat_app / "core").is_dir():
        return flat_app
    raise RuntimeError("Cannot find app package root (neither src/app nor app)")


def webapp_dir() -> Path:
    return app_pkg_root() / "webapp"


def webapp_path(*parts: str) -> str:
    return str(webapp_dir().joinpath(*parts))


def data_dir() -> Path:
    return app_pkg_root() / "data"


def data_path(*parts: str) -> str:
    return str(data_dir().joinpath(*parts))


def core_dir() -> Path:
    return app_pkg_root() / "core"


def core_path(*parts: str) -> str:
    return str(core_dir().joinpath(*parts))


def pythonpath_entries() -> list[str]:
    """Directories to put on sys.path so `import app` works (for scripts / tools)."""
    r = repo_root()
    if (r / "src" / "app").is_dir():
        return [str(r / "src")]
    return [str(r)]
