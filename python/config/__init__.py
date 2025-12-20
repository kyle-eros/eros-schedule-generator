"""
Configuration package for EROS Schedule Generator.

Provides centralized configuration management with YAML-based defaults
and environment variable overrides. Supports different configurations
for development, testing, and production environments.
"""

from .database import get_database_path, DEFAULT_DB_PATH
from .settings import Settings

__all__ = [
    "Settings",
    "get_database_path",
    "DEFAULT_DB_PATH",
]
