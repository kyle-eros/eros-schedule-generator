#!/usr/bin/env python3
"""
EROS Database MCP Server - Main Entry Point

A Model Context Protocol (MCP) server providing database access tools for the
EROS schedule generation system. Implements JSON-RPC 2.0 protocol over stdin/stdout.

This server exposes 33 tools for:
- Creator profile and performance data retrieval
- Caption selection with freshness scoring
- Optimal timing analysis
- Volume assignment management
- Content type rankings
- Send type configuration
- Channel management
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
- EROS_STDIN_TIMEOUT: Stdin read timeout in seconds (default: 300)
- EROS_REQUEST_TIMEOUT: Request execution timeout in seconds (default: 30)
- EROS_MAX_REQUEST_SIZE: Maximum request size in bytes (default: 1MB)

Author: EROS Development Team
Version: 3.0.0
"""

import atexit
import json
import logging
import os
import select
import signal
import sys
import time
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
    PROTOCOL_VERSION,
    SERVER_VERSION,
    create_response,
    create_error_response,
)
from mcp.tools import get_all_tools, dispatch_tool
from mcp.tools.base import format_tool_result, get_tool_stats
from mcp.connection import close_pool, get_pool

# Request timeout configuration
STDIN_TIMEOUT = float(os.environ.get("EROS_STDIN_TIMEOUT", "300"))  # 5 minutes
REQUEST_TIMEOUT = float(os.environ.get("EROS_REQUEST_TIMEOUT", "30"))  # 30 seconds
MAX_REQUEST_SIZE = int(os.environ.get("EROS_MAX_REQUEST_SIZE", str(1024 * 1024)))  # 1MB


def initialize_server() -> None:
    """
    Initialize server components.

    Starts metrics server, initializes connection pool, and registers
    shutdown handlers.
    """
    logger.info("Initializing EROS MCP Server v3.0.0")

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


def handle_health(request_id: Any) -> dict[str, Any]:
    """
    Handle health check requests.

    Returns health status including:
    - Server version and uptime
    - Connection pool metrics
    - Database connectivity test
    - Overall health status

    Args:
        request_id: The JSON-RPC request ID.

    Returns:
        JSON-RPC response with health status.
    """
    from mcp.connection import get_pool_health, pooled_connection

    try:
        # Get connection pool health
        pool_health = get_pool_health()

        # Test database connectivity
        try:
            with pooled_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            database_status = "connected"
        except Exception as db_error:
            logger.error(f"Database health check failed: {db_error}")
            database_status = f"error: {str(db_error)}"

        # Get tool registry stats
        tool_stats = get_tool_stats()

        # Overall health determination
        overall_status = "healthy"
        if pool_health["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif pool_health["status"] == "degraded" or database_status != "connected":
            overall_status = "degraded"

        health_response = {
            "status": overall_status,
            "version": SERVER_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "database": database_status,
            "pool_health": pool_health,
            "tools_registered": tool_stats["total_tools"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return create_response(health_response, request_id)

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        error_response = {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return create_error_response(ERROR_SERVER, "Health check failed", request_id)


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
    elif method == "health":
        return handle_health(request_id)
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


def run_server() -> None:
    """
    Main server loop with stdin timeout.

    Implements timeout-aware stdin reading to prevent indefinite blocking.
    Handles parent process termination detection and request size validation.
    """
    protocol = MCPProtocol()
    mcp_logger = get_mcp_logger()

    logger.info("MCP Server ready, listening for requests on stdin")

    while True:
        # Use select to implement stdin read timeout
        ready, _, _ = select.select([sys.stdin], [], [], STDIN_TIMEOUT)

        if not ready:
            # Timeout - check if parent process is still alive
            if os.getppid() == 1:  # Init process (parent died)
                logger.info("Parent process terminated, shutting down")
                shutdown_server()
                sys.exit(0)
            continue

        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                logger.info("Received EOF, shutting down gracefully")
                shutdown_server()
                sys.exit(0)

            line = line.strip()
            if not line:
                continue

            # Validate request size
            if len(line) > MAX_REQUEST_SIZE:
                error_response = create_error_response(
                    ERROR_SERVER,
                    f"Request exceeds maximum size of {MAX_REQUEST_SIZE} bytes",
                    None
                )
                print(json.dumps(error_response), flush=True)
                continue

            # Process request with existing logic
            request = protocol.parse_request(line)
            response = handle_request(request)

            if response is not None:
                print(json.dumps(response), flush=True)

        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down")
            shutdown_server()
            sys.exit(0)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            error_response = create_error_response(
                ERROR_PARSE, str(e), None
            )
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            logger.exception(f"Unexpected error processing request: {e}")
            error_response = create_error_response(
                ERROR_SERVER, str(e), None
            )
            print(json.dumps(error_response), flush=True)


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

    # Run the main server loop with timeout support
    run_server()


if __name__ == "__main__":
    main()
