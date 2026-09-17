"""Runtime configuration, resolved from the environment."""

from __future__ import annotations

import os
from pathlib import Path


def _data_dir() -> Path:
    """Where the SQLite database lives.

    ``BEP_DATA_DIR`` wins; on Fly.io that is the mounted volume (``/data``).
    Otherwise fall back to a per-user directory so the CLI works anywhere.
    """
    configured = os.environ.get("BEP_DATA_DIR")
    if configured:
        path = Path(configured)
    elif Path("/data").is_dir() and os.access("/data", os.W_OK):
        path = Path("/data")
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "bep"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JSON_SORT_KEYS = False
    APP_NAME = "BEP Bench"
    APP_TAGLINE = "Interactive BIM Execution Plan authoring and scoring"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa: N802 - Flask config convention
        url = os.environ.get("DATABASE_URL")
        if url:
            # SQLAlchemy 2.x dropped the bare postgres:// scheme.
            return url.replace("postgres://", "postgresql://", 1)
        return f"sqlite:///{_data_dir() / 'bep.sqlite3'}"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    WTF_CSRF_ENABLED = False

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa: N802
        return os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


def load_config(testing: bool = False) -> Config:
    return TestConfig() if testing else Config()
