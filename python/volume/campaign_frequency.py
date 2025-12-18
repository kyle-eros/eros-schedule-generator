"""
Campaign frequency enforcement for optimal scheduling.

This module validates campaign types are scheduled at optimal frequencies to
maximize revenue. Based on reference analysis:
- Only 5 campaigns in 30 days = UNDERPERFORMING
- Recommendation: 10-15 descriptive + 4-5 games = 14-20/month
- Current system: ~5-10/month (180-300% BELOW optimal)

The module enforces spacing rules and provides recommendations for improving
campaign frequency to meet performance targets.

Usage:
    from python.volume.campaign_frequency import (
        validate_campaign_frequency,
        CAMPAIGN_FREQUENCY_RULES,
    )

    schedule = [
        {'campaign_type': 'descriptive_wall_campaign', 'scheduled_time': datetime(2025, 1, 15, 14, 0)},
        {'campaign_type': 'spin_the_wheel_game', 'scheduled_time': datetime(2025, 1, 20, 14, 0)},
    ]
    result = validate_campaign_frequency(schedule)
    if not result['is_valid']:
        for warning in result['warnings']:
            print(f"[{warning['severity']}] {warning['message']}")
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# =============================================================================
# Campaign Frequency Configuration
# =============================================================================

# Target monthly campaign count based on reference analysis
# Reference: 14-20 campaigns/month optimal (10-15 descriptive + 4-5 games)
MINIMUM_MONTHLY_CAMPAIGNS: int = 14
OPTIMAL_MONTHLY_CAMPAIGNS: int = 20
CRITICALLY_LOW_THRESHOLD: int = 5

# Campaign frequency rules derived from performance analysis
CAMPAIGN_FREQUENCY_RULES: dict[str, dict[str, Any]] = {
    'descriptive_wall_campaign': {
        'min_days_between': 2,
        'max_days_between': 3,
        'monthly_target': (10, 15),
        'rationale': 'Top converters (8 of top 10 in 365-day analysis)',
    },
    'spin_the_wheel_game': {
        'frequency': 'weekly',
        'min_days_between': 7,
        'max_days_between': 7,
        'monthly_target': (4, 5),
        'rationale': 'High single performance ($5,178 reference), weekly cadence',
    },
    'bundle_wall_campaign': {
        'min_days_between': 5,
        'max_days_between': 7,
        'monthly_target': (4, 6),
        'rationale': 'Value-focused, needs spacing for scarcity',
    },
    'game_other': {
        'min_days_between': 7,
        'max_days_between': 14,
        'monthly_target': (2, 4),
        'rationale': 'Lower-performing game types',
    },
}


# =============================================================================
# Type Aliases for Clarity
# =============================================================================

WarningDict = dict[str, Any]
RecommendationDict = dict[str, Any]
ValidationResult = dict[str, Any]


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_campaign_dates(
    schedule: list[dict[str, Any]],
) -> dict[str, list[datetime]]:
    """Extract campaign dates grouped by campaign type.

    Args:
        schedule: List of schedule items with campaign_type and scheduled_time.

    Returns:
        Dictionary mapping campaign_type to sorted list of scheduled datetimes.
    """
    campaign_dates: dict[str, list[datetime]] = {}

    for item in schedule:
        campaign_type = item.get('campaign_type')
        scheduled_time = item.get('scheduled_time')

        if not campaign_type:
            continue

        # Handle None or missing scheduled_time
        if scheduled_time is None:
            continue

        # Convert string to datetime if needed
        if isinstance(scheduled_time, str):
            try:
                scheduled_time = datetime.fromisoformat(scheduled_time)
            except ValueError:
                continue

        if not isinstance(scheduled_time, datetime):
            continue

        if campaign_type not in campaign_dates:
            campaign_dates[campaign_type] = []
        campaign_dates[campaign_type].append(scheduled_time)

    # Sort dates for each campaign type
    for campaign_type in campaign_dates:
        campaign_dates[campaign_type].sort()

    return campaign_dates


def _calculate_schedule_days(campaign_dates: dict[str, list[datetime]]) -> int:
    """Calculate the number of days covered by the schedule.

    Args:
        campaign_dates: Dictionary of campaign types to their scheduled dates.

    Returns:
        Number of days from earliest to latest scheduled item (minimum 1).
    """
    if not campaign_dates:
        return 0

    all_dates: list[datetime] = []
    for dates in campaign_dates.values():
        all_dates.extend(dates)

    if not all_dates:
        return 0

    min_date = min(all_dates).date()
    max_date = max(all_dates).date()

    # Add 1 because both endpoints are included
    return (max_date - min_date).days + 1


def _check_spacing_violations(
    dates: list[datetime],
    campaign_type: str,
    rules: dict[str, Any],
) -> list[WarningDict]:
    """Check for spacing violations between consecutive campaign dates.

    Args:
        dates: Sorted list of scheduled datetimes for a campaign type.
        campaign_type: The campaign type being validated.
        rules: Frequency rules for this campaign type.

    Returns:
        List of warning dictionaries for any violations found.
    """
    warnings: list[WarningDict] = []
    min_days = rules.get('min_days_between', 1)
    max_days = rules.get('max_days_between', 14)

    for i in range(len(dates) - 1):
        current = dates[i]
        next_date = dates[i + 1]

        # Calculate days between (using date to ignore time component)
        days_between = (next_date.date() - current.date()).days

        # Same-day scheduling is a critical violation
        if days_between == 0:
            warnings.append({
                'type': campaign_type,
                'message': (
                    f"Same-day scheduling detected for {campaign_type}: "
                    f"{current.strftime('%Y-%m-%d')} has multiple entries"
                ),
                'severity': 'critical',
                'rationale': 'Same-day campaigns reduce scarcity impact and fatigue audience',
            })
        elif days_between < min_days:
            warnings.append({
                'type': campaign_type,
                'message': (
                    f"{campaign_type} spacing too tight: {days_between} days between "
                    f"{current.strftime('%Y-%m-%d')} and {next_date.strftime('%Y-%m-%d')} "
                    f"(minimum: {min_days} days)"
                ),
                'severity': 'high',
                'rationale': rules.get('rationale', 'Insufficient spacing reduces effectiveness'),
            })
        elif days_between > max_days:
            warnings.append({
                'type': campaign_type,
                'message': (
                    f"{campaign_type} gap exceeds maximum: {days_between} days between "
                    f"{current.strftime('%Y-%m-%d')} and {next_date.strftime('%Y-%m-%d')} "
                    f"(maximum: {max_days} days)"
                ),
                'severity': 'medium',
                'rationale': f"Opportunity loss: {rules.get('rationale', 'Missing revenue potential')}",
            })

    return warnings


def _calculate_monthly_projection(
    count: int,
    schedule_days: int,
) -> float:
    """Project monthly count based on schedule coverage.

    Args:
        count: Number of campaigns in the schedule.
        schedule_days: Number of days the schedule covers.

    Returns:
        Projected monthly (30-day) count, or 0 if no schedule days.
    """
    if schedule_days <= 0:
        return 0.0

    daily_rate = count / schedule_days
    return daily_rate * 30


def _check_monthly_target(
    campaign_type: str,
    count: int,
    schedule_days: int,
    rules: dict[str, Any],
) -> tuple[Optional[WarningDict], float]:
    """Check if campaign type meets monthly target.

    Args:
        campaign_type: The campaign type being validated.
        count: Number of campaigns of this type in schedule.
        schedule_days: Number of days the schedule covers.
        rules: Frequency rules for this campaign type.

    Returns:
        Tuple of (warning dict or None, monthly projection).
    """
    monthly_projection = _calculate_monthly_projection(count, schedule_days)
    min_target, max_target = rules.get('monthly_target', (0, 100))

    if monthly_projection < min_target:
        return (
            {
                'type': campaign_type,
                'message': (
                    f"{campaign_type} under-scheduled: projected {monthly_projection:.1f}/month "
                    f"(target: {min_target}-{max_target}/month)"
                ),
                'severity': 'high',
                'rationale': rules.get('rationale', 'Below optimal frequency'),
            },
            monthly_projection,
        )

    return None, monthly_projection


# =============================================================================
# Main Validation Function
# =============================================================================

def validate_campaign_frequency(
    schedule: list[dict[str, Any]],
    lookback_days: int = 30,
) -> ValidationResult:
    """Validate campaign types are scheduled at optimal frequencies.

    Analyzes the schedule to ensure campaign spacing rules are followed
    and monthly targets are met. The target is 14-20 campaigns/month
    (vs current ~5/month baseline).

    Args:
        schedule: List of schedule items, each containing:
            - 'campaign_type': str - The campaign type identifier
            - 'scheduled_time': datetime or str - When the campaign is scheduled
        lookback_days: Number of days to consider for monthly projections.
            Defaults to 30. Note: actual schedule_days is calculated dynamically
            from the schedule data.

    Returns:
        Dictionary with validation result:
            - 'is_valid': bool - Whether all frequency requirements are met
            - 'warnings': list[WarningDict] - List of warning dictionaries
            - 'recommendations': list[RecommendationDict] - List of recommendations
            - 'total_monthly_projection': float - Projected total campaigns/month
            - 'schedule_days': int - Number of days the schedule spans
            - 'campaign_counts': dict[str, int] - Count per campaign type
            - 'campaign_projections': dict[str, float] - Monthly projection per type

    Warning severity levels:
        - 'critical': Same-day scheduling, total volume critically low
        - 'high': Below minimum spacing, under-scheduled vs target
        - 'medium': Gap exceeds maximum (opportunity loss)

    Example:
        >>> schedule = [
        ...     {'campaign_type': 'descriptive_wall_campaign',
        ...      'scheduled_time': datetime(2025, 1, 15, 14, 0)},
        ...     {'campaign_type': 'descriptive_wall_campaign',
        ...      'scheduled_time': datetime(2025, 1, 17, 14, 0)},
        ...     {'campaign_type': 'spin_the_wheel_game',
        ...      'scheduled_time': datetime(2025, 1, 20, 14, 0)},
        ... ]
        >>> result = validate_campaign_frequency(schedule)
        >>> result['is_valid']
        False
        >>> len(result['warnings']) > 0
        True
    """
    warnings: list[WarningDict] = []
    recommendations: list[RecommendationDict] = []

    # Handle empty schedule gracefully
    if not schedule:
        return {
            'is_valid': False,
            'warnings': [{
                'type': 'schedule',
                'message': 'Empty schedule provided - no campaigns to validate',
                'severity': 'critical',
            }],
            'recommendations': [{
                'type': 'schedule',
                'message': 'Add campaigns to the schedule',
                'rationale': 'A valid schedule requires campaign entries',
            }],
            'total_monthly_projection': 0.0,
            'schedule_days': 0,
            'campaign_counts': {},
            'campaign_projections': {},
        }

    # Extract campaign dates by type
    campaign_dates = _extract_campaign_dates(schedule)

    # Handle schedule with no valid campaign data
    if not campaign_dates:
        return {
            'is_valid': False,
            'warnings': [{
                'type': 'schedule',
                'message': 'No valid campaign entries found (missing campaign_type or scheduled_time)',
                'severity': 'critical',
            }],
            'recommendations': [{
                'type': 'schedule',
                'message': 'Ensure all schedule items have campaign_type and scheduled_time',
                'rationale': 'Valid scheduling requires both campaign type and timing',
            }],
            'total_monthly_projection': 0.0,
            'schedule_days': 0,
            'campaign_counts': {},
            'campaign_projections': {},
        }

    # Calculate schedule span dynamically
    schedule_days = _calculate_schedule_days(campaign_dates)

    # Track counts and projections
    campaign_counts: dict[str, int] = {}
    campaign_projections: dict[str, float] = {}
    total_campaign_count = 0

    # Validate each campaign type in rules
    for campaign_type, rules in CAMPAIGN_FREQUENCY_RULES.items():
        dates = campaign_dates.get(campaign_type, [])
        count = len(dates)
        campaign_counts[campaign_type] = count
        total_campaign_count += count

        # Check if this campaign type is missing entirely
        if count == 0:
            recommendations.append({
                'type': campaign_type,
                'message': f"Add {campaign_type} campaigns (target: {rules['monthly_target'][0]}-{rules['monthly_target'][1]}/month)",
                'rationale': rules.get('rationale', 'Missing high-value campaign type'),
            })
            campaign_projections[campaign_type] = 0.0
            continue

        # Check spacing violations between consecutive dates
        spacing_warnings = _check_spacing_violations(dates, campaign_type, rules)
        warnings.extend(spacing_warnings)

        # Check monthly target
        target_warning, projection = _check_monthly_target(
            campaign_type, count, schedule_days, rules
        )
        campaign_projections[campaign_type] = projection
        if target_warning:
            warnings.append(target_warning)

    # Add counts for campaign types not in rules
    for campaign_type, dates in campaign_dates.items():
        if campaign_type not in CAMPAIGN_FREQUENCY_RULES:
            count = len(dates)
            campaign_counts[campaign_type] = count
            total_campaign_count += count
            campaign_projections[campaign_type] = _calculate_monthly_projection(
                count, schedule_days
            )

    # Calculate total monthly projection
    total_monthly_projection = _calculate_monthly_projection(
        total_campaign_count, schedule_days
    )

    # Check overall campaign frequency
    if total_monthly_projection < CRITICALLY_LOW_THRESHOLD:
        warnings.append({
            'type': 'total_frequency',
            'message': (
                f"Campaign frequency critically low: {total_monthly_projection:.1f}/month "
                f"(minimum: {MINIMUM_MONTHLY_CAMPAIGNS}, optimal: {OPTIMAL_MONTHLY_CAMPAIGNS})"
            ),
            'severity': 'critical',
            'rationale': (
                'Reference analysis shows 5 campaigns/month = UNDERPERFORMING. '
                'Target 14-20 campaigns/month for optimal revenue.'
            ),
        })
    elif total_monthly_projection < MINIMUM_MONTHLY_CAMPAIGNS:
        warnings.append({
            'type': 'total_frequency',
            'message': (
                f"Campaign frequency below target: {total_monthly_projection:.1f}/month "
                f"(minimum: {MINIMUM_MONTHLY_CAMPAIGNS}, optimal: {OPTIMAL_MONTHLY_CAMPAIGNS})"
            ),
            'severity': 'high',
            'rationale': (
                'Current system operates at 180-300% BELOW optimal. '
                'Increase campaign frequency to maximize revenue.'
            ),
        })

    # Determine overall validity (no critical or high severity warnings)
    critical_or_high = [w for w in warnings if w['severity'] in ('critical', 'high')]
    is_valid = len(critical_or_high) == 0

    return {
        'is_valid': is_valid,
        'warnings': warnings,
        'recommendations': recommendations,
        'total_monthly_projection': total_monthly_projection,
        'schedule_days': schedule_days,
        'campaign_counts': campaign_counts,
        'campaign_projections': campaign_projections,
    }


# =============================================================================
# Convenience Functions
# =============================================================================

def get_frequency_rules() -> dict[str, dict[str, Any]]:
    """Get the campaign frequency rules dictionary.

    Returns:
        Copy of CAMPAIGN_FREQUENCY_RULES to prevent modification.
    """
    return CAMPAIGN_FREQUENCY_RULES.copy()


def get_campaign_types() -> list[str]:
    """Get list of campaign types with defined frequency rules.

    Returns:
        List of campaign type names.
    """
    return list(CAMPAIGN_FREQUENCY_RULES.keys())


def get_monthly_targets() -> dict[str, tuple[int, int]]:
    """Get monthly target ranges for each campaign type.

    Returns:
        Dictionary mapping campaign type to (min, max) monthly targets.
    """
    return {
        campaign_type: rules['monthly_target']
        for campaign_type, rules in CAMPAIGN_FREQUENCY_RULES.items()
    }


__all__ = [
    # Constants
    'CAMPAIGN_FREQUENCY_RULES',
    'MINIMUM_MONTHLY_CAMPAIGNS',
    'OPTIMAL_MONTHLY_CAMPAIGNS',
    'CRITICALLY_LOW_THRESHOLD',
    # Main validation function
    'validate_campaign_frequency',
    # Convenience functions
    'get_frequency_rules',
    'get_campaign_types',
    'get_monthly_targets',
]
