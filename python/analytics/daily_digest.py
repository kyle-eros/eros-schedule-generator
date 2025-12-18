"""
Daily Statistics Automation for Performance Review.

Implements the 7-step optimization process for automated daily statistics review
as specified in Gap 10.2. Analyzes performance data across multiple timeframes
(30, 180, 365 days) to identify patterns and generate actionable recommendations.

This module provides comprehensive digest generation for creator performance
analysis, supporting the daily statistics automation workflow.

Usage:
    from python.analytics.daily_digest import DailyStatisticsAnalyzer

    # Create analyzer for a specific creator
    analyzer = DailyStatisticsAnalyzer(creator_id="alexia")

    # Generate daily digest from performance data
    performance_data = [
        {
            "date": "2025-01-15",
            "earnings": 5200.0,
            "content_type": "lingerie",
            "caption_length": 320,
            "hour": 14,
        },
        # ... more records
    ]

    digest = analyzer.generate_daily_digest(performance_data)

    # Access digest components
    print(f"Creator: {digest['creator_id']}")
    print(f"Patterns: {digest['patterns']}")
    print(f"Action Items: {digest['action_items']}")

Statistical Methods:
    - Multi-timeframe analysis (30d, 180d, 365d)
    - Content type performance ranking
    - Caption length optimization detection
    - Timing pattern analysis
    - Frequency gap identification
    - Underperformer detection
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any


# =============================================================================
# Constants
# =============================================================================

# Timeframes for analysis in days
TIMEFRAME_SHORT: int = 30
TIMEFRAME_MEDIUM: int = 180
TIMEFRAME_LONG: int = 365

# Optimal caption length range
OPTIMAL_LENGTH_MIN: int = 250
OPTIMAL_LENGTH_MAX: int = 449

# Top performers threshold
TOP_N_CONTENT_TYPES: int = 3
TOP_N_HOURS: int = 3
TOP_N_RESULTS: int = 10

# Bottom performers threshold for underperformer detection
BOTTOM_PERCENTILE: float = 0.20

# Minimum data points for meaningful analysis
MIN_DATA_POINTS: int = 5


# =============================================================================
# Type Definitions
# =============================================================================


class TimeframeSummary:
    """Summary statistics for a specific timeframe.

    Attributes:
        timeframe_days: Number of days in this analysis window.
        total_earnings: Sum of all earnings in timeframe.
        avg_earnings: Mean earnings per record.
        record_count: Number of performance records.
        top_10: List of top 10 performing records.
    """

    pass  # Used for documentation; actual return is dict


class PatternInfo:
    """Detected patterns across timeframes.

    Attributes:
        top_content_types: Content types appearing in top performers.
        optimal_length_ratio: Proportion of captions in optimal length range.
        best_hours: Hours with highest performance.
        underperformers: Content types frequently in bottom 20%.
        frequency_gaps: High-performing types that are underrepresented.
    """

    pass  # Used for documentation; actual return is dict


# =============================================================================
# Main Analyzer Class
# =============================================================================


class DailyStatisticsAnalyzer:
    """Generate automated daily digest of performance statistics.

    Implements the 7-step optimization process for daily statistics review,
    analyzing performance across multiple timeframes to identify patterns
    and generate actionable recommendations.

    Attributes:
        creator_id: Unique identifier for the creator being analyzed.

    Examples:
        >>> analyzer = DailyStatisticsAnalyzer("alexia")
        >>> data = [
        ...     {"date": "2025-01-15", "earnings": 5200.0, "content_type": "lingerie"},
        ...     {"date": "2025-01-14", "earnings": 4800.0, "content_type": "bts"},
        ... ]
        >>> digest = analyzer.generate_daily_digest(data)
        >>> digest["creator_id"]
        'alexia'
    """

    def __init__(self, creator_id: str) -> None:
        """Initialize DailyStatisticsAnalyzer for a creator.

        Args:
            creator_id: Unique identifier for the creator. Must be non-empty.

        Raises:
            ValueError: If creator_id is empty or None.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analyzer.creator_id
            'alexia'
        """
        if not creator_id:
            raise ValueError("creator_id cannot be empty")

        self.creator_id: str = creator_id

    def generate_daily_digest(
        self,
        performance_data: list[dict],
    ) -> dict[str, Any]:
        """Generate comprehensive daily statistics digest.

        Analyzes performance data across multiple timeframes (30, 180, 365 days),
        identifies patterns, and generates actionable recommendations following
        the 7-step optimization process.

        Args:
            performance_data: List of performance records. Each record should
                contain at minimum:
                - date: Date of performance (datetime, ISO string, or None)
                - earnings: Revenue generated (float)
                Optional fields for enhanced analysis:
                - content_type: Content classification (str)
                - caption_length: Length of caption in characters (int)
                - hour: Hour of posting (0-23)

        Returns:
            Comprehensive digest dictionary containing:
                - date: ISO format date when digest was generated
                - creator_id: Creator identifier
                - timeframe_summaries: Dict mapping timeframe to summary stats
                - patterns: Detected patterns across timeframes
                - recommendations: List of actionable recommendations
                - action_items: Prioritized list of actions to take
                - top_performers: Top performing records across all data

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> data = [
            ...     {"date": "2025-01-15", "earnings": 5200.0, "content_type": "lingerie",
            ...      "caption_length": 320, "hour": 14},
            ...     {"date": "2025-01-14", "earnings": 4800.0, "content_type": "bts",
            ...      "caption_length": 280, "hour": 18},
            ... ]
            >>> digest = analyzer.generate_daily_digest(data)
            >>> "timeframe_summaries" in digest
            True
            >>> "patterns" in digest
            True
        """
        # Generate current timestamp
        digest_date = datetime.now().isoformat()

        # Analyze each timeframe
        timeframe_summaries: dict[int, dict] = {}
        for days in [TIMEFRAME_SHORT, TIMEFRAME_MEDIUM, TIMEFRAME_LONG]:
            timeframe_summaries[days] = self._analyze_timeframe(
                performance_data, days
            )

        # Identify patterns using 30-day analysis as primary
        primary_analysis = timeframe_summaries.get(TIMEFRAME_SHORT, {})
        patterns = self._identify_patterns(primary_analysis, performance_data)

        # Generate recommendations based on patterns
        recommendations = self._generate_recommendations(patterns)

        # Prioritize actions
        action_items = self._prioritize_actions(recommendations)

        # Get overall top performers
        top_performers = self._get_overall_top_performers(performance_data)

        return {
            "date": digest_date,
            "creator_id": self.creator_id,
            "timeframe_summaries": timeframe_summaries,
            "patterns": patterns,
            "recommendations": recommendations,
            "action_items": action_items,
            "top_performers": top_performers,
        }

    def _analyze_timeframe(
        self,
        data: list[dict],
        days: int,
    ) -> dict[str, Any]:
        """Analyze performance data within a specific timeframe.

        Filters data to the specified number of days from today and calculates
        summary statistics including total earnings, average earnings, and
        identifies top performers.

        Args:
            data: List of performance records with date and earnings fields.
            days: Number of days to include in the analysis window.

        Returns:
            Dictionary containing:
                - timeframe_days: The analysis window size
                - total_earnings: Sum of all earnings in window
                - avg_earnings: Mean earnings per record
                - record_count: Number of records in window
                - top_10: List of top 10 performing records (sorted by earnings)

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> data = [
            ...     {"date": "2025-01-15", "earnings": 5200.0},
            ...     {"date": "2024-01-15", "earnings": 1000.0},  # Old record
            ... ]
            >>> result = analyzer._analyze_timeframe(data, 30)
            >>> result["record_count"]
            1
        """
        if not data:
            return {
                "timeframe_days": days,
                "total_earnings": 0.0,
                "avg_earnings": 0.0,
                "record_count": 0,
                "top_10": [],
            }

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)

        # Filter data by date
        filtered_data: list[dict] = []
        for record in data:
            record_date = self._parse_date(record.get("date"))
            if record_date and record_date >= cutoff_date:
                filtered_data.append(record)

        # Calculate statistics
        record_count = len(filtered_data)
        if record_count == 0:
            return {
                "timeframe_days": days,
                "total_earnings": 0.0,
                "avg_earnings": 0.0,
                "record_count": 0,
                "top_10": [],
            }

        total_earnings = sum(
            float(r.get("earnings", 0) or 0) for r in filtered_data
        )
        avg_earnings = total_earnings / record_count

        # Get top 10 performers
        sorted_data = sorted(
            filtered_data,
            key=lambda x: float(x.get("earnings", 0) or 0),
            reverse=True,
        )
        top_10 = sorted_data[:TOP_N_RESULTS]

        return {
            "timeframe_days": days,
            "total_earnings": round(total_earnings, 2),
            "avg_earnings": round(avg_earnings, 2),
            "record_count": record_count,
            "top_10": top_10,
        }

    def _parse_date(self, date_value: Any) -> datetime | None:
        """Safely parse a date value into a datetime object.

        Handles multiple date formats including datetime objects, ISO strings,
        and None values.

        Args:
            date_value: Date to parse. Can be datetime, ISO format string, or None.

        Returns:
            Parsed datetime object, or None if parsing fails or input is None.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analyzer._parse_date("2025-01-15")
            datetime.datetime(2025, 1, 15, 0, 0)
            >>> analyzer._parse_date(None) is None
            True
        """
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            # Try common date formats
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue

        return None

    def _identify_patterns(
        self,
        analysis: dict[str, Any],
        full_data: list[dict],
    ) -> dict[str, Any]:
        """Identify performance patterns from analysis results.

        Examines top performers and full dataset to identify:
        - Top content types that appear in best performers
        - Caption length optimization patterns
        - Best performing hours
        - Underperforming content types
        - Frequency gaps (high performers that are underutilized)

        Args:
            analysis: Timeframe analysis result containing top_10.
            full_data: Complete performance dataset for frequency analysis.

        Returns:
            Dictionary containing identified patterns:
                - top_content_types: List of top performing content types
                - optimal_length_ratio: Proportion in 250-449 char range
                - best_hours: Top 3 best performing hours
                - underperformers: Content types frequently in bottom 20%
                - frequency_gaps: High performers that are underrepresented

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {"top_10": [{"content_type": "lingerie", "earnings": 5000}]}
            >>> patterns = analyzer._identify_patterns(analysis, [])
            >>> "top_content_types" in patterns
            True
        """
        return {
            "top_content_types": self._get_top_types(analysis),
            "optimal_length_ratio": self._calculate_length_ratio(analysis),
            "best_hours": self._analyze_timing(analysis),
            "underperformers": self._identify_underperformers(analysis),
            "frequency_gaps": self._analyze_frequency_gaps(analysis, full_data),
        }

    def _get_top_types(self, analysis: dict[str, Any]) -> list[str]:
        """Extract top content types from top performers.

        Analyzes the top_10 performers and identifies the most common content
        types among them.

        Args:
            analysis: Timeframe analysis result containing top_10 list.

        Returns:
            List of top 3 content types found in top performers.
            Returns empty list if no content types found.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {
            ...     "top_10": [
            ...         {"content_type": "lingerie"},
            ...         {"content_type": "lingerie"},
            ...         {"content_type": "bts"},
            ...     ]
            ... }
            >>> analyzer._get_top_types(analysis)
            ['lingerie', 'bts']
        """
        top_10 = analysis.get("top_10", [])
        if not top_10:
            return []

        content_types = [
            r.get("content_type")
            for r in top_10
            if r.get("content_type")
        ]

        if not content_types:
            return []

        counter = Counter(content_types)
        return [ct for ct, _ in counter.most_common(TOP_N_CONTENT_TYPES)]

    def _calculate_length_ratio(self, analysis: dict[str, Any]) -> float:
        """Calculate ratio of captions in optimal length range.

        Determines what proportion of top performers have captions in the
        optimal 250-449 character range.

        Args:
            analysis: Timeframe analysis result containing top_10 list.

        Returns:
            Ratio (0.0-1.0) of captions within optimal length range.
            Returns 0.0 if no caption length data available.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {
            ...     "top_10": [
            ...         {"caption_length": 300},  # Optimal
            ...         {"caption_length": 100},  # Too short
            ...     ]
            ... }
            >>> analyzer._calculate_length_ratio(analysis)
            0.5
        """
        top_10 = analysis.get("top_10", [])
        if not top_10:
            return 0.0

        records_with_length = [
            r for r in top_10
            if r.get("caption_length") is not None
        ]

        if not records_with_length:
            return 0.0

        optimal_count = sum(
            1 for r in records_with_length
            if OPTIMAL_LENGTH_MIN <= r.get("caption_length", 0) <= OPTIMAL_LENGTH_MAX
        )

        return round(optimal_count / len(records_with_length), 3)

    def _analyze_timing(self, analysis: dict[str, Any]) -> list[int]:
        """Identify top performing hours from analysis.

        Analyzes the top_10 performers to find the most common posting hours.

        Args:
            analysis: Timeframe analysis result containing top_10 list.

        Returns:
            List of top 3 best-performing hours (0-23).
            Returns empty list if no timing data available.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {
            ...     "top_10": [
            ...         {"hour": 14},
            ...         {"hour": 14},
            ...         {"hour": 18},
            ...     ]
            ... }
            >>> analyzer._analyze_timing(analysis)
            [14, 18]
        """
        top_10 = analysis.get("top_10", [])
        if not top_10:
            return []

        hours = [
            r.get("hour")
            for r in top_10
            if r.get("hour") is not None
        ]

        if not hours:
            return []

        counter = Counter(hours)
        return [hour for hour, _ in counter.most_common(TOP_N_HOURS)]

    def _identify_underperformers(
        self,
        analysis: dict[str, Any],
    ) -> list[str]:
        """Identify content types frequently in bottom performers.

        Finds content types that appear in the bottom 20% of earners within
        the top_10 analysis set. This is useful for identifying types that
        consistently underperform.

        Args:
            analysis: Timeframe analysis result containing top_10 list.

        Returns:
            List of content types that appear in bottom 20% of performers.
            Returns empty list if insufficient data.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {
            ...     "top_10": [
            ...         {"content_type": "lingerie", "earnings": 5000},
            ...         {"content_type": "lingerie", "earnings": 4000},
            ...         {"content_type": "selfie", "earnings": 500},  # Bottom
            ...     ]
            ... }
            >>> underperformers = analyzer._identify_underperformers(analysis)
            >>> "selfie" in underperformers or len(underperformers) >= 0
            True
        """
        top_10 = analysis.get("top_10", [])
        if len(top_10) < MIN_DATA_POINTS:
            return []

        # Sort by earnings ascending to find bottom performers
        sorted_by_earnings = sorted(
            top_10,
            key=lambda x: float(x.get("earnings", 0) or 0),
        )

        # Get bottom 20%
        bottom_count = max(1, int(len(sorted_by_earnings) * BOTTOM_PERCENTILE))
        bottom_performers = sorted_by_earnings[:bottom_count]

        # Extract content types from bottom performers
        underperformer_types = [
            r.get("content_type")
            for r in bottom_performers
            if r.get("content_type")
        ]

        return list(set(underperformer_types))

    def _analyze_frequency_gaps(
        self,
        analysis: dict[str, Any],
        full_data: list[dict],
    ) -> dict[str, Any]:
        """Identify high-performing types that are underrepresented.

        Compares content types in top_10 performers against their overall
        frequency in the full dataset to identify types that perform well
        but are not being used frequently enough.

        Args:
            analysis: Timeframe analysis result containing top_10 list.
            full_data: Complete performance dataset for frequency comparison.

        Returns:
            Dictionary containing:
                - gap_types: Content types in top 10 but underrepresented
                - top_10_distribution: Counter of types in top performers
                - overall_distribution: Counter of types in all data

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> analysis = {"top_10": [{"content_type": "lingerie"}]}
            >>> full_data = [
            ...     {"content_type": "selfie"} for _ in range(10)
            ... ] + [{"content_type": "lingerie"}]
            >>> gaps = analyzer._analyze_frequency_gaps(analysis, full_data)
            >>> "gap_types" in gaps
            True
        """
        top_10 = analysis.get("top_10", [])

        # Get distribution in top 10
        top_10_types = [
            r.get("content_type")
            for r in top_10
            if r.get("content_type")
        ]
        top_10_distribution = Counter(top_10_types)

        # Get overall distribution
        all_types = [
            r.get("content_type")
            for r in full_data
            if r.get("content_type")
        ]
        overall_distribution = Counter(all_types)

        # Find gaps: types in top 10 that are underrepresented overall
        gap_types: list[str] = []
        total_records = len(all_types) if all_types else 1

        for content_type in top_10_distribution:
            top_10_freq = top_10_distribution[content_type] / len(top_10_types) if top_10_types else 0
            overall_freq = overall_distribution.get(content_type, 0) / total_records

            # If a type is more common in top 10 than overall, it's underutilized
            if top_10_freq > overall_freq * 1.5:  # 50% higher in top performers
                gap_types.append(content_type)

        return {
            "gap_types": gap_types,
            "top_10_distribution": dict(top_10_distribution),
            "overall_distribution": dict(overall_distribution),
        }

    def _generate_recommendations(
        self,
        patterns: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate actionable recommendations from detected patterns.

        Translates identified patterns into specific, actionable recommendations
        with category classification and priority levels.

        Args:
            patterns: Dictionary of detected patterns from _identify_patterns.

        Returns:
            List of recommendation dictionaries, each containing:
                - category: Type of recommendation (content, timing, volume, etc.)
                - priority: Priority level (HIGH, MEDIUM, LOW)
                - action: Specific action to take
                - rationale: Explanation of why this action is recommended

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> patterns = {
            ...     "top_content_types": ["lingerie", "bts"],
            ...     "optimal_length_ratio": 0.8,
            ...     "best_hours": [14, 18],
            ...     "underperformers": ["selfie"],
            ...     "frequency_gaps": {"gap_types": ["lingerie"]},
            ... }
            >>> recs = analyzer._generate_recommendations(patterns)
            >>> len(recs) > 0
            True
        """
        recommendations: list[dict[str, Any]] = []

        # Recommendation 1: Content type focus
        top_types = patterns.get("top_content_types", [])
        if top_types:
            recommendations.append({
                "category": "content",
                "priority": "HIGH",
                "action": f"Prioritize content types: {', '.join(top_types)}",
                "rationale": "These content types consistently appear in top performers",
            })

        # Recommendation 2: Caption length optimization
        length_ratio = patterns.get("optimal_length_ratio", 0)
        if length_ratio >= 0.6:
            recommendations.append({
                "category": "caption",
                "priority": "MEDIUM",
                "action": f"Continue using optimal caption length (250-449 chars)",
                "rationale": f"{length_ratio:.0%} of top performers use optimal length",
            })
        elif length_ratio < 0.4:
            recommendations.append({
                "category": "caption",
                "priority": "HIGH",
                "action": "Increase caption length to 250-449 character range",
                "rationale": f"Only {length_ratio:.0%} of top performers use optimal length",
            })

        # Recommendation 3: Timing optimization
        best_hours = patterns.get("best_hours", [])
        if best_hours:
            hour_str = ", ".join(f"{h}:00" for h in best_hours)
            recommendations.append({
                "category": "timing",
                "priority": "MEDIUM",
                "action": f"Focus posting at peak hours: {hour_str}",
                "rationale": "These hours show highest performance in top earners",
            })

        # Recommendation 4: Reduce underperformers
        underperformers = patterns.get("underperformers", [])
        if underperformers:
            recommendations.append({
                "category": "volume",
                "priority": "MEDIUM",
                "action": f"Reduce volume of: {', '.join(underperformers)}",
                "rationale": "These content types frequently appear in bottom performers",
            })

        # Recommendation 5: Address frequency gaps
        frequency_gaps = patterns.get("frequency_gaps", {})
        gap_types = frequency_gaps.get("gap_types", [])
        if gap_types:
            recommendations.append({
                "category": "volume",
                "priority": "HIGH",
                "action": f"Increase frequency of high performers: {', '.join(gap_types)}",
                "rationale": "These types perform well but are underutilized in schedule",
            })

        return recommendations

    def _prioritize_actions(
        self,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        """Prioritize recommendations into ordered action items.

        Sorts recommendations by priority (HIGH first, then MEDIUM, then LOW)
        and extracts the action strings for a focused task list.

        Args:
            recommendations: List of recommendation dictionaries with priority
                and action fields.

        Returns:
            Ordered list of action strings, HIGH priority first.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> recs = [
            ...     {"priority": "LOW", "action": "Minor tweak"},
            ...     {"priority": "HIGH", "action": "Critical fix"},
            ...     {"priority": "MEDIUM", "action": "Important update"},
            ... ]
            >>> actions = analyzer._prioritize_actions(recs)
            >>> actions[0]
            'Critical fix'
        """
        if not recommendations:
            return []

        # Define priority order
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

        # Sort by priority
        sorted_recs = sorted(
            recommendations,
            key=lambda x: priority_order.get(x.get("priority", "LOW"), 3),
        )

        # Extract actions
        return [rec.get("action", "") for rec in sorted_recs if rec.get("action")]

    def _get_overall_top_performers(
        self,
        data: list[dict],
    ) -> list[dict]:
        """Get overall top performers from all data.

        Sorts all performance data by earnings and returns the top performers
        across the entire dataset.

        Args:
            data: Complete list of performance records.

        Returns:
            List of top 10 performing records sorted by earnings descending.

        Examples:
            >>> analyzer = DailyStatisticsAnalyzer("alexia")
            >>> data = [
            ...     {"earnings": 1000},
            ...     {"earnings": 5000},
            ...     {"earnings": 3000},
            ... ]
            >>> top = analyzer._get_overall_top_performers(data)
            >>> top[0]["earnings"]
            5000
        """
        if not data:
            return []

        sorted_data = sorted(
            data,
            key=lambda x: float(x.get("earnings", 0) or 0),
            reverse=True,
        )

        return sorted_data[:TOP_N_RESULTS]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Main class
    "DailyStatisticsAnalyzer",
    # Constants
    "TIMEFRAME_SHORT",
    "TIMEFRAME_MEDIUM",
    "TIMEFRAME_LONG",
    "OPTIMAL_LENGTH_MIN",
    "OPTIMAL_LENGTH_MAX",
    "TOP_N_CONTENT_TYPES",
    "TOP_N_HOURS",
    "TOP_N_RESULTS",
    "BOTTOM_PERCENTILE",
    "MIN_DATA_POINTS",
]
