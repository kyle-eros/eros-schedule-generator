"""
Registry package for EROS Schedule Generator.

Provides singleton registries for send types and other configuration data
loaded from the database. Registries cache configuration data for fast
runtime lookups without repeated database queries.
"""

from .send_type_registry import SendTypeRegistry

__all__ = [
    "SendTypeRegistry",
]
