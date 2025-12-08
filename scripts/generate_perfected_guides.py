#!/usr/bin/env python3
"""
Generate Perfected Volume Guides - v2.0
Creates unique, historically-grounded PPV volume guides for all active creators.

This script analyzes each creator's historical performance data to generate
customized 7-day PPV volume recommendations with:
- Day-of-week performance factors using Bayesian shrinkage
- Page-type specific strategies (free vs paid)
- Content pricing recommendations
- Follow-up/bump message strategies
- Key insights derived from historical data

Usage:
    python generate_perfected_guides.py --all
    python generate_perfected_guides.py --creator missalexa
    python generate_perfected_guides.py --all --dry-run
"""

import sqlite3
import os
import argparse
import random
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# =============================================================================
# CONSTANTS
# =============================================================================

PORTFOLIO_DAY_FACTORS = {
    'Sunday': 0.82,
    'Monday': 0.99,
    'Tuesday': 0.96,
    'Wednesday': 1.10,
    'Thursday': 1.16,
    'Friday': 1.10,
    'Saturday': 0.86
}

# Map SQLite day-of-week (0=Sunday) to day names
DOW_TO_NAME = {
    0: 'Sunday',
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday'
}

FREE_PAGE_STRATEGY = {
    "volume_boost": 1.15,
    "peak_day_max_modifier": 1.5,
    "weekend_min_modifier": 0.7,
    "bump_ratio": 1.0,
    "max_ppv_per_day": 6,
    "fatigue_threshold_weekly": 42
}

PAID_PAGE_STRATEGY = {
    "volume_boost": 1.0,
    "peak_day_max_modifier": 1.3,
    "weekend_min_modifier": 0.5,
    "bump_ratio": 0.5,
    "max_ppv_per_day": 5,
    "fatigue_threshold_weekly": 35
}

PRICING_TIERS = {
    "solo": {"base": (12, 15), "free_adj": 0, "paid_adj": 2},
    "bundle": {"base": (18, 22), "free_adj": 0, "paid_adj": 3},
    "bg_sextape": {"base": (22, 28), "free_adj": 0, "paid_adj": 5},
    "dick_rating": {"base": (15, 25), "free_adj": 0, "paid_adj": 3},
    "custom": {"base": (35, 50), "free_adj": 0, "paid_adj": 8}
}

DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CreatorData:
    """Holds creator profile and metrics."""
    creator_id: str
    page_name: str
    display_name: str
    page_type: str  # 'free' or 'paid'
    fans: int
    total_earnings: float
    performance_tier: int
    avg_conversion: float
    base_volume: int  # 2-5 PPV/day


@dataclass
class DayPerformance:
    """Performance metrics for a specific day of week."""
    day_name: str
    sample_count: int
    avg_earnings: float
    raw_factor: float
    blended_factor: float
    data_quality: str


@dataclass
class TopDay:
    """Represents a top-earning historical day."""
    date: str
    day_of_week: str
    ppvs_sent: int
    revenue: float
    avg_per_ppv: float


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection(db_path: str) -> sqlite3.Connection:
    """
    Connect to EROS database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active database connection.

    Raises:
        FileNotFoundError: If database file doesn't exist.
        sqlite3.Error: If connection fails.
    """
    expanded_path = os.path.expanduser(db_path)
    if not os.path.exists(expanded_path):
        raise FileNotFoundError(f"Database not found: {expanded_path}")

    conn = sqlite3.connect(expanded_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_all_creators(conn: sqlite3.Connection) -> List[CreatorData]:
    """
    Load all active creators with their metrics.

    Args:
        conn: Database connection.

    Returns:
        List of CreatorData objects for all active creators.
    """
    query = """
        SELECT
            creator_id,
            page_name,
            display_name,
            page_type,
            COALESCE(current_active_fans, current_fan_count, 0) as fans,
            COALESCE(current_total_earnings, 0) as total_earnings,
            COALESCE(performance_tier, 3) as performance_tier,
            COALESCE(avg_purchase_rate, 0) as avg_conversion
        FROM creators
        WHERE is_active = 1
        ORDER BY current_total_earnings DESC
    """

    creators = []
    for row in conn.execute(query):
        fans = row['fans'] or 0
        page_type = row['page_type'] or 'free'
        base_volume = calculate_base_volume(fans, page_type)

        creators.append(CreatorData(
            creator_id=row['creator_id'],
            page_name=row['page_name'],
            display_name=row['display_name'] or row['page_name'],
            page_type=page_type,
            fans=fans,
            total_earnings=row['total_earnings'] or 0,
            performance_tier=row['performance_tier'] or 3,
            avg_conversion=row['avg_conversion'] or 0,
            base_volume=base_volume
        ))

    return creators


def load_day_performance(conn: sqlite3.Connection, creator_id: str) -> Dict[str, DayPerformance]:
    """
    Query mass_messages for day-of-week performance metrics.

    Args:
        conn: Database connection.
        creator_id: The creator's unique identifier.

    Returns:
        Dictionary mapping day names to DayPerformance objects.
    """
    query = """
        SELECT
            sending_day_of_week,
            COUNT(*) as sample_count,
            AVG(earnings) as avg_earnings,
            SUM(earnings) as total_earnings
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND earnings > 0
        GROUP BY sending_day_of_week
    """

    results = {}
    rows = list(conn.execute(query, (creator_id,)))

    # Calculate total earnings for this creator to compute raw factors
    total_creator_earnings = sum(row['total_earnings'] for row in rows) if rows else 0
    total_samples = sum(row['sample_count'] for row in rows) if rows else 0

    # Expected earnings if all days were equal
    avg_daily_earnings = total_creator_earnings / 7 if total_creator_earnings > 0 else 0

    for row in rows:
        dow = row['sending_day_of_week']
        day_name = DOW_TO_NAME.get(dow, 'Unknown')
        sample_count = row['sample_count']
        avg_earnings = row['avg_earnings'] or 0
        day_total = row['total_earnings'] or 0

        # Raw factor: how this day compares to the average
        raw_factor = (day_total / avg_daily_earnings) if avg_daily_earnings > 0 else 1.0

        # Determine data quality based on sample count
        if sample_count >= 50:
            data_quality = "High"
        elif sample_count >= 20:
            data_quality = "Medium"
        elif sample_count >= 5:
            data_quality = "Low"
        else:
            data_quality = "Minimal"

        # Blended factor will be calculated later with Bayesian shrinkage
        results[day_name] = DayPerformance(
            day_name=day_name,
            sample_count=sample_count,
            avg_earnings=avg_earnings,
            raw_factor=raw_factor,
            blended_factor=raw_factor,  # Placeholder, updated in calculate_day_factors
            data_quality=data_quality
        )

    # Fill in missing days with portfolio defaults
    for day_name in DAY_ORDER:
        if day_name not in results:
            results[day_name] = DayPerformance(
                day_name=day_name,
                sample_count=0,
                avg_earnings=0,
                raw_factor=PORTFOLIO_DAY_FACTORS[day_name],
                blended_factor=PORTFOLIO_DAY_FACTORS[day_name],
                data_quality="None"
            )

    return results


def load_top_days(conn: sqlite3.Connection, creator_id: str, limit: int = 5) -> List[TopDay]:
    """
    Get top N earning days for a creator.

    Args:
        conn: Database connection.
        creator_id: The creator's unique identifier.
        limit: Number of top days to return.

    Returns:
        List of TopDay objects sorted by revenue descending.
    """
    query = """
        SELECT
            date(sending_time) as day_date,
            sending_day_of_week,
            COUNT(*) as ppvs_sent,
            SUM(earnings) as revenue
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND earnings > 0
        GROUP BY date(sending_time)
        ORDER BY revenue DESC
        LIMIT ?
    """

    top_days = []
    for row in conn.execute(query, (creator_id, limit)):
        dow = row['sending_day_of_week']
        day_name = DOW_TO_NAME.get(dow, 'Unknown')
        ppvs = row['ppvs_sent']
        revenue = row['revenue'] or 0

        top_days.append(TopDay(
            date=row['day_date'],
            day_of_week=day_name,
            ppvs_sent=ppvs,
            revenue=revenue,
            avg_per_ppv=revenue / ppvs if ppvs > 0 else 0
        ))

    return top_days


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def calculate_base_volume(fans: int, page_type: str) -> int:
    """
    Determine base PPV/day from fan count bracket.

    Args:
        fans: Number of active fans.
        page_type: 'free' or 'paid'.

    Returns:
        Base PPV count per day (2-5).

    Volume Tiers:
        PAID: 0-999=2, 1K-5K=3, 5K-15K=4, 15K+=5
        FREE: 0-999=2, 1K-5K=3, 5K-20K=4, 20K+=5
    """
    if page_type == 'paid':
        if fans >= 15000:
            return 5
        elif fans >= 5000:
            return 4
        elif fans >= 1000:
            return 3
        else:
            return 2
    else:  # free
        if fans >= 20000:
            return 5
        elif fans >= 5000:
            return 4
        elif fans >= 1000:
            return 3
        else:
            return 2


def apply_bayesian_shrinkage(creator_factor: float, portfolio_factor: float,
                              sample_count: int, k: int = 20) -> float:
    """
    Blend creator factor with portfolio based on sample size.

    This implements Bayesian shrinkage to handle low-sample creators by
    pulling their factors toward the portfolio average proportionally
    to their data scarcity.

    Args:
        creator_factor: The creator's raw performance factor.
        portfolio_factor: The portfolio-wide baseline factor.
        sample_count: Number of samples for this measurement.
        k: Shrinkage constant (samples needed for 50% weight).

    Returns:
        Blended factor clamped to [0.7, 1.3].
    """
    if sample_count <= 0:
        return portfolio_factor

    weight = sample_count / (sample_count + k)
    blended = (weight * creator_factor) + ((1 - weight) * portfolio_factor)
    return max(0.7, min(1.3, blended))


def calculate_day_factors(day_performance: Dict[str, DayPerformance],
                          total_samples: int) -> Dict[str, float]:
    """
    Calculate final day factors with Bayesian shrinkage.

    Args:
        day_performance: Dictionary of DayPerformance objects.
        total_samples: Total sample count across all days.

    Returns:
        Dictionary mapping day names to factors (0.7-1.3).
    """
    factors = {}

    for day_name in DAY_ORDER:
        perf = day_performance.get(day_name)
        portfolio_factor = PORTFOLIO_DAY_FACTORS[day_name]

        if perf and perf.sample_count > 0:
            blended = apply_bayesian_shrinkage(
                creator_factor=perf.raw_factor,
                portfolio_factor=portfolio_factor,
                sample_count=perf.sample_count
            )
            # Update the performance object with blended factor
            perf.blended_factor = blended
            factors[day_name] = blended
        else:
            factors[day_name] = portfolio_factor

    return factors


def get_page_strategy(page_type: str) -> dict:
    """
    Return appropriate strategy based on page type.

    Args:
        page_type: 'free' or 'paid'.

    Returns:
        Strategy dictionary with volume and constraint parameters.
    """
    if page_type == 'free':
        return FREE_PAGE_STRATEGY.copy()
    return PAID_PAGE_STRATEGY.copy()


def calculate_daily_volumes(base_volume: int, day_factors: Dict[str, float],
                           strategy: dict) -> Dict[str, int]:
    """
    Apply factors and constraints to get final daily PPV counts.

    Args:
        base_volume: Base PPV/day for this creator.
        day_factors: Dictionary of day factors.
        strategy: Page strategy dictionary.

    Returns:
        Dictionary mapping day names to final PPV counts.
    """
    volumes = {}
    max_ppv = strategy['max_ppv_per_day']
    volume_boost = strategy['volume_boost']
    min_ppv = 2  # Hard floor - never less than 2 PPV/day

    for day_name in DAY_ORDER:
        factor = day_factors.get(day_name, 1.0)

        # Apply factor and boost
        raw_volume = base_volume * factor * volume_boost

        # STRICT CLAMPING: min 2, max per strategy (5 paid, 6 free)
        final_volume = max(min_ppv, min(max_ppv, round(raw_volume)))
        volumes[day_name] = final_volume

    # Weekly cap check - if over fatigue threshold, scale down proportionally
    weekly_total = sum(volumes.values())
    fatigue_threshold = strategy['fatigue_threshold_weekly']

    if weekly_total > fatigue_threshold:
        scale_factor = fatigue_threshold / weekly_total
        for day_name in DAY_ORDER:
            scaled = volumes[day_name] * scale_factor
            volumes[day_name] = max(min_ppv, min(max_ppv, round(scaled)))

    return volumes


def inject_authentic_variation(volumes: Dict[str, int],
                               day_factors: Dict[str, float],
                               seed: int,
                               max_ppv: int = 6) -> Dict[str, int]:
    """
    Add controlled randomness for natural variation.

    This prevents guides from looking too formulaic while preserving
    the strategic intent based on performance data.

    Rules:
    1. Sort days by factor (performance)
    2. Protect top 2 and bottom 2 days
    3. Randomly swap 2 middle days
    4. Add +/-1 to 2 random non-protected days

    Args:
        volumes: Initial volume calculations.
        day_factors: Day performance factors for ranking.
        seed: Random seed for reproducibility.
        max_ppv: Maximum PPV per day (5 for paid, 6 for free).

    Returns:
        Modified volume dictionary with authentic variation.
    """
    # Use creator-specific seed for reproducibility
    rng = random.Random(seed)

    # Sort days by factor to identify protected days
    sorted_days = sorted(DAY_ORDER, key=lambda d: day_factors.get(d, 1.0), reverse=True)

    # Protect top 2 (best performers) and bottom 2 (recovery days)
    protected = set(sorted_days[:2] + sorted_days[-2:])
    middle_days = [d for d in sorted_days if d not in protected]

    # Create mutable copy
    varied = volumes.copy()

    # Randomly swap 2 middle days (if we have enough)
    if len(middle_days) >= 2:
        swap_candidates = rng.sample(middle_days, 2)
        v1, v2 = varied[swap_candidates[0]], varied[swap_candidates[1]]
        varied[swap_candidates[0]] = v2
        varied[swap_candidates[1]] = v1

    # Add +/-1 to 2 random non-protected days
    adjustable_days = [d for d in DAY_ORDER if d not in protected]
    if adjustable_days:
        adjust_count = min(2, len(adjustable_days))
        adjust_days = rng.sample(adjustable_days, adjust_count)

        for day in adjust_days:
            current = varied[day]
            adjustment = rng.choice([-1, 1])
            # STRICT bounds: min 2, max per page type (passed as param)
            new_value = max(2, min(max_ppv, current + adjustment))
            varied[day] = new_value

    return varied


def generate_rationale(day: str, factor: float, avg_earnings: float,
                       sample_count: int) -> str:
    """
    Generate human-readable rationale for each day's volume.

    Args:
        day: Day name.
        factor: Performance factor for this day.
        avg_earnings: Average earnings per PPV on this day.
        sample_count: Historical sample count.

    Returns:
        Rationale string explaining the recommendation.
    """
    if sample_count == 0:
        return f"Portfolio baseline ({PORTFOLIO_DAY_FACTORS[day]:.2f}x typical)"

    if factor >= 1.15:
        strength = "Peak performer"
        action = "maximize volume"
    elif factor >= 1.05:
        strength = "Above average"
        action = "strong push day"
    elif factor >= 0.95:
        strength = "Average performer"
        action = "steady engagement"
    elif factor >= 0.85:
        strength = "Below average"
        action = "moderate volume"
    else:
        strength = "Recovery day"
        action = "conserve for peaks"

    if avg_earnings > 0:
        return f"{strength} (${avg_earnings:.0f} avg/PPV) - {action}"
    return f"{strength} based on {sample_count} samples - {action}"


def calculate_pricing(page_type: str) -> Dict[str, Tuple[int, int]]:
    """
    Calculate content type pricing with page-type adjustment.

    Args:
        page_type: 'free' or 'paid'.

    Returns:
        Dictionary mapping content types to (min, max) price tuples.
    """
    pricing = {}
    adj_key = 'paid_adj' if page_type == 'paid' else 'free_adj'

    for content_type, tier in PRICING_TIERS.items():
        base_min, base_max = tier['base']
        adjustment = tier[adj_key]
        pricing[content_type] = (base_min + adjustment, base_max + adjustment)

    return pricing


def generate_insights(creator: CreatorData, day_factors: Dict[str, float],
                     top_days: List[TopDay], day_performance: Dict[str, DayPerformance]) -> List[str]:
    """
    Generate creator-specific key insights.

    Args:
        creator: Creator data object.
        day_factors: Day performance factors.
        top_days: List of top earning days.
        day_performance: Day performance metrics.

    Returns:
        List of insight strings.
    """
    insights = []

    # Best and worst days
    sorted_days = sorted(DAY_ORDER, key=lambda d: day_factors.get(d, 1.0), reverse=True)
    best_day = sorted_days[0]
    worst_day = sorted_days[-1]

    best_factor = day_factors.get(best_day, 1.0)
    worst_factor = day_factors.get(worst_day, 1.0)

    insights.append(
        f"**Peak Day:** {best_day} ({best_factor:.2f}x) - Maximize volume and premium content"
    )
    insights.append(
        f"**Recovery Day:** {worst_day} ({worst_factor:.2f}x) - Use for maintenance and lower-tier content"
    )

    # Page type strategy
    if creator.page_type == 'free':
        insights.append(
            "**Free Page Advantage:** Higher volume tolerance - push 15% more PPVs during peaks"
        )
    else:
        insights.append(
            "**Paid Page Strategy:** Quality over quantity - focus on premium content and fewer bumps"
        )

    # Volume tier insight
    volume_labels = {2: "Conservative", 3: "Moderate", 4: "Active", 5: "High Volume"}
    label = volume_labels.get(creator.base_volume, "Standard")
    insights.append(
        f"**Volume Tier:** {label} ({creator.base_volume} base PPV/day) based on {creator.fans:,} fans"
    )

    # Top day pattern (if available)
    if top_days:
        dow_counts: Dict[str, int] = {}
        for td in top_days:
            dow_counts[td.day_of_week] = dow_counts.get(td.day_of_week, 0) + 1

        if dow_counts:
            top_dow = max(dow_counts.items(), key=lambda x: x[1])
            if top_dow[1] >= 2:
                insights.append(
                    f"**Historical Pattern:** {top_dow[0]} appears in {top_dow[1]} of top 5 earning days"
                )

    # Sample quality insight
    total_samples = sum(p.sample_count for p in day_performance.values())
    if total_samples >= 100:
        insights.append(
            f"**Data Confidence:** High ({total_samples:,} historical PPVs analyzed)"
        )
    elif total_samples >= 30:
        insights.append(
            f"**Data Confidence:** Medium ({total_samples:,} historical PPVs) - factors balanced with portfolio trends"
        )
    else:
        insights.append(
            f"**Data Confidence:** Low ({total_samples:,} historical PPVs) - using portfolio baselines"
        )

    return insights


# =============================================================================
# GUIDE GENERATION
# =============================================================================

def generate_guide_markdown(creator: CreatorData,
                           daily_volumes: Dict[str, int],
                           day_factors: Dict[str, float],
                           day_performance: Dict[str, DayPerformance],
                           top_days: List[TopDay],
                           strategy: dict) -> str:
    """
    Render complete markdown guide for a creator.

    Args:
        creator: Creator data object.
        daily_volumes: Final daily PPV volumes.
        day_factors: Day performance factors.
        day_performance: Day performance details.
        top_days: Top earning historical days.
        strategy: Page strategy dictionary.

    Returns:
        Complete markdown guide as string.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Calculate totals
    weekly_total = sum(daily_volumes.values())
    total_samples = sum(p.sample_count for p in day_performance.values())

    # Volume tier label
    volume_labels = {2: "Low", 3: "Mid", 4: "High", 5: "Ultra"}
    volume_tier = volume_labels.get(creator.base_volume, "Standard")

    # Best and worst days
    sorted_days = sorted(DAY_ORDER, key=lambda d: day_factors.get(d, 1.0), reverse=True)
    best_days = ", ".join(sorted_days[:2])
    recovery_days = ", ".join(sorted_days[-2:])

    # Best day earnings
    best_day = sorted_days[0]
    best_perf = day_performance.get(best_day)
    best_avg = best_perf.avg_earnings if best_perf else 0

    worst_day = sorted_days[-1]

    # Projected revenue (simple estimate based on average per PPV)
    avg_per_ppv = 0
    if total_samples > 0:
        total_earnings = sum(p.avg_earnings * p.sample_count for p in day_performance.values())
        avg_per_ppv = total_earnings / total_samples if total_samples > 0 else 25
    else:
        avg_per_ppv = 25  # Default estimate

    projected_weekly = weekly_total * avg_per_ppv

    # Generate pricing
    pricing = calculate_pricing(creator.page_type)

    # Generate insights
    insights = generate_insights(creator, day_factors, top_days, day_performance)
    insights_bullets = "\n".join(f"- {i}" for i in insights)

    # Build daily table
    daily_rows = []
    for day in DAY_ORDER:
        vol = daily_volumes[day]
        factor = day_factors.get(day, 1.0)
        perf = day_performance.get(day)
        avg_earn = perf.avg_earnings if perf else 0
        samples = perf.sample_count if perf else 0
        rationale = generate_rationale(day, factor, avg_earn, samples)
        daily_rows.append(f"| {day} | {vol} | {factor:.2f}x | {rationale} |")

    daily_table = "\n".join(daily_rows)

    # Build top days table
    if top_days:
        top_days_rows = []
        for td in top_days:
            top_days_rows.append(
                f"| {td.date} | {td.day_of_week} | {td.ppvs_sent} | ${td.revenue:,.0f} | ${td.avg_per_ppv:.0f} |"
            )
        top_days_table = "\n".join(top_days_rows)
    else:
        top_days_table = "| No historical data available | - | - | - | - |"

    # Build pricing table
    pricing_rows = []
    content_display_names = {
        "solo": "Solo/Selfie",
        "bundle": "Bundle (3-5)",
        "bg_sextape": "B/G Sextape",
        "dick_rating": "Dick Rating",
        "custom": "Custom/Interactive"
    }
    for content_type, (min_p, max_p) in pricing.items():
        display_name = content_display_names.get(content_type, content_type.title())
        base_min, base_max = PRICING_TIERS[content_type]['base']
        adj = min_p - base_min
        adj_str = f"+${adj}" if adj > 0 else "None"
        pricing_rows.append(
            f"| {display_name} | ${base_min}-${base_max} | {adj_str} | ${min_p}-${max_p} |"
        )
    pricing_table = "\n".join(pricing_rows)

    # Calculate bumps per day
    avg_volume = weekly_total / 7
    bumps_per_day = round(avg_volume * strategy['bump_ratio'])
    bumps_per_day = max(1, bumps_per_day)

    # Page type display
    page_display = "Free Page" if creator.page_type == 'free' else "Paid Page"

    guide = f"""# {creator.display_name} - 7-Day PPV Volume Guide
## {page_display} | Generated: {now}

---

## Creator Profile

| Metric | Value |
|--------|-------|
| Active Fans | {creator.fans:,} |
| Page Type | {page_display} |
| Performance Tier | Tier {creator.performance_tier} |
| Total Revenue | ${creator.total_earnings:,.0f} |
| Avg Conversion | {creator.avg_conversion:.2f}% |
| Volume Tier | {volume_tier} ({creator.base_volume}/day base) |

---

## Weekly Overview

| Stat | Value |
|------|-------|
| Total Weekly PPVs | {weekly_total} |
| Projected Revenue | ${projected_weekly:,.0f} |
| Best Days | {best_days} |
| Recovery Days | {recovery_days} |

---

## Daily PPV Targets

| Day | PPVs | Factor | Rationale |
|-----|------|--------|-----------|
{daily_table}

**Historical Basis:** Based on {total_samples:,} PPVs showing {best_day} as peak earner (${best_avg:.0f} avg/PPV) and {worst_day} as recovery opportunity.

---

## Pricing by Content Type

| Content Type | Base | Adjustment | Recommended |
|--------------|------|------------|-------------|
{pricing_table}

---

## Follow-Up Strategy

| Metric | Value |
|--------|-------|
| Bumps per Day | {bumps_per_day} |
| Bump Delay | 15-35 min |
| Best Bump Times | After highest-performing PPVs |

---

## Top 5 Historical Earning Days

| Date | Day | PPVs | Revenue | $/PPV |
|------|-----|------|---------|-------|
{top_days_table}

---

## Key Insights

{insights_bullets}

---

*Generated by EROS Perfected Volume Guide v2.0*
*Based on {total_samples:,} historical PPVs*
"""

    return guide


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point for generating perfected volume guides."""
    parser = argparse.ArgumentParser(
        description="Generate Perfected Volume Guides for EROS creators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_perfected_guides.py --all              # Generate for all creators
  python generate_perfected_guides.py --creator missalexa  # Single creator
  python generate_perfected_guides.py --all --dry-run    # Preview mode
        """
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate guides for all active creators"
    )
    parser.add_argument(
        "--creator",
        type=str,
        help="Generate guide for a specific creator (by page_name)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview output without writing files"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=os.path.expanduser("~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"),
        help="Path to EROS database"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.expanduser("~/Developer/EROS-SD-MAIN-PROJECT/output/creator-volume-guides/volume-guides"),
        help="Output directory for guides"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for variation (default: 42)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.creator:
        parser.error("Must specify --all or --creator")

    # Set random seed for reproducibility
    random.seed(args.seed)

    try:
        conn = get_db_connection(args.db)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return 1

    print(f"Connected to database: {args.db}")

    # Load creators
    creators = load_all_creators(conn)
    print(f"Loaded {len(creators)} active creators")

    # Filter to specific creator if requested
    if args.creator:
        creators = [c for c in creators if c.page_name.lower() == args.creator.lower()]
        if not creators:
            print(f"Error: Creator '{args.creator}' not found or not active")
            conn.close()
            return 1

    # Setup output directory
    output_dir = Path(args.output)
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {output_dir}")

    # Generate guides
    generated = 0
    errors = 0

    print("\n" + "=" * 60)
    print("GENERATING VOLUME GUIDES")
    print("=" * 60 + "\n")

    for creator in creators:
        try:
            # Load historical data
            day_perf = load_day_performance(conn, creator.creator_id)
            top_days = load_top_days(conn, creator.creator_id)

            # Calculate factors
            total_samples = sum(d.sample_count for d in day_perf.values())
            day_factors = calculate_day_factors(day_perf, total_samples)

            # Get strategy and calculate volumes
            strategy = get_page_strategy(creator.page_type)
            daily_volumes = calculate_daily_volumes(creator.base_volume, day_factors, strategy)

            # Inject variation (using creator-specific seed)
            daily_volumes = inject_authentic_variation(
                daily_volumes,
                day_factors,
                seed=hash(creator.page_name) % (2**31),
                max_ppv=strategy['max_ppv_per_day']
            )

            # Generate markdown
            guide = generate_guide_markdown(
                creator,
                daily_volumes,
                day_factors,
                day_perf,
                top_days,
                strategy
            )

            weekly_total = sum(daily_volumes.values())

            if args.dry_run:
                print(f"[DRY-RUN] {creator.page_name}")
                print(f"  Page Type: {creator.page_type}")
                print(f"  Fans: {creator.fans:,}")
                print(f"  Base Volume: {creator.base_volume} PPV/day")
                print(f"  Weekly PPVs: {weekly_total}")
                print(f"  Daily: {daily_volumes}")
                print(f"  Samples: {total_samples:,}")
                print()
            else:
                output_path = output_dir / f"{creator.page_name}_volume_guide.md"
                output_path.write_text(guide)
                print(f"Generated: {creator.page_name} ({weekly_total} weekly PPVs, {total_samples:,} samples)")

            generated += 1

        except Exception as e:
            print(f"Error generating guide for {creator.page_name}: {e}")
            errors += 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total guides generated: {generated}")
    if errors:
        print(f"Errors encountered: {errors}")
    if not args.dry_run:
        print(f"Output location: {output_dir}")

    conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
