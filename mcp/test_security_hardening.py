#!/usr/bin/env python3
"""
Security Hardening Validation Test Suite for EROS MCP Server

Tests all Wave 1 security enhancements:
- Enhanced SQL injection protection in execute_query
- Database connection security (timeout, secure_delete, busy_timeout)
- Input validation for creator_id and key parameters
- Security event logging

Author: Security Engineering Team
Version: 1.0.0

NOTE: These are integration tests that require the MCP server subprocess.
Run separately with: python3 mcp/test_security_hardening.py
"""

import json
import subprocess
import sys
from typing import Any

import pytest

# Mark all tests in this module as integration tests that require MCP server subprocess
pytestmark = pytest.mark.skip(reason="Integration tests requiring MCP server subprocess - run directly with python3")


def send_mcp_request(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Send a request to the MCP server via stdin/stdout.

    Args:
        method: MCP method name.
        params: Request parameters.

    Returns:
        Response dictionary.
    """
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }

    process = subprocess.Popen(
        ["python3", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = process.communicate(input=json.dumps(request) + "\n", timeout=5)

    # Print stderr for logging output
    if stderr:
        print(f"STDERR: {stderr}", file=sys.stderr)

    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to decode response: {stdout}", file=sys.stderr)
        raise


def test_sql_injection_pragma_blocking():
    """Test that PRAGMA commands are blocked in execute_query."""
    print("TEST: SQL Injection - PRAGMA blocking")

    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "PRAGMA table_info(creators)"
        }
    })

    if "error" in response:
        print(f"  ERROR: {response['error']}")
    else:
        result = json.loads(response["result"]["content"][0]["text"])
        assert "error" in result, "PRAGMA should be blocked"
        # PRAGMA is caught by non-SELECT check first, which is acceptable
        assert "SELECT" in result["error"] or "PRAGMA" in result["error"], "Error should mention SELECT or PRAGMA"
        print("  PASS: PRAGMA commands blocked")

    # Test PRAGMA embedded in SELECT (should also be blocked)
    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT 1; PRAGMA table_info(creators)"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Embedded PRAGMA should be blocked"
    assert "PRAGMA" in result["error"], "Error should mention PRAGMA keyword"
    print("  PASS: Embedded PRAGMA in SELECT blocked")


def test_sql_injection_comment_blocking():
    """Test that comment injection patterns are blocked."""
    print("\nTEST: SQL Injection - Comment pattern blocking")

    # Test /* */ pattern
    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT * FROM creators WHERE creator_id = 'test' /* comment */"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "/* */ comments should be blocked"
    assert "comment syntax" in result["error"], "Error should mention comment syntax"
    print("  PASS: /* */ comment pattern blocked")

    # Test -- pattern
    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT * FROM creators -- comment"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "-- comments should be blocked"
    assert "comment syntax" in result["error"], "Error should mention comment syntax"
    print("  PASS: -- comment pattern blocked")


def test_query_complexity_limits():
    """Test that query complexity limits are enforced."""
    print("\nTEST: Query complexity - JOIN limit")

    # Create a query with too many JOINs (>5)
    query = """
        SELECT c.*
        FROM creators c
        JOIN volume_assignments va1 ON c.creator_id = va1.creator_id
        JOIN volume_assignments va2 ON c.creator_id = va2.creator_id
        JOIN volume_assignments va3 ON c.creator_id = va3.creator_id
        JOIN volume_assignments va4 ON c.creator_id = va4.creator_id
        JOIN volume_assignments va5 ON c.creator_id = va5.creator_id
        JOIN volume_assignments va6 ON c.creator_id = va6.creator_id
    """

    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {"query": query}
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Excessive JOINs should be blocked"
    assert "JOIN limit" in result["error"], "Error should mention JOIN limit"
    print("  PASS: Excessive JOINs blocked")


def test_query_subquery_limits():
    """Test that subquery limits are enforced."""
    print("\nTEST: Query complexity - Subquery limit")

    # Create a query with too many subqueries (>3)
    query = """
        SELECT *
        FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM creators
                    )
                )
            )
        )
    """

    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {"query": query}
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Excessive subqueries should be blocked"
    assert "subquery limit" in result["error"], "Error should mention subquery limit"
    print("  PASS: Excessive subqueries blocked")


def test_query_limit_injection():
    """Test that LIMIT clause is auto-injected for large result sets."""
    print("\nTEST: Query row limit - Auto LIMIT injection")

    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT * FROM creators"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "results" in result, "Query should succeed with auto LIMIT"
    assert result["count"] <= 10000, "Result count should not exceed MAX_QUERY_RESULT_ROWS"
    print(f"  PASS: Auto LIMIT injection working (returned {result['count']} rows)")


def test_query_excessive_limit_blocking():
    """Test that excessive LIMIT values are blocked."""
    print("\nTEST: Query row limit - Excessive LIMIT blocking")

    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT * FROM creators LIMIT 20000"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Excessive LIMIT should be blocked"
    assert "LIMIT exceeds" in result["error"], "Error should mention LIMIT exceeds"
    print("  PASS: Excessive LIMIT blocked")


def test_creator_id_validation():
    """Test creator_id input validation."""
    print("\nTEST: Input validation - creator_id format")

    # Test with invalid characters (SQL injection attempt)
    response = send_mcp_request("tools/call", {
        "name": "get_creator_profile",
        "arguments": {
            "creator_id": "test'; DROP TABLE creators; --"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Invalid creator_id should be rejected"
    assert "invalid characters" in result["error"].lower(), "Error should mention invalid characters"
    print("  PASS: SQL injection in creator_id blocked")

    # Test with excessive length
    response = send_mcp_request("tools/call", {
        "name": "get_creator_profile",
        "arguments": {
            "creator_id": "a" * 150
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Excessively long creator_id should be rejected"
    assert "maximum length" in result["error"].lower(), "Error should mention maximum length"
    print("  PASS: Excessive length creator_id blocked")


def test_key_input_validation():
    """Test key input validation (send_type_key, channel_key, etc.)."""
    print("\nTEST: Input validation - key format")

    # Test send_type_key with invalid characters
    response = send_mcp_request("tools/call", {
        "name": "get_send_type_details",
        "arguments": {
            "send_type_key": "test<script>alert('xss')</script>"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Invalid send_type_key should be rejected"
    assert "invalid characters" in result["error"].lower(), "Error should mention invalid characters"
    print("  PASS: XSS attempt in send_type_key blocked")

    # Test channel_key with excessive length
    response = send_mcp_request("tools/call", {
        "name": "get_audience_targets",
        "arguments": {
            "channel_key": "x" * 100
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "error" in result, "Excessively long channel_key should be rejected"
    assert "maximum length" in result["error"].lower(), "Error should mention maximum length"
    print("  PASS: Excessive length channel_key blocked")


def test_valid_inputs():
    """Test that valid inputs still work correctly."""
    print("\nTEST: Valid inputs - Ensure legitimate requests work")

    # Test valid execute_query
    response = send_mcp_request("tools/call", {
        "name": "execute_query",
        "arguments": {
            "query": "SELECT creator_id, page_name FROM creators LIMIT 5"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    assert "results" in result, "Valid query should succeed"
    assert "error" not in result, "Valid query should not return error"
    print("  PASS: Valid execute_query works")

    # Test valid creator_id (alphanumeric with underscore)
    response = send_mcp_request("tools/call", {
        "name": "get_creator_profile",
        "arguments": {
            "creator_id": "creator_123"
        }
    })

    result = json.loads(response["result"]["content"][0]["text"])
    # May not find creator, but shouldn't have validation error
    if "error" in result:
        assert "invalid" not in result["error"].lower(), "Valid format should not trigger validation error"
    print("  PASS: Valid creator_id format accepted")


def main():
    """Run all security hardening validation tests."""
    print("=" * 70)
    print("EROS MCP Server - Wave 1 Security Hardening Validation")
    print("=" * 70)

    try:
        # TASK 1.1.1: Enhanced execute_query SQL Protection
        print("\n--- TASK 1.1.1: Enhanced SQL Injection Protection ---")
        test_sql_injection_pragma_blocking()
        test_sql_injection_comment_blocking()
        test_query_complexity_limits()
        test_query_subquery_limits()
        test_query_limit_injection()
        test_query_excessive_limit_blocking()

        # TASK 1.1.3: Input Validation
        print("\n--- TASK 1.1.3: Input Validation ---")
        test_creator_id_validation()
        test_key_input_validation()

        # Validate legitimate requests still work
        print("\n--- Regression Testing ---")
        test_valid_inputs()

        print("\n" + "=" * 70)
        print("ALL SECURITY TESTS PASSED!")
        print("=" * 70)
        return 0

    except AssertionError as e:
        print(f"\n\nTEST FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n\nUNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
