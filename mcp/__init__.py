"""
EROS MCP Server Package

A Model Context Protocol (MCP) server providing database access tools for the
EROS schedule generation system.

This package provides:
- server: Main entry point and request routing
- protocol: JSON-RPC 2.0 protocol handling
- connection: Database connection management
- tools: All 17 MCP tool implementations
- utils: Security validation and helper functions

Usage:
    python -m mcp.server

Or run directly:
    python mcp/server.py

Environment Variables:
    EROS_DB_PATH: Path to the SQLite database (optional, has default)
"""

from mcp.server import main
from mcp.protocol import MCPProtocol
from mcp.connection import (
    db_connection,
    get_db_connection,
    pooled_connection,
    get_pool,
    get_pool_health,
    warm_pool,
    reset_pool,
    close_pool,
)

# Import all tools for backward compatibility
from mcp.tools.creator import (
    get_active_creators,
    get_creator_profile,
    get_persona_profile,
    get_vault_availability,
)
from mcp.tools.caption import (
    get_top_captions,
    get_send_type_captions,
)
from mcp.tools.schedule import save_schedule
from mcp.tools.send_types import (
    get_send_types,
    get_send_type_details,
    get_volume_config,
)
from mcp.tools.performance import (
    get_best_timing,
    get_volume_assignment,
    get_performance_trends,
    get_content_type_rankings,
)
from mcp.tools.targeting import (
    get_channels,
    get_audience_targets,
)
from mcp.tools.query import execute_query

__version__ = "2.2.0"
__all__ = [
    # Main entry point
    "main",
    # Protocol
    "MCPProtocol",
    # Connection management
    "db_connection",
    "get_db_connection",
    "pooled_connection",
    "get_pool",
    "get_pool_health",
    "warm_pool",
    "reset_pool",
    "close_pool",
    # Creator tools
    "get_active_creators",
    "get_creator_profile",
    "get_persona_profile",
    "get_vault_availability",
    # Caption tools
    "get_top_captions",
    "get_send_type_captions",
    # Schedule tools
    "save_schedule",
    # Send type tools
    "get_send_types",
    "get_send_type_details",
    "get_volume_config",
    # Performance tools
    "get_best_timing",
    "get_volume_assignment",
    "get_performance_trends",
    "get_content_type_rankings",
    # Targeting tools
    "get_channels",
    "get_audience_targets",
    # Query tool
    "execute_query",
]
