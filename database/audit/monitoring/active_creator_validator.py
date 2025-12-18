#!/usr/bin/env python3
"""
EROS Active Creator Page Name Validator

Production-ready validation tool for monitoring active creator page_name integrity
in the EROS database. Designed for scheduled monitoring via cron.

Exit Codes:
    0: All validations passed (clean state)
    1: Fragmentation or critical issues detected (action required)
    2: Script error (database connection, invalid arguments, etc.)

Usage:
    python active_creator_validator.py --db /path/to/eros_sd_main.db
    python active_creator_validator.py --db ./eros_sd_main.db --format json
    python active_creator_validator.py --db ./eros_sd_main.db --format html --output report.html

Author: EROS Team
Version: 1.0.0
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ValidationStatus(Enum):
    """Validation check result status."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class QualityGrade(Enum):
    """Overall quality grade classification."""
    EXCELLENT = "A"
    GOOD = "B"
    FAIR = "C"
    POOR = "D"
    CRITICAL = "F"


@dataclass
class ValidationResult:
    """Result of a single validation check.

    Attributes:
        check_name: Human-readable name of the validation
        status: Pass/Fail/Warning status
        affected_count: Number of issues found (0 for PASS)
        details: Specific details about issues (creator_ids, page_names, etc.)
        recommendation: Action to take if check failed
        metadata: Additional metadata (counts, percentages, etc.)
    """
    check_name: str
    status: ValidationStatus
    affected_count: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report.

    Attributes:
        timestamp: ISO format timestamp of report generation
        database_path: Path to database that was validated
        total_active_creators: Count of active creators
        overall_status: Overall PASS/FAIL status
        quality_grade: Letter grade (A-F)
        results: List of individual validation results
        recommendations: List of recommended actions
    """
    timestamp: str
    database_path: str
    total_active_creators: int
    overall_status: ValidationStatus
    quality_grade: QualityGrade
    results: List[ValidationResult]
    recommendations: List[str] = field(default_factory=list)


class ActiveCreatorValidator:
    """Validates page_name integrity for active creators in EROS database.

    Performs 5 core validations:
        1. Active creator fragmentation (multiple page_names per creator_id)
        2. Case consistency (no case variations)
        3. Canonical name match (mm.page_name = c.page_name when joined)
        4. NULL page_name check
        5. Coverage percentage (% of messages with creator_id)
    """

    def __init__(self, db_path: str, coverage_threshold: float = 0.95, verbose: bool = False):
        """Initialize validator.

        Args:
            db_path: Path to SQLite database file
            coverage_threshold: Minimum coverage percentage for PASS (0.0-1.0)
            verbose: Enable verbose debug output

        Raises:
            FileNotFoundError: If database file does not exist
            sqlite3.Error: If database connection fails
        """
        self.db_path = Path(db_path)
        self.coverage_threshold = coverage_threshold
        self.verbose = verbose
        self.conn: Optional[sqlite3.Connection] = None

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

    def __enter__(self) -> "ActiveCreatorValidator":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def connect(self) -> None:
        """Establish database connection.

        Raises:
            sqlite3.Error: If connection fails
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            if self.verbose:
                print(f"Connected to database: {self.db_path}", file=sys.stderr)
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Failed to connect to database: {e}") from e

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            if self.verbose:
                print("Database connection closed", file=sys.stderr)

    def _execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute SQL query and return results.

        Args:
            query: SQL query string
            params: Query parameters for parameterized queries

        Returns:
            List of result rows

        Raises:
            sqlite3.Error: If query execution fails
        """
        if not self.conn:
            raise sqlite3.Error("Database not connected")

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Query execution failed: {e}\nQuery: {query}") from e

    def get_total_active_creators(self) -> int:
        """Get count of active creators.

        Returns:
            Number of creators with is_active = 1
        """
        query = "SELECT COUNT(*) as count FROM creators WHERE is_active = 1"
        result = self._execute_query(query)
        return result[0]["count"]

    def check_active_creator_fragmentation(self) -> ValidationResult:
        """Check for multiple page_names per active creator_id.

        Returns:
            ValidationResult with fragmentation details
        """
        query = """
        WITH active_creator_names AS (
            SELECT
                mm.creator_id,
                mm.page_name,
                COUNT(*) as occurrence_count
            FROM mass_messages mm
            INNER JOIN creators c ON mm.creator_id = c.creator_id
            WHERE c.is_active = 1
                AND mm.page_name IS NOT NULL
            GROUP BY mm.creator_id, mm.page_name
        ),
        fragmented_creators AS (
            SELECT
                creator_id,
                COUNT(DISTINCT page_name) as name_count,
                GROUP_CONCAT(page_name || ' (' || occurrence_count || ')', ', ') as all_names
            FROM active_creator_names
            GROUP BY creator_id
            HAVING COUNT(DISTINCT page_name) > 1
        )
        SELECT * FROM fragmented_creators
        ORDER BY name_count DESC, creator_id
        """

        results = self._execute_query(query)

        if not results:
            return ValidationResult(
                check_name="Active Creator Fragmentation Check",
                status=ValidationStatus.PASS,
                affected_count=0,
                details=[],
                recommendation="",
                metadata={"description": "No fragmentation detected"}
            )

        details = [
            {
                "creator_id": row["creator_id"],
                "name_count": row["name_count"],
                "all_names": row["all_names"]
            }
            for row in results
        ]

        return ValidationResult(
            check_name="Active Creator Fragmentation Check",
            status=ValidationStatus.FAIL,
            affected_count=len(results),
            details=details,
            recommendation=(
                "CRITICAL: Fragmentation detected. Run consolidation script to merge "
                "page_name variants and update creator canonical page_name."
            ),
            metadata={
                "description": f"{len(results)} creator(s) have multiple page_name values"
            }
        )

    def check_case_consistency(self) -> ValidationResult:
        """Check for case variations in page_names for active creators.

        Returns:
            ValidationResult with case inconsistency details
        """
        query = """
        WITH active_creator_canonical AS (
            SELECT creator_id, page_name as canonical_name
            FROM creators
            WHERE is_active = 1
        ),
        case_mismatches AS (
            SELECT
                mm.creator_id,
                acc.canonical_name,
                mm.page_name as message_name,
                COUNT(*) as occurrence_count
            FROM mass_messages mm
            INNER JOIN active_creator_canonical acc ON mm.creator_id = acc.creator_id
            WHERE mm.page_name IS NOT NULL
                AND mm.page_name != acc.canonical_name
                AND LOWER(mm.page_name) = LOWER(acc.canonical_name)
            GROUP BY mm.creator_id, mm.page_name
        )
        SELECT * FROM case_mismatches
        ORDER BY occurrence_count DESC
        """

        results = self._execute_query(query)

        if not results:
            return ValidationResult(
                check_name="Case Consistency Validation",
                status=ValidationStatus.PASS,
                affected_count=0,
                details=[],
                recommendation="",
                metadata={"description": "All page_names match canonical case"}
            )

        total_mismatches = sum(row["occurrence_count"] for row in results)
        details = [
            {
                "creator_id": row["creator_id"],
                "canonical_name": row["canonical_name"],
                "message_name": row["message_name"],
                "occurrence_count": row["occurrence_count"]
            }
            for row in results
        ]

        return ValidationResult(
            check_name="Case Consistency Validation",
            status=ValidationStatus.WARNING,
            affected_count=len(results),
            details=details,
            recommendation=(
                "Update mass_messages.page_name to match canonical case from creators table. "
                "This is a cosmetic issue but should be fixed for consistency."
            ),
            metadata={
                "description": f"{len(results)} creator(s) have case mismatches",
                "total_affected_messages": total_mismatches
            }
        )

    def check_canonical_name_match(self) -> ValidationResult:
        """Check that creator_id messages use correct canonical page_name.

        Returns:
            ValidationResult with canonical mismatch details
        """
        query = """
        WITH active_creator_canonical AS (
            SELECT creator_id, page_name as canonical_name
            FROM creators
            WHERE is_active = 1
        ),
        name_mismatches AS (
            SELECT
                mm.creator_id,
                acc.canonical_name,
                mm.page_name as message_name,
                COUNT(*) as occurrence_count
            FROM mass_messages mm
            INNER JOIN active_creator_canonical acc ON mm.creator_id = acc.creator_id
            WHERE mm.page_name IS NOT NULL
                AND LOWER(mm.page_name) != LOWER(acc.canonical_name)
            GROUP BY mm.creator_id, mm.page_name
        )
        SELECT * FROM name_mismatches
        ORDER BY occurrence_count DESC
        """

        results = self._execute_query(query)

        if not results:
            return ValidationResult(
                check_name="Canonical Name Match",
                status=ValidationStatus.PASS,
                affected_count=0,
                details=[],
                recommendation="",
                metadata={"description": "All creator_id messages use correct page_name"}
            )

        total_mismatches = sum(row["occurrence_count"] for row in results)
        details = [
            {
                "creator_id": row["creator_id"],
                "canonical_name": row["canonical_name"],
                "message_name": row["message_name"],
                "occurrence_count": row["occurrence_count"]
            }
            for row in results
        ]

        return ValidationResult(
            check_name="Canonical Name Match",
            status=ValidationStatus.FAIL,
            affected_count=len(results),
            details=details,
            recommendation=(
                "CRITICAL: Non-canonical page_names detected. Run UPDATE query to align "
                "mass_messages.page_name with creators.page_name for affected creator_ids."
            ),
            metadata={
                "description": f"{len(results)} creator(s) have non-canonical page_names",
                "total_affected_messages": total_mismatches
            }
        )

    def check_null_page_names(self) -> ValidationResult:
        """Check for NULL page_names for active creator messages.

        Returns:
            ValidationResult with NULL page_name details
        """
        query = """
        SELECT
            mm.creator_id,
            c.page_name as canonical_name,
            COUNT(*) as null_count
        FROM mass_messages mm
        INNER JOIN creators c ON mm.creator_id = c.creator_id
        WHERE c.is_active = 1
            AND mm.page_name IS NULL
        GROUP BY mm.creator_id, c.page_name
        ORDER BY null_count DESC
        """

        results = self._execute_query(query)

        if not results:
            return ValidationResult(
                check_name="NULL Page Name Check",
                status=ValidationStatus.PASS,
                affected_count=0,
                details=[],
                recommendation="",
                metadata={"description": "No NULL page_names for active creators"}
            )

        total_nulls = sum(row["null_count"] for row in results)
        details = [
            {
                "creator_id": row["creator_id"],
                "canonical_name": row["canonical_name"],
                "null_count": row["null_count"]
            }
            for row in results
        ]

        return ValidationResult(
            check_name="NULL Page Name Check",
            status=ValidationStatus.FAIL,
            affected_count=len(results),
            details=details,
            recommendation=(
                "CRITICAL: NULL page_names found. Run UPDATE to backfill from creators table "
                "for all messages with creator_id but NULL page_name."
            ),
            metadata={
                "description": f"{len(results)} creator(s) have NULL page_names",
                "total_null_messages": total_nulls
            }
        )

    def check_coverage_analysis(self) -> ValidationResult:
        """Analyze coverage percentage of messages with creator_id.

        Returns:
            ValidationResult with coverage statistics
        """
        query = """
        SELECT
            COUNT(*) as total_messages,
            SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) as with_creator_id,
            ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as coverage_pct
        FROM mass_messages
        """

        result = self._execute_query(query)[0]

        total = result["total_messages"]
        with_id = result["with_creator_id"]
        coverage = result["coverage_pct"] / 100.0  # Convert to 0-1 range

        # Determine status based on threshold
        if coverage >= self.coverage_threshold:
            status = ValidationStatus.PASS
            description = "Excellent coverage"
        elif coverage >= 0.70:
            status = ValidationStatus.WARNING
            description = "Acceptable coverage but below threshold"
        else:
            status = ValidationStatus.FAIL
            description = "Poor coverage - significant orphaned data"

        return ValidationResult(
            check_name="Coverage Analysis",
            status=status,
            affected_count=total - with_id,
            details=[],
            recommendation=(
                "Review orphaned messages without creator_id. These may be historical data "
                "or require backfill from page_name matching."
            ) if status != ValidationStatus.PASS else "",
            metadata={
                "description": description,
                "total_messages": total,
                "with_creator_id": with_id,
                "without_creator_id": total - with_id,
                "coverage_percentage": round(coverage * 100, 2),
                "threshold_percentage": round(self.coverage_threshold * 100, 2)
            }
        )

    def run_all_validations(self) -> ValidationReport:
        """Run all validation checks and generate comprehensive report.

        Returns:
            ValidationReport with all results
        """
        if self.verbose:
            print("Running validation checks...", file=sys.stderr)

        total_active = self.get_total_active_creators()

        # Run all validation checks
        results = [
            self.check_active_creator_fragmentation(),
            self.check_case_consistency(),
            self.check_canonical_name_match(),
            self.check_null_page_names(),
            self.check_coverage_analysis()
        ]

        # Determine overall status
        has_fail = any(r.status == ValidationStatus.FAIL for r in results)
        has_warning = any(r.status == ValidationStatus.WARNING for r in results)

        if has_fail:
            overall_status = ValidationStatus.FAIL
        elif has_warning:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.PASS

        # Calculate quality grade
        fail_count = sum(1 for r in results if r.status == ValidationStatus.FAIL)
        warning_count = sum(1 for r in results if r.status == ValidationStatus.WARNING)

        if fail_count == 0 and warning_count == 0:
            quality_grade = QualityGrade.EXCELLENT
        elif fail_count == 0 and warning_count <= 1:
            quality_grade = QualityGrade.GOOD
        elif fail_count <= 1:
            quality_grade = QualityGrade.FAIR
        elif fail_count <= 2:
            quality_grade = QualityGrade.POOR
        else:
            quality_grade = QualityGrade.CRITICAL

        # Collect recommendations
        recommendations = [
            r.recommendation for r in results
            if r.recommendation and r.status != ValidationStatus.PASS
        ]

        return ValidationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            database_path=str(self.db_path.absolute()),
            total_active_creators=total_active,
            overall_status=overall_status,
            quality_grade=quality_grade,
            results=results,
            recommendations=recommendations
        )


class ReportFormatter:
    """Formats validation reports in different output formats."""

    @staticmethod
    def format_text(report: ValidationReport, verbose: bool = False) -> str:
        """Format report as human-readable text.

        Args:
            report: ValidationReport to format
            verbose: Include detailed issue information

        Returns:
            Formatted text report
        """
        lines = [
            "=" * 70,
            "EROS Active Creator Page Name Validation Report",
            "=" * 70,
            f"Timestamp: {report.timestamp}",
            f"Database: {report.database_path}",
            f"Active Creators: {report.total_active_creators}",
            "",
            f"OVERALL STATUS: {ReportFormatter._status_icon(report.overall_status)} {report.overall_status.value}",
            f"Quality Grade: {report.quality_grade.value} ({report.quality_grade.name})",
            "",
            "Validation Results:",
            "-" * 70
        ]

        for result in report.results:
            icon = ReportFormatter._status_icon(result.status)
            lines.append(f"[{result.status.value}] {icon} {result.check_name}")

            if result.metadata.get("description"):
                lines.append(f"  Status: {result.metadata['description']}")

            if result.affected_count > 0:
                lines.append(f"  Affected: {result.affected_count}")

            # Add metadata details
            for key, value in result.metadata.items():
                if key != "description" and not key.endswith("_messages"):
                    display_key = key.replace("_", " ").title()
                    lines.append(f"  {display_key}: {value}")

            # Add detailed issues if verbose
            if verbose and result.details:
                lines.append("  Details:")
                for detail in result.details[:5]:  # Limit to first 5
                    detail_str = ", ".join(f"{k}={v}" for k, v in detail.items())
                    lines.append(f"    - {detail_str}")
                if len(result.details) > 5:
                    lines.append(f"    ... and {len(result.details) - 5} more")

            if result.recommendation:
                lines.append(f"  Recommendation: {result.recommendation}")

            lines.append("")

        lines.extend([
            "=" * 70,
            "CONCLUSION:",
        ])

        if report.overall_status == ValidationStatus.PASS:
            lines.append(
                "All active creators have clean, non-fragmented page_name values. "
                "No action required."
            )
        else:
            lines.append(
                f"Found {len(report.recommendations)} issue(s) requiring attention. "
                "See recommendations above."
            )

        lines.append("=" * 70)

        return "\n".join(lines)

    @staticmethod
    def format_json(report: ValidationReport) -> str:
        """Format report as JSON.

        Args:
            report: ValidationReport to format

        Returns:
            JSON string
        """
        data = {
            "timestamp": report.timestamp,
            "database_path": report.database_path,
            "total_active_creators": report.total_active_creators,
            "overall_status": report.overall_status.value,
            "quality_grade": report.quality_grade.value,
            "results": [
                {
                    "check_name": r.check_name,
                    "status": r.status.value,
                    "affected_count": r.affected_count,
                    "details": r.details,
                    "recommendation": r.recommendation,
                    "metadata": r.metadata
                }
                for r in report.results
            ],
            "recommendations": report.recommendations
        }

        return json.dumps(data, indent=2)

    @staticmethod
    def format_html(report: ValidationReport) -> str:
        """Format report as HTML.

        Args:
            report: ValidationReport to format

        Returns:
            HTML string
        """
        status_colors = {
            ValidationStatus.PASS: "#28a745",
            ValidationStatus.WARNING: "#ffc107",
            ValidationStatus.FAIL: "#dc3545"
        }

        grade_colors = {
            QualityGrade.EXCELLENT: "#28a745",
            QualityGrade.GOOD: "#5cb85c",
            QualityGrade.FAIR: "#f0ad4e",
            QualityGrade.POOR: "#ff8c00",
            QualityGrade.CRITICAL: "#dc3545"
        }

        overall_color = status_colors[report.overall_status]
        grade_color = grade_colors[report.quality_grade]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>EROS Active Creator Validation Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .header {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .header-item {{
            margin: 5px 0;
            color: #666;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            color: white;
            font-weight: bold;
            margin: 10px 0;
        }}
        .validation-result {{
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
            background: #fafafa;
        }}
        .result-header {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        .result-status {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 3px;
            color: white;
            font-size: 12px;
            margin-left: 10px;
        }}
        .metadata {{
            margin: 10px 0;
            color: #555;
        }}
        .recommendation {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin-top: 10px;
            border-radius: 3px;
        }}
        .conclusion {{
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin-top: 20px;
            border-radius: 3px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>EROS Active Creator Page Name Validation Report</h1>

        <div class="header">
            <div class="header-item"><strong>Timestamp:</strong> {report.timestamp}</div>
            <div class="header-item"><strong>Database:</strong> {report.database_path}</div>
            <div class="header-item"><strong>Active Creators:</strong> {report.total_active_creators}</div>
        </div>

        <div>
            <span class="status-badge" style="background-color: {overall_color};">
                Overall Status: {report.overall_status.value}
            </span>
            <span class="status-badge" style="background-color: {grade_color};">
                Quality Grade: {report.quality_grade.value} ({report.quality_grade.name})
            </span>
        </div>

        <h2>Validation Results</h2>
"""

        for result in report.results:
            color = status_colors[result.status]
            html += f"""
        <div class="validation-result">
            <div class="result-header">
                {result.check_name}
                <span class="result-status" style="background-color: {color};">{result.status.value}</span>
            </div>
"""

            if result.metadata.get("description"):
                html += f"            <div class=\"metadata\"><strong>Status:</strong> {result.metadata['description']}</div>\n"

            if result.affected_count > 0:
                html += f"            <div class=\"metadata\"><strong>Affected:</strong> {result.affected_count}</div>\n"

            for key, value in result.metadata.items():
                if key != "description" and not key.endswith("_messages"):
                    display_key = key.replace("_", " ").title()
                    html += f"            <div class=\"metadata\"><strong>{display_key}:</strong> {value}</div>\n"

            if result.details:
                html += "            <div class=\"metadata\"><strong>Details:</strong></div>\n"
                html += "            <table>\n"

                # Get headers from first detail
                if result.details:
                    headers = list(result.details[0].keys())
                    html += "                <tr>" + "".join(f"<th>{h.replace('_', ' ').title()}</th>" for h in headers) + "</tr>\n"

                    for detail in result.details[:10]:  # Limit to 10 rows
                        html += "                <tr>" + "".join(f"<td>{detail.get(h, '')}</td>" for h in headers) + "</tr>\n"

                    if len(result.details) > 10:
                        html += f"                <tr><td colspan=\"{len(headers)}\"><em>... and {len(result.details) - 10} more</em></td></tr>\n"

                html += "            </table>\n"

            if result.recommendation:
                html += f"            <div class=\"recommendation\"><strong>Recommendation:</strong> {result.recommendation}</div>\n"

            html += "        </div>\n"

        conclusion_text = (
            "All active creators have clean, non-fragmented page_name values. No action required."
            if report.overall_status == ValidationStatus.PASS
            else f"Found {len(report.recommendations)} issue(s) requiring attention. See recommendations above."
        )

        html += f"""
        <div class="conclusion">
            <strong>Conclusion:</strong> {conclusion_text}
        </div>
    </div>
</body>
</html>
"""

        return html

    @staticmethod
    def _status_icon(status: ValidationStatus) -> str:
        """Get unicode icon for status.

        Args:
            status: ValidationStatus

        Returns:
            Unicode icon character
        """
        icons = {
            ValidationStatus.PASS: "✅",
            ValidationStatus.WARNING: "⚠️",
            ValidationStatus.FAIL: "❌"
        }
        return icons.get(status, "❓")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Validate page_name integrity for active creators in EROS database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --db ./eros_sd_main.db
  %(prog)s --db ./eros_sd_main.db --format json --output report.json
  %(prog)s --db ./eros_sd_main.db --format html --output report.html --verbose
  %(prog)s --db ./eros_sd_main.db --threshold 0.90

Exit Codes:
  0  All validations passed (clean state)
  1  Fragmentation or critical issues detected (action required)
  2  Script error (database connection, invalid arguments, etc.)
        """
    )

    parser.add_argument(
        "--db",
        required=True,
        help="Path to SQLite database file"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text", "html"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--output",
        help="Write output to file instead of stdout"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include detailed debug information"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        help="Minimum coverage threshold for PASS (default: 0.95)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0=success, 1=validation failed, 2=error)
    """
    try:
        args = parse_args()

        # Validate threshold
        if not 0.0 <= args.threshold <= 1.0:
            print("Error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
            return 2

        # Run validation
        with ActiveCreatorValidator(args.db, args.threshold, args.verbose) as validator:
            report = validator.run_all_validations()

        # Format output
        if args.format == "json":
            output = ReportFormatter.format_json(report)
        elif args.format == "html":
            output = ReportFormatter.format_html(report)
        else:  # text
            output = ReportFormatter.format_text(report, verbose=args.verbose)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(output, encoding="utf-8")
            print(f"Report written to: {output_path.absolute()}", file=sys.stderr)
        else:
            print(output)

        # Determine exit code
        if report.overall_status == ValidationStatus.FAIL:
            return 1
        else:
            return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
