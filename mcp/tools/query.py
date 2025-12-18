"""
EROS MCP Server Query Tool

Provides secure read-only SQL query execution with comprehensive
SQL injection protection and query complexity limits.
"""

import logging
import re
import sqlite3
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import rows_to_list
from mcp.utils.security import (
    MAX_QUERY_JOINS,
    MAX_QUERY_SUBQUERIES,
    MAX_QUERY_RESULT_ROWS,
)

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="execute_query",
    description="Execute a read-only SQL SELECT query for custom analysis.",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query to execute"
            },
            "params": {
                "type": "array",
                "description": "Optional list of parameters for the query",
                "items": {}
            }
        },
        "required": ["query"]
    }
)
def execute_query(
    query: str,
    params: Optional[list[Any]] = None
) -> dict[str, Any]:
    """
    Execute a read-only SQL query for custom analysis.

    SECURITY: Only SELECT queries are allowed with comprehensive SQL injection protection.
    - Blocks dangerous keywords and PRAGMA commands
    - Detects comment injection attempts
    - Enforces query complexity limits
    - Limits result set size

    Args:
        query: SQL query string (must be SELECT).
        params: Optional list of parameters for the query.

    Returns:
        Dictionary containing:
            - results: List of result rows as dictionaries
            - count: Number of rows returned
            - columns: List of column names
    """
    # Log query attempt (sanitized)
    query_preview = query[:100].replace('\n', ' ').replace('\r', '')
    logger.info(f"execute_query called: {query_preview}...")

    # Security check: only allow SELECT queries
    normalized_query = query.strip().upper()
    if not normalized_query.startswith("SELECT"):
        logger.warning(f"Blocked non-SELECT query: {query_preview}")
        return {"error": "Only SELECT queries are allowed for security reasons"}

    # Enhanced security: block dangerous keywords
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "ATTACH", "DETACH",
        "PRAGMA", "VACUUM", "REINDEX", "ANALYZE"
    ]
    for keyword in dangerous_keywords:
        if keyword in normalized_query:
            logger.warning(f"Blocked query with dangerous keyword '{keyword}': {query_preview}")
            return {"error": f"Query contains disallowed keyword: {keyword}"}

    # Detect comment injection patterns
    if "/*" in query or "*/" in query or "--" in query:
        logger.warning(f"Blocked query with comment injection pattern: {query_preview}")
        return {"error": "Query contains disallowed comment syntax (/* */ or --)"}

    # Enforce query complexity limits
    join_count = normalized_query.count(" JOIN ")
    if join_count > MAX_QUERY_JOINS:
        logger.warning(f"Blocked query exceeding JOIN limit ({join_count} > {MAX_QUERY_JOINS}): {query_preview}")
        return {"error": f"Query exceeds maximum JOIN limit of {MAX_QUERY_JOINS} (found {join_count})"}

    # Count subqueries (simplified detection)
    subquery_count = normalized_query.count("SELECT") - 1  # Subtract main SELECT
    if subquery_count > MAX_QUERY_SUBQUERIES:
        logger.warning(f"Blocked query exceeding subquery limit ({subquery_count} > {MAX_QUERY_SUBQUERIES}): {query_preview}")
        return {"error": f"Query exceeds maximum subquery limit of {MAX_QUERY_SUBQUERIES} (found {subquery_count})"}

    # Inject LIMIT clause if not present to prevent massive result sets
    if "LIMIT" not in normalized_query:
        query = f"{query.rstrip(';')} LIMIT {MAX_QUERY_RESULT_ROWS}"
        logger.info(f"Injected LIMIT {MAX_QUERY_RESULT_ROWS} to protect against large result sets")
    else:
        # Validate existing LIMIT doesn't exceed maximum
        limit_match = re.search(r'LIMIT\s+(\d+)', normalized_query)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > MAX_QUERY_RESULT_ROWS:
                logger.warning(f"Blocked query with excessive LIMIT ({limit_value} > {MAX_QUERY_RESULT_ROWS}): {query_preview}")
                return {"error": f"Query LIMIT exceeds maximum of {MAX_QUERY_RESULT_ROWS} (requested {limit_value})"}

    conn = get_db_connection()
    try:
        params = params or []
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []

        results = rows_to_list(rows)

        logger.info(f"execute_query successful: returned {len(results)} rows")
        return {
            "results": results,
            "count": len(results),
            "columns": columns
        }
    except sqlite3.Error as e:
        logger.error(f"Query execution error: {str(e)} for query: {query_preview}")
        return {"error": f"Query execution error: {str(e)}"}
    finally:
        conn.close()
