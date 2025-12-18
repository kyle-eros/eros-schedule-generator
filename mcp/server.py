#!/usr/bin/env python3
"""
EROS Database MCP Server - Main Entry Point

A Model Context Protocol (MCP) server providing database access tools for the
EROS schedule generation system. Implements JSON-RPC 2.0 protocol over stdin/stdout.

This server exposes 17 tools for:
- Creator profile and performance data retrieval
- Caption selection with freshness scoring
- Optimal timing analysis
- Volume assignment management
- Content type rankings
- Send type configuration
- Channel and audience target management
- Schedule persistence

Features:
- Prometheus metrics collection (port 9090 by default)
- Structured JSON logging with request tracing
- Connection pooling with health checks

Configuration:
- EROS_DB_PATH: Database file location
- EROS_METRICS_ENABLED: Enable/disable metrics (default: true)
- EROS_METRICS_PORT: Prometheus metrics port (default: 9090)
- EROS_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR)
- EROS_LOG_FORMAT: Log format (json, text)

Author: EROS Development Team
Version: 2.2.0
"""

import atexit
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path for direct script execution
if __name__ == "__main__":
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

# Initialize logging first
from mcp.logging_config import setup_logging, get_mcp_logger

# Setup logging before other imports
setup_logging()
logger = logging.getLogger("eros_db_server")

# Initialize metrics (optional - graceful degradation if prometheus not available)
try:
    from mcp.metrics import start_metrics_server, get_metrics_summary
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Prometheus metrics not available - prometheus_client not installed")

# Import protocol and tools after logging is configured
from mcp.protocol import (
    MCPProtocol,
    ERROR_PARSE,
    ERROR_METHOD_NOT_FOUND,
    ERROR_INVALID_PARAMS,
    ERROR_SERVER,
    create_response,
    create_error_response,
)
from mcp.tools import get_all_tools, dispatch_tool
from mcp.tools.base import format_tool_result, get_tool_stats
from mcp.connection import close_pool, get_pool


def initialize_server() -> None:
    """
    Initialize server components.

    Starts metrics server, initializes connection pool, and registers
    shutdown handlers.
    """
    logger.info("Initializing EROS MCP Server v2.2.0")

    # Start Prometheus metrics server
    if METRICS_AVAILABLE:
        metrics_started = start_metrics_server()
        if metrics_started:
            logger.info("Prometheus metrics server started")
        else:
            logger.info("Prometheus metrics server not started (disabled or unavailable)")

    # Initialize connection pool (lazy, but log stats)
    try:
        pool = get_pool()
        pool_stats = pool.get_stats()
        logger.info(
            f"Connection pool initialized: "
            f"size={pool_stats['pool_size']}, "
            f"max_overflow={pool_stats['max_overflow']}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")

    # Log tool registration
    tool_stats = get_tool_stats()
    logger.info(f"Registered {tool_stats['total_tools']} MCP tools")

    # Register shutdown handler
    atexit.register(shutdown_server)

    logger.info("Server initialization complete")


def shutdown_server() -> None:
    """
    Clean shutdown of server components.

    Closes connection pool and performs cleanup.
    """
    logger.info("Shutting down EROS MCP Server...")

    try:
        close_pool()
        logger.info("Connection pool closed")
    except Exception as e:
        logger.error(f"Error closing connection pool: {e}")

    logger.info("Server shutdown complete")


def handle_initialize(request_id: Any) -> dict[str, Any]:
    """
    Handle the initialize MCP method.

    Args:
        request_id: The JSON-RPC request ID.

    Returns:
        JSON-RPC response with server info and capabilities.
    """
    protocol = MCPProtocol()
    return create_response(protocol.format_initialize_result(), request_id)


def handle_tools_list(request_id: Any) -> dict[str, Any]:
    """
    Handle the tools/list MCP method.

    Args:
        request_id: The JSON-RPC request ID.

    Returns:
        JSON-RPC response with list of available tools.
    """
    protocol = MCPProtocol()
    tools = get_all_tools()
    return create_response(protocol.format_tools_list_result(tools), request_id)


def handle_tools_call(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the tools/call MCP method.

    Args:
        request_id: The JSON-RPC request ID.
        params: The call parameters including 'name' and 'arguments'.

    Returns:
        JSON-RPC response with tool execution result.
    """
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    try:
        result = dispatch_tool(tool_name, arguments)
        protocol = MCPProtocol()
        return create_response(protocol.format_tool_call_result(result), request_id)
    except KeyError as e:
        return create_error_response(ERROR_METHOD_NOT_FOUND, str(e), request_id)
    except TypeError as e:
        return create_error_response(ERROR_INVALID_PARAMS, f"Invalid parameters: {str(e)}", request_id)
    except Exception as e:
        return create_error_response(ERROR_SERVER, f"Tool execution error: {str(e)}", request_id)


def handle_request(request: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Route incoming JSON-RPC request to appropriate handler.

    Args:
        request: The JSON-RPC request object.

    Returns:
        JSON-RPC response object, or None for notifications.
    """
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return handle_initialize(request_id)
    elif method == "tools/list":
        return handle_tools_list(request_id)
    elif method == "tools/call":
        return handle_tools_call(request_id, params)
    elif method == "notifications/initialized":
        # Notification, no response needed
        return None
    else:
        return create_error_response(
            ERROR_METHOD_NOT_FOUND,
            f"Method not found: {method}",
            request_id
        )


def handle_signal(signum: int, frame: Any) -> None:
    """
    Handle termination signals gracefully.

    Args:
        signum: Signal number.
        frame: Current stack frame.
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_server()
    sys.exit(0)


def main() -> None:
    """
    Main entry point for the MCP server.

    Reads JSON-RPC requests from stdin (one per line) and writes responses to stdout.
    """
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initialize server components
    initialize_server()

    # Disable output buffering for immediate responses
    sys.stdout.reconfigure(line_buffering=True)

    protocol = MCPProtocol()
    mcp_logger = get_mcp_logger()

    logger.info("MCP Server ready, listening for requests on stdin")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = protocol.parse_request(line)
            response = handle_request(request)

            # Only output if there's a response (notifications don't get responses)
            if response is not None:
                print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            error_response = create_error_response(
                ERROR_PARSE,
                f"Parse error: {str(e)}",
                None
            )
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
