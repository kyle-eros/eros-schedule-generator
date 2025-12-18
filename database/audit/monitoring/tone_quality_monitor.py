#!/usr/bin/env python3
"""
Tone Quality Monitor for EROS Caption Bank

Production-ready monitoring script for tracking tone classification quality,
detecting anomalies, and generating weekly reports.

Phase 4B of the Tone Classification Backfill Plan.

Usage:
    python tone_quality_monitor.py check    # Quick health check
    python tone_quality_monitor.py report   # Generate weekly report
    python tone_quality_monitor.py alerts   # Check for alert conditions
    python tone_quality_monitor.py metrics  # Show key metrics
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
except ImportError:
    print("Missing dependencies. Install with: pip install typer rich")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

DATABASE_PATH = Path(
    "~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
).expanduser()
REPORTS_DIR = Path(
    "~/Developer/EROS-SD-MAIN-PROJECT/database/audit/monitoring/reports"
).expanduser()
BASELINE_FILE = Path(
    "~/Developer/EROS-SD-MAIN-PROJECT/database/audit/plans/002-baseline-metrics.txt"
).expanduser()

# Baseline metrics (from completed backfill)
BASELINE_METRICS = {
    "total_captions": 60670,
    "tone_distribution": {
        "seductive": 61.4,
        "aggressive": 16.8,
        "playful": 10.6,
        "submissive": 8.3,
        "dominant": 1.6,
        "bratty": 1.4,
    },
    "average_confidence": 0.628,
    "snapshot_date": "2024-12-12",
}

# Alert thresholds
ALERT_THRESHOLDS = {
    "null_tone_critical": 0,  # Any NULL tones is critical
    "confidence_warning": 0.60,  # Warn if avg confidence drops below
    "distribution_shift_warning": 5.0,  # Warn if distribution shifts > 5%
    "low_confidence_threshold": 0.6,  # Captions below this are "low confidence"
}


# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tone_quality_monitor")


# =============================================================================
# Data Classes
# =============================================================================


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    OK = "OK"


@dataclass
class Alert:
    """Represents a monitoring alert."""

    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: Any
    threshold: Any = None
    recommendation: str = ""


@dataclass
class ToneMetrics:
    """Tone classification metrics."""

    total_captions: int = 0
    null_tone_count: int = 0
    tone_distribution: dict[str, float] = field(default_factory=dict)
    avg_confidence: float = 0.0
    avg_confidence_by_tone: dict[str, float] = field(default_factory=dict)
    classification_method_distribution: dict[str, int] = field(default_factory=dict)
    low_confidence_count: int = 0
    new_captions_count: int = 0
    timestamp: str = ""


# =============================================================================
# Database Operations
# =============================================================================


def get_db_connection() -> sqlite3.Connection:
    """Create database connection with row factory."""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_tone_metrics() -> ToneMetrics:
    """Fetch all tone-related metrics from the database."""
    metrics = ToneMetrics(timestamp=datetime.now().isoformat())

    with get_db_connection() as conn:
        # Total captions and NULL tones
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN tone IS NULL THEN 1 ELSE 0 END) as null_count,
                AVG(CASE WHEN classification_confidence IS NOT NULL
                    THEN classification_confidence ELSE NULL END) as avg_conf,
                SUM(CASE WHEN classification_confidence < ? THEN 1 ELSE 0 END) as low_conf
            FROM caption_bank
            WHERE is_active = 1
            """,
            (ALERT_THRESHOLDS["low_confidence_threshold"],),
        ).fetchone()

        metrics.total_captions = row["total"] or 0
        metrics.null_tone_count = row["null_count"] or 0
        metrics.avg_confidence = row["avg_conf"] or 0.0
        metrics.low_confidence_count = row["low_conf"] or 0

        # Tone distribution
        rows = conn.execute(
            """
            SELECT
                tone,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank WHERE is_active = 1), 1) as pct,
                ROUND(AVG(classification_confidence), 3) as avg_conf
            FROM caption_bank
            WHERE is_active = 1 AND tone IS NOT NULL
            GROUP BY tone
            ORDER BY count DESC
            """
        ).fetchall()

        for row in rows:
            tone = row["tone"]
            metrics.tone_distribution[tone] = row["pct"]
            metrics.avg_confidence_by_tone[tone] = row["avg_conf"]

        # Classification method distribution
        rows = conn.execute(
            """
            SELECT
                classification_method,
                COUNT(*) as count
            FROM caption_bank
            WHERE is_active = 1 AND classification_method IS NOT NULL
            GROUP BY classification_method
            ORDER BY count DESC
            """
        ).fetchall()

        for row in rows:
            method = row["classification_method"]
            metrics.classification_method_distribution[method] = row["count"]

        # New captions (added in last 24 hours)
        row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM caption_bank
            WHERE is_active = 1
              AND created_at >= datetime('now', '-1 day')
            """
        ).fetchone()
        metrics.new_captions_count = row["count"] or 0

    return metrics


# =============================================================================
# Alert Checking
# =============================================================================


def check_alerts(metrics: ToneMetrics) -> list[Alert]:
    """Check all alert conditions and return list of alerts."""
    alerts: list[Alert] = []

    # 1. NULL tones check (CRITICAL)
    if metrics.null_tone_count > ALERT_THRESHOLDS["null_tone_critical"]:
        alerts.append(
            Alert(
                severity=AlertSeverity.CRITICAL,
                message=f"Detected {metrics.null_tone_count} captions with NULL tone",
                metric_name="null_tone_count",
                current_value=metrics.null_tone_count,
                threshold=0,
                recommendation="Run tone classification backfill immediately",
            )
        )
    else:
        alerts.append(
            Alert(
                severity=AlertSeverity.OK,
                message="No NULL tones detected",
                metric_name="null_tone_count",
                current_value=0,
                threshold=0,
            )
        )

    # 2. Average confidence check (WARNING)
    if metrics.avg_confidence < ALERT_THRESHOLDS["confidence_warning"]:
        alerts.append(
            Alert(
                severity=AlertSeverity.WARNING,
                message=f"Average confidence {metrics.avg_confidence:.3f} below threshold",
                metric_name="avg_confidence",
                current_value=metrics.avg_confidence,
                threshold=ALERT_THRESHOLDS["confidence_warning"],
                recommendation="Review low-confidence classifications for quality",
            )
        )
    else:
        alerts.append(
            Alert(
                severity=AlertSeverity.OK,
                message=f"Average confidence {metrics.avg_confidence:.3f} is acceptable",
                metric_name="avg_confidence",
                current_value=metrics.avg_confidence,
                threshold=ALERT_THRESHOLDS["confidence_warning"],
            )
        )

    # 3. Distribution shift check (WARNING)
    for tone, baseline_pct in BASELINE_METRICS["tone_distribution"].items():
        current_pct = metrics.tone_distribution.get(tone, 0.0)
        shift = abs(current_pct - baseline_pct)

        if shift > ALERT_THRESHOLDS["distribution_shift_warning"]:
            alerts.append(
                Alert(
                    severity=AlertSeverity.WARNING,
                    message=f"Tone '{tone}' distribution shifted {shift:.1f}% from baseline",
                    metric_name=f"distribution_{tone}",
                    current_value=current_pct,
                    threshold=baseline_pct,
                    recommendation=f"Review classification logic for '{tone}' tone",
                )
            )

    # 4. New unclassified captions (INFO)
    if metrics.new_captions_count > 0:
        # Check if any new captions lack tone
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM caption_bank
                WHERE is_active = 1
                  AND created_at >= datetime('now', '-1 day')
                  AND tone IS NULL
                """
            ).fetchone()
            unclassified_new = row["count"] or 0

        if unclassified_new > 0:
            alerts.append(
                Alert(
                    severity=AlertSeverity.INFO,
                    message=f"{unclassified_new} new captions pending tone classification",
                    metric_name="new_unclassified",
                    current_value=unclassified_new,
                    recommendation="Run classification on new captions",
                )
            )

    # 5. Low confidence count check
    low_conf_pct = (
        (metrics.low_confidence_count / metrics.total_captions * 100)
        if metrics.total_captions > 0
        else 0
    )
    if low_conf_pct > 20:  # More than 20% low confidence
        alerts.append(
            Alert(
                severity=AlertSeverity.WARNING,
                message=f"{metrics.low_confidence_count} captions ({low_conf_pct:.1f}%) have low confidence",
                metric_name="low_confidence_count",
                current_value=metrics.low_confidence_count,
                threshold=f"<{ALERT_THRESHOLDS['low_confidence_threshold']}",
                recommendation="Consider re-classifying low confidence captions with AI",
            )
        )

    return alerts


# =============================================================================
# Report Generation
# =============================================================================


def generate_weekly_report(metrics: ToneMetrics, alerts: list[Alert]) -> str:
    """Generate weekly report in Markdown format."""
    report_lines = [
        "# Tone Quality Monitoring Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Database:** {DATABASE_PATH}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Total Active Captions:** {metrics.total_captions:,}",
        f"- **NULL Tones:** {metrics.null_tone_count:,}",
        f"- **Average Confidence:** {metrics.avg_confidence:.3f}",
        f"- **Low Confidence Captions:** {metrics.low_confidence_count:,}",
        f"- **New Captions (24h):** {metrics.new_captions_count:,}",
        "",
        "---",
        "",
        "## Alert Status",
        "",
    ]

    # Group alerts by severity
    critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
    warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
    info_alerts = [a for a in alerts if a.severity == AlertSeverity.INFO]
    ok_alerts = [a for a in alerts if a.severity == AlertSeverity.OK]

    if critical_alerts:
        report_lines.append("### CRITICAL Alerts")
        report_lines.append("")
        for alert in critical_alerts:
            report_lines.append(f"- **{alert.message}**")
            if alert.recommendation:
                report_lines.append(f"  - Recommendation: {alert.recommendation}")
        report_lines.append("")

    if warning_alerts:
        report_lines.append("### WARNING Alerts")
        report_lines.append("")
        for alert in warning_alerts:
            report_lines.append(f"- {alert.message}")
            if alert.recommendation:
                report_lines.append(f"  - Recommendation: {alert.recommendation}")
        report_lines.append("")

    if info_alerts:
        report_lines.append("### INFO Alerts")
        report_lines.append("")
        for alert in info_alerts:
            report_lines.append(f"- {alert.message}")
            if alert.recommendation:
                report_lines.append(f"  - Recommendation: {alert.recommendation}")
        report_lines.append("")

    if not critical_alerts and not warning_alerts and not info_alerts:
        report_lines.append("**All systems OK** - No alerts detected.")
        report_lines.append("")

    # Tone distribution table
    report_lines.extend(
        [
            "---",
            "",
            "## Tone Distribution",
            "",
            "| Tone | Current % | Baseline % | Shift | Avg Confidence |",
            "|------|-----------|------------|-------|----------------|",
        ]
    )

    for tone in ["seductive", "aggressive", "playful", "submissive", "dominant", "bratty"]:
        current_pct = metrics.tone_distribution.get(tone, 0.0)
        baseline_pct = BASELINE_METRICS["tone_distribution"].get(tone, 0.0)
        shift = current_pct - baseline_pct
        shift_str = f"+{shift:.1f}" if shift >= 0 else f"{shift:.1f}"
        avg_conf = metrics.avg_confidence_by_tone.get(tone, 0.0)
        report_lines.append(
            f"| {tone} | {current_pct:.1f}% | {baseline_pct:.1f}% | {shift_str}% | {avg_conf:.3f} |"
        )

    report_lines.append("")

    # Classification method table
    report_lines.extend(
        [
            "---",
            "",
            "## Classification Methods",
            "",
            "| Method | Count | Percentage |",
            "|--------|-------|------------|",
        ]
    )

    total = sum(metrics.classification_method_distribution.values())
    for method, count in sorted(
        metrics.classification_method_distribution.items(), key=lambda x: -x[1]
    )[:10]:  # Top 10
        pct = count / total * 100 if total > 0 else 0
        report_lines.append(f"| {method} | {count:,} | {pct:.1f}% |")

    if len(metrics.classification_method_distribution) > 10:
        other_count = sum(
            sorted(metrics.classification_method_distribution.values())[:-10]
        )
        other_pct = other_count / total * 100 if total > 0 else 0
        report_lines.append(f"| (other) | {other_count:,} | {other_pct:.1f}% |")

    report_lines.append("")

    # Recommendations section
    report_lines.extend(
        [
            "---",
            "",
            "## Recommendations",
            "",
        ]
    )

    recommendations = []
    if critical_alerts:
        recommendations.append(
            "1. **URGENT:** Address all CRITICAL alerts immediately"
        )
    if metrics.null_tone_count > 0:
        recommendations.append(
            f"2. Run tone classification on {metrics.null_tone_count} unclassified captions"
        )
    if metrics.avg_confidence < 0.65:
        recommendations.append(
            "3. Consider improving classification methods for higher confidence"
        )
    if metrics.low_confidence_count > metrics.total_captions * 0.15:
        recommendations.append(
            "4. Review and re-classify low confidence captions with AI"
        )

    if not recommendations:
        recommendations.append("No action items - tone quality is within acceptable parameters")

    report_lines.extend(recommendations)
    report_lines.extend(
        [
            "",
            "---",
            "",
            "*Report generated by tone_quality_monitor.py*",
        ]
    )

    return "\n".join(report_lines)


def save_report(report_content: str) -> Path:
    """Save report to the reports directory."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"tone_quality_report_{timestamp}.md"
    report_path.write_text(report_content)
    return report_path


# =============================================================================
# CLI Commands
# =============================================================================

app = typer.Typer(help="Tone Quality Monitor for EROS Caption Bank")
console = Console()


@app.command()
def check():
    """Quick health check - shows status at a glance."""
    try:
        metrics = fetch_tone_metrics()
        alerts = check_alerts(metrics)

        # Determine overall status
        has_critical = any(a.severity == AlertSeverity.CRITICAL for a in alerts)
        has_warning = any(a.severity == AlertSeverity.WARNING for a in alerts)

        if has_critical:
            status_color = "red"
            status_text = "CRITICAL"
        elif has_warning:
            status_color = "yellow"
            status_text = "WARNING"
        else:
            status_color = "green"
            status_text = "HEALTHY"

        # Create summary panel
        summary = f"""[bold]Status:[/bold] [{status_color}]{status_text}[/{status_color}]

[bold]Total Captions:[/bold] {metrics.total_captions:,}
[bold]NULL Tones:[/bold] {metrics.null_tone_count:,}
[bold]Avg Confidence:[/bold] {metrics.avg_confidence:.3f}
[bold]Low Confidence:[/bold] {metrics.low_confidence_count:,}
[bold]New (24h):[/bold] {metrics.new_captions_count:,}"""

        console.print(
            Panel(summary, title="Tone Quality Health Check", border_style=status_color)
        )

        # Show critical/warning alerts
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]

        if critical_alerts:
            console.print("\n[bold red]CRITICAL ALERTS:[/bold red]")
            for alert in critical_alerts:
                console.print(f"  [red]! {alert.message}[/red]")

        if warning_alerts:
            console.print("\n[bold yellow]WARNINGS:[/bold yellow]")
            for alert in warning_alerts:
                console.print(f"  [yellow]! {alert.message}[/yellow]")

        if not critical_alerts and not warning_alerts:
            console.print("\n[green]All checks passed![/green]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Health check failed")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def report():
    """Generate and save weekly report."""
    try:
        console.print("[bold]Generating weekly report...[/bold]")

        metrics = fetch_tone_metrics()
        alerts = check_alerts(metrics)
        report_content = generate_weekly_report(metrics, alerts)
        report_path = save_report(report_content)

        console.print(f"[green]Report saved to:[/green] {report_path}")

        # Also display to console
        console.print("\n" + "-" * 60)
        console.print(report_content)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Report generation failed")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def alerts():
    """Check and display all alert conditions."""
    try:
        metrics = fetch_tone_metrics()
        alert_list = check_alerts(metrics)

        # Create alerts table
        table = Table(title="Alert Status", box=box.ROUNDED)
        table.add_column("Severity", style="bold")
        table.add_column("Metric")
        table.add_column("Message")
        table.add_column("Recommendation")

        severity_colors = {
            AlertSeverity.CRITICAL: "red",
            AlertSeverity.WARNING: "yellow",
            AlertSeverity.INFO: "blue",
            AlertSeverity.OK: "green",
        }

        for alert in alert_list:
            color = severity_colors.get(alert.severity, "white")
            table.add_row(
                f"[{color}]{alert.severity.value}[/{color}]",
                alert.metric_name,
                alert.message,
                alert.recommendation or "-",
            )

        console.print(table)

        # Summary
        critical_count = sum(1 for a in alert_list if a.severity == AlertSeverity.CRITICAL)
        warning_count = sum(1 for a in alert_list if a.severity == AlertSeverity.WARNING)
        info_count = sum(1 for a in alert_list if a.severity == AlertSeverity.INFO)

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Critical: [red]{critical_count}[/red]")
        console.print(f"  Warning:  [yellow]{warning_count}[/yellow]")
        console.print(f"  Info:     [blue]{info_count}[/blue]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Alert check failed")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def metrics():
    """Show detailed key metrics."""
    try:
        metrics = fetch_tone_metrics()

        # Overview panel
        overview = Table(title="Overview Metrics", box=box.ROUNDED)
        overview.add_column("Metric", style="bold")
        overview.add_column("Value", justify="right")
        overview.add_column("Status")

        # NULL tones
        null_status = "[green]OK[/green]" if metrics.null_tone_count == 0 else "[red]CRITICAL[/red]"
        overview.add_row("Total Captions", f"{metrics.total_captions:,}", "")
        overview.add_row("NULL Tones", f"{metrics.null_tone_count:,}", null_status)

        # Confidence
        conf_status = (
            "[green]OK[/green]"
            if metrics.avg_confidence >= ALERT_THRESHOLDS["confidence_warning"]
            else "[yellow]WARNING[/yellow]"
        )
        overview.add_row("Average Confidence", f"{metrics.avg_confidence:.3f}", conf_status)

        # Low confidence
        low_conf_pct = (
            metrics.low_confidence_count / metrics.total_captions * 100
            if metrics.total_captions > 0
            else 0
        )
        low_status = "[green]OK[/green]" if low_conf_pct <= 20 else "[yellow]WARNING[/yellow]"
        overview.add_row(
            "Low Confidence (<0.6)",
            f"{metrics.low_confidence_count:,} ({low_conf_pct:.1f}%)",
            low_status,
        )
        overview.add_row("New Captions (24h)", f"{metrics.new_captions_count:,}", "")

        console.print(overview)

        # Tone distribution table
        tone_table = Table(title="\nTone Distribution", box=box.ROUNDED)
        tone_table.add_column("Tone", style="bold")
        tone_table.add_column("Current %", justify="right")
        tone_table.add_column("Baseline %", justify="right")
        tone_table.add_column("Shift", justify="right")
        tone_table.add_column("Avg Confidence", justify="right")

        for tone in ["seductive", "aggressive", "playful", "submissive", "dominant", "bratty"]:
            current_pct = metrics.tone_distribution.get(tone, 0.0)
            baseline_pct = BASELINE_METRICS["tone_distribution"].get(tone, 0.0)
            shift = current_pct - baseline_pct
            shift_str = f"+{shift:.1f}%" if shift >= 0 else f"{shift:.1f}%"
            shift_color = (
                "[red]" if abs(shift) > 5 else "[yellow]" if abs(shift) > 2 else "[green]"
            )
            avg_conf = metrics.avg_confidence_by_tone.get(tone, 0.0)

            tone_table.add_row(
                tone,
                f"{current_pct:.1f}%",
                f"{baseline_pct:.1f}%",
                f"{shift_color}{shift_str}[/]",
                f"{avg_conf:.3f}",
            )

        console.print(tone_table)

        # Classification methods table (top 10)
        method_table = Table(title="\nClassification Methods (Top 10)", box=box.ROUNDED)
        method_table.add_column("Method", style="bold")
        method_table.add_column("Count", justify="right")
        method_table.add_column("Percentage", justify="right")

        total = sum(metrics.classification_method_distribution.values())
        sorted_methods = sorted(
            metrics.classification_method_distribution.items(), key=lambda x: -x[1]
        )

        for method, count in sorted_methods[:10]:
            pct = count / total * 100 if total > 0 else 0
            method_table.add_row(method, f"{count:,}", f"{pct:.1f}%")

        console.print(method_table)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Metrics display failed")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    app()
