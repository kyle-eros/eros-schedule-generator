"""
EROS MCP Server Tool Base

Provides the tool decorator pattern and registry for registering MCP tools.
All tool functions should use the @mcp_tool decorator to register themselves.

Features:
- Automatic tool registration
- Integrated Prometheus metrics collection
- Structured request/response logging
- Request tracing with unique IDs
- Rate limiting (token bucket algorithm)

Version: 3.0.0
"""

import json
import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger("eros_db_server.tools")

# Global tool registry - maps tool name to tool metadata and function
TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def mcp_tool(
    name: str,
    description: str,
    schema: dict[str, Any]
) -> Callable:
    """
    Decorator to register a function as an MCP tool.

    Automatically instruments the function with:
    - Prometheus metrics (request count, latency, errors)
    - Structured logging (request/response, timing, errors)
    - Request tracing (unique request IDs)

    Args:
        name: The unique name for this tool (used in tools/call requests).
        description: Human-readable description of what the tool does.
        schema: JSON Schema defining the tool's input parameters.

    Returns:
        Decorator function that registers the tool and returns the wrapped function.

    Example:
        @mcp_tool(
            name="get_creator_profile",
            description="Get comprehensive profile for a creator",
            schema={
                "type": "object",
                "properties": {
                    "creator_id": {
                        "type": "string",
                        "description": "The creator_id or page_name"
                    }
                },
                "required": ["creator_id"]
            }
        )
        def get_creator_profile(creator_id: str) -> dict[str, Any]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Import here to avoid circular imports and allow graceful degradation
            try:
                from mcp.metrics import (
                    REQUEST_COUNT,
                    REQUEST_LATENCY,
                    REQUEST_IN_PROGRESS,
                    ACTIVE_REQUESTS,
                    ERROR_COUNT,
                    SLOW_QUERIES,
                )
                metrics_available = True
            except ImportError:
                metrics_available = False

            try:
                from mcp.logging_config import (
                    get_mcp_logger,
                    set_current_request_id,
                    clear_current_request_id,
                    SLOW_QUERY_THRESHOLD_MS,
                )
                logging_available = True
                mcp_logger = get_mcp_logger()
            except ImportError:
                logging_available = False
                SLOW_QUERY_THRESHOLD_MS = 500

            # Rate limiting check
            try:
                from mcp.rate_limiter import check_rate_limit, RateLimitExceeded
                rate_limiting_available = True
            except ImportError:
                rate_limiting_available = False
                RateLimitExceeded = Exception  # Fallback

            # Check rate limit before processing
            if rate_limiting_available:
                try:
                    check_rate_limit(name)
                except RateLimitExceeded as e:
                    # Log rate limit hit
                    if logging_available:
                        request_id = mcp_logger.log_request(name, kwargs)
                        mcp_logger.log_error(request_id, e)
                        clear_current_request_id()

                    # Update metrics
                    if metrics_available:
                        REQUEST_COUNT.labels(tool=name, status='rate_limited').inc()

                    # Re-raise with structured error
                    raise

            # Start timing
            start_time = time.perf_counter()

            # Log request start
            request_id = None
            if logging_available:
                request_id = mcp_logger.log_request(name, kwargs)
                set_current_request_id(request_id)

            # Update metrics - request started
            if metrics_available:
                REQUEST_COUNT.labels(tool=name, status='started').inc()
                REQUEST_IN_PROGRESS.inc()
                ACTIVE_REQUESTS.labels(tool=name).inc()

            try:
                # Execute the actual tool function
                result = func(*args, **kwargs)

                # Calculate duration
                duration_seconds = time.perf_counter() - start_time
                duration_ms = duration_seconds * 1000

                # Update metrics - success
                if metrics_available:
                    REQUEST_COUNT.labels(tool=name, status='success').inc()
                    REQUEST_LATENCY.labels(tool=name).observe(duration_seconds)

                    # Track slow requests
                    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                        SLOW_QUERIES.labels(tool=name).inc()

                # Log response
                if logging_available:
                    mcp_logger.log_response(
                        request_id,
                        duration_ms=duration_ms,
                        status="success"
                    )

                return result

            except Exception as e:
                # Calculate duration
                duration_seconds = time.perf_counter() - start_time
                duration_ms = duration_seconds * 1000

                # Update metrics - error
                if metrics_available:
                    error_type = type(e).__name__
                    ERROR_COUNT.labels(tool=name, error_type=error_type).inc()
                    REQUEST_COUNT.labels(tool=name, status='error').inc()
                    REQUEST_LATENCY.labels(tool=name).observe(duration_seconds)

                # Log error
                if logging_available:
                    mcp_logger.log_error(request_id, e)

                raise

            finally:
                # Clean up metrics gauges
                if metrics_available:
                    REQUEST_IN_PROGRESS.dec()
                    ACTIVE_REQUESTS.labels(tool=name).dec()

                # Clear request context
                if logging_available:
                    clear_current_request_id()

        # Register the tool
        TOOL_REGISTRY[name] = {
            "function": wrapper,
            "description": description,
            "schema": schema,
            "name": name
        }

        logger.debug(f"Registered MCP tool: {name}")
        return wrapper

    return decorator


def get_all_tools() -> list[dict[str, Any]]:
    """
    Get all registered tools in the format expected by tools/list response.

    Returns:
        List of tool definitions with name, description, and inputSchema.
    """
    tools = []
    for name, tool_info in TOOL_REGISTRY.items():
        tools.append({
            "name": name,
            "description": tool_info["description"],
            "inputSchema": tool_info["schema"]
        })
    return tools


def dispatch_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch a tool call to the registered handler.

    Args:
        tool_name: The name of the tool to call.
        arguments: The arguments to pass to the tool function.

    Returns:
        The result from the tool function.

    Raises:
        KeyError: If the tool is not registered.
        TypeError: If the arguments don't match the function signature.
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {tool_name}")

    handler = TOOL_REGISTRY[tool_name]["function"]
    return handler(**arguments)


def format_tool_result(result: Any) -> dict[str, Any]:
    """
    Format a tool result for the MCP response.

    Args:
        result: The result from a tool function.

    Returns:
        Formatted result with content array containing text.
    """
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2, default=str)
            }
        ]
    }


def get_tool_stats() -> dict[str, Any]:
    """
    Get statistics about registered tools.

    Returns:
        Dictionary containing tool registry statistics.
    """
    return {
        "total_tools": len(TOOL_REGISTRY),
        "tools": list(TOOL_REGISTRY.keys())
    }
