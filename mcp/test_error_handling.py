#!/usr/bin/env python3
"""
EROS MCP Database Server - Error Handling Test Suite

Tests error handling and edge cases for all MCP tools.
Validates:
1. Invalid creator ID handling
2. Invalid parameter validation
3. Edge case handling
4. SQL security (injection prevention)
5. Boundary testing

Run with: python mcp/test_error_handling.py
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Callable

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.eros_db_server import (
    get_active_creators,
    get_creator_profile,
    get_top_captions,
    get_best_timing,
    get_volume_assignment,
    get_performance_trends,
    get_content_type_rankings,
    get_persona_profile,
    get_vault_availability,
    execute_query,
    handle_request,
)


class TestResult:
    """Stores a single test result."""
    def __init__(self, test_case: str, expected: str, actual: str, status: str):
        self.test_case = test_case
        self.expected = expected
        self.actual = actual
        self.status = status  # PASS, FAIL, WARN


class TestCategory:
    """Stores results for a test category."""
    def __init__(self, name: str):
        self.name = name
        self.results: list[TestResult] = []

    def add_result(self, test_case: str, expected: str, actual: str, passed: bool):
        status = "PASS" if passed else "FAIL"
        self.results.append(TestResult(test_case, expected, actual, status))

    def get_pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "PASS")

    def get_total_count(self) -> int:
        return len(self.results)


def run_error_handling_tests():
    """Run comprehensive error handling tests."""

    categories: list[TestCategory] = []

    # =========================================================================
    # CATEGORY 1: Invalid Creator ID Tests
    # =========================================================================
    cat1 = TestCategory("Invalid Creator ID")

    # Test 1.1: get_creator_profile with nonexistent creator
    result = get_creator_profile("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_creator_profile with nonexistent_creator_12345",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.2: get_top_captions with invalid creator
    result = get_top_captions("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_top_captions with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.3: get_best_timing with invalid creator
    result = get_best_timing("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_best_timing with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.4: get_volume_assignment with invalid creator
    result = get_volume_assignment("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_volume_assignment with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.5: get_performance_trends with invalid creator
    result = get_performance_trends("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_performance_trends with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.6: get_content_type_rankings with invalid creator
    result = get_content_type_rankings("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_content_type_rankings with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.7: get_persona_profile with invalid creator
    result = get_persona_profile("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_persona_profile with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    # Test 1.8: get_vault_availability with invalid creator
    result = get_vault_availability("nonexistent_creator_12345")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat1.add_result(
        "get_vault_availability with invalid creator",
        "Error message returned",
        f"error={has_error}, msg='{error_msg[:50]}'" if error_msg else f"error={has_error}",
        has_error and "not found" in error_msg.lower()
    )

    categories.append(cat1)

    # =========================================================================
    # CATEGORY 2: Invalid Parameters Tests
    # =========================================================================
    cat2 = TestCategory("Invalid Parameters")

    # Test 2.1: get_performance_trends with invalid period
    result = get_performance_trends("any_creator", period="invalid_period")
    has_error = "error" in result
    error_msg = result.get("error", "")
    # Note: This will first fail on creator not found, so we test with a valid creator
    creators = get_active_creators()
    if creators.get("creators"):
        valid_creator = creators["creators"][0]["creator_id"]
        result = get_performance_trends(valid_creator, period="invalid_period")
        has_error = "error" in result
        error_msg = result.get("error", "")
        cat2.add_result(
            "get_performance_trends with invalid period ('invalid_period')",
            "Error about invalid period",
            f"error={has_error}, msg='{error_msg}'",
            has_error and "period" in error_msg.lower()
        )

        # Test 2.1b: period with wrong format
        result = get_performance_trends(valid_creator, period="15d")
        has_error = "error" in result
        error_msg = result.get("error", "")
        cat2.add_result(
            "get_performance_trends with period='15d' (not 7d/14d/30d)",
            "Error about invalid period",
            f"error={has_error}, msg='{error_msg}'",
            has_error and "period" in error_msg.lower()
        )
    else:
        cat2.add_result(
            "get_performance_trends with invalid period",
            "Error about invalid period",
            "SKIP - No creators available",
            False
        )

    # Test 2.2: get_active_creators with invalid page_type
    result = get_active_creators(page_type="invalid_type")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat2.add_result(
        "get_active_creators with page_type='invalid_type'",
        "Error about invalid page_type",
        f"error={has_error}, msg='{error_msg}'",
        has_error and "page_type" in error_msg.lower()
    )

    # Test 2.3: get_top_captions with negative min_performance
    if creators.get("creators"):
        valid_creator = creators["creators"][0]["creator_id"]
        result = get_top_captions(valid_creator, min_performance=-50)
        has_error = "error" in result
        # Negative min_performance might return results (all pass) or be handled
        # Check if it returns valid data or an error
        is_handled = has_error or ("captions" in result)
        cat2.add_result(
            "get_top_captions with min_performance=-50",
            "Either error or valid results (negative treated as all pass)",
            f"error={has_error}, has_captions={'captions' in result}",
            is_handled
        )

    categories.append(cat2)

    # =========================================================================
    # CATEGORY 3: Edge Cases Tests
    # =========================================================================
    cat3 = TestCategory("Edge Cases")

    if creators.get("creators"):
        valid_creator = creators["creators"][0]["creator_id"]

        # Test 3.1: get_top_captions with limit=0
        result = get_top_captions(valid_creator, limit=0)
        has_error = "error" in result
        count = result.get("count", -1)
        cat3.add_result(
            "get_top_captions with limit=0",
            "Either error or empty results (count=0)",
            f"error={has_error}, count={count}",
            has_error or count == 0
        )

        # Test 3.2: get_best_timing with days_lookback=0
        result = get_best_timing(valid_creator, days_lookback=0)
        has_error = "error" in result
        # days_lookback=0 means no historical data
        hours_count = len(result.get("best_hours", []))
        cat3.add_result(
            "get_best_timing with days_lookback=0",
            "Either error or empty results (no historical period)",
            f"error={has_error}, best_hours_count={hours_count}",
            has_error or hours_count == 0
        )

    # Test 3.3: execute_query with empty query
    result = execute_query("")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat3.add_result(
        "execute_query with empty query",
        "Error message about invalid query",
        f"error={has_error}, msg='{error_msg[:50] if error_msg else 'none'}'",
        has_error
    )

    # Test 3.4: execute_query with whitespace only
    result = execute_query("   ")
    has_error = "error" in result
    error_msg = result.get("error", "")
    cat3.add_result(
        "execute_query with whitespace-only query",
        "Error message about invalid query",
        f"error={has_error}, msg='{error_msg[:50] if error_msg else 'none'}'",
        has_error
    )

    categories.append(cat3)

    # =========================================================================
    # CATEGORY 4: SQL Security Tests
    # =========================================================================
    cat4 = TestCategory("SQL Security")

    # Test 4.1: DROP TABLE
    result = execute_query("DROP TABLE creators")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("DROP" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'DROP TABLE creators'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.2: SQL injection via semicolon (compound statement)
    result = execute_query("SELECT * FROM creators; DROP TABLE creators")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("DROP" in error_msg.upper() or "disallowed" in error_msg.lower())
    cat4.add_result(
        "execute_query with 'SELECT...; DROP TABLE creators'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.3: INSERT statement
    result = execute_query("INSERT INTO creators (creator_id, page_name) VALUES ('test', 'test')")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("INSERT" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'INSERT INTO creators...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.4: UPDATE statement
    result = execute_query("UPDATE creators SET is_active = 0 WHERE 1=1")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("UPDATE" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'UPDATE creators...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.5: DELETE statement
    result = execute_query("DELETE FROM creators WHERE 1=1")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("DELETE" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'DELETE FROM creators...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.6: ALTER TABLE
    result = execute_query("ALTER TABLE creators ADD COLUMN test TEXT")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("ALTER" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'ALTER TABLE...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.7: CREATE TABLE
    result = execute_query("CREATE TABLE test_table (id INTEGER)")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error and ("CREATE" in error_msg.upper() or "SELECT" in error_msg)
    cat4.add_result(
        "execute_query with 'CREATE TABLE...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.8: TRUNCATE (if supported by SQLite)
    result = execute_query("TRUNCATE TABLE creators")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error  # Either blocked by security or not supported by SQLite
    cat4.add_result(
        "execute_query with 'TRUNCATE TABLE...'",
        "Blocked (either security or unsupported)",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.9: SELECT with subquery containing DROP
    result = execute_query("SELECT (SELECT DROP TABLE creators) FROM creators")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error
    cat4.add_result(
        "execute_query with subquery containing DROP",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    # Test 4.10: ATTACH DATABASE (potential file access)
    result = execute_query("ATTACH DATABASE '/tmp/test.db' AS test")
    has_error = "error" in result
    error_msg = result.get("error", "")
    blocked = has_error
    cat4.add_result(
        "execute_query with 'ATTACH DATABASE...'",
        "Blocked with security error",
        f"blocked={blocked}, msg='{error_msg}'",
        blocked
    )

    categories.append(cat4)

    # =========================================================================
    # CATEGORY 5: Boundary Testing
    # =========================================================================
    cat5 = TestCategory("Boundary Testing")

    if creators.get("creators"):
        valid_creator = creators["creators"][0]["creator_id"]

        # Test 5.1: get_top_captions with very large limit
        result = get_top_captions(valid_creator, limit=1000)
        has_error = "error" in result
        count = result.get("count", -1)
        cat5.add_result(
            "get_top_captions with limit=1000 (very large)",
            "Returns results without error (may be fewer than 1000)",
            f"error={has_error}, count={count}",
            not has_error and count >= 0
        )

        # Test 5.2: get_top_captions with limit=10000 (extreme)
        result = get_top_captions(valid_creator, limit=10000)
        has_error = "error" in result
        count = result.get("count", -1)
        cat5.add_result(
            "get_top_captions with limit=10000 (extreme)",
            "Handles gracefully (returns results or reasonable error)",
            f"error={has_error}, count={count}",
            not has_error or "limit" in result.get("error", "").lower()
        )

        # Test 5.3: get_best_timing with days_lookback=365 (full year)
        result = get_best_timing(valid_creator, days_lookback=365)
        has_error = "error" in result
        hours_count = len(result.get("best_hours", []))
        cat5.add_result(
            "get_best_timing with days_lookback=365 (full year)",
            "Returns results without error",
            f"error={has_error}, best_hours_count={hours_count}",
            not has_error
        )

        # Test 5.4: get_best_timing with days_lookback=1 (minimal)
        result = get_best_timing(valid_creator, days_lookback=1)
        has_error = "error" in result
        hours_count = len(result.get("best_hours", []))
        cat5.add_result(
            "get_best_timing with days_lookback=1 (minimal)",
            "Returns results without error (may be empty)",
            f"error={has_error}, best_hours_count={hours_count}",
            not has_error
        )

        # Test 5.5: get_top_captions with very high min_performance
        result = get_top_captions(valid_creator, min_performance=999)
        has_error = "error" in result
        count = result.get("count", -1)
        cat5.add_result(
            "get_top_captions with min_performance=999 (unreachable)",
            "Returns empty results without error",
            f"error={has_error}, count={count}",
            not has_error and count == 0
        )

        # Test 5.6: get_active_creators with tier=0 (invalid)
        result = get_active_creators(tier=0)
        has_error = "error" in result
        count = result.get("count", -1)
        # Tier 0 doesn't exist but query should run without error (return 0 results)
        cat5.add_result(
            "get_active_creators with tier=0 (outside 1-5 range)",
            "Returns empty results or error",
            f"error={has_error}, count={count}",
            has_error or count == 0
        )

        # Test 5.7: get_active_creators with tier=99 (extreme)
        result = get_active_creators(tier=99)
        has_error = "error" in result
        count = result.get("count", -1)
        cat5.add_result(
            "get_active_creators with tier=99 (extreme value)",
            "Returns empty results or error",
            f"error={has_error}, count={count}",
            has_error or count == 0
        )

    categories.append(cat5)

    return categories


def generate_report(categories: list[TestCategory]) -> str:
    """Generate markdown report from test results."""

    report = []
    report.append("## Error Handling Test Results")
    report.append("")
    report.append(f"**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Server:** EROS MCP Database Server v1.0.0")
    report.append("")

    total_pass = 0
    total_tests = 0
    security_pass = True

    for cat in categories:
        report.append(f"### Category: {cat.name}")
        report.append("| Test Case | Expected | Actual | Status |")
        report.append("|-----------|----------|--------|--------|")

        for result in cat.results:
            status_icon = "PASS" if result.status == "PASS" else "FAIL"
            # Escape pipes in actual output
            actual_escaped = result.actual.replace("|", "\\|")
            report.append(f"| {result.test_case} | {result.expected} | {actual_escaped} | {status_icon} |")

        cat_pass = cat.get_pass_count()
        cat_total = cat.get_total_count()
        total_pass += cat_pass
        total_tests += cat_total

        report.append("")
        report.append(f"**{cat.name} Score:** {cat_pass}/{cat_total}")
        report.append("")

        if cat.name == "SQL Security":
            security_pass = cat_pass == cat_total

    # Security summary
    report.append("### Security Tests: " + ("PASS" if security_pass else "FAIL"))
    if security_pass:
        report.append("All SQL injection and destructive query attempts were blocked successfully.")
    else:
        report.append("WARNING: Some security tests failed. Review the SQL Security category above.")
    report.append("")

    # Overall score
    score = int((total_pass / total_tests) * 100) if total_tests > 0 else 0
    report.append(f"### Overall Error Handling Score: {score}/100")
    report.append("")
    report.append(f"**Tests Passed:** {total_pass}/{total_tests}")
    report.append("")

    # Summary by category
    report.append("### Summary by Category")
    report.append("| Category | Passed | Total | Score |")
    report.append("|----------|--------|-------|-------|")
    for cat in categories:
        cat_pass = cat.get_pass_count()
        cat_total = cat.get_total_count()
        cat_score = int((cat_pass / cat_total) * 100) if cat_total > 0 else 0
        report.append(f"| {cat.name} | {cat_pass} | {cat_total} | {cat_score}% |")

    return "\n".join(report)


def main():
    """Run error handling tests and print report."""
    print("Running EROS MCP Error Handling Tests...")
    print("=" * 60)

    categories = run_error_handling_tests()
    report = generate_report(categories)

    print(report)

    # Return exit code based on results
    total_pass = sum(cat.get_pass_count() for cat in categories)
    total_tests = sum(cat.get_total_count() for cat in categories)

    return 0 if total_pass == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
