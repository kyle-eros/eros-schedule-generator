"""
EROS MCP Server Protocol Handling

Implements JSON-RPC 2.0 protocol for the Model Context Protocol (MCP).
Handles request parsing, response formatting, and error handling.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("eros_db_server")

# MCP Protocol Version
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "eros-db-server"
SERVER_VERSION = "2.2.0"

# JSON-RPC Error Codes
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603
ERROR_SERVER = -32000


class MCPProtocol:
    """
    Handler for MCP JSON-RPC protocol operations.

    Provides methods for parsing requests, formatting responses,
    and handling protocol-level operations.
    """

    def parse_request(self, line: str) -> dict[str, Any]:
        """
        Parse a JSON-RPC request from a string.

        Args:
            line: The raw JSON string from stdin.

        Returns:
            Parsed request dictionary with method, id, and params.

        Raises:
            json.JSONDecodeError: If the input is not valid JSON.
        """
        return json.loads(line)

    def format_response(
        self,
        result: Any,
        request_id: Any
    ) -> str:
        """
        Format a successful JSON-RPC response.

        Args:
            result: The result data to include in the response.
            request_id: The request ID to echo back.

        Returns:
            JSON string of the response.
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        return json.dumps(response)

    def format_error(
        self,
        code: int,
        message: str,
        request_id: Any = None
    ) -> str:
        """
        Format a JSON-RPC error response.

        Args:
            code: The error code (use ERROR_* constants).
            message: Human-readable error message.
            request_id: The request ID to echo back (None for parse errors).

        Returns:
            JSON string of the error response.
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        return json.dumps(response)

    def format_initialize_result(self) -> dict[str, Any]:
        """
        Format the result for an initialize request.

        Returns:
            Initialize result with protocol version, capabilities, and server info.
        """
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION
            }
        }

    def format_tools_list_result(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Format the result for a tools/list request.

        Args:
            tools: List of tool definitions.

        Returns:
            Tools list result.
        """
        return {
            "tools": tools
        }

    def format_tool_call_result(self, result: Any) -> dict[str, Any]:
        """
        Format the result for a tools/call request.

        Args:
            result: The result from the tool function.

        Returns:
            Tool call result with content array.
        """
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str)
                }
            ]
        }

    def format_tool_call_error(
        self,
        code: int,
        message: str
    ) -> dict[str, Any]:
        """
        Format an error for use in a JSON-RPC response.

        Args:
            code: The error code.
            message: Human-readable error message.

        Returns:
            Error object for JSON-RPC response.
        """
        return {
            "code": code,
            "message": message
        }


def create_response(
    result: Any,
    request_id: Any
) -> dict[str, Any]:
    """
    Create a JSON-RPC success response object.

    Args:
        result: The result data.
        request_id: The request ID.

    Returns:
        Response dictionary.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }


def create_error_response(
    code: int,
    message: str,
    request_id: Any = None
) -> dict[str, Any]:
    """
    Create a JSON-RPC error response object.

    Args:
        code: The error code.
        message: Human-readable error message.
        request_id: The request ID (None for parse errors).

    Returns:
        Error response dictionary.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }
