"""
Centralized database path resolution with env var support.

Provides consistent database path handling across all Python modules.
"""
import os
from pathlib import Path
from typing import Optional


def _get_project_root() -> Path:
    """Find project root by looking for CLAUDE.md marker file."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "CLAUDE.md").exists():
            return parent
    return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _get_project_root()
DEFAULT_DB_PATH = str(PROJECT_ROOT / "database" / "eros_sd_main.db")
DB_PATH_ENV_VAR = "EROS_DB_PATH"


def get_database_path(validate: bool = True) -> str:
    """
    Get database path with env var override support.

    Args:
        validate: Whether to check if path exists (default True).

    Returns:
        Absolute path to database file.

    Raises:
        FileNotFoundError: If validate=True and database doesn't exist.
    """
    path = os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH)
    abs_path = os.path.abspath(path)

    if validate and not os.path.exists(abs_path):
        raise FileNotFoundError(f"Database not found: {abs_path}")

    return abs_path


__all__ = ["get_database_path", "DEFAULT_DB_PATH", "DB_PATH_ENV_VAR", "PROJECT_ROOT"]
