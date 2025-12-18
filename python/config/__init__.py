"""
Configuration package for EROS Schedule Generator.

Provides centralized configuration management with YAML-based defaults
and environment variable overrides. Supports different configurations
for development, testing, and production environments.
"""

from .settings import Settings

__all__ = [
    "Settings",
]
