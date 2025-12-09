#!/usr/bin/env python3
"""
Analyze Creator - Generate creator analytics brief.

This script generates a comprehensive analytics brief for a creator,
including performance metrics, best hours, content performance,
and scheduling recommendations.

Usage:
    python analyze_creator.py --creator missalexa
    python analyze_creator.py --creator-id abc123 --period 90
    python analyze_creator.py --creator missalexa --output brief.md
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from volume_optimizer import MultiFactorVolumeOptimizer, VolumeStrategy

# Path resolution for database and SQL files
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "database" / "eros_sd_main.db"
SQL_DIR = SCRIPT_DIR.parent / "assets" / "sql"


@dataclass
class AIInsightsRequest:
    """Structured data for Claude to generate strategic insights."""

    creator_name: str
    display_name: str

    # Performance metrics
    total_revenue_30d: float
    avg_revenue_per_message: float
    total_messages_30d: int
    purchase_rate: float
    view_rate: float

    # Timing data
    best_hours: list[dict]
    best_days: list[dict]

    # Content performance
    best_content_types: list[dict]

    # Caption health
    total_captions: int
    fresh_captions: int
    exhausted_captions: int
    avg_freshness: float

    # Persona
    primary_tone: str
    emoji_frequency: str
    slang_level: str

    # Volume
    volume_level: str
    ppv_per_day: int

    # Benchmarks
    vs_agency_avg: str = ""
    percentile_rank: str = ""


@dataclass
class CreatorBrief:
    """Comprehensive creator analytics brief."""

    # Identity
    creator_id: str
    page_name: str
    display_name: str
    page_type: str  # paid or free

    # Current Metrics
    active_fans: int = 0
    total_earnings: float = 0.0
    message_net: float = 0.0
    avg_earnings_per_fan: float = 0.0
    contribution_pct: float = 0.0
    of_ranking: str = ""
    performance_tier: int = 3

    # Volume Assignment
    volume_level: str = "Mid"
    ppv_per_day: int = 4
    bump_per_day: int = 4

    # Historical Performance
    total_messages: int = 0
    avg_earnings_per_message: float = 0.0
    avg_view_rate: float = 0.0
    avg_purchase_rate: float = 0.0

    # Best Performing
    best_hours: list[dict[str, Any]] = field(default_factory=list)
    best_days: list[dict[str, Any]] = field(default_factory=list)
    best_content_types: list[dict[str, Any]] = field(default_factory=list)

    # Caption Pool
    total_captions: int = 0
    fresh_captions: int = 0
    exhausted_captions: int = 0
    avg_freshness: float = 0.0

    # Persona
    primary_tone: str = ""
    emoji_frequency: str = ""
    slang_level: str = ""

    # Vault Summary
    vault_content_types: list[str] = field(default_factory=list)
    vault_total_types: int = 0

    # Period Info
    analysis_period_days: int = 30
    analysis_date: str = ""


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_sql_file(filename: str) -> str:
    """Load SQL query from assets/sql directory."""
    sql_path = SQL_DIR / filename
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    return sql_path.read_text()


def get_volume_level(active_fans: int) -> tuple[str, int, int]:
    """
    Determine volume level based on fan count.

    DEPRECATED: Use analyze_volume_recommendation() for multi-factor optimization.

    Returns:
        Tuple of (level_name, ppv_per_day, bump_per_day)
    """
    # Legacy fallback for simple fan-count based volume
    if active_fans < 1000:
        return ("Low", 2, 2)
    elif active_fans < 5000:
        return ("Mid", 4, 4)
    elif active_fans < 15000:
        return ("High", 7, 7)
    else:
        return ("Ultra", 9, 9)


def analyze_volume_recommendation(creator_id: str, conn: sqlite3.Connection) -> VolumeStrategy:
    """
    Get volume recommendation using multi-factor optimizer.

    This function uses the centralized MultiFactorVolumeOptimizer which
    considers multiple factors:
    - Fan count brackets (base volume)
    - Performance tier (revenue contribution)
    - Conversion rate
    - Niche/persona type
    - Subscription price
    - Account age

    Args:
        creator_id: Creator UUID or page_name
        conn: Database connection

    Returns:
        VolumeStrategy with comprehensive volume recommendations
    """
    optimizer = MultiFactorVolumeOptimizer(conn)
    return optimizer.calculate_optimal_volume(creator_id)


def generate_brief(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
    period_days: int = 30,
) -> CreatorBrief | None:
    """
    Generate a comprehensive analytics brief for a creator.

    Args:
        conn: Database connection
        creator_name: Creator page name (optional)
        creator_id: Creator UUID (optional)
        period_days: Number of days for historical analysis

    Returns:
        CreatorBrief or None if creator not found
    """
    if not creator_name and not creator_id:
        raise ValueError("Must provide either creator_name or creator_id")

    # Load creator profile
    if creator_name:
        query = """
            SELECT c.*, cp.primary_tone, cp.emoji_frequency, cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.page_name = ? OR c.display_name = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_name, creator_name))
    else:
        query = """
            SELECT c.*, cp.primary_tone, cp.emoji_frequency, cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_id,))

    row = cursor.fetchone()
    if not row:
        return None

    profile = dict(row)
    cid = profile["creator_id"]

    # Get volume level using multi-factor optimizer
    active_fans = profile.get("current_active_fans") or 0
    try:
        volume_strategy = analyze_volume_recommendation(cid, conn)
        volume_level = volume_strategy.volume_level
        ppv_per_day = volume_strategy.ppv_per_day
        bump_per_day = volume_strategy.bump_per_day
    except Exception:
        # Fallback to legacy simple volume calculation if optimizer fails
        volume_level, ppv_per_day, bump_per_day = get_volume_level(active_fans)

    # Initialize brief
    brief = CreatorBrief(
        creator_id=cid,
        page_name=profile["page_name"],
        display_name=profile["display_name"],
        page_type=profile["page_type"],
        active_fans=active_fans,
        total_earnings=profile.get("current_total_earnings") or 0.0,
        message_net=profile.get("current_message_net") or 0.0,
        avg_earnings_per_fan=profile.get("current_avg_earnings_per_fan") or 0.0,
        contribution_pct=profile.get("current_contribution_pct") or 0.0,
        of_ranking=profile.get("current_of_ranking") or "",
        performance_tier=profile.get("performance_tier") or 3,
        volume_level=volume_level,
        ppv_per_day=ppv_per_day,
        bump_per_day=bump_per_day,
        primary_tone=profile.get("primary_tone") or "",
        emoji_frequency=profile.get("emoji_frequency") or "",
        slang_level=profile.get("slang_level") or "",
        analysis_period_days=period_days,
        analysis_date=date.today().isoformat(),
    )

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    # Get historical performance
    perf_query = """
        SELECT
            COUNT(*) as total_messages,
            AVG(earnings) as avg_earnings,
            AVG(view_rate) as avg_view_rate,
            AVG(purchase_rate) as avg_purchase_rate
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sending_time >= ?
    """
    cursor = conn.execute(perf_query, (cid, start_date.isoformat()))
    perf_row = cursor.fetchone()
    if perf_row:
        brief.total_messages = perf_row["total_messages"] or 0
        brief.avg_earnings_per_message = perf_row["avg_earnings"] or 0.0
        brief.avg_view_rate = perf_row["avg_view_rate"] or 0.0
        brief.avg_purchase_rate = perf_row["avg_purchase_rate"] or 0.0

    # Get best hours
    hours_query = """
        SELECT
            sending_hour as hour,
            COUNT(*) as count,
            AVG(earnings) as avg_earnings,
            AVG(view_rate) as avg_view_rate
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sending_time >= ?
        GROUP BY sending_hour
        ORDER BY avg_earnings DESC
        LIMIT 5
    """
    cursor = conn.execute(hours_query, (cid, start_date.isoformat()))
    brief.best_hours = [
        {
            "hour": row["hour"],
            "count": row["count"],
            "avg_earnings": round(row["avg_earnings"] or 0, 2),
            "avg_view_rate": round(row["avg_view_rate"] or 0, 4),
        }
        for row in cursor.fetchall()
    ]

    # Get best days
    days_query = """
        SELECT
            sending_day_of_week as day,
            COUNT(*) as count,
            AVG(earnings) as avg_earnings
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sending_time >= ?
        GROUP BY sending_day_of_week
        ORDER BY avg_earnings DESC
        LIMIT 5
    """
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    cursor = conn.execute(days_query, (cid, start_date.isoformat()))
    brief.best_days = [
        {
            "day": day_names[row["day"]] if row["day"] is not None else "Unknown",
            "day_number": row["day"],
            "count": row["count"],
            "avg_earnings": round(row["avg_earnings"] or 0, 2),
        }
        for row in cursor.fetchall()
    ]

    # Get best content types
    content_query = """
        SELECT
            ct.type_name,
            COUNT(*) as count,
            AVG(mm.earnings) as avg_earnings
        FROM mass_messages mm
        JOIN content_types ct ON mm.content_type_id = ct.content_type_id
        WHERE mm.creator_id = ?
          AND mm.message_type = 'ppv'
          AND mm.sending_time >= ?
        GROUP BY ct.type_name
        ORDER BY avg_earnings DESC
        LIMIT 5
    """
    cursor = conn.execute(content_query, (cid, start_date.isoformat()))
    brief.best_content_types = [
        {
            "type_name": row["type_name"],
            "count": row["count"],
            "avg_earnings": round(row["avg_earnings"] or 0, 2),
        }
        for row in cursor.fetchall()
    ]

    # Get caption pool stats
    caption_query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN freshness_score >= 30 THEN 1 ELSE 0 END) as fresh,
            SUM(CASE WHEN freshness_score < 25 THEN 1 ELSE 0 END) as exhausted,
            AVG(freshness_score) as avg_freshness
        FROM caption_bank
        WHERE is_active = 1
          AND (creator_id = ? OR is_universal = 1)
    """
    cursor = conn.execute(caption_query, (cid,))
    caption_row = cursor.fetchone()
    if caption_row:
        brief.total_captions = caption_row["total"] or 0
        brief.fresh_captions = caption_row["fresh"] or 0
        brief.exhausted_captions = caption_row["exhausted"] or 0
        brief.avg_freshness = caption_row["avg_freshness"] or 0.0

    # Get vault summary
    vault_query = """
        SELECT ct.type_name
        FROM vault_matrix vm
        JOIN content_types ct ON vm.content_type_id = ct.content_type_id
        WHERE vm.creator_id = ?
          AND vm.has_content = 1
        ORDER BY ct.type_name
    """
    cursor = conn.execute(vault_query, (cid,))
    brief.vault_content_types = [row["type_name"] for row in cursor.fetchall()]
    brief.vault_total_types = len(brief.vault_content_types)

    return brief


def format_markdown(brief: CreatorBrief) -> str:
    """Format brief as Markdown."""
    lines = [
        f"# Creator Brief: {brief.display_name}",
        "",
        f"**Analysis Date:** {brief.analysis_date}",
        f"**Period:** Last {brief.analysis_period_days} days",
        "",
        "## Profile",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Page Name | {brief.page_name} |",
        f"| Page Type | {brief.page_type} |",
        f"| Active Fans | {brief.active_fans:,} |",
        f"| Volume Level | **{brief.volume_level}** ({brief.ppv_per_day} PPV/day, {brief.bump_per_day} Bump/day) |",
        f"| Performance Tier | {brief.performance_tier} |",
        f"| OF Ranking | {brief.of_ranking} |",
        "",
        "## Financial Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Earnings | ${brief.total_earnings:,.2f} |",
        f"| Message Revenue | ${brief.message_net:,.2f} |",
        f"| Avg per Fan | ${brief.avg_earnings_per_fan:.2f} |",
        f"| Contribution | {brief.contribution_pct:.2f}% |",
        "",
        "## Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Messages Sent | {brief.total_messages:,} |",
        f"| Avg Earnings/Message | ${brief.avg_earnings_per_message:.2f} |",
        f"| Avg View Rate | {brief.avg_view_rate:.2%} |",
        f"| Avg Purchase Rate | {brief.avg_purchase_rate:.2%} |",
        "",
    ]

    if brief.best_hours:
        lines.append("## Best Performing Hours")
        lines.append("")
        lines.append("| Hour | Count | Avg Earnings | View Rate |")
        lines.append("|------|-------|--------------|-----------|")
        for h in brief.best_hours:
            lines.append(
                f"| {h['hour']:02d}:00 | {h['count']} | ${h['avg_earnings']:.2f} | "
                f"{h['avg_view_rate']:.2%} |"
            )
        lines.append("")

    if brief.best_days:
        lines.append("## Best Performing Days")
        lines.append("")
        lines.append("| Day | Count | Avg Earnings |")
        lines.append("|-----|-------|--------------|")
        for d in brief.best_days:
            lines.append(f"| {d['day']} | {d['count']} | ${d['avg_earnings']:.2f} |")
        lines.append("")

    if brief.best_content_types:
        lines.append("## Top Content Types")
        lines.append("")
        lines.append("| Type | Count | Avg Earnings |")
        lines.append("|------|-------|--------------|")
        for ct in brief.best_content_types:
            lines.append(f"| {ct['type_name']} | {ct['count']} | ${ct['avg_earnings']:.2f} |")
        lines.append("")

    lines.extend(
        [
            "## Caption Pool",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Captions | {brief.total_captions:,} |",
            f"| Fresh (>= 30) | {brief.fresh_captions:,} |",
            f"| Exhausted (< 25) | {brief.exhausted_captions:,} |",
            f"| Avg Freshness | {brief.avg_freshness:.1f} |",
            "",
        ]
    )

    if brief.primary_tone:
        lines.extend(
            [
                "## Persona",
                "",
                "| Attribute | Value |",
                "|-----------|-------|",
                f"| Primary Tone | {brief.primary_tone} |",
                f"| Emoji Frequency | {brief.emoji_frequency} |",
                f"| Slang Level | {brief.slang_level} |",
                "",
            ]
        )

    if brief.vault_content_types:
        lines.extend(
            [
                "## Vault Inventory",
                "",
                f"**Available Content Types ({brief.vault_total_types}):** "
                + ", ".join(brief.vault_content_types),
                "",
            ]
        )

    return "\n".join(lines)


def format_json(brief: CreatorBrief) -> str:
    """Format brief as JSON."""
    return json.dumps(asdict(brief), indent=2)


# =============================================================================
# DYNAMIC AGENCY BENCHMARKS - Compare creator to agency portfolio
# =============================================================================


@dataclass
class AgencyBenchmarks:
    """Dynamic benchmarks calculated from all agency creators."""

    agency_avg_revenue: float
    agency_avg_purchase_rate: float
    agency_avg_view_rate: float
    agency_avg_earnings_per_message: float

    creator_revenue_percentile: int  # 0-100
    creator_purchase_rate_percentile: int
    creator_view_rate_percentile: int
    creator_earnings_percentile: int

    overall_percentile: int  # Combined ranking
    vs_agency_revenue: str  # e.g., "+15% above agency avg"
    performance_tier_label: str  # "Top Performer", "Above Average", "Average", "Below Average"


def calculate_agency_benchmarks(conn: sqlite3.Connection, brief: CreatorBrief) -> AgencyBenchmarks:
    """
    Calculate dynamic benchmarks comparing this creator to the agency portfolio.

    Args:
        conn: Database connection
        brief: The creator's brief with performance data

    Returns:
        AgencyBenchmarks with percentile rankings and comparisons
    """
    # Get agency-wide statistics from all creators
    stats_query = """
        SELECT
            AVG(current_message_net) as avg_revenue,
            AVG(current_total_earnings) as avg_total_earnings
        FROM creators
        WHERE current_active_fans > 0
    """
    cursor = conn.execute(stats_query)
    agency_stats = cursor.fetchone()

    # Get per-message stats from mass_messages for 30-day window
    mm_stats_query = """
        SELECT
            AVG(CAST(earnings AS REAL) / NULLIF(sent_count, 0)) as avg_earnings_per_send,
            AVG(purchase_rate) as avg_purchase_rate,
            AVG(view_rate) as avg_view_rate
        FROM mass_messages
        WHERE message_type = 'ppv'
          AND sending_time >= date('now', '-30 days')
    """
    cursor = conn.execute(mm_stats_query)
    mm_stats = cursor.fetchone()

    agency_avg_revenue = float(agency_stats["avg_revenue"] or 0)
    agency_avg_purchase_rate = float(mm_stats["avg_purchase_rate"] or 0)
    agency_avg_view_rate = float(mm_stats["avg_view_rate"] or 0)
    agency_avg_epm = float(mm_stats["avg_earnings_per_send"] or 0)

    # Calculate percentile rankings for this creator
    # Revenue percentile
    revenue_percentile_query = """
        SELECT COUNT(*) * 100 / (SELECT COUNT(*) FROM creators WHERE current_message_net > 0)
        FROM creators
        WHERE current_message_net <= ?
          AND current_message_net > 0
    """
    cursor = conn.execute(revenue_percentile_query, (brief.message_net,))
    row = cursor.fetchone()
    revenue_percentile = int(row[0] if row and row[0] else 50)

    # Purchase rate percentile (based on creator's average)
    purchase_rate_percentile = _calculate_percentile(
        brief.avg_purchase_rate,
        agency_avg_purchase_rate,
        0.25,  # max expected 25%
    )

    # View rate percentile
    view_rate_percentile = _calculate_percentile(
        brief.avg_view_rate,
        agency_avg_view_rate,
        0.80,  # max expected 80%
    )

    # Earnings per message percentile
    epm_percentile = _calculate_percentile(
        brief.avg_earnings_per_message,
        agency_avg_epm,
        10.0,  # max expected $10
    )

    # Overall percentile (weighted average)
    overall_percentile = int(
        (revenue_percentile * 0.40)
        + (purchase_rate_percentile * 0.25)
        + (view_rate_percentile * 0.20)
        + (epm_percentile * 0.15)
    )

    # Calculate vs agency revenue
    if agency_avg_revenue > 0:
        revenue_diff = ((brief.message_net - agency_avg_revenue) / agency_avg_revenue) * 100
        if revenue_diff > 0:
            vs_agency_revenue = f"+{revenue_diff:.0f}% above agency avg"
        else:
            vs_agency_revenue = f"{revenue_diff:.0f}% below agency avg"
    else:
        vs_agency_revenue = "N/A"

    # Determine performance tier label
    if overall_percentile >= 80:
        performance_tier_label = "Top Performer (Top 20%)"
    elif overall_percentile >= 60:
        performance_tier_label = "Above Average"
    elif overall_percentile >= 40:
        performance_tier_label = "Average"
    elif overall_percentile >= 20:
        performance_tier_label = "Below Average"
    else:
        performance_tier_label = "Needs Attention (Bottom 20%)"

    return AgencyBenchmarks(
        agency_avg_revenue=agency_avg_revenue,
        agency_avg_purchase_rate=agency_avg_purchase_rate,
        agency_avg_view_rate=agency_avg_view_rate,
        agency_avg_earnings_per_message=agency_avg_epm,
        creator_revenue_percentile=revenue_percentile,
        creator_purchase_rate_percentile=purchase_rate_percentile,
        creator_view_rate_percentile=view_rate_percentile,
        creator_earnings_percentile=epm_percentile,
        overall_percentile=overall_percentile,
        vs_agency_revenue=vs_agency_revenue,
        performance_tier_label=performance_tier_label,
    )


def _calculate_percentile(value: float, avg: float, max_expected: float) -> int:
    """
    Calculate a simple percentile based on value vs average.

    This is a simplified percentile that:
    - 50 = at average
    - 100 = at or above max expected
    - 0 = at or below 0
    """
    if value <= 0:
        return 0
    if max_expected <= 0:
        return 50

    # Normalize to 0-100 based on position in expected range
    percentile = int((value / max_expected) * 100)
    return min(100, max(0, percentile))


def prepare_insights_request(
    brief: CreatorBrief, benchmarks: AgencyBenchmarks | None = None
) -> str:
    """
    Generate a structured markdown prompt for Claude to provide strategic insights.

    Args:
        brief: The CreatorBrief containing all performance data
        benchmarks: Optional AgencyBenchmarks for competitive positioning

    Returns:
        A markdown-formatted prompt string for Claude
    """
    # Build the insights request object
    insights = AIInsightsRequest(
        creator_name=brief.page_name,
        display_name=brief.display_name,
        total_revenue_30d=brief.message_net,
        avg_revenue_per_message=brief.avg_earnings_per_message,
        total_messages_30d=brief.total_messages,
        purchase_rate=brief.avg_purchase_rate,
        view_rate=brief.avg_view_rate,
        best_hours=brief.best_hours,
        best_days=brief.best_days,
        best_content_types=brief.best_content_types,
        total_captions=brief.total_captions,
        fresh_captions=brief.fresh_captions,
        exhausted_captions=brief.exhausted_captions,
        avg_freshness=brief.avg_freshness,
        primary_tone=brief.primary_tone,
        emoji_frequency=brief.emoji_frequency,
        slang_level=brief.slang_level,
        volume_level=brief.volume_level,
        ppv_per_day=brief.ppv_per_day,
        vs_agency_avg=benchmarks.vs_agency_revenue if benchmarks else "",
        percentile_rank=f"{benchmarks.overall_percentile}th percentile" if benchmarks else "",
    )

    # Build the prompt
    lines = [
        f"# Strategic Insights Request: {insights.display_name}",
        "",
        "## Performance Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Revenue (30d) | ${insights.total_revenue_30d:,.2f} |",
        f"| Avg Revenue per Message | ${insights.avg_revenue_per_message:.2f} |",
        f"| Messages Sent (30d) | {insights.total_messages_30d:,} |",
        f"| Purchase Rate | {insights.purchase_rate:.2%} |",
        f"| View Rate | {insights.view_rate:.2%} |",
        f"| Volume Level | {insights.volume_level} ({insights.ppv_per_day} PPV/day) |",
        "",
    ]

    # Agency benchmarks section (if available)
    if benchmarks:
        lines.extend(
            [
                "## Agency Competitive Position",
                "",
                "| Metric | Creator | Agency Avg | Percentile |",
                "|--------|---------|------------|------------|",
                f"| Revenue (30d) | ${insights.total_revenue_30d:,.0f} | ${benchmarks.agency_avg_revenue:,.0f} | {benchmarks.creator_revenue_percentile}th |",
                f"| Purchase Rate | {insights.purchase_rate:.1%} | {benchmarks.agency_avg_purchase_rate:.1%} | {benchmarks.creator_purchase_rate_percentile}th |",
                f"| View Rate | {insights.view_rate:.1%} | {benchmarks.agency_avg_view_rate:.1%} | {benchmarks.creator_view_rate_percentile}th |",
                f"| Earnings/Message | ${insights.avg_revenue_per_message:.2f} | ${benchmarks.agency_avg_earnings_per_message:.2f} | {benchmarks.creator_earnings_percentile}th |",
                "",
                f"**Overall Ranking:** {benchmarks.performance_tier_label} ({benchmarks.overall_percentile}th percentile)",
                f"**vs Agency Average:** {benchmarks.vs_agency_revenue}",
                "",
            ]
        )

    # Best performing hours
    if insights.best_hours:
        lines.append("## Best Performing Hours (Top 5)")
        lines.append("")
        for i, h in enumerate(insights.best_hours[:5], 1):
            lines.append(
                f"{i}. **{h['hour']:02d}:00** - ${h['avg_earnings']:.2f} avg, "
                f"{h['avg_view_rate']:.1%} view rate ({h['count']} messages)"
            )
        lines.append("")

    # Best performing days
    if insights.best_days:
        lines.append("## Best Performing Days (Top 5)")
        lines.append("")
        for i, d in enumerate(insights.best_days[:5], 1):
            lines.append(
                f"{i}. **{d['day']}** - ${d['avg_earnings']:.2f} avg ({d['count']} messages)"
            )
        lines.append("")

    # Top content types
    if insights.best_content_types:
        lines.append("## Top Content Types (Top 5)")
        lines.append("")
        for i, ct in enumerate(insights.best_content_types[:5], 1):
            lines.append(
                f"{i}. **{ct['type_name']}** - ${ct['avg_earnings']:.2f} avg ({ct['count']} messages)"
            )
        lines.append("")

    # Caption health
    lines.extend(
        [
            "## Caption Health",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Captions | {insights.total_captions:,} |",
            f"| Fresh (score >= 30) | {insights.fresh_captions:,} |",
            f"| Exhausted (score < 25) | {insights.exhausted_captions:,} |",
            f"| Average Freshness | {insights.avg_freshness:.1f} |",
            "",
        ]
    )

    # Persona profile
    if insights.primary_tone:
        lines.extend(
            [
                "## Persona Profile",
                "",
                f"- **Primary Tone:** {insights.primary_tone}",
                f"- **Emoji Frequency:** {insights.emoji_frequency}",
                f"- **Slang Level:** {insights.slang_level}",
                "",
            ]
        )

    # Analysis task
    lines.extend(
        [
            "---",
            "",
            "## Analysis Task",
            "",
            "Based on the data above, provide strategic insights in the following JSON format:",
            "",
            "```json",
            "{",
            '  "performance_summary": "2-3 sentence overview of this creator\'s performance",',
            '  "key_strength": "What this creator does best based on the data",',
            '  "primary_challenge": "Biggest opportunity for improvement",',
            '  "timing_insight": "Specific timing optimization recommendation",',
            '  "content_insight": "Content strategy recommendation based on top performers",',
            '  "caption_health_insight": "Caption freshness management recommendation",',
            '  "immediate_actions": ["Action 1", "Action 2", "Action 3"],',
            '  "strategic_opportunities": ["Opportunity 1", "Opportunity 2"],',
            '  "risk_factors": ["Issue to watch"]',
            "}",
            "```",
            "",
            "## Guidelines",
            "",
            "- Be SPECIFIC to this creator's data, not generic advice",
            "- Reference actual numbers from the data above",
            "- Prioritize high-impact, actionable recommendations",
            "- Consider industry benchmarks:",
            "  - View rate: 60%+ is good, 70%+ is excellent",
            "  - Purchase rate: 15%+ is good, 20%+ is excellent",
            "  - Revenue per message: $2+ is good, $5+ is excellent",
            "- Focus on what the data reveals, not assumptions",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate creator analytics brief.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_creator.py --creator missalexa
    python analyze_creator.py --creator-id abc123 --period 90
    python analyze_creator.py --creator missalexa --output brief.md --format markdown
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument(
        "--period", "-p", type=int, default=30, help="Analysis period in days (default: 30)"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")
    parser.add_argument(
        "--insights",
        action="store_true",
        help="Output context for Claude AI to generate strategic insights",
    )

    args = parser.parse_args()

    if not args.creator and not args.creator_id:
        parser.error("Must specify --creator or --creator-id")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        brief = generate_brief(
            conn, creator_name=args.creator, creator_id=args.creator_id, period_days=args.period
        )

        if not brief:
            print("Error: Creator not found", file=sys.stderr)
            sys.exit(1)

        # Handle insights request mode
        if args.insights:
            insights_prompt = prepare_insights_request(brief)

            if args.output:
                Path(args.output).write_text(insights_prompt)
                print(f"Insights request written to {args.output}")
            else:
                print(insights_prompt)

            return  # Exit after outputting insights request

        if args.format == "json":
            output = format_json(brief)
        else:
            output = format_markdown(brief)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Brief written to {args.output}")
        else:
            print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
