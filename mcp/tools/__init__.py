"""
EROS MCP Server Tools Package

This package contains all MCP tool implementations organized by domain.
Tools are registered via the @mcp_tool decorator from base.py.
"""

from mcp.tools.base import mcp_tool, TOOL_REGISTRY, get_all_tools, dispatch_tool

# Import all tool modules to trigger registration
from mcp.tools import creator
from mcp.tools import caption
from mcp.tools import schedule
from mcp.tools import send_types
from mcp.tools import performance
from mcp.tools import targeting
from mcp.tools import query

__all__ = [
    "mcp_tool",
    "TOOL_REGISTRY",
    "get_all_tools",
    "dispatch_tool",
]
