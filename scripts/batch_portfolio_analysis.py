#!/usr/bin/env python3
"""
Batch Portfolio Analysis - Comprehensive analysis of entire OnlyFans creator portfolio.

This module provides type-safe data classes and analysis functions for generating
Fortune 500-quality strategic reports across all creators in the EROS database.

Features:
- Quick Analysis: 7-step fast analysis for daily monitoring
- Deep Analysis: 9-phase comprehensive strategic deep-dive
- Portfolio Summary: Aggregate metrics and cross-creator insights
- Export: Markdown and JSON output formats

Usage:
    python batch_portfolio_analysis.py --mode quick
    python batch_portfolio_analysis.py --mode deep --output-dir ./reports
    python batch_portfolio_analysis.py --creator missalexa --mode deep

Author: EROS Schedule Generator
Version: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# Import from analyze_creator for reuse in quick analysis
from analyze_creator import (
    CreatorBrief,
    AgencyBenchmarks,
    generate_brief,
    calculate_agency_benchmarks,
)

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION & PATHS
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "database" / "eros_sd_main.db"
SQL_DIR = SCRIPT_DIR.parent / "assets" / "sql"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "portfolio_analysis"

# Caption freshness thresholds
FRESHNESS_CRITICAL = 30  # Below this is critically stale
FRESHNESS_STALE = 50     # Below this needs attention
FRESHNESS_GOOD = 70      # Good freshness level
FRESHNESS_EXCELLENT = 80 # Fresh captions

# Percentile thresholds for portfolio positioning
PERCENTILE_ELITE = 90    # Elite performer
PERCENTILE_TOP = 75      # Top performer
PERCENTILE_STRONG = 50   # Strong performer
PERCENTILE_DEVELOPING = 25  # Developing


# =============================================================================
# ENUMS
# =============================================================================

class AnalysisMode(Enum):
    """Analysis mode selection."""
    QUICK = "quick"
    DEEP = "deep"
    FULL = "full"  # Both quick and deep


class HealthRating(Enum):
    """Overall health rating for creators."""
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    BELOW_AVERAGE = "Below Average"
    CRITICAL = "Critical"


class BenchmarkRating(Enum):
    """Performance benchmark rating scale."""
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    POOR = "Poor"


# =============================================================================
# HELPER DATA CLASSES
# =============================================================================

@dataclass
class MonthlyTrend:
    """Monthly PPV performance trend data point."""
    month: str  # YYYY-MM format
    ppv_count: int
    revenue: float
    avg_earnings: float
    purchase_rate: float
    revenue_per_send: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class WeekOverWeek:
    """Week-over-week comparison metrics."""
    current_week_ppvs: int
    current_week_revenue: float
    current_week_purchase_rate: float
    previous_week_ppvs: int
    previous_week_revenue: float
    previous_week_purchase_rate: float
    revenue_change_pct: float
    purchase_rate_change_pct: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class HourlyPerformance:
    """Performance metrics for a specific hour."""
    hour: int  # 0-23
    count: int
    total_revenue: float
    avg_earnings: float
    purchase_rate: float
    revenue_per_send: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DailyPerformance:
    """Performance metrics for a day of week."""
    day: str  # Full name: Monday, Tuesday, etc.
    day_number: int  # 0=Sunday, 6=Saturday
    count: int
    avg_earnings: float
    purchase_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class HeatmapEntry:
    """Hour + Day combination performance entry."""
    day: str  # Short name: Mon, Tue, etc.
    hour: int
    count: int
    avg_earnings: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ContentTypePerformance:
    """Performance metrics for a content type."""
    type_name: str
    type_category: str
    uses: int
    total_revenue: float
    avg_earnings: float
    view_rate: float
    purchase_rate: float
    avg_price: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ContentGap:
    """Content gap analysis entry."""
    type_name: str
    type_category: str
    in_vault: bool
    quantity: int
    quality_rating: str | None
    times_used: int
    avg_earnings: float | None
    status: str  # UNTAPPED, NEEDS CONTENT, OVERUSED, OK

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class PriceTierPerformance:
    """Performance metrics for a price tier."""
    price_tier: str  # e.g., "$1-5", "$6-10"
    count: int
    total_revenue: float
    avg_earnings: float
    purchase_rate: float
    revenue_per_send: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OptimalPrice:
    """Optimal pricing recommendation by content type."""
    type_name: str
    avg_price: float
    avg_earnings: float
    purchase_rate: float
    recommended_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CaptionPerformance:
    """Individual caption performance data."""
    caption_id: str
    preview: str  # First 60 chars
    tone: str | None
    performance_score: float | None
    freshness_score: float
    times_used: int
    avg_earnings: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TonePerformance:
    """Performance metrics by caption tone."""
    tone: str
    count: int
    avg_earnings: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TierComparison:
    """Creator's tier compared to other tiers."""
    tier: int
    tier_count: int
    tier_avg_earnings: float
    tier_avg_fans: float
    tier_avg_efficiency: float
    tier_avg_renew_pct: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class QuickWin:
    """Quick win recommendation."""
    action: str
    implementation: str
    expected_impact: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RoadmapItem:
    """90-day roadmap item."""
    month: int  # 1, 2, or 3
    phase: str  # Foundation, Growth, Optimization
    objective: str
    key_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class KPI:
    """Key Performance Indicator tracking entry."""
    metric: str
    current: float
    target_30d: float
    target_90d: float
    unit: str = ""  # e.g., "%", "$", ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CreatorRanking:
    """Creator ranking entry for portfolio summaries."""
    creator_id: str
    page_name: str
    display_name: str
    value: float  # The metric value used for ranking
    rank: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CreatorAttention:
    """Creator requiring attention entry."""
    creator_id: str
    page_name: str
    display_name: str
    reason: str
    severity: str  # critical, high, medium, low
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AnalysisError:
    """Error encountered during analysis."""
    creator_id: str
    page_name: str
    phase: str
    error_type: str
    error_message: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# =============================================================================
# QUICK ANALYSIS DATA CLASS (7-Step)
# =============================================================================

@dataclass
class QuickAnalysisResult:
    """
    Quick Analysis Result - Contains 7-step analysis output.

    This is the fast analysis mode designed for daily monitoring
    and quick health checks across the portfolio.

    Steps:
    1. Load creator profile and metrics
    2. Calculate volume level
    3. Get historical performance
    4. Identify best hours/days
    5. Get top content types
    6. Assess caption health
    7. Load persona data
    """
    # Identity
    creator_id: str
    page_name: str
    display_name: str

    # Imported from analyze_creator.py
    # Note: Import at runtime to avoid circular imports
    brief: Any  # CreatorBrief
    benchmarks: Any | None = None  # AgencyBenchmarks

    # Metadata
    generated_at: str = ""  # ISO timestamp
    analysis_duration_ms: int = 0

    def __post_init__(self) -> None:
        """Set generated_at if not provided."""
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "creator_id": self.creator_id,
            "page_name": self.page_name,
            "display_name": self.display_name,
            "generated_at": self.generated_at,
            "analysis_duration_ms": self.analysis_duration_ms,
        }
        # Handle brief and benchmarks which may be dataclasses
        if self.brief:
            result["brief"] = asdict(self.brief) if hasattr(self.brief, "__dataclass_fields__") else self.brief
        if self.benchmarks:
            result["benchmarks"] = asdict(self.benchmarks) if hasattr(self.benchmarks, "__dataclass_fields__") else self.benchmarks
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuickAnalysisResult:
        """Create instance from dictionary."""
        return cls(
            creator_id=data["creator_id"],
            page_name=data["page_name"],
            display_name=data["display_name"],
            brief=data.get("brief"),
            benchmarks=data.get("benchmarks"),
            generated_at=data.get("generated_at", ""),
            analysis_duration_ms=data.get("analysis_duration_ms", 0),
        )


# =============================================================================
# DEEP ANALYSIS DATA CLASSES (9-Phase)
# =============================================================================

@dataclass
class RevenueAnalysis:
    """
    Phase 2: Revenue Architecture Analysis.

    Complete revenue breakdown with multi-stream analysis
    and benchmark comparisons.
    """
    # Revenue breakdown
    total_earnings: float
    subscription_net: float
    message_net: float
    tips_net: float
    posts_net: float

    # Percentages
    msg_pct: float  # Message revenue as % of total
    sub_pct: float  # Subscription revenue as % of total
    msg_sub_ratio: float  # Message:Subscription ratio

    # Per-fan metrics
    earnings_per_fan: float
    spend_per_spender: float

    # Retention
    renew_on_pct: float
    contribution_pct: float

    # Benchmark ratings
    msg_sub_rating: str = ""  # POOR, AVG, GOOD, EXCELLENT
    earnings_per_fan_rating: str = ""
    renew_on_rating: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevenueAnalysis:
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class PPVAnalysis:
    """
    Phase 3: PPV Performance Deep Dive.

    Comprehensive PPV metrics including trends,
    volatility analysis, and benchmark comparisons.
    """
    # Overall metrics
    total_ppvs: int
    total_revenue: float
    avg_earnings: float

    # Rates
    view_rate_pct: float
    purchase_rate_pct: float
    revenue_per_send: float

    # Pricing
    avg_price: float
    earnings_volatility: float

    # Trends
    monthly_trends: list[MonthlyTrend] = field(default_factory=list)
    week_over_week: WeekOverWeek | None = None

    # Benchmark ratings
    view_rate_rating: str = ""
    purchase_rate_rating: str = ""
    rps_rating: str = ""  # Revenue per send rating

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["monthly_trends"] = [t.to_dict() for t in self.monthly_trends]
        result["week_over_week"] = self.week_over_week.to_dict() if self.week_over_week else None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PPVAnalysis:
        """Create instance from dictionary."""
        monthly_trends = [MonthlyTrend(**t) for t in data.pop("monthly_trends", [])]
        wow_data = data.pop("week_over_week", None)
        week_over_week = WeekOverWeek(**wow_data) if wow_data else None
        return cls(**data, monthly_trends=monthly_trends, week_over_week=week_over_week)


@dataclass
class TimingAnalysis:
    """
    Phase 4: Timing Optimization Analysis.

    Hour-by-hour and day-by-day performance data
    with heatmap combinations for optimal scheduling.
    """
    # Performance data
    hourly_performance: list[HourlyPerformance] = field(default_factory=list)
    daily_performance: list[DailyPerformance] = field(default_factory=list)
    top_combinations: list[HeatmapEntry] = field(default_factory=list)

    # Best performers
    best_hours: list[int] = field(default_factory=list)  # Top 3 hours
    best_days: list[str] = field(default_factory=list)  # Top 3 days

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hourly_performance": [h.to_dict() for h in self.hourly_performance],
            "daily_performance": [d.to_dict() for d in self.daily_performance],
            "top_combinations": [c.to_dict() for c in self.top_combinations],
            "best_hours": self.best_hours,
            "best_days": self.best_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimingAnalysis:
        """Create instance from dictionary."""
        return cls(
            hourly_performance=[HourlyPerformance(**h) for h in data.get("hourly_performance", [])],
            daily_performance=[DailyPerformance(**d) for d in data.get("daily_performance", [])],
            top_combinations=[HeatmapEntry(**c) for c in data.get("top_combinations", [])],
            best_hours=data.get("best_hours", []),
            best_days=data.get("best_days", []),
        )


@dataclass
class ContentAnalysis:
    """
    Phase 5: Content Type Performance.

    Content type rankings, gap analysis,
    and utilization recommendations.
    """
    # Performance rankings
    content_rankings: list[ContentTypePerformance] = field(default_factory=list)

    # Gap analysis
    content_gaps: list[ContentGap] = field(default_factory=list)

    # Quick references
    top_content_types: list[str] = field(default_factory=list)  # Top 3
    underutilized_types: list[str] = field(default_factory=list)  # UNTAPPED status

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "content_rankings": [c.to_dict() for c in self.content_rankings],
            "content_gaps": [g.to_dict() for g in self.content_gaps],
            "top_content_types": self.top_content_types,
            "underutilized_types": self.underutilized_types,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentAnalysis:
        """Create instance from dictionary."""
        return cls(
            content_rankings=[ContentTypePerformance(**c) for c in data.get("content_rankings", [])],
            content_gaps=[ContentGap(**g) for g in data.get("content_gaps", [])],
            top_content_types=data.get("top_content_types", []),
            underutilized_types=data.get("underutilized_types", []),
        )


@dataclass
class PricingAnalysis:
    """
    Phase 6: Pricing Strategy Analysis.

    Price tier performance and optimal pricing
    recommendations by content type.
    """
    # Tier performance
    price_tier_performance: list[PriceTierPerformance] = field(default_factory=list)

    # Optimal prices by content type
    optimal_prices: list[OptimalPrice] = field(default_factory=list)

    # Recommendations
    recommended_price_range: dict[str, float] = field(default_factory=dict)  # min, max, sweet_spot

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "price_tier_performance": [p.to_dict() for p in self.price_tier_performance],
            "optimal_prices": [o.to_dict() for o in self.optimal_prices],
            "recommended_price_range": self.recommended_price_range,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PricingAnalysis:
        """Create instance from dictionary."""
        return cls(
            price_tier_performance=[PriceTierPerformance(**p) for p in data.get("price_tier_performance", [])],
            optimal_prices=[OptimalPrice(**o) for o in data.get("optimal_prices", [])],
            recommended_price_range=data.get("recommended_price_range", {}),
        )


@dataclass
class CaptionAnalysis:
    """
    Phase 7: Caption Intelligence.

    Caption library health, top performers,
    underperformers, and tone effectiveness.
    """
    # Library health
    total_captions: int = 0
    avg_freshness: float = 0.0
    fresh_count: int = 0  # >= 80
    stale_count: int = 0  # < 50
    critical_stale_count: int = 0  # < 30

    # Top and bottom performers
    top_captions: list[CaptionPerformance] = field(default_factory=list)
    bottom_captions: list[CaptionPerformance] = field(default_factory=list)

    # Tone analysis
    tone_effectiveness: list[TonePerformance] = field(default_factory=list)

    # Overall rating
    caption_health_rating: str = ""  # Excellent, Good, Needs Attention, Critical

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_captions": self.total_captions,
            "avg_freshness": self.avg_freshness,
            "fresh_count": self.fresh_count,
            "stale_count": self.stale_count,
            "critical_stale_count": self.critical_stale_count,
            "top_captions": [c.to_dict() for c in self.top_captions],
            "bottom_captions": [c.to_dict() for c in self.bottom_captions],
            "tone_effectiveness": [t.to_dict() for t in self.tone_effectiveness],
            "caption_health_rating": self.caption_health_rating,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaptionAnalysis:
        """Create instance from dictionary."""
        return cls(
            total_captions=data.get("total_captions", 0),
            avg_freshness=data.get("avg_freshness", 0.0),
            fresh_count=data.get("fresh_count", 0),
            stale_count=data.get("stale_count", 0),
            critical_stale_count=data.get("critical_stale_count", 0),
            top_captions=[CaptionPerformance(**c) for c in data.get("top_captions", [])],
            bottom_captions=[CaptionPerformance(**c) for c in data.get("bottom_captions", [])],
            tone_effectiveness=[TonePerformance(**t) for t in data.get("tone_effectiveness", [])],
            caption_health_rating=data.get("caption_health_rating", ""),
        )


@dataclass
class PersonaAnalysis:
    """
    Phase 8: Persona & Voice Analysis.

    Communication style profiling for
    persona-matched caption selection.
    """
    # Core persona attributes
    primary_tone: str = ""
    secondary_tone: str = ""
    emoji_frequency: str = ""  # high, medium, low
    favorite_emojis: str = ""  # Comma-separated
    slang_level: str = ""  # heavy, moderate, minimal

    # Sentiment
    avg_sentiment: float = 0.0  # -1 to 1
    sentiment_label: str = ""  # positive, neutral, negative

    # Style
    avg_caption_length: int = 0
    communication_style: str = ""  # e.g., "playful", "professional", "intimate"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonaAnalysis:
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class PortfolioPosition:
    """
    Phase 9: Portfolio Positioning.

    Creator's rank and percentile position
    within the agency portfolio.
    """
    # Rankings (1 = best)
    earnings_rank: int = 0
    fans_rank: int = 0
    efficiency_rank: int = 0  # Earnings per fan

    # Percentiles (100 = top)
    earnings_percentile: int = 0
    fans_percentile: int = 0
    efficiency_percentile: int = 0

    # Tier comparison
    tier_comparison: TierComparison | None = None

    # Position summary
    competitive_position: str = ""  # e.g., "Top Performer", "Rising Star", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["tier_comparison"] = self.tier_comparison.to_dict() if self.tier_comparison else None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioPosition:
        """Create instance from dictionary."""
        tier_data = data.pop("tier_comparison", None)
        tier_comparison = TierComparison(**tier_data) if tier_data else None
        return cls(**data, tier_comparison=tier_comparison)


@dataclass
class DeepAnalysisResult:
    """
    Deep Analysis Result - Complete 9-phase strategic analysis.

    This is the comprehensive analysis mode designed for
    weekly reviews, underperformer deep-dives, and strategic planning.

    Phases:
    1. Creator Discovery & Context
    2. Revenue Architecture Analysis
    3. PPV Performance Deep Dive
    4. Timing Optimization Analysis
    5. Content Type Performance
    6. Pricing Strategy Analysis
    7. Caption Intelligence
    8. Persona & Voice Analysis
    9. Portfolio Positioning
    """
    # Identity
    creator_id: str
    page_name: str
    display_name: str

    # Phase 2: Revenue
    revenue: RevenueAnalysis | None = None

    # Phase 3: PPV
    ppv: PPVAnalysis | None = None

    # Phase 4: Timing
    timing: TimingAnalysis | None = None

    # Phase 5: Content
    content: ContentAnalysis | None = None

    # Phase 6: Pricing
    pricing: PricingAnalysis | None = None

    # Phase 7: Captions
    captions: CaptionAnalysis | None = None

    # Phase 8: Persona
    persona: PersonaAnalysis | None = None

    # Phase 9: Portfolio Position
    portfolio_position: PortfolioPosition | None = None

    # Executive Summary
    health_score: int = 0  # 0-100
    health_rating: str = ""  # Excellent, Good, Average, Below Average, Critical
    top_priorities: list[str] = field(default_factory=list)  # Top 3

    # Recommendations
    quick_wins: list[QuickWin] = field(default_factory=list)
    thirty_day_plan: list[str] = field(default_factory=list)  # Week 1-4 actions
    ninety_day_roadmap: list[RoadmapItem] = field(default_factory=list)
    kpis_to_track: list[KPI] = field(default_factory=list)

    # Metadata
    generated_at: str = ""
    analysis_duration_ms: int = 0

    def __post_init__(self) -> None:
        """Set generated_at if not provided."""
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "creator_id": self.creator_id,
            "page_name": self.page_name,
            "display_name": self.display_name,
            "revenue": self.revenue.to_dict() if self.revenue else None,
            "ppv": self.ppv.to_dict() if self.ppv else None,
            "timing": self.timing.to_dict() if self.timing else None,
            "content": self.content.to_dict() if self.content else None,
            "pricing": self.pricing.to_dict() if self.pricing else None,
            "captions": self.captions.to_dict() if self.captions else None,
            "persona": self.persona.to_dict() if self.persona else None,
            "portfolio_position": self.portfolio_position.to_dict() if self.portfolio_position else None,
            "health_score": self.health_score,
            "health_rating": self.health_rating,
            "top_priorities": self.top_priorities,
            "quick_wins": [q.to_dict() for q in self.quick_wins],
            "thirty_day_plan": self.thirty_day_plan,
            "ninety_day_roadmap": [r.to_dict() for r in self.ninety_day_roadmap],
            "kpis_to_track": [k.to_dict() for k in self.kpis_to_track],
            "generated_at": self.generated_at,
            "analysis_duration_ms": self.analysis_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeepAnalysisResult:
        """Create instance from dictionary."""
        return cls(
            creator_id=data["creator_id"],
            page_name=data["page_name"],
            display_name=data["display_name"],
            revenue=RevenueAnalysis.from_dict(data["revenue"]) if data.get("revenue") else None,
            ppv=PPVAnalysis.from_dict(data["ppv"]) if data.get("ppv") else None,
            timing=TimingAnalysis.from_dict(data["timing"]) if data.get("timing") else None,
            content=ContentAnalysis.from_dict(data["content"]) if data.get("content") else None,
            pricing=PricingAnalysis.from_dict(data["pricing"]) if data.get("pricing") else None,
            captions=CaptionAnalysis.from_dict(data["captions"]) if data.get("captions") else None,
            persona=PersonaAnalysis.from_dict(data["persona"]) if data.get("persona") else None,
            portfolio_position=PortfolioPosition.from_dict(data["portfolio_position"]) if data.get("portfolio_position") else None,
            health_score=data.get("health_score", 0),
            health_rating=data.get("health_rating", ""),
            top_priorities=data.get("top_priorities", []),
            quick_wins=[QuickWin(**q) for q in data.get("quick_wins", [])],
            thirty_day_plan=data.get("thirty_day_plan", []),
            ninety_day_roadmap=[RoadmapItem(**r) for r in data.get("ninety_day_roadmap", [])],
            kpis_to_track=[KPI(**k) for k in data.get("kpis_to_track", [])],
            generated_at=data.get("generated_at", ""),
            analysis_duration_ms=data.get("analysis_duration_ms", 0),
        )


# =============================================================================
# PORTFOLIO SUMMARY DATA CLASS
# =============================================================================

@dataclass
class PortfolioSummary:
    """
    Portfolio Summary - Aggregate analysis across all creators.

    Provides cross-creator insights, tier distributions,
    rankings, and portfolio-wide health metrics.
    """
    # Metadata
    analysis_timestamp: str = ""
    total_duration_seconds: float = 0.0

    # Creator counts
    total_creators: int = 0
    active_creators: int = 0
    paid_pages: int = 0
    free_pages: int = 0

    # Portfolio revenue
    total_portfolio_earnings: float = 0.0
    total_message_revenue: float = 0.0
    total_subscription_revenue: float = 0.0

    # Averages
    avg_earnings_per_creator: float = 0.0
    avg_fans_per_creator: float = 0.0
    avg_purchase_rate: float = 0.0
    avg_view_rate: float = 0.0

    # Distributions
    tier_distribution: dict[int, int] = field(default_factory=dict)  # tier -> count
    volume_distribution: dict[str, int] = field(default_factory=dict)  # level -> count

    # Rankings
    top_5_by_revenue: list[CreatorRanking] = field(default_factory=list)
    top_5_by_fans: list[CreatorRanking] = field(default_factory=list)
    top_5_by_efficiency: list[CreatorRanking] = field(default_factory=list)
    bottom_5_by_revenue: list[CreatorRanking] = field(default_factory=list)

    # Attention required
    needs_attention: list[CreatorAttention] = field(default_factory=list)

    # Caption health (portfolio-wide)
    total_captions: int = 0
    fresh_captions: int = 0
    stale_captions: int = 0
    avg_freshness: float = 0.0

    # Analysis status
    successful_analyses: int = 0
    failed_analyses: int = 0
    errors: list[AnalysisError] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set analysis_timestamp if not provided."""
        if not self.analysis_timestamp:
            self.analysis_timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "analysis_timestamp": self.analysis_timestamp,
            "total_duration_seconds": self.total_duration_seconds,
            "total_creators": self.total_creators,
            "active_creators": self.active_creators,
            "paid_pages": self.paid_pages,
            "free_pages": self.free_pages,
            "total_portfolio_earnings": self.total_portfolio_earnings,
            "total_message_revenue": self.total_message_revenue,
            "total_subscription_revenue": self.total_subscription_revenue,
            "avg_earnings_per_creator": self.avg_earnings_per_creator,
            "avg_fans_per_creator": self.avg_fans_per_creator,
            "avg_purchase_rate": self.avg_purchase_rate,
            "avg_view_rate": self.avg_view_rate,
            "tier_distribution": self.tier_distribution,
            "volume_distribution": self.volume_distribution,
            "top_5_by_revenue": [r.to_dict() for r in self.top_5_by_revenue],
            "top_5_by_fans": [r.to_dict() for r in self.top_5_by_fans],
            "top_5_by_efficiency": [r.to_dict() for r in self.top_5_by_efficiency],
            "bottom_5_by_revenue": [r.to_dict() for r in self.bottom_5_by_revenue],
            "needs_attention": [a.to_dict() for a in self.needs_attention],
            "total_captions": self.total_captions,
            "fresh_captions": self.fresh_captions,
            "stale_captions": self.stale_captions,
            "avg_freshness": self.avg_freshness,
            "successful_analyses": self.successful_analyses,
            "failed_analyses": self.failed_analyses,
            "errors": [e.to_dict() for e in self.errors],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioSummary:
        """Create instance from dictionary."""
        return cls(
            analysis_timestamp=data.get("analysis_timestamp", ""),
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
            total_creators=data.get("total_creators", 0),
            active_creators=data.get("active_creators", 0),
            paid_pages=data.get("paid_pages", 0),
            free_pages=data.get("free_pages", 0),
            total_portfolio_earnings=data.get("total_portfolio_earnings", 0.0),
            total_message_revenue=data.get("total_message_revenue", 0.0),
            total_subscription_revenue=data.get("total_subscription_revenue", 0.0),
            avg_earnings_per_creator=data.get("avg_earnings_per_creator", 0.0),
            avg_fans_per_creator=data.get("avg_fans_per_creator", 0.0),
            avg_purchase_rate=data.get("avg_purchase_rate", 0.0),
            avg_view_rate=data.get("avg_view_rate", 0.0),
            tier_distribution=data.get("tier_distribution", {}),
            volume_distribution=data.get("volume_distribution", {}),
            top_5_by_revenue=[CreatorRanking(**r) for r in data.get("top_5_by_revenue", [])],
            top_5_by_fans=[CreatorRanking(**r) for r in data.get("top_5_by_fans", [])],
            top_5_by_efficiency=[CreatorRanking(**r) for r in data.get("top_5_by_efficiency", [])],
            bottom_5_by_revenue=[CreatorRanking(**r) for r in data.get("bottom_5_by_revenue", [])],
            needs_attention=[CreatorAttention(**a) for a in data.get("needs_attention", [])],
            total_captions=data.get("total_captions", 0),
            fresh_captions=data.get("fresh_captions", 0),
            stale_captions=data.get("stale_captions", 0),
            avg_freshness=data.get("avg_freshness", 0.0),
            successful_analyses=data.get("successful_analyses", 0),
            failed_analyses=data.get("failed_analyses", 0),
            errors=[AnalysisError(**e) for e in data.get("errors", [])],
        )


# =============================================================================
# BATCH ANALYSIS RESULT
# =============================================================================

@dataclass
class BatchAnalysisResult:
    """
    Complete batch analysis result containing all creator analyses.

    This is the top-level container for a full portfolio analysis run.
    """
    # Quick analyses (7-step)
    quick_analyses: list[QuickAnalysisResult] = field(default_factory=list)

    # Deep analyses (9-phase)
    deep_analyses: list[DeepAnalysisResult] = field(default_factory=list)

    # Portfolio summary
    portfolio_summary: PortfolioSummary | None = None

    # Metadata
    analysis_mode: str = ""  # quick, deep, full
    started_at: str = ""
    completed_at: str = ""
    total_duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "quick_analyses": [q.to_dict() for q in self.quick_analyses],
            "deep_analyses": [d.to_dict() for d in self.deep_analyses],
            "portfolio_summary": self.portfolio_summary.to_dict() if self.portfolio_summary else None,
            "analysis_mode": self.analysis_mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_json(self, path: Path) -> None:
        """Save to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchAnalysisResult:
        """Create instance from dictionary."""
        return cls(
            quick_analyses=[QuickAnalysisResult.from_dict(q) for q in data.get("quick_analyses", [])],
            deep_analyses=[DeepAnalysisResult.from_dict(d) for d in data.get("deep_analyses", [])],
            portfolio_summary=PortfolioSummary.from_dict(data["portfolio_summary"]) if data.get("portfolio_summary") else None,
            analysis_mode=data.get("analysis_mode", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
        )

    @classmethod
    def load_json(cls, path: Path) -> BatchAnalysisResult:
        """Load from JSON file."""
        data = json.loads(path.read_text())
        return cls.from_dict(data)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class CreatorNotFoundError(DatabaseError):
    """Raised when a creator is not found in the database."""

    def __init__(self, creator_id: str) -> None:
        self.creator_id = creator_id
        super().__init__(f"Creator not found: {creator_id}")


class InsufficientDataError(DatabaseError):
    """Raised when there is insufficient data for analysis."""

    def __init__(self, creator_id: str, data_type: str, required: int = 0, found: int = 0) -> None:
        self.creator_id = creator_id
        self.data_type = data_type
        self.required = required
        self.found = found
        msg = f"Insufficient {data_type} data for creator {creator_id}"
        if required > 0:
            msg += f" (required: {required}, found: {found})"
        super().__init__(msg)


class QueryExecutionError(DatabaseError):
    """Raised when a SQL query fails to execute."""

    def __init__(self, query_name: str, original_error: Exception) -> None:
        self.query_name = query_name
        self.original_error = original_error
        super().__init__(f"Query '{query_name}' failed: {original_error}")


# =============================================================================
# DATABASE MANAGER
# =============================================================================


class DatabaseManager:
    """
    Manages database connections and query execution for batch analysis.

    This class provides:
    - Context manager support for safe connection handling
    - SQL file caching for performance
    - Query result mapping to dataclasses
    - Comprehensive error handling

    Usage:
        with DatabaseManager(db_path) as db:
            creators = db.get_all_active_creators()
            for creator in creators:
                revenue = db.get_revenue_breakdown(creator["creator_id"])

    Or manually:
        db = DatabaseManager(db_path)
        db.connect()
        try:
            creators = db.get_all_active_creators()
        finally:
            db.close()
    """

    # SQL directory relative to this script
    SQL_DIR = Path(__file__).parent.parent / "assets" / "sql" / "batch_analysis"

    def __init__(self, db_path: Path | str) -> None:
        """
        Initialize DatabaseManager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._sql_cache: dict[str, str] = {}

    def connect(self) -> sqlite3.Connection:
        """
        Open database connection.

        Returns:
            Active database connection.

        Raises:
            DatabaseError: If connection fails.
        """
        if self._conn is not None:
            return self._conn

        if not self.db_path.exists():
            raise DatabaseError(f"Database file not found: {self.db_path}")

        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys and optimize for read queries
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA query_only = ON")
            return self._conn
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    def close(self) -> None:
        """Close database connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit."""
        self.close()

    def get_connection(self) -> sqlite3.Connection:
        """
        Get the underlying database connection.

        Returns the active connection, creating one if necessary.
        This method provides controlled access to the connection
        for cases where direct SQL execution is needed.

        Returns:
            Active sqlite3.Connection instance.

        Raises:
            DatabaseError: If connection cannot be established.
        """
        if self._conn is None:
            self.connect()
        return self._conn  # type: ignore[return-value]

    def _load_sql(self, filename: str) -> str:
        """
        Load SQL query from file with caching.

        Args:
            filename: Name of the SQL file (e.g., "get_active_creators.sql").

        Returns:
            SQL query string.

        Raises:
            DatabaseError: If SQL file not found.
        """
        if filename in self._sql_cache:
            return self._sql_cache[filename]

        sql_path = self.SQL_DIR / filename
        if not sql_path.exists():
            raise DatabaseError(f"SQL file not found: {sql_path}")

        sql = sql_path.read_text(encoding="utf-8")
        self._sql_cache[filename] = sql
        return sql

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """
        Execute SQL query and return all results.

        Args:
            sql: SQL query string.
            params: Query parameters (for parameterized queries).

        Returns:
            List of Row objects.

        Raises:
            QueryExecutionError: If query execution fails.
        """
        if self._conn is None:
            self.connect()

        try:
            cursor = self._conn.execute(sql, params)  # type: ignore[union-attr]
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise QueryExecutionError("query", e) from e

    def _execute_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        """
        Execute SQL query and return first result or None.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            Single Row object or None if no results.
        """
        results = self._execute(sql, params)
        return results[0] if results else None

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Convert value to float, handling NULL."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Convert value to int, handling NULL."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _safe_str(self, value: Any, default: str = "") -> str:
        """Convert value to string, handling NULL."""
        if value is None:
            return default
        return str(value)

    # =========================================================================
    # QUERY FUNCTIONS
    # =========================================================================

    def get_all_active_creators(self) -> list[dict[str, Any]]:
        """
        Get all active creators with key metrics.

        Returns:
            List of creator dictionaries with metrics.
        """
        sql = self._load_sql("get_active_creators.sql")
        rows = self._execute(sql)

        creators = []
        for row in rows:
            creators.append({
                "creator_id": row["creator_id"],
                "page_name": row["page_name"],
                "display_name": row["display_name"],
                "page_type": row["page_type"],
                "subscription_price": self._safe_float(row["subscription_price"]),
                "timezone": self._safe_str(row["timezone"]),
                "current_active_fans": self._safe_int(row["current_active_fans"]),
                "current_total_earnings": self._safe_float(row["current_total_earnings"]),
                "current_message_net": self._safe_float(row["current_message_net"]),
                "current_subscription_net": self._safe_float(row["current_subscription_net"]),
                "current_tips_net": self._safe_float(row["current_tips_net"]),
                "current_avg_earnings_per_fan": self._safe_float(row["current_avg_earnings_per_fan"]),
                "current_renew_on_pct": self._safe_float(row["current_renew_on_pct"]),
                "current_of_ranking": self._safe_float(row["current_of_ranking"]),
                "performance_tier": self._safe_int(row["performance_tier"]),
                "metrics_snapshot_date": self._safe_str(row["metrics_snapshot_date"]),
                "persona_type": self._safe_str(row["persona_type"]),
                "account_age_days": self._safe_int(row["account_age_days"]),
                "volume_level": self._safe_str(row["volume_level"]),
                "primary_tone": self._safe_str(row["primary_tone"]),
                "emoji_frequency": self._safe_str(row["emoji_frequency"]),
                "slang_level": self._safe_str(row["slang_level"]),
                "ppv_count_30d": self._safe_int(row["ppv_count_30d"]),
                "ppv_revenue_30d": self._safe_float(row["ppv_revenue_30d"]),
            })

        return creators

    def get_revenue_breakdown(self, creator_id: str) -> RevenueAnalysis:
        """
        Get revenue architecture analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            RevenueAnalysis dataclass with complete revenue breakdown.

        Raises:
            CreatorNotFoundError: If creator not found.
        """
        sql = self._load_sql("revenue_breakdown.sql")
        row = self._execute_one(sql, (creator_id,))

        if row is None:
            raise CreatorNotFoundError(creator_id)

        return RevenueAnalysis(
            total_earnings=self._safe_float(row["total_earnings"]),
            subscription_net=self._safe_float(row["subscription_revenue"]),
            message_net=self._safe_float(row["message_revenue"]),
            tips_net=self._safe_float(row["tips_revenue"]),
            posts_net=self._safe_float(row["posts_revenue"]),
            msg_pct=self._safe_float(row["message_pct"]),
            sub_pct=self._safe_float(row["subscription_pct"]),
            msg_sub_ratio=self._safe_float(row["message_sub_ratio"]),
            earnings_per_fan=self._safe_float(row["earnings_per_fan"]),
            spend_per_spender=self._safe_float(row["spend_per_spender"]),
            renew_on_pct=self._safe_float(row["renew_on_pct"]),
            contribution_pct=self._safe_float(row["current_contribution_pct"]),
            msg_sub_rating=self._safe_str(row["msg_sub_rating"]),
            earnings_per_fan_rating=self._safe_str(row["earnings_per_fan_rating"]),
            renew_on_rating=self._safe_str(row["renew_on_rating"]),
        )

    def get_ppv_metrics(self, creator_id: str) -> PPVAnalysis:
        """
        Get PPV performance deep dive for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            PPVAnalysis dataclass with comprehensive PPV metrics.

        Raises:
            InsufficientDataError: If no PPV data found.
        """
        sql = self._load_sql("ppv_metrics.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        # The ORDER BY is optional since we parse by section anyway
        sql = sql.replace(
            """ORDER BY
    CASE section
        WHEN 'overall' THEN 1
        WHEN 'monthly' THEN 2
        WHEN 'weekly_comparison' THEN 3
    END,
    sort_order;""",
            ";"
        )
        # Query uses creator_id 4 times
        rows = self._execute(sql, (creator_id, creator_id, creator_id, creator_id))

        if not rows:
            raise InsufficientDataError(creator_id, "PPV")

        # Parse sections
        overall_data: dict[str, Any] = {}
        monthly_trends: list[MonthlyTrend] = []
        current_week_data: dict[str, Any] = {}
        previous_week_data: dict[str, Any] = {}

        for row in rows:
            section = row["section"]

            if section == "overall":
                overall_data = {
                    "total_ppvs": self._safe_int(row["metric_int"]),
                    "total_revenue": self._safe_float(row["metric_float"]),
                    "avg_earnings": self._safe_float(row["metric_float2"]),
                    "view_rate_pct": self._safe_float(row["rate1"]),
                    "purchase_rate_pct": self._safe_float(row["rate2"]),
                    "revenue_per_send": self._safe_float(row["rate3"]),
                    "avg_price": self._safe_float(row["price"]),
                    "view_rate_rating": self._safe_str(row["view_rate_rating"]),
                    "purchase_rate_rating": self._safe_str(row["purchase_rate_rating"]),
                    "rps_rating": self._safe_str(row["rps_rating"]),
                }

            elif section == "monthly":
                monthly_trends.append(MonthlyTrend(
                    month=self._safe_str(row["view_rate_rating"]),  # month stored in this column
                    ppv_count=self._safe_int(row["metric_int"]),
                    revenue=self._safe_float(row["metric_float"]),
                    avg_earnings=self._safe_float(row["metric_float2"]),
                    purchase_rate=self._safe_float(row["rate1"]),
                    revenue_per_send=self._safe_float(row["rate2"]),
                ))

            elif section == "weekly_comparison":
                period = row["view_rate_rating"]  # period stored in this column
                if period == "current_week":
                    current_week_data = {
                        "ppvs": self._safe_int(row["metric_int"]),
                        "revenue": self._safe_float(row["metric_float"]),
                        "purchase_rate": self._safe_float(row["rate1"]),
                    }
                elif period == "previous_week":
                    previous_week_data = {
                        "ppvs": self._safe_int(row["metric_int"]),
                        "revenue": self._safe_float(row["metric_float"]),
                        "purchase_rate": self._safe_float(row["rate1"]),
                    }

        # Build week-over-week comparison
        week_over_week: WeekOverWeek | None = None
        if current_week_data and previous_week_data:
            curr_revenue = current_week_data.get("revenue", 0.0)
            prev_revenue = previous_week_data.get("revenue", 0.0)
            curr_rate = current_week_data.get("purchase_rate", 0.0)
            prev_rate = previous_week_data.get("purchase_rate", 0.0)

            revenue_change = ((curr_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0.0
            rate_change = ((curr_rate - prev_rate) / prev_rate * 100) if prev_rate > 0 else 0.0

            week_over_week = WeekOverWeek(
                current_week_ppvs=current_week_data.get("ppvs", 0),
                current_week_revenue=curr_revenue,
                current_week_purchase_rate=curr_rate,
                previous_week_ppvs=previous_week_data.get("ppvs", 0),
                previous_week_revenue=prev_revenue,
                previous_week_purchase_rate=prev_rate,
                revenue_change_pct=round(revenue_change, 1),
                purchase_rate_change_pct=round(rate_change, 1),
            )

        # Calculate earnings volatility (standard deviation / mean)
        # Using monthly data for volatility calculation
        if len(monthly_trends) >= 2:
            earnings_values = [t.avg_earnings for t in monthly_trends if t.avg_earnings > 0]
            if earnings_values:
                mean_earnings = sum(earnings_values) / len(earnings_values)
                variance = sum((e - mean_earnings) ** 2 for e in earnings_values) / len(earnings_values)
                volatility = (variance ** 0.5) / mean_earnings * 100 if mean_earnings > 0 else 0.0
            else:
                volatility = 0.0
        else:
            volatility = 0.0

        return PPVAnalysis(
            total_ppvs=overall_data.get("total_ppvs", 0),
            total_revenue=overall_data.get("total_revenue", 0.0),
            avg_earnings=overall_data.get("avg_earnings", 0.0),
            view_rate_pct=overall_data.get("view_rate_pct", 0.0),
            purchase_rate_pct=overall_data.get("purchase_rate_pct", 0.0),
            revenue_per_send=overall_data.get("revenue_per_send", 0.0),
            avg_price=overall_data.get("avg_price", 0.0),
            earnings_volatility=round(volatility, 1),
            monthly_trends=monthly_trends,
            week_over_week=week_over_week,
            view_rate_rating=overall_data.get("view_rate_rating", ""),
            purchase_rate_rating=overall_data.get("purchase_rate_rating", ""),
            rps_rating=overall_data.get("rps_rating", ""),
        )

    def get_timing_analysis(self, creator_id: str) -> TimingAnalysis:
        """
        Get timing optimization analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            TimingAnalysis dataclass with hourly and daily performance.
        """
        sql = self._load_sql("timing_analysis.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section
        WHEN 'hourly' THEN 1
        WHEN 'daily' THEN 2
        WHEN 'heatmap' THEN 3
    END,
    rank_by_earnings;""",
            ";"
        )
        # Query uses creator_id 3 times
        rows = self._execute(sql, (creator_id, creator_id, creator_id))

        hourly_performance: list[HourlyPerformance] = []
        daily_performance: list[DailyPerformance] = []
        top_combinations: list[HeatmapEntry] = []

        for row in rows:
            section = row["section"]

            if section == "hourly":
                hourly_performance.append(HourlyPerformance(
                    hour=self._safe_int(row["key_int"]),
                    count=self._safe_int(row["count"]),
                    total_revenue=self._safe_float(row["total_revenue"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                    purchase_rate=self._safe_float(row["purchase_rate_pct"]),
                    revenue_per_send=self._safe_float(row["rps"]),
                ))

            elif section == "daily":
                daily_performance.append(DailyPerformance(
                    day=self._safe_str(row["key_text"]),
                    day_number=self._safe_int(row["key_int"]),
                    count=self._safe_int(row["count"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                    purchase_rate=self._safe_float(row["purchase_rate_pct"]),
                ))

            elif section == "heatmap":
                top_combinations.append(HeatmapEntry(
                    day=self._safe_str(row["key_text"]),
                    hour=self._safe_int(row["key_int"]),
                    count=self._safe_int(row["count"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                ))

        # Extract best hours and days (top 3 by earnings)
        sorted_hourly = sorted(hourly_performance, key=lambda x: x.avg_earnings, reverse=True)
        best_hours = [h.hour for h in sorted_hourly[:3]]

        sorted_daily = sorted(daily_performance, key=lambda x: x.avg_earnings, reverse=True)
        best_days = [d.day for d in sorted_daily[:3]]

        return TimingAnalysis(
            hourly_performance=hourly_performance,
            daily_performance=daily_performance,
            top_combinations=top_combinations[:10],  # Limit to top 10
            best_hours=best_hours,
            best_days=best_days,
        )

    def get_content_performance(self, creator_id: str) -> ContentAnalysis:
        """
        Get content type performance analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            ContentAnalysis dataclass with content rankings and gap analysis.
        """
        sql = self._load_sql("content_performance.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section WHEN 'performance' THEN 1 ELSE 2 END,
    rank_by_earnings;""",
            ";"
        )
        # Query uses creator_id 2 times
        rows = self._execute(sql, (creator_id, creator_id))

        content_rankings: list[ContentTypePerformance] = []
        content_gaps: list[ContentGap] = []

        for row in rows:
            section = row["section"]

            if section == "performance":
                content_rankings.append(ContentTypePerformance(
                    type_name=self._safe_str(row["type_name"]),
                    type_category=self._safe_str(row["type_category"]),
                    uses=self._safe_int(row["uses"]),
                    total_revenue=self._safe_float(row["total_revenue"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                    view_rate=self._safe_float(row["view_rate_pct"]),
                    purchase_rate=self._safe_float(row["purchase_rate_pct"]),
                    avg_price=self._safe_float(row["avg_price"]),
                ))

            elif section == "gap_analysis":
                content_gaps.append(ContentGap(
                    type_name=self._safe_str(row["type_name"]),
                    type_category=self._safe_str(row["type_category"]),
                    in_vault=bool(row["in_vault"]),
                    quantity=self._safe_int(row["quantity"]),
                    quality_rating=row["quality_rating"] if row["quality_rating"] else None,
                    times_used=self._safe_int(row["uses"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]) if row["avg_earnings"] else None,
                    status=self._safe_str(row["status"]),
                ))

        # Extract top content types (top 3 by earnings)
        sorted_rankings = sorted(content_rankings, key=lambda x: x.avg_earnings, reverse=True)
        top_content_types = [c.type_name for c in sorted_rankings[:3]]

        # Extract underutilized types (UNTAPPED status)
        underutilized_types = [g.type_name for g in content_gaps if g.status == "UNTAPPED"]

        return ContentAnalysis(
            content_rankings=content_rankings,
            content_gaps=content_gaps,
            top_content_types=top_content_types,
            underutilized_types=underutilized_types,
        )

    def get_pricing_analysis(self, creator_id: str) -> PricingAnalysis:
        """
        Get pricing strategy analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            PricingAnalysis dataclass with tier performance and optimal pricing.
        """
        sql = self._load_sql("pricing_analysis.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section
        WHEN 'price_tier' THEN 1
        WHEN 'optimal_by_content' THEN 2
        WHEN 'sensitivity' THEN 3
    END,
    sort_key;""",
            ";"
        )
        # Query uses creator_id 3 times
        rows = self._execute(sql, (creator_id, creator_id, creator_id))

        price_tier_performance: list[PriceTierPerformance] = []
        optimal_prices: list[OptimalPrice] = []
        sensitivity_data: dict[str, dict[str, Any]] = {}

        for row in rows:
            section = row["section"]

            if section == "price_tier":
                price_tier_performance.append(PriceTierPerformance(
                    price_tier=self._safe_str(row["key_text"]),
                    count=self._safe_int(row["count"]),
                    total_revenue=self._safe_float(row["total_revenue"]),
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                    purchase_rate=self._safe_float(row["purchase_rate_pct"]),
                    revenue_per_send=self._safe_float(row["rps"]),
                ))

            elif section == "optimal_by_content":
                optimal_prices.append(OptimalPrice(
                    type_name=self._safe_str(row["key_text"]),
                    avg_price=self._safe_float(row["sort_key"]),  # avg_price stored as sort_key
                    avg_earnings=self._safe_float(row["avg_earnings"]),
                    purchase_rate=self._safe_float(row["purchase_rate_pct"]),
                    recommended_price=None,  # Can be calculated based on pricing_recommendation
                ))

            elif section == "sensitivity":
                segment = self._safe_str(row["key_text"])
                sensitivity_data[segment] = {
                    "count": self._safe_int(row["count"]),
                    "total_revenue": self._safe_float(row["total_revenue"]),
                    "avg_earnings": self._safe_float(row["avg_earnings"]),
                    "purchase_rate": self._safe_float(row["purchase_rate_pct"]),
                }

        # Calculate recommended price range from tier performance
        if price_tier_performance:
            # Find tier with best revenue per send
            best_tier = max(price_tier_performance, key=lambda x: x.revenue_per_send)
            # Extract numeric range from tier name (e.g., "$11-15" -> 11, 15)
            tier_range = best_tier.price_tier.replace("$", "").replace("+", "-50")
            parts = tier_range.split("-")
            if len(parts) == 2:
                try:
                    min_price = float(parts[0])
                    max_price = float(parts[1])
                    sweet_spot = (min_price + max_price) / 2
                    recommended_price_range = {
                        "min": min_price,
                        "max": max_price,
                        "sweet_spot": round(sweet_spot, 2),
                    }
                except ValueError:
                    recommended_price_range = {}
            else:
                recommended_price_range = {}
        else:
            recommended_price_range = {}

        return PricingAnalysis(
            price_tier_performance=price_tier_performance,
            optimal_prices=optimal_prices,
            recommended_price_range=recommended_price_range,
        )

    def get_caption_health(self, creator_id: str) -> CaptionAnalysis:
        """
        Get caption intelligence analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            CaptionAnalysis dataclass with caption health metrics.
        """
        sql = self._load_sql("caption_health.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section
        WHEN 'health_summary' THEN 1
        WHEN 'top_performers' THEN 2
        WHEN 'underperformers' THEN 3
        WHEN 'tone_effectiveness' THEN 4
    END,
    sort_order;""",
            ";"
        )
        # Query uses creator_id 4 times
        rows = self._execute(sql, (creator_id, creator_id, creator_id, creator_id))

        # Initialize with defaults
        total_captions = 0
        avg_freshness = 0.0
        fresh_count = 0
        stale_count = 0
        critical_stale_count = 0
        top_captions: list[CaptionPerformance] = []
        bottom_captions: list[CaptionPerformance] = []
        tone_effectiveness: list[TonePerformance] = []

        for row in rows:
            section = row["section"]

            if section == "health_summary":
                total_captions = self._safe_int(row["metric_int1"])
                fresh_count = self._safe_int(row["metric_int2"])
                stale_count = self._safe_int(row["metric_int3"])
                critical_stale_count = self._safe_int(row["metric_int4"])
                avg_freshness = self._safe_float(row["metric_float1"])

            elif section == "top_performers":
                top_captions.append(CaptionPerformance(
                    caption_id=self._safe_str(row["caption_id"]),
                    preview=self._safe_str(row["preview"]),
                    tone=row["tone"] if row["tone"] else None,
                    performance_score=self._safe_float(row["metric_int2"]) if row["metric_int2"] else None,
                    freshness_score=self._safe_float(row["metric_int3"]),
                    times_used=self._safe_int(row["metric_int1"]),
                    avg_earnings=self._safe_float(row["metric_float1"]),
                ))

            elif section == "underperformers":
                bottom_captions.append(CaptionPerformance(
                    caption_id=self._safe_str(row["caption_id"]),
                    preview=self._safe_str(row["preview"]),
                    tone=row["tone"] if row["tone"] else None,
                    performance_score=None,
                    freshness_score=self._safe_float(row["metric_int3"]),
                    times_used=self._safe_int(row["metric_int1"]),
                    avg_earnings=self._safe_float(row["metric_float1"]),
                ))

            elif section == "tone_effectiveness":
                tone_effectiveness.append(TonePerformance(
                    tone=self._safe_str(row["tone"]),
                    count=self._safe_int(row["metric_int1"]),
                    avg_earnings=self._safe_float(row["metric_float1"]),
                ))

        # Determine caption health rating
        if avg_freshness >= 70 and critical_stale_count == 0:
            caption_health_rating = "Excellent"
        elif avg_freshness >= 50 and critical_stale_count <= 5:
            caption_health_rating = "Good"
        elif avg_freshness >= 30:
            caption_health_rating = "Needs Attention"
        else:
            caption_health_rating = "Critical"

        return CaptionAnalysis(
            total_captions=total_captions,
            avg_freshness=avg_freshness,
            fresh_count=fresh_count,
            stale_count=stale_count,
            critical_stale_count=critical_stale_count,
            top_captions=top_captions,
            bottom_captions=bottom_captions,
            tone_effectiveness=tone_effectiveness,
            caption_health_rating=caption_health_rating,
        )

    def get_persona_profile(self, creator_id: str) -> PersonaAnalysis:
        """
        Get persona and voice analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            PersonaAnalysis dataclass with persona attributes.

        Raises:
            CreatorNotFoundError: If creator not found.
        """
        sql = self._load_sql("persona_profile.sql")
        row = self._execute_one(sql, (creator_id,))

        if row is None:
            raise CreatorNotFoundError(creator_id)

        # Determine communication style from attributes
        primary_tone = self._safe_str(row["primary_tone"])
        slang_level = self._safe_str(row["slang_level"])
        emoji_freq = self._safe_str(row["emoji_frequency"])

        if primary_tone in ("playful", "flirty") and slang_level in ("heavy", "light"):
            communication_style = "playful"
        elif primary_tone in ("professional", "informative") and emoji_freq in ("none", "light"):
            communication_style = "professional"
        elif primary_tone in ("intimate", "romantic"):
            communication_style = "intimate"
        elif primary_tone in ("teasing", "naughty"):
            communication_style = "provocative"
        else:
            communication_style = "casual"

        # Derive sentiment label from avg_sentiment
        avg_sentiment = self._safe_float(row["avg_sentiment"])
        if avg_sentiment > 0.5:
            sentiment_label = "very positive"
        elif avg_sentiment > 0.2:
            sentiment_label = "positive"
        elif avg_sentiment > -0.2:
            sentiment_label = "neutral"
        elif avg_sentiment > -0.5:
            sentiment_label = "negative"
        else:
            sentiment_label = "very negative"

        return PersonaAnalysis(
            primary_tone=primary_tone,
            secondary_tone="",  # Not provided in current query
            emoji_frequency=self._safe_str(row["emoji_frequency"]),
            favorite_emojis=self._safe_str(row["favorite_emojis"]),
            slang_level=slang_level,
            avg_sentiment=avg_sentiment,
            sentiment_label=sentiment_label,
            avg_caption_length=self._safe_int(row["avg_caption_length"]),
            communication_style=communication_style,
        )

    def get_portfolio_positioning(self, creator_id: str) -> PortfolioPosition:
        """
        Get portfolio positioning analysis for a creator.

        Args:
            creator_id: The creator's unique identifier.

        Returns:
            PortfolioPosition dataclass with rankings and tier comparison.

        Raises:
            CreatorNotFoundError: If creator not found.
        """
        sql = self._load_sql("portfolio_positioning.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section WHEN 'creator_position' THEN 1 ELSE 2 END,
    performance_tier;""",
            ";"
        )
        rows = self._execute(sql, (creator_id,))

        if not rows:
            raise CreatorNotFoundError(creator_id)

        # Parse sections
        creator_data: dict[str, Any] = {}
        tier_data: dict[str, Any] = {}

        for row in rows:
            section = row["section"]

            if section == "creator_position":
                creator_data = {
                    "earnings_rank": self._safe_int(row["earnings_rank"]),
                    "fans_rank": self._safe_int(row["fans_rank"]),
                    "efficiency_rank": self._safe_int(row["efficiency_rank"]),
                    "earnings_percentile": int(100 - self._safe_float(row["earnings_percentile"])),
                    "fans_percentile": int(100 - self._safe_float(row["fans_percentile"])),
                    "efficiency_percentile": int(100 - self._safe_float(row["efficiency_percentile"])),
                    "performance_tier": self._safe_int(row["performance_tier"]),
                    "tier_avg_earnings": self._safe_float(row["tier_avg_earnings"]),
                    "tier_avg_fans": self._safe_float(row["tier_avg_fans"]),
                    "tier_avg_efficiency": self._safe_float(row["tier_avg_efficiency"]),
                    "total_creators": self._safe_int(row["total_creators"]),
                }

            elif section == "tier_summary":
                tier_num = self._safe_int(row["performance_tier"])
                if tier_num == creator_data.get("performance_tier"):
                    tier_data = {
                        "tier": tier_num,
                        "tier_count": self._safe_int(row["total_creators"]),
                        "tier_avg_earnings": self._safe_float(row["earnings"]),
                        "tier_avg_fans": self._safe_float(row["fans"]),
                        "tier_avg_efficiency": self._safe_float(row["efficiency"]),
                        "tier_avg_renew_pct": self._safe_float(row["renew_pct"]),
                    }

        if not creator_data:
            raise CreatorNotFoundError(creator_id)

        # Build tier comparison
        tier_comparison: TierComparison | None = None
        if tier_data:
            tier_comparison = TierComparison(
                tier=tier_data["tier"],
                tier_count=tier_data["tier_count"],
                tier_avg_earnings=tier_data["tier_avg_earnings"],
                tier_avg_fans=tier_data["tier_avg_fans"],
                tier_avg_efficiency=tier_data["tier_avg_efficiency"],
                tier_avg_renew_pct=tier_data["tier_avg_renew_pct"],
            )

        # Determine competitive position based on percentiles
        earnings_pct = creator_data["earnings_percentile"]
        if earnings_pct >= 90:
            competitive_position = "Elite Performer"
        elif earnings_pct >= 75:
            competitive_position = "Top Performer"
        elif earnings_pct >= 50:
            competitive_position = "Strong Performer"
        elif earnings_pct >= 25:
            competitive_position = "Developing"
        else:
            competitive_position = "Growth Opportunity"

        return PortfolioPosition(
            earnings_rank=creator_data["earnings_rank"],
            fans_rank=creator_data["fans_rank"],
            efficiency_rank=creator_data["efficiency_rank"],
            earnings_percentile=creator_data["earnings_percentile"],
            fans_percentile=creator_data["fans_percentile"],
            efficiency_percentile=creator_data["efficiency_percentile"],
            tier_comparison=tier_comparison,
            competitive_position=competitive_position,
        )

    def get_portfolio_summary(self) -> dict[str, Any]:
        """
        Get portfolio-wide summary statistics.

        Returns:
            Dictionary with portfolio aggregates, tier distribution,
            top performers, and health metrics.
        """
        sql = self._load_sql("portfolio_summary.sql")
        # Remove the ORDER BY clause that references 'section' which doesn't work with UNION ALL
        sql = sql.replace(
            """ORDER BY
    CASE section
        WHEN 'portfolio_totals' THEN 1
        WHEN 'tier_distribution' THEN 2
        WHEN 'top_by_revenue' THEN 3
        WHEN 'top_by_fans' THEN 4
        WHEN 'top_by_efficiency' THEN 5
        WHEN 'caption_health' THEN 6
        WHEN 'recent_ppv_30d' THEN 7
    END,
    sort_order;""",
            ";"
        )
        rows = self._execute(sql)

        result: dict[str, Any] = {
            "totals": {},
            "tier_distribution": {},
            "top_by_revenue": [],
            "top_by_fans": [],
            "top_by_efficiency": [],
            "caption_health": {},
            "recent_ppv_30d": {},
        }

        for row in rows:
            section = row["section"]

            if section == "portfolio_totals":
                result["totals"] = {
                    "total_creators": self._safe_int(row["total_creators"]),
                    "active_creators": self._safe_int(row["active_creators"]),
                    "total_earnings": self._safe_float(row["total_earnings"]),
                    "total_message_revenue": self._safe_float(row["total_message_revenue"]),
                    "total_subscription_revenue": self._safe_float(row["total_subscription_revenue"]),
                    "total_fans": self._safe_int(row["total_fans"]),
                    "avg_earnings_per_creator": self._safe_float(row["avg_earnings_per_creator"]),
                    "avg_fans_per_creator": self._safe_int(row["avg_fans_per_creator"]),
                    "avg_earnings_per_fan": self._safe_float(row["avg_earnings_per_fan"]),
                    "avg_renew_pct": self._safe_float(row["avg_renew_pct"]),
                    "avg_msg_sub_ratio": self._safe_float(row["avg_msg_sub_ratio"]),
                }

            elif section == "tier_distribution":
                tier_name = self._safe_str(row["identifier"])
                tier_num = tier_name.replace("Tier ", "")
                result["tier_distribution"][tier_num] = {
                    "count": self._safe_int(row["total_creators"]),
                    "tier_earnings": self._safe_float(row["total_earnings"]),
                    "avg_earnings": self._safe_float(row["total_message_revenue"]),
                    "tier_fans": self._safe_int(row["total_fans"]),
                    "pct_of_portfolio": self._safe_float(row["avg_earnings_per_creator"]),
                }

            elif section == "top_by_revenue":
                result["top_by_revenue"].append({
                    "page_name": self._safe_str(row["identifier"]),
                    "performance_tier": self._safe_int(row["total_creators"]),
                    "fans": self._safe_int(row["active_creators"]),
                    "earnings": self._safe_float(row["total_earnings"]),
                    "rank": self._safe_int(row["sort_order"]),
                })

            elif section == "top_by_fans":
                result["top_by_fans"].append({
                    "page_name": self._safe_str(row["identifier"]),
                    "performance_tier": self._safe_int(row["total_creators"]),
                    "fans": self._safe_int(row["active_creators"]),
                    "earnings": self._safe_float(row["total_earnings"]),
                    "rank": self._safe_int(row["sort_order"]),
                })

            elif section == "top_by_efficiency":
                result["top_by_efficiency"].append({
                    "page_name": self._safe_str(row["identifier"]),
                    "performance_tier": self._safe_int(row["total_creators"]),
                    "fans": self._safe_int(row["active_creators"]),
                    "earnings": self._safe_float(row["total_earnings"]),
                    "efficiency": self._safe_float(row["total_message_revenue"]),
                    "rank": self._safe_int(row["sort_order"]),
                })

            elif section == "caption_health":
                result["caption_health"] = {
                    "total_captions": self._safe_int(row["total_creators"]),
                    "fresh_count": self._safe_int(row["active_creators"]),
                    "good_count": self._safe_int(row["total_earnings"]),
                    "stale_count": self._safe_int(row["total_message_revenue"]),
                    "critical_count": self._safe_int(row["total_subscription_revenue"]),
                    "avg_freshness": self._safe_float(row["avg_earnings_per_creator"]),
                }

            elif section == "recent_ppv_30d":
                result["recent_ppv_30d"] = {
                    "total_ppvs": self._safe_int(row["total_creators"]),
                    "active_senders": self._safe_int(row["active_creators"]),
                    "total_revenue": self._safe_float(row["total_earnings"]),
                    "avg_earnings": self._safe_float(row["total_message_revenue"]),
                    "avg_purchase_rate": self._safe_float(row["avg_earnings_per_creator"]),
                    "avg_view_rate": self._safe_float(row["avg_fans_per_creator"]),
                }

        return result


# =============================================================================
# PHASE 4: QUICK ANALYSIS FUNCTION (7-Step)
# =============================================================================


def run_quick_analysis(
    db: DatabaseManager,
    creator_id: str,
    creator_name: str,
    display_name: str = ""
) -> QuickAnalysisResult:
    """
    Execute 7-step quick analysis for a single creator.

    The 7 steps are:
    1. Load creator profile
    2. Calculate revenue metrics
    3. Analyze PPV performance
    4. Identify best timing
    5. Evaluate content types
    6. Assess caption health
    7. Generate benchmarks vs agency

    This function reuses the battle-tested `generate_brief` and
    `calculate_agency_benchmarks` functions from analyze_creator.py.

    Args:
        db: DatabaseManager instance with active connection
        creator_id: Creator's unique UUID
        creator_name: Creator's page name (e.g., "missalexa")
        display_name: Optional display name for the creator

    Returns:
        QuickAnalysisResult containing brief and benchmarks

    Raises:
        CreatorNotFoundError: If creator not found in database
        InsufficientDataError: If insufficient data for meaningful analysis
    """
    start_time = time.perf_counter()

    # Get the raw sqlite3 connection for analyze_creator functions
    conn = db.get_connection()

    # Step 1-6: Generate the creator brief
    # This covers:
    #   1. Load creator profile
    #   2. Calculate revenue metrics
    #   3. Analyze PPV performance (historical)
    #   4. Identify best timing (hours/days)
    #   5. Evaluate content types
    #   6. Assess caption health
    brief = generate_brief(
        conn=conn,
        creator_name=creator_name,
        creator_id=creator_id,
        period_days=30  # Default 30-day analysis window
    )

    if brief is None:
        raise CreatorNotFoundError(creator_id)

    # Step 7: Generate agency benchmarks
    # Compare this creator's performance to the agency portfolio
    benchmarks: AgencyBenchmarks | None = None
    try:
        benchmarks = calculate_agency_benchmarks(conn, brief)
    except Exception as e:
        # Log warning but continue - benchmarks are optional
        logger.warning(
            f"Could not calculate agency benchmarks for {creator_name}: {e}"
        )

    # Calculate analysis duration
    end_time = time.perf_counter()
    duration_ms = int((end_time - start_time) * 1000)

    # Build and return the result
    result = QuickAnalysisResult(
        creator_id=creator_id,
        page_name=creator_name,
        display_name=display_name or brief.display_name,
        brief=brief,
        benchmarks=benchmarks,
        analysis_duration_ms=duration_ms,
    )

    logger.info(
        f"Quick analysis complete for {creator_name} in {duration_ms}ms"
    )

    return result


# =============================================================================
# PHASE 5: DEEP ANALYSIS HELPER FUNCTIONS
# =============================================================================


def calculate_health_score(
    revenue: RevenueAnalysis | None,
    ppv: PPVAnalysis | None,
    captions: CaptionAnalysis | None,
    persona: PersonaAnalysis | None,
    position: PortfolioPosition | None,
) -> tuple[int, str]:
    """
    Calculate overall creator health score (0-100) and rating label.

    The health score is a weighted composite of five key areas:
    - Revenue Health (25%): msg:sub ratio, earnings per fan
    - PPV Performance (25%): view rate, purchase rate, RPS
    - Caption Health (20%): freshness, pool size
    - Persona Completeness (15%): profile data quality
    - Portfolio Position (15%): relative ranking

    Args:
        revenue: RevenueAnalysis from Phase 2
        ppv: PPVAnalysis from Phase 3
        captions: CaptionAnalysis from Phase 7
        persona: PersonaAnalysis from Phase 8
        position: PortfolioPosition from Phase 9

    Returns:
        Tuple of (score: int 0-100, rating_label: str)
    """
    total_score = 0.0
    total_weight = 0.0

    # --- Revenue Health (25%) ---
    if revenue is not None:
        revenue_score = 0.0

        # msg:sub ratio (target: 1.0+, excellent: 2.0+)
        if revenue.msg_sub_ratio >= 2.0:
            revenue_score += 40
        elif revenue.msg_sub_ratio >= 1.5:
            revenue_score += 35
        elif revenue.msg_sub_ratio >= 1.0:
            revenue_score += 30
        elif revenue.msg_sub_ratio >= 0.5:
            revenue_score += 20
        else:
            revenue_score += 10

        # earnings per fan (target: $10+, excellent: $20+)
        if revenue.earnings_per_fan >= 20:
            revenue_score += 40
        elif revenue.earnings_per_fan >= 15:
            revenue_score += 35
        elif revenue.earnings_per_fan >= 10:
            revenue_score += 30
        elif revenue.earnings_per_fan >= 5:
            revenue_score += 20
        else:
            revenue_score += 10

        # renew on percentage (target: 30%+, excellent: 50%+)
        if revenue.renew_on_pct >= 50:
            revenue_score += 20
        elif revenue.renew_on_pct >= 40:
            revenue_score += 17
        elif revenue.renew_on_pct >= 30:
            revenue_score += 14
        elif revenue.renew_on_pct >= 20:
            revenue_score += 10
        else:
            revenue_score += 5

        total_score += revenue_score * 0.25
        total_weight += 0.25

    # --- PPV Performance (25%) ---
    if ppv is not None:
        ppv_score = 0.0

        # view rate (target: 50%+, excellent: 70%+)
        if ppv.view_rate_pct >= 70:
            ppv_score += 35
        elif ppv.view_rate_pct >= 60:
            ppv_score += 30
        elif ppv.view_rate_pct >= 50:
            ppv_score += 25
        elif ppv.view_rate_pct >= 40:
            ppv_score += 20
        else:
            ppv_score += 10

        # purchase rate (target: 5%+, excellent: 10%+)
        if ppv.purchase_rate_pct >= 10:
            ppv_score += 35
        elif ppv.purchase_rate_pct >= 7:
            ppv_score += 30
        elif ppv.purchase_rate_pct >= 5:
            ppv_score += 25
        elif ppv.purchase_rate_pct >= 3:
            ppv_score += 20
        else:
            ppv_score += 10

        # revenue per send (target: $0.50+, excellent: $1.00+)
        if ppv.revenue_per_send >= 1.00:
            ppv_score += 30
        elif ppv.revenue_per_send >= 0.75:
            ppv_score += 25
        elif ppv.revenue_per_send >= 0.50:
            ppv_score += 20
        elif ppv.revenue_per_send >= 0.25:
            ppv_score += 15
        else:
            ppv_score += 8

        total_score += ppv_score * 0.25
        total_weight += 0.25

    # --- Caption Health (20%) ---
    if captions is not None:
        caption_score = 0.0

        # avg freshness (target: 50+, excellent: 80+)
        if captions.avg_freshness >= 80:
            caption_score += 50
        elif captions.avg_freshness >= 65:
            caption_score += 42
        elif captions.avg_freshness >= 50:
            caption_score += 35
        elif captions.avg_freshness >= 35:
            caption_score += 25
        else:
            caption_score += 10

        # pool size (target: 50+, excellent: 100+)
        if captions.total_captions >= 100:
            caption_score += 30
        elif captions.total_captions >= 75:
            caption_score += 25
        elif captions.total_captions >= 50:
            caption_score += 20
        elif captions.total_captions >= 25:
            caption_score += 15
        else:
            caption_score += 8

        # critical stale count penalty
        if captions.critical_stale_count == 0:
            caption_score += 20
        elif captions.critical_stale_count <= 3:
            caption_score += 15
        elif captions.critical_stale_count <= 5:
            caption_score += 10
        elif captions.critical_stale_count <= 10:
            caption_score += 5
        # else no bonus

        total_score += caption_score * 0.20
        total_weight += 0.20

    # --- Persona Completeness (15%) ---
    if persona is not None:
        persona_score = 0.0

        # Check core attributes presence
        if persona.primary_tone:
            persona_score += 25
        if persona.emoji_frequency:
            persona_score += 20
        if persona.slang_level:
            persona_score += 20
        if persona.communication_style:
            persona_score += 20
        if persona.avg_caption_length > 0:
            persona_score += 15

        total_score += persona_score * 0.15
        total_weight += 0.15

    # --- Portfolio Position (15%) ---
    if position is not None:
        position_score = 0.0

        # earnings percentile (top 10% = excellent)
        if position.earnings_percentile >= 90:
            position_score += 40
        elif position.earnings_percentile >= 75:
            position_score += 35
        elif position.earnings_percentile >= 50:
            position_score += 28
        elif position.earnings_percentile >= 25:
            position_score += 20
        else:
            position_score += 10

        # efficiency percentile
        if position.efficiency_percentile >= 90:
            position_score += 35
        elif position.efficiency_percentile >= 75:
            position_score += 30
        elif position.efficiency_percentile >= 50:
            position_score += 23
        elif position.efficiency_percentile >= 25:
            position_score += 15
        else:
            position_score += 8

        # competitive position bonus
        competitive_bonuses = {
            "Elite Performer": 25,
            "Top Performer": 20,
            "Strong Performer": 15,
            "Developing": 10,
            "Growth Opportunity": 5,
        }
        position_score += competitive_bonuses.get(position.competitive_position, 5)

        total_score += position_score * 0.15
        total_weight += 0.15

    # Normalize score to 0-100 based on available data
    if total_weight > 0:
        final_score = int(round(total_score / total_weight))
    else:
        final_score = 0

    # Clamp to 0-100
    final_score = max(0, min(100, final_score))

    # Determine rating label
    if final_score >= 85:
        rating = HealthRating.EXCELLENT.value
    elif final_score >= 70:
        rating = HealthRating.GOOD.value
    elif final_score >= 50:
        rating = HealthRating.AVERAGE.value
    elif final_score >= 30:
        rating = HealthRating.BELOW_AVERAGE.value
    else:
        rating = HealthRating.CRITICAL.value

    return final_score, rating


def generate_priorities(
    revenue: RevenueAnalysis | None,
    ppv: PPVAnalysis | None,
    timing: TimingAnalysis | None,
    content: ContentAnalysis | None,
    captions: CaptionAnalysis | None,
) -> list[str]:
    """
    Generate top 5 strategic priorities based on analysis data.

    Priorities are ordered by potential revenue impact and urgency.

    Args:
        revenue: RevenueAnalysis from Phase 2
        ppv: PPVAnalysis from Phase 3
        timing: TimingAnalysis from Phase 4
        content: ContentAnalysis from Phase 5
        captions: CaptionAnalysis from Phase 7

    Returns:
        List of up to 5 priority strings, most important first.
    """
    priorities: list[tuple[int, str]] = []  # (urgency_score, priority_text)

    # --- Revenue Priorities ---
    if revenue is not None:
        # Low msg:sub ratio - major revenue opportunity
        if revenue.msg_sub_ratio < 0.5:
            priorities.append((
                100,
                "CRITICAL: Increase PPV messaging volume - msg:sub ratio is severely low "
                f"({revenue.msg_sub_ratio:.2f}x). Target 1.0x minimum."
            ))
        elif revenue.msg_sub_ratio < 1.0:
            priorities.append((
                80,
                f"Increase PPV messaging frequency - msg:sub ratio ({revenue.msg_sub_ratio:.2f}x) "
                "below target. Aim for 1.5x for optimal revenue."
            ))

        # Low earnings per fan
        if revenue.earnings_per_fan < 5:
            priorities.append((
                85,
                f"Improve monetization efficiency - earnings per fan (${revenue.earnings_per_fan:.2f}) "
                "is below industry standard ($10+). Review pricing and engagement."
            ))
        elif revenue.earnings_per_fan < 10:
            priorities.append((
                65,
                f"Optimize fan monetization - earnings per fan (${revenue.earnings_per_fan:.2f}) "
                "has room for improvement. Target $15-20 range."
            ))

        # Low renewal rate
        if revenue.renew_on_pct < 20:
            priorities.append((
                90,
                f"Address subscriber retention crisis - renewal rate ({revenue.renew_on_pct:.1f}%) "
                "is critically low. Focus on engagement and value delivery."
            ))
        elif revenue.renew_on_pct < 30:
            priorities.append((
                70,
                f"Improve subscriber retention - renewal rate ({revenue.renew_on_pct:.1f}%) "
                "needs attention. Target 40%+ for stability."
            ))

    # --- PPV Priorities ---
    if ppv is not None:
        # Low purchase rate
        if ppv.purchase_rate_pct < 3:
            priorities.append((
                88,
                f"Revamp PPV strategy - purchase rate ({ppv.purchase_rate_pct:.1f}%) "
                "is below threshold. Review pricing, timing, and content quality."
            ))
        elif ppv.purchase_rate_pct < 5:
            priorities.append((
                68,
                f"Optimize PPV conversion - purchase rate ({ppv.purchase_rate_pct:.1f}%) "
                "can be improved. Test different price points and content types."
            ))

        # Low view rate
        if ppv.view_rate_pct < 40:
            priorities.append((
                75,
                f"Improve message engagement - view rate ({ppv.view_rate_pct:.1f}%) "
                "suggests timing or subject line issues. Optimize send schedule."
            ))

        # Low RPS
        if ppv.revenue_per_send < 0.25:
            priorities.append((
                72,
                f"Increase revenue per send (${ppv.revenue_per_send:.2f}) - "
                "consider raising prices or improving content quality."
            ))

    # --- Caption Priorities ---
    if captions is not None:
        # Critical caption freshness
        if captions.avg_freshness < 30:
            priorities.append((
                95,
                "URGENT: Caption library critically stale - average freshness "
                f"({captions.avg_freshness:.0f}%) below minimum. Add new captions immediately."
            ))
        elif captions.avg_freshness < 50:
            priorities.append((
                60,
                f"Refresh caption library - freshness ({captions.avg_freshness:.0f}%) "
                "is declining. Schedule new caption creation this week."
            ))

        # Small caption pool
        if captions.total_captions < 25:
            priorities.append((
                78,
                f"Expand caption library - only {captions.total_captions} captions available. "
                "Target 75+ for adequate rotation and variety."
            ))

        # Too many critical stale
        if captions.critical_stale_count > 10:
            priorities.append((
                73,
                f"Archive stale captions - {captions.critical_stale_count} captions are critically "
                "overused. Mark for retirement or rewrite."
            ))

    # --- Timing Priorities ---
    if timing is not None:
        # Check if utilizing best hours
        if len(timing.best_hours) >= 3 and len(timing.hourly_performance) > 0:
            # See if top 3 hours have significantly better performance
            best_hour_earnings = [
                h.avg_earnings for h in timing.hourly_performance if h.hour in timing.best_hours
            ]
            if best_hour_earnings and timing.hourly_performance:
                avg_best = sum(best_hour_earnings) / len(best_hour_earnings)
                all_avg = sum(h.avg_earnings for h in timing.hourly_performance) / len(timing.hourly_performance)
                if avg_best > all_avg * 1.3:  # 30% better
                    best_hours_str = ", ".join(f"{h}:00" for h in timing.best_hours[:3])
                    priorities.append((
                        55,
                        f"Optimize posting schedule - peak hours ({best_hours_str}) "
                        f"show {((avg_best/all_avg)-1)*100:.0f}% better earnings. Concentrate sends here."
                    ))

    # --- Content Priorities ---
    if content is not None:
        # Underutilized content types
        if content.underutilized_types:
            untapped = ", ".join(content.underutilized_types[:3])
            priorities.append((
                50,
                f"Explore untapped content types: {untapped} - "
                "available in vault but rarely used in PPVs."
            ))

        # Content type diversification
        if content.top_content_types and len(content.content_rankings) > 3:
            top_revenue_share = sum(
                c.total_revenue for c in content.content_rankings[:2]
            ) / max(sum(c.total_revenue for c in content.content_rankings), 1) * 100
            if top_revenue_share > 80:
                priorities.append((
                    45,
                    f"Diversify content strategy - top 2 types account for {top_revenue_share:.0f}% "
                    "of revenue. Test other formats to reduce dependency."
                ))

    # Sort by urgency (highest first) and take top 5
    priorities.sort(key=lambda x: x[0], reverse=True)
    return [p[1] for p in priorities[:5]]


def generate_quick_wins(
    timing: TimingAnalysis | None,
    pricing: PricingAnalysis | None,
    content: ContentAnalysis | None,
) -> list[QuickWin]:
    """
    Generate actionable quick wins implementable this week.

    Quick wins are low-effort, high-impact changes that can be
    implemented immediately without significant resource investment.

    Args:
        timing: TimingAnalysis from Phase 4
        pricing: PricingAnalysis from Phase 6
        content: ContentAnalysis from Phase 5

    Returns:
        List of QuickWin objects with action, implementation, and expected impact.
    """
    quick_wins: list[QuickWin] = []

    # --- Timing Quick Wins ---
    if timing is not None and timing.best_hours:
        best_hours_str = ", ".join(f"{h}:00" for h in timing.best_hours[:3])
        quick_wins.append(QuickWin(
            action="Shift PPV sends to peak hours",
            implementation=f"Schedule all PPVs for {best_hours_str} (highest performing hours)",
            expected_impact="10-25% increase in view rate and conversions"
        ))

        if timing.best_days:
            best_days_str = ", ".join(timing.best_days[:3])
            quick_wins.append(QuickWin(
                action="Increase volume on best-performing days",
                implementation=f"Add +1-2 extra PPVs on {best_days_str}",
                expected_impact="15-30% revenue lift from timing optimization"
            ))

    # --- Pricing Quick Wins ---
    if pricing is not None:
        if pricing.recommended_price_range:
            sweet_spot = pricing.recommended_price_range.get("sweet_spot", 0)
            if sweet_spot > 0:
                quick_wins.append(QuickWin(
                    action="Adjust PPV pricing to sweet spot",
                    implementation=f"Price most PPVs at ${sweet_spot:.0f} (optimal conversion/revenue balance)",
                    expected_impact="5-15% revenue increase from price optimization"
                ))

        # Check for underpriced content
        if pricing.optimal_prices:
            underpriced = [
                op for op in pricing.optimal_prices
                if op.purchase_rate > 10 and op.avg_price < 12
            ]
            if underpriced:
                content_type = underpriced[0].type_name
                quick_wins.append(QuickWin(
                    action=f"Increase {content_type} pricing",
                    implementation=f"Test ${underpriced[0].avg_price + 3:.0f}-{underpriced[0].avg_price + 5:.0f} "
                                  f"for {content_type} (high demand, low price)",
                    expected_impact="10-20% revenue gain from price correction"
                ))

    # --- Content Quick Wins ---
    if content is not None:
        # Use top performing content types
        if content.top_content_types:
            top_type = content.top_content_types[0]
            quick_wins.append(QuickWin(
                action=f"Increase {top_type} content frequency",
                implementation=f"Schedule 2-3 additional {top_type} PPVs this week",
                expected_impact="8-15% revenue boost from proven content"
            ))

        # Tap into underutilized types
        if content.underutilized_types:
            untapped = content.underutilized_types[0]
            quick_wins.append(QuickWin(
                action=f"Test {untapped} content",
                implementation=f"Create 2-3 PPVs with {untapped} content from vault",
                expected_impact="Potential new revenue stream; test for audience interest"
            ))

    # Limit to top 5 quick wins
    return quick_wins[:5]


def generate_thirty_day_plan(
    revenue: RevenueAnalysis | None,
    ppv: PPVAnalysis | None,
    captions: CaptionAnalysis | None,
) -> list[str]:
    """
    Generate 30-day improvement plan organized by week.

    The plan focuses on systematic improvements that require
    more time to implement than quick wins.

    Args:
        revenue: RevenueAnalysis from Phase 2
        ppv: PPVAnalysis from Phase 3
        captions: CaptionAnalysis from Phase 7

    Returns:
        List of 4 weekly action items (one per week).
    """
    plan: list[str] = []

    # Week 1: Foundation & Quick Fixes
    week1_actions = []
    if captions is not None and captions.avg_freshness < 60:
        week1_actions.append("refresh stale captions")
    if ppv is not None and ppv.purchase_rate_pct < 5:
        week1_actions.append("audit pricing strategy")
    if revenue is not None and revenue.msg_sub_ratio < 0.8:
        week1_actions.append("increase PPV frequency")

    if week1_actions:
        plan.append(f"Week 1 (Foundation): {'; '.join(week1_actions[:3])}")
    else:
        plan.append("Week 1 (Foundation): Establish baseline metrics and verify tracking accuracy")

    # Week 2: Optimization
    week2_actions = []
    if ppv is not None:
        if ppv.view_rate_pct < 50:
            week2_actions.append("A/B test send times and subject lines")
        if ppv.earnings_volatility > 30:
            week2_actions.append("standardize content quality")
    if captions is not None and captions.total_captions < 50:
        week2_actions.append("create 15-20 new caption variations")

    if week2_actions:
        plan.append(f"Week 2 (Optimization): {'; '.join(week2_actions[:3])}")
    else:
        plan.append("Week 2 (Optimization): Test pricing variations and timing adjustments")

    # Week 3: Expansion
    week3_actions = []
    if revenue is not None:
        if revenue.earnings_per_fan < 10:
            week3_actions.append("launch premium content tier")
        if revenue.renew_on_pct < 35:
            week3_actions.append("implement retention campaign")
    week3_actions.append("explore new content formats")

    plan.append(f"Week 3 (Expansion): {'; '.join(week3_actions[:3])}")

    # Week 4: Analysis & Iteration
    week4_actions = [
        "analyze 30-day results vs baseline",
        "identify winning strategies to scale",
        "document learnings for next cycle"
    ]
    plan.append(f"Week 4 (Analysis): {'; '.join(week4_actions)}")

    return plan


def generate_ninety_day_roadmap(
    health_score: int,
    position: PortfolioPosition | None,
    revenue: RevenueAnalysis | None,
) -> list[RoadmapItem]:
    """
    Generate 90-day transformation roadmap with monthly phases.

    The roadmap provides strategic direction for sustained growth
    over a quarter, building from foundation to optimization.

    Args:
        health_score: Overall health score (0-100)
        position: PortfolioPosition from Phase 9
        revenue: RevenueAnalysis from Phase 2

    Returns:
        List of 3 RoadmapItem objects (one per month).
    """
    roadmap: list[RoadmapItem] = []

    # --- Month 1: Foundation ---
    month1_objective = "Establish strong operational foundation"
    month1_actions = []

    if health_score < 50:
        month1_objective = "Stabilize performance metrics and address critical gaps"
        month1_actions.extend([
            "Audit and fix all data tracking issues",
            "Establish daily performance monitoring",
            "Create emergency content pipeline"
        ])
    elif health_score < 70:
        month1_actions.extend([
            "Optimize existing content rotation",
            "Implement consistent posting schedule",
            "Refresh caption library"
        ])
    else:
        month1_actions.extend([
            "Document winning strategies",
            "Build scalable content templates",
            "Establish efficiency benchmarks"
        ])

    if revenue is not None and revenue.msg_sub_ratio < 1.0:
        month1_actions.append("Increase PPV messaging to 1.0x target")

    roadmap.append(RoadmapItem(
        month=1,
        phase="Foundation",
        objective=month1_objective,
        key_actions=month1_actions[:4]
    ))

    # --- Month 2: Growth ---
    month2_objective = "Scale proven strategies and expand reach"
    month2_actions = []

    if position is not None:
        if position.earnings_percentile < 50:
            month2_objective = "Accelerate growth to reach top 50% of portfolio"
            month2_actions.extend([
                "Launch intensive content campaign",
                "Test aggressive pricing strategies",
                "Implement fan re-engagement program"
            ])
        elif position.earnings_percentile < 75:
            month2_actions.extend([
                "Scale top-performing content types",
                "Expand to new content categories",
                "Optimize for peak engagement hours"
            ])
        else:
            month2_actions.extend([
                "Defend market position with innovation",
                "Test premium pricing tiers",
                "Build exclusive content pipeline"
            ])

    month2_actions.append("Review Month 1 results and adjust strategy")
    roadmap.append(RoadmapItem(
        month=2,
        phase="Growth",
        objective=month2_objective,
        key_actions=month2_actions[:4]
    ))

    # --- Month 3: Optimization ---
    month3_objective = "Maximize efficiency and prepare for next quarter"
    month3_actions = [
        "Analyze full quarter performance data",
        "Identify and eliminate underperforming strategies",
        "Double down on highest ROI activities",
        "Plan Q+1 strategic initiatives"
    ]

    if revenue is not None and revenue.renew_on_pct < 40:
        month3_actions.insert(0, "Launch subscriber loyalty program")

    roadmap.append(RoadmapItem(
        month=3,
        phase="Optimization",
        objective=month3_objective,
        key_actions=month3_actions[:4]
    ))

    return roadmap


def generate_kpis(
    revenue: RevenueAnalysis | None,
    ppv: PPVAnalysis | None,
    captions: CaptionAnalysis | None,
) -> list[KPI]:
    """
    Generate KPIs to track for ongoing performance monitoring.

    KPIs include current values and targets for 30-day and 90-day horizons.

    Args:
        revenue: RevenueAnalysis from Phase 2
        ppv: PPVAnalysis from Phase 3
        captions: CaptionAnalysis from Phase 7

    Returns:
        List of KPI objects with metrics, current values, and targets.
    """
    kpis: list[KPI] = []

    # --- Revenue KPIs ---
    if revenue is not None:
        # Msg:Sub Ratio
        current_ratio = revenue.msg_sub_ratio
        target_30d = max(current_ratio * 1.15, 1.0)  # 15% improvement or 1.0 minimum
        target_90d = max(current_ratio * 1.4, 1.5)   # 40% improvement or 1.5 minimum
        kpis.append(KPI(
            metric="Msg:Sub Ratio",
            current=round(current_ratio, 2),
            target_30d=round(target_30d, 2),
            target_90d=round(target_90d, 2),
            unit="x"
        ))

        # Earnings per Fan
        current_epf = revenue.earnings_per_fan
        target_30d_epf = current_epf * 1.10  # 10% improvement
        target_90d_epf = max(current_epf * 1.25, 15.0)  # 25% or $15 minimum
        kpis.append(KPI(
            metric="Earnings per Fan",
            current=round(current_epf, 2),
            target_30d=round(target_30d_epf, 2),
            target_90d=round(target_90d_epf, 2),
            unit="$"
        ))

        # Renewal Rate
        current_renew = revenue.renew_on_pct
        target_30d_renew = min(current_renew + 5, 60)  # +5 pts
        target_90d_renew = min(current_renew + 12, 65)  # +12 pts
        kpis.append(KPI(
            metric="Renewal Rate",
            current=round(current_renew, 1),
            target_30d=round(target_30d_renew, 1),
            target_90d=round(target_90d_renew, 1),
            unit="%"
        ))

    # --- PPV KPIs ---
    if ppv is not None:
        # Purchase Rate
        current_pr = ppv.purchase_rate_pct
        target_30d_pr = min(current_pr * 1.15, 15)  # 15% improvement, cap at 15%
        target_90d_pr = min(current_pr * 1.35, 18)  # 35% improvement, cap at 18%
        kpis.append(KPI(
            metric="Purchase Rate",
            current=round(current_pr, 1),
            target_30d=round(target_30d_pr, 1),
            target_90d=round(target_90d_pr, 1),
            unit="%"
        ))

        # View Rate
        current_vr = ppv.view_rate_pct
        target_30d_vr = min(current_vr + 5, 80)  # +5 pts
        target_90d_vr = min(current_vr + 12, 85)  # +12 pts
        kpis.append(KPI(
            metric="View Rate",
            current=round(current_vr, 1),
            target_30d=round(target_30d_vr, 1),
            target_90d=round(target_90d_vr, 1),
            unit="%"
        ))

        # Revenue per Send
        current_rps = ppv.revenue_per_send
        target_30d_rps = current_rps * 1.12  # 12% improvement
        target_90d_rps = max(current_rps * 1.30, 0.75)  # 30% or $0.75 minimum
        kpis.append(KPI(
            metric="Revenue per Send",
            current=round(current_rps, 2),
            target_30d=round(target_30d_rps, 2),
            target_90d=round(target_90d_rps, 2),
            unit="$"
        ))

    # --- Caption KPIs ---
    if captions is not None:
        # Average Freshness
        current_fresh = captions.avg_freshness
        target_30d_fresh = min(current_fresh + 10, 85)  # +10 pts
        target_90d_fresh = min(current_fresh + 20, 90)  # +20 pts
        kpis.append(KPI(
            metric="Caption Freshness",
            current=round(current_fresh, 0),
            target_30d=round(target_30d_fresh, 0),
            target_90d=round(target_90d_fresh, 0),
            unit=""
        ))

        # Caption Pool Size
        current_pool = captions.total_captions
        target_30d_pool = max(current_pool + 15, 50)  # +15 or 50 minimum
        target_90d_pool = max(current_pool + 40, 100)  # +40 or 100 minimum
        kpis.append(KPI(
            metric="Caption Pool Size",
            current=float(current_pool),
            target_30d=float(target_30d_pool),
            target_90d=float(target_90d_pool),
            unit=""
        ))

    return kpis


# =============================================================================
# PHASE 5: DEEP ANALYSIS FUNCTION (9-Phase)
# =============================================================================


def run_deep_analysis(
    db: DatabaseManager,
    creator_id: str,
    creator_name: str,
    display_name: str = ""
) -> DeepAnalysisResult:
    """
    Execute comprehensive 9-phase deep analysis for a single creator.

    The 9 phases are:
    1. Creator Discovery (handled by caller - creator_id is passed in)
    2. Revenue Architecture Analysis
    3. PPV Performance Deep Dive
    4. Timing Optimization Analysis
    5. Content Type Performance
    6. Pricing Strategy Analysis
    7. Caption Intelligence
    8. Persona & Voice Analysis
    9. Portfolio Positioning

    After all phases, this function:
    - Calculates an overall health score (0-100)
    - Generates top priorities
    - Creates quick wins for immediate implementation
    - Builds a 30-day improvement plan
    - Constructs a 90-day strategic roadmap
    - Defines KPIs to track

    Args:
        db: DatabaseManager instance with active connection
        creator_id: Creator's unique UUID
        creator_name: Creator's page name (e.g., "missalexa")
        display_name: Optional display name for the creator

    Returns:
        DeepAnalysisResult containing all 9 phases plus recommendations

    Raises:
        CreatorNotFoundError: If creator not found in database
    """
    start_time = time.perf_counter()
    logger.info(f"Starting deep analysis for {creator_name} ({creator_id})")

    # Ensure database connection is open
    db.get_connection()

    # Initialize phase results with None (will be filled as we go)
    revenue: RevenueAnalysis | None = None
    ppv: PPVAnalysis | None = None
    timing: TimingAnalysis | None = None
    content: ContentAnalysis | None = None
    pricing: PricingAnalysis | None = None
    captions: CaptionAnalysis | None = None
    persona: PersonaAnalysis | None = None
    position: PortfolioPosition | None = None

    # --- Phase 2: Revenue Architecture Analysis ---
    try:
        logger.debug(f"Phase 2: Revenue analysis for {creator_name}")
        revenue = db.get_revenue_breakdown(creator_id)
    except CreatorNotFoundError:
        logger.warning(f"Phase 2 failed: Creator {creator_name} not found")
        raise
    except Exception as e:
        logger.warning(f"Phase 2 failed for {creator_name}: {e}")
        # Continue with other phases

    # --- Phase 3: PPV Performance Deep Dive ---
    try:
        logger.debug(f"Phase 3: PPV analysis for {creator_name}")
        ppv = db.get_ppv_metrics(creator_id)
    except InsufficientDataError:
        logger.warning(f"Phase 3: Insufficient PPV data for {creator_name}")
    except Exception as e:
        logger.warning(f"Phase 3 failed for {creator_name}: {e}")

    # --- Phase 4: Timing Optimization Analysis ---
    try:
        logger.debug(f"Phase 4: Timing analysis for {creator_name}")
        timing = db.get_timing_analysis(creator_id)
    except Exception as e:
        logger.warning(f"Phase 4 failed for {creator_name}: {e}")

    # --- Phase 5: Content Type Performance ---
    try:
        logger.debug(f"Phase 5: Content analysis for {creator_name}")
        content = db.get_content_performance(creator_id)
    except Exception as e:
        logger.warning(f"Phase 5 failed for {creator_name}: {e}")

    # --- Phase 6: Pricing Strategy Analysis ---
    try:
        logger.debug(f"Phase 6: Pricing analysis for {creator_name}")
        pricing = db.get_pricing_analysis(creator_id)
    except Exception as e:
        logger.warning(f"Phase 6 failed for {creator_name}: {e}")

    # --- Phase 7: Caption Intelligence ---
    try:
        logger.debug(f"Phase 7: Caption analysis for {creator_name}")
        captions = db.get_caption_health(creator_id)
    except Exception as e:
        logger.warning(f"Phase 7 failed for {creator_name}: {e}")

    # --- Phase 8: Persona & Voice Analysis ---
    try:
        logger.debug(f"Phase 8: Persona analysis for {creator_name}")
        persona = db.get_persona_profile(creator_id)
    except CreatorNotFoundError:
        logger.warning(f"Phase 8: No persona data for {creator_name}")
    except Exception as e:
        logger.warning(f"Phase 8 failed for {creator_name}: {e}")

    # --- Phase 9: Portfolio Positioning ---
    try:
        logger.debug(f"Phase 9: Portfolio positioning for {creator_name}")
        position = db.get_portfolio_positioning(creator_id)
    except CreatorNotFoundError:
        logger.warning(f"Phase 9: Could not calculate positioning for {creator_name}")
    except Exception as e:
        logger.warning(f"Phase 9 failed for {creator_name}: {e}")

    # --- Calculate Health Score ---
    logger.debug(f"Calculating health score for {creator_name}")
    health_score, health_rating = calculate_health_score(
        revenue=revenue,
        ppv=ppv,
        captions=captions,
        persona=persona,
        position=position
    )

    # --- Generate Recommendations ---
    logger.debug(f"Generating recommendations for {creator_name}")

    # Top priorities
    top_priorities = generate_priorities(
        revenue=revenue,
        ppv=ppv,
        timing=timing,
        content=content,
        captions=captions
    )

    # Quick wins
    quick_wins = generate_quick_wins(
        timing=timing,
        pricing=pricing,
        content=content
    )

    # 30-day plan
    thirty_day_plan = generate_thirty_day_plan(
        revenue=revenue,
        ppv=ppv,
        captions=captions
    )

    # 90-day roadmap
    ninety_day_roadmap = generate_ninety_day_roadmap(
        health_score=health_score,
        position=position,
        revenue=revenue
    )

    # KPIs to track
    kpis_to_track = generate_kpis(
        revenue=revenue,
        ppv=ppv,
        captions=captions
    )

    # --- Calculate Duration ---
    end_time = time.perf_counter()
    duration_ms = int((end_time - start_time) * 1000)

    # --- Build Result ---
    result = DeepAnalysisResult(
        creator_id=creator_id,
        page_name=creator_name,
        display_name=display_name,
        revenue=revenue,
        ppv=ppv,
        timing=timing,
        content=content,
        pricing=pricing,
        captions=captions,
        persona=persona,
        portfolio_position=position,
        health_score=health_score,
        health_rating=health_rating,
        top_priorities=top_priorities,
        quick_wins=quick_wins,
        thirty_day_plan=thirty_day_plan,
        ninety_day_roadmap=ninety_day_roadmap,
        kpis_to_track=kpis_to_track,
        analysis_duration_ms=duration_ms,
    )

    logger.info(
        f"Deep analysis complete for {creator_name}: "
        f"health_score={health_score} ({health_rating}), "
        f"duration={duration_ms}ms"
    )

    return result


# =============================================================================
# PHASE 6: OUTPUT FORMATTERS
# =============================================================================


def format_table(
    headers: list[str],
    rows: list[list[str]],
    align: list[str] | None = None,
) -> str:
    """
    Format data as a Markdown table with aligned columns.

    Args:
        headers: Column headers.
        rows: List of row data (each row is a list of cell values).
        align: Optional alignment per column ('left', 'center', 'right').
               Defaults to left alignment for all columns.

    Returns:
        Formatted Markdown table string.

    Example:
        >>> format_table(
        ...     ["Name", "Revenue", "Status"],
        ...     [["Alice", "$100", "Active"], ["Bob", "$200", "Inactive"]],
        ...     align=["left", "right", "center"]
        ... )
    """
    if not headers:
        return ""

    num_cols = len(headers)

    # Default to left alignment
    if align is None:
        align = ["left"] * num_cols
    elif len(align) < num_cols:
        # Extend with left alignment if not enough specified
        align = align + ["left"] * (num_cols - len(align))

    # Calculate column widths (minimum 3 for separator)
    col_widths = [max(3, len(str(h))) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build header row
    header_cells = []
    for i, h in enumerate(headers):
        header_cells.append(str(h).ljust(col_widths[i]))
    header_row = "| " + " | ".join(header_cells) + " |"

    # Build separator row with alignment
    sep_cells = []
    for i, a in enumerate(align[:num_cols]):
        width = col_widths[i]
        if a == "center":
            sep_cells.append(":" + "-" * (width - 2) + ":")
        elif a == "right":
            sep_cells.append("-" * (width - 1) + ":")
        else:  # left
            sep_cells.append(":" + "-" * (width - 1))
    separator_row = "| " + " | ".join(sep_cells) + " |"

    # Build data rows
    data_rows = []
    for row in rows:
        cells = []
        for i in range(num_cols):
            cell_value = str(row[i]) if i < len(row) else ""
            cells.append(cell_value.ljust(col_widths[i]))
        data_rows.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_row, separator_row] + data_rows)


def _get_rating_emoji(rating: str) -> str:
    """
    Get status emoji for a rating string.

    Args:
        rating: Rating string (e.g., 'Excellent', 'Good', 'Poor').

    Returns:
        Appropriate emoji indicator.
    """
    rating_lower = rating.lower() if rating else ""
    if rating_lower in ("excellent", "good", "top performer", "top tier"):
        return "+"
    elif rating_lower in ("average", "mid performer", "needs attention"):
        return "~"
    elif rating_lower in ("poor", "below average", "critical", "underperformer"):
        return "-"
    return ""


def _format_currency(value: float, show_cents: bool = True) -> str:
    """Format a value as currency."""
    if show_cents:
        return f"${value:,.2f}"
    return f"${value:,.0f}"


def _format_percentage(value: float, decimals: int = 1) -> str:
    """Format a value as percentage."""
    return f"{value:.{decimals}f}%"


def _format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return iso_timestamp or "N/A"


# -----------------------------------------------------------------------------
# Quick Analysis Formatters
# -----------------------------------------------------------------------------


def format_quick_analysis_markdown(result: QuickAnalysisResult) -> str:
    """
    Format quick analysis as human-readable Markdown.

    Sections:
    - Header with creator name and timestamp
    - Profile Summary table
    - Financial Snapshot table
    - Performance Metrics table
    - Best Hours & Days
    - Caption Health
    - Agency Benchmarks comparison

    Args:
        result: QuickAnalysisResult dataclass instance.

    Returns:
        Formatted Markdown string.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Quick Analysis: {result.display_name or result.page_name}")
    lines.append("")
    lines.append(f"**Generated:** {_format_timestamp(result.generated_at)}")
    lines.append(f"**Analysis Duration:** {result.analysis_duration_ms}ms")
    lines.append("")
    lines.append("---")
    lines.append("")

    brief = result.brief
    if not brief:
        lines.append("*No brief data available.*")
        return "\n".join(lines)

    # Profile Summary
    lines.append("## Profile Summary")
    lines.append("")
    profile_table = format_table(
        headers=["Attribute", "Value"],
        rows=[
            ["Page Name", brief.page_name],
            ["Display Name", brief.display_name or "N/A"],
            ["Page Type", brief.page_type.capitalize()],
            ["Active Fans", f"{brief.active_fans:,}"],
            ["Performance Tier", f"Tier {brief.performance_tier}"],
            ["Volume Level", brief.volume_level],
        ],
        align=["left", "left"],
    )
    lines.append(profile_table)
    lines.append("")

    # Financial Snapshot
    lines.append("## Financial Snapshot")
    lines.append("")
    financial_table = format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Total Earnings", _format_currency(brief.total_earnings)],
            ["Message Revenue", _format_currency(brief.message_net)],
            ["Earnings/Fan", _format_currency(brief.avg_earnings_per_fan)],
            ["Contribution %", _format_percentage(brief.contribution_pct)],
            ["OF Ranking", brief.of_ranking or "N/A"],
        ],
        align=["left", "right"],
    )
    lines.append(financial_table)
    lines.append("")

    # Performance Metrics
    lines.append("## Performance Metrics")
    lines.append("")
    perf_table = format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Total Messages", f"{brief.total_messages:,}"],
            ["Avg Earnings/Message", _format_currency(brief.avg_earnings_per_message)],
            ["View Rate", _format_percentage(brief.avg_view_rate)],
            ["Purchase Rate", _format_percentage(brief.avg_purchase_rate)],
            ["PPV/Day", str(brief.ppv_per_day)],
            ["Bump/Day", str(brief.bump_per_day)],
        ],
        align=["left", "right"],
    )
    lines.append(perf_table)
    lines.append("")

    # Best Hours & Days
    lines.append("## Best Performing Times")
    lines.append("")

    if brief.best_hours:
        lines.append("### Top Hours")
        lines.append("")
        hour_rows = []
        for h in brief.best_hours[:5]:
            hour_val = h.get("hour", 0)
            hour_label = f"{hour_val}:00"
            if hour_val < 12:
                hour_label += " AM"
            else:
                hour_label += " PM"
            hour_rows.append([
                hour_label,
                str(h.get("count", 0)),
                _format_currency(h.get("avg_earnings", 0)),
            ])
        lines.append(format_table(
            headers=["Hour", "PPV Count", "Avg Earnings"],
            rows=hour_rows,
            align=["left", "right", "right"],
        ))
        lines.append("")

    if brief.best_days:
        lines.append("### Top Days")
        lines.append("")
        day_rows = []
        for d in brief.best_days[:5]:
            day_rows.append([
                d.get("day_name", "N/A"),
                str(d.get("count", 0)),
                _format_currency(d.get("avg_earnings", 0)),
            ])
        lines.append(format_table(
            headers=["Day", "PPV Count", "Avg Earnings"],
            rows=day_rows,
            align=["left", "right", "right"],
        ))
        lines.append("")

    # Caption Health
    lines.append("## Caption Health")
    lines.append("")
    caption_table = format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Total Captions", f"{brief.total_captions:,}"],
            ["Fresh (>= 30)", f"{brief.fresh_captions:,}"],
            ["Exhausted (< 25)", f"{brief.exhausted_captions:,}"],
            ["Avg Freshness", f"{brief.avg_freshness:.1f}"],
        ],
        align=["left", "right"],
    )
    lines.append(caption_table)
    lines.append("")

    # Persona
    if brief.primary_tone:
        lines.append("## Persona Profile")
        lines.append("")
        persona_table = format_table(
            headers=["Attribute", "Value"],
            rows=[
                ["Primary Tone", brief.primary_tone],
                ["Emoji Frequency", brief.emoji_frequency],
                ["Slang Level", brief.slang_level],
            ],
            align=["left", "left"],
        )
        lines.append(persona_table)
        lines.append("")

    # Agency Benchmarks
    benchmarks = result.benchmarks
    if benchmarks:
        lines.append("## Agency Benchmarks")
        lines.append("")
        lines.append(f"**Overall Percentile:** {benchmarks.overall_percentile}th")
        lines.append(f"**Performance Tier:** {benchmarks.performance_tier_label}")
        lines.append(f"**vs Agency Revenue:** {benchmarks.vs_agency_revenue}")
        lines.append("")
        bench_table = format_table(
            headers=["Metric", "Agency Avg", "Creator Percentile"],
            rows=[
                [
                    "Revenue",
                    _format_currency(benchmarks.agency_avg_revenue),
                    f"{benchmarks.creator_revenue_percentile}th",
                ],
                [
                    "Purchase Rate",
                    _format_percentage(benchmarks.agency_avg_purchase_rate),
                    f"{benchmarks.creator_purchase_rate_percentile}th",
                ],
                [
                    "View Rate",
                    _format_percentage(benchmarks.agency_avg_view_rate),
                    f"{benchmarks.creator_view_rate_percentile}th",
                ],
                [
                    "Earnings/Message",
                    _format_currency(benchmarks.agency_avg_earnings_per_message),
                    f"{benchmarks.creator_earnings_percentile}th",
                ],
            ],
            align=["left", "right", "right"],
        )
        lines.append(bench_table)
        lines.append("")

    lines.append("---")
    lines.append("*Generated by EROS Schedule Generator*")

    return "\n".join(lines)


def format_quick_analysis_json(result: QuickAnalysisResult) -> str:
    """
    Format quick analysis as pretty-printed JSON.

    Args:
        result: QuickAnalysisResult dataclass instance.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(result.to_dict(), indent=2, default=str)


# -----------------------------------------------------------------------------
# Deep Analysis Formatters
# -----------------------------------------------------------------------------


def format_deep_analysis_markdown(result: DeepAnalysisResult) -> str:
    """
    Format deep analysis as Fortune 500-quality Markdown report.

    Sections:
    - Executive Summary with health score
    - Phase 2: Revenue Architecture table
    - Phase 3: PPV Performance with trends
    - Phase 4: Timing Optimization with heatmap
    - Phase 5: Content Type Performance
    - Phase 6: Pricing Strategy
    - Phase 7: Caption Intelligence
    - Phase 8: Persona Profile
    - Phase 9: Portfolio Position
    - Strategic Recommendations

    Args:
        result: DeepAnalysisResult dataclass instance.

    Returns:
        Formatted Markdown string.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Strategic Analysis: {result.display_name or result.page_name}")
    lines.append("")
    lines.append(f"**Generated:** {_format_timestamp(result.generated_at)}")
    lines.append(f"**Health Score:** {result.health_score}/100 ({result.health_rating})")
    lines.append(f"**Analysis Duration:** {result.analysis_duration_ms}ms")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    # Build executive summary metrics
    exec_rows = []
    if result.revenue:
        msg_rating = result.revenue.msg_sub_rating or "N/A"
        exec_rows.append(["Revenue Health", f"{result.revenue.msg_pct:.0f}%", f"{_get_rating_emoji(msg_rating)} {msg_rating}"])
    if result.ppv:
        ppv_rating = result.ppv.purchase_rate_rating or "N/A"
        exec_rows.append(["PPV Performance", _format_percentage(result.ppv.purchase_rate_pct), f"{_get_rating_emoji(ppv_rating)} {ppv_rating}"])
    if result.captions:
        caption_rating = result.captions.caption_health_rating or "N/A"
        exec_rows.append(["Caption Health", f"{result.captions.avg_freshness:.0f}", f"{_get_rating_emoji(caption_rating)} {caption_rating}"])
    if result.portfolio_position:
        pos_label = result.portfolio_position.competitive_position or "N/A"
        exec_rows.append(["Portfolio Rank", f"#{result.portfolio_position.earnings_rank}", f"{_get_rating_emoji(pos_label)} {pos_label}"])

    if exec_rows:
        lines.append(format_table(
            headers=["Metric", "Value", "Rating"],
            rows=exec_rows,
            align=["left", "right", "left"],
        ))
        lines.append("")

    # Top Priorities
    if result.top_priorities:
        lines.append("### Top Priorities")
        lines.append("")
        for i, priority in enumerate(result.top_priorities, 1):
            lines.append(f"{i}. {priority}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Phase 2: Revenue Architecture
    if result.revenue:
        rev = result.revenue
        lines.append("## Phase 2: Revenue Architecture")
        lines.append("")
        lines.append(format_table(
            headers=["Revenue Source", "Amount", "% of Total"],
            rows=[
                ["Messages", _format_currency(rev.message_net), _format_percentage(rev.msg_pct)],
                ["Subscriptions", _format_currency(rev.subscription_net), _format_percentage(rev.sub_pct)],
                ["Tips", _format_currency(rev.tips_net), _format_percentage(100 - rev.msg_pct - rev.sub_pct if rev.tips_net > 0 else 0)],
                ["Posts", _format_currency(rev.posts_net), "N/A"],
                ["**Total**", f"**{_format_currency(rev.total_earnings)}**", "**100%**"],
            ],
            align=["left", "right", "right"],
        ))
        lines.append("")
        lines.append("**Key Ratios:**")
        lines.append(f"- Message:Subscription Ratio: **{rev.msg_sub_ratio:.2f}** ({rev.msg_sub_rating})")
        lines.append(f"- Earnings per Fan: **{_format_currency(rev.earnings_per_fan)}** ({rev.earnings_per_fan_rating})")
        lines.append(f"- Renewal Rate: **{_format_percentage(rev.renew_on_pct)}** ({rev.renew_on_rating})")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Phase 3: PPV Performance
    if result.ppv:
        ppv = result.ppv
        lines.append("## Phase 3: PPV Performance")
        lines.append("")
        lines.append(format_table(
            headers=["Metric", "Value", "Rating"],
            rows=[
                ["Total PPVs", f"{ppv.total_ppvs:,}", ""],
                ["Total Revenue", _format_currency(ppv.total_revenue), ""],
                ["Avg Earnings", _format_currency(ppv.avg_earnings), ""],
                ["View Rate", _format_percentage(ppv.view_rate_pct), f"{_get_rating_emoji(ppv.view_rate_rating)} {ppv.view_rate_rating}"],
                ["Purchase Rate", _format_percentage(ppv.purchase_rate_pct), f"{_get_rating_emoji(ppv.purchase_rate_rating)} {ppv.purchase_rate_rating}"],
                ["Revenue/Send", _format_currency(ppv.revenue_per_send), f"{_get_rating_emoji(ppv.rps_rating)} {ppv.rps_rating}"],
                ["Avg Price", _format_currency(ppv.avg_price), ""],
            ],
            align=["left", "right", "left"],
        ))
        lines.append("")

        # Monthly trends
        if ppv.monthly_trends:
            lines.append("### Monthly Trends")
            lines.append("")
            trend_rows = []
            for trend in ppv.monthly_trends[-6:]:  # Last 6 months
                trend_rows.append([
                    trend.month,
                    str(trend.ppv_count),
                    _format_currency(trend.revenue),
                    _format_currency(trend.avg_earnings),
                    _format_percentage(trend.purchase_rate),
                ])
            lines.append(format_table(
                headers=["Month", "PPV Count", "Revenue", "Avg Earnings", "Purchase Rate"],
                rows=trend_rows,
                align=["left", "right", "right", "right", "right"],
            ))
            lines.append("")

        # Week over week
        if ppv.week_over_week:
            wow = ppv.week_over_week
            lines.append("### Week-over-Week Comparison")
            lines.append("")
            lines.append(format_table(
                headers=["Metric", "Current Week", "Previous Week", "Change"],
                rows=[
                    ["PPV Count", str(wow.current_week_ppvs), str(wow.previous_week_ppvs), ""],
                    ["Revenue", _format_currency(wow.current_week_revenue), _format_currency(wow.previous_week_revenue), f"{wow.revenue_change_pct:+.1f}%"],
                    ["Purchase Rate", _format_percentage(wow.current_week_purchase_rate), _format_percentage(wow.previous_week_purchase_rate), f"{wow.purchase_rate_change_pct:+.1f}%"],
                ],
                align=["left", "right", "right", "right"],
            ))
            lines.append("")

        lines.append("---")
        lines.append("")

    # Phase 4: Timing Optimization
    if result.timing:
        timing = result.timing
        lines.append("## Phase 4: Timing Optimization")
        lines.append("")

        if timing.best_hours:
            lines.append(f"**Best Hours:** {', '.join(f'{h}:00' for h in timing.best_hours[:3])}")
        if timing.best_days:
            lines.append(f"**Best Days:** {', '.join(timing.best_days[:3])}")
        lines.append("")

        # Hourly performance
        if timing.hourly_performance:
            lines.append("### Hourly Performance (Top 8)")
            lines.append("")
            sorted_hours = sorted(timing.hourly_performance, key=lambda x: x.total_revenue, reverse=True)[:8]
            hour_rows = []
            for hp in sorted_hours:
                hour_label = f"{hp.hour:02d}:00"
                hour_rows.append([
                    hour_label,
                    str(hp.count),
                    _format_currency(hp.total_revenue),
                    _format_currency(hp.avg_earnings),
                    _format_percentage(hp.purchase_rate),
                ])
            lines.append(format_table(
                headers=["Hour", "Count", "Total Revenue", "Avg Earnings", "Purchase Rate"],
                rows=hour_rows,
                align=["left", "right", "right", "right", "right"],
            ))
            lines.append("")

        # Daily performance
        if timing.daily_performance:
            lines.append("### Daily Performance")
            lines.append("")
            day_rows = []
            for dp in timing.daily_performance:
                day_rows.append([
                    dp.day,
                    str(dp.count),
                    _format_currency(dp.avg_earnings),
                    _format_percentage(dp.purchase_rate),
                ])
            lines.append(format_table(
                headers=["Day", "Count", "Avg Earnings", "Purchase Rate"],
                rows=day_rows,
                align=["left", "right", "right", "right"],
            ))
            lines.append("")

        # Top combinations (heatmap style)
        if timing.top_combinations:
            lines.append("### Top Hour+Day Combinations")
            lines.append("")
            combo_rows = []
            for entry in timing.top_combinations[:10]:
                combo_rows.append([
                    f"{entry.day} {entry.hour:02d}:00",
                    str(entry.count),
                    _format_currency(entry.avg_earnings),
                ])
            lines.append(format_table(
                headers=["Time Slot", "Count", "Avg Earnings"],
                rows=combo_rows,
                align=["left", "right", "right"],
            ))
            lines.append("")

        lines.append("---")
        lines.append("")

    # Phase 5: Content Type Performance
    if result.content:
        content = result.content
        lines.append("## Phase 5: Content Type Performance")
        lines.append("")

        if content.top_content_types:
            lines.append(f"**Top Performers:** {', '.join(content.top_content_types[:3])}")
        if content.underutilized_types:
            lines.append(f"**Underutilized:** {', '.join(content.underutilized_types[:3])}")
        lines.append("")

        # Content rankings
        if content.content_rankings:
            lines.append("### Content Rankings")
            lines.append("")
            content_rows = []
            for ct in content.content_rankings[:10]:
                content_rows.append([
                    ct.type_name,
                    ct.type_category,
                    str(ct.uses),
                    _format_currency(ct.total_revenue),
                    _format_currency(ct.avg_earnings),
                    _format_percentage(ct.purchase_rate),
                ])
            lines.append(format_table(
                headers=["Type", "Category", "Uses", "Revenue", "Avg Earnings", "Purchase Rate"],
                rows=content_rows,
                align=["left", "left", "right", "right", "right", "right"],
            ))
            lines.append("")

        # Content gaps
        if content.content_gaps:
            gaps_needing_attention = [g for g in content.content_gaps if g.status in ("UNTAPPED", "NEEDS CONTENT")]
            if gaps_needing_attention:
                lines.append("### Content Gaps")
                lines.append("")
                gap_rows = []
                for gap in gaps_needing_attention[:5]:
                    gap_rows.append([
                        gap.type_name,
                        "Yes" if gap.in_vault else "No",
                        str(gap.quantity),
                        str(gap.times_used),
                        gap.status,
                    ])
                lines.append(format_table(
                    headers=["Type", "In Vault", "Qty", "Times Used", "Status"],
                    rows=gap_rows,
                    align=["left", "center", "right", "right", "left"],
                ))
                lines.append("")

        lines.append("---")
        lines.append("")

    # Phase 6: Pricing Strategy
    if result.pricing:
        pricing = result.pricing
        lines.append("## Phase 6: Pricing Strategy")
        lines.append("")

        if pricing.recommended_price_range:
            rpr = pricing.recommended_price_range
            lines.append(f"**Recommended Price Range:** {_format_currency(rpr.get('min', 0))} - {_format_currency(rpr.get('max', 0))}")
            lines.append(f"**Sweet Spot:** {_format_currency(rpr.get('sweet_spot', 0))}")
            lines.append("")

        # Price tier performance
        if pricing.price_tier_performance:
            lines.append("### Price Tier Performance")
            lines.append("")
            tier_rows = []
            for tier in pricing.price_tier_performance:
                tier_rows.append([
                    tier.price_tier,
                    str(tier.count),
                    _format_currency(tier.total_revenue),
                    _format_currency(tier.avg_earnings),
                    _format_percentage(tier.purchase_rate),
                ])
            lines.append(format_table(
                headers=["Price Tier", "Count", "Revenue", "Avg Earnings", "Purchase Rate"],
                rows=tier_rows,
                align=["left", "right", "right", "right", "right"],
            ))
            lines.append("")

        # Optimal prices by content type
        if pricing.optimal_prices:
            lines.append("### Optimal Pricing by Content Type")
            lines.append("")
            opt_rows = []
            for op in pricing.optimal_prices[:8]:
                opt_rows.append([
                    op.type_name,
                    _format_currency(op.avg_price),
                    _format_currency(op.avg_earnings),
                    _format_percentage(op.purchase_rate),
                    _format_currency(op.recommended_price) if op.recommended_price else "N/A",
                ])
            lines.append(format_table(
                headers=["Type", "Avg Price", "Avg Earnings", "Purchase Rate", "Recommended"],
                rows=opt_rows,
                align=["left", "right", "right", "right", "right"],
            ))
            lines.append("")

        lines.append("---")
        lines.append("")

    # Phase 7: Caption Intelligence
    if result.captions:
        captions = result.captions
        lines.append("## Phase 7: Caption Intelligence")
        lines.append("")
        lines.append(f"**Caption Health Rating:** {captions.caption_health_rating}")
        lines.append("")
        lines.append(format_table(
            headers=["Metric", "Value"],
            rows=[
                ["Total Captions", f"{captions.total_captions:,}"],
                ["Avg Freshness", f"{captions.avg_freshness:.1f}"],
                ["Fresh (>= 80)", f"{captions.fresh_count:,}"],
                ["Stale (< 50)", f"{captions.stale_count:,}"],
                ["Critical (< 30)", f"{captions.critical_stale_count:,}"],
            ],
            align=["left", "right"],
        ))
        lines.append("")

        # Top captions
        if captions.top_captions:
            lines.append("### Top Performing Captions")
            lines.append("")
            top_rows = []
            for cap in captions.top_captions[:5]:
                top_rows.append([
                    cap.preview[:40] + "..." if len(cap.preview) > 40 else cap.preview,
                    cap.tone or "N/A",
                    _format_currency(cap.avg_earnings),
                    str(cap.times_used),
                ])
            lines.append(format_table(
                headers=["Preview", "Tone", "Avg Earnings", "Uses"],
                rows=top_rows,
                align=["left", "left", "right", "right"],
            ))
            lines.append("")

        # Tone effectiveness
        if captions.tone_effectiveness:
            lines.append("### Tone Effectiveness")
            lines.append("")
            tone_rows = []
            for tone in captions.tone_effectiveness[:6]:
                tone_rows.append([
                    tone.tone,
                    str(tone.count),
                    _format_currency(tone.avg_earnings),
                ])
            lines.append(format_table(
                headers=["Tone", "Count", "Avg Earnings"],
                rows=tone_rows,
                align=["left", "right", "right"],
            ))
            lines.append("")

        lines.append("---")
        lines.append("")

    # Phase 8: Persona Profile
    if result.persona and result.persona.primary_tone:
        persona = result.persona
        lines.append("## Phase 8: Persona Profile")
        lines.append("")
        lines.append(format_table(
            headers=["Attribute", "Value"],
            rows=[
                ["Primary Tone", persona.primary_tone],
                ["Secondary Tone", persona.secondary_tone or "N/A"],
                ["Emoji Frequency", persona.emoji_frequency],
                ["Favorite Emojis", persona.favorite_emojis or "N/A"],
                ["Slang Level", persona.slang_level],
                ["Avg Caption Length", f"{persona.avg_caption_length} chars"],
                ["Communication Style", persona.communication_style or "N/A"],
                ["Sentiment", f"{persona.sentiment_label} ({persona.avg_sentiment:.2f})"],
            ],
            align=["left", "left"],
        ))
        lines.append("")
        lines.append("---")
        lines.append("")

    # Phase 9: Portfolio Position
    if result.portfolio_position:
        pos = result.portfolio_position
        lines.append("## Phase 9: Portfolio Position")
        lines.append("")
        lines.append(f"**Competitive Position:** {pos.competitive_position}")
        lines.append("")
        lines.append(format_table(
            headers=["Metric", "Rank", "Percentile"],
            rows=[
                ["Earnings", f"#{pos.earnings_rank}", f"{pos.earnings_percentile}th"],
                ["Fans", f"#{pos.fans_rank}", f"{pos.fans_percentile}th"],
                ["Efficiency", f"#{pos.efficiency_rank}", f"{pos.efficiency_percentile}th"],
            ],
            align=["left", "right", "right"],
        ))
        lines.append("")

        if pos.tier_comparison:
            tc = pos.tier_comparison
            lines.append("### Tier Comparison")
            lines.append("")
            lines.append(f"**Tier {tc.tier}** ({tc.tier_count} creators)")
            lines.append(format_table(
                headers=["Tier Avg", "Value"],
                rows=[
                    ["Earnings", _format_currency(tc.tier_avg_earnings)],
                    ["Fans", f"{tc.tier_avg_fans:,.0f}"],
                    ["Efficiency", _format_currency(tc.tier_avg_efficiency)],
                    ["Renewal %", _format_percentage(tc.tier_avg_renew_pct)],
                ],
                align=["left", "right"],
            ))
            lines.append("")

        lines.append("---")
        lines.append("")

    # Strategic Recommendations
    lines.append("## Strategic Recommendations")
    lines.append("")

    # Quick Wins
    if result.quick_wins:
        lines.append("### Quick Wins (This Week)")
        lines.append("")
        for qw in result.quick_wins:
            lines.append(f"**{qw.action}**")
            lines.append(f"- Implementation: {qw.implementation}")
            lines.append(f"- Expected Impact: {qw.expected_impact}")
            lines.append("")

    # 30-Day Plan
    if result.thirty_day_plan:
        lines.append("### 30-Day Plan")
        lines.append("")
        for i, action in enumerate(result.thirty_day_plan, 1):
            week_num = (i - 1) // 2 + 1
            lines.append(f"- **Week {week_num}:** {action}")
        lines.append("")

    # 90-Day Roadmap
    if result.ninety_day_roadmap:
        lines.append("### 90-Day Roadmap")
        lines.append("")
        for item in result.ninety_day_roadmap:
            lines.append(f"**Month {item.month}: {item.phase}**")
            lines.append(f"- Objective: {item.objective}")
            if item.key_actions:
                for action in item.key_actions:
                    lines.append(f"  - {action}")
            lines.append("")

    # KPIs to Track
    if result.kpis_to_track:
        lines.append("### KPIs to Track")
        lines.append("")
        kpi_rows = []
        for kpi in result.kpis_to_track:
            unit = kpi.unit
            current = f"{kpi.current:.1f}{unit}" if unit else f"{kpi.current:.1f}"
            target_30 = f"{kpi.target_30d:.1f}{unit}" if unit else f"{kpi.target_30d:.1f}"
            target_90 = f"{kpi.target_90d:.1f}{unit}" if unit else f"{kpi.target_90d:.1f}"
            kpi_rows.append([kpi.metric, current, target_30, target_90])
        lines.append(format_table(
            headers=["KPI", "Current", "30-Day Target", "90-Day Target"],
            rows=kpi_rows,
            align=["left", "right", "right", "right"],
        ))
        lines.append("")

    lines.append("---")
    lines.append("*Generated by EROS Schedule Generator - Fortune 500 Quality Strategic Report*")

    return "\n".join(lines)


def format_deep_analysis_json(result: DeepAnalysisResult) -> str:
    """
    Format deep analysis as pretty-printed JSON.

    Args:
        result: DeepAnalysisResult dataclass instance.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(result.to_dict(), indent=2, default=str)


# -----------------------------------------------------------------------------
# Portfolio Summary Formatters
# -----------------------------------------------------------------------------


def format_portfolio_summary_markdown(summary: PortfolioSummary) -> str:
    """
    Format portfolio summary as executive dashboard.

    Sections:
    - Portfolio Overview stats
    - Revenue Breakdown
    - Tier Distribution table
    - Top 5 Performers tables (revenue, fans, efficiency)
    - Creators Needing Attention
    - Caption Health Portfolio-Wide
    - Processing Stats
    - Error Log (if any)

    Args:
        summary: PortfolioSummary dataclass instance.

    Returns:
        Formatted Markdown string.
    """
    lines: list[str] = []

    # Header
    lines.append("# Portfolio Executive Dashboard")
    lines.append("")
    lines.append(f"**Generated:** {_format_timestamp(summary.analysis_timestamp)}")
    lines.append(f"**Analysis Duration:** {summary.total_duration_seconds:.1f} seconds")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Portfolio Overview
    lines.append("## Portfolio Overview")
    lines.append("")
    lines.append(format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Total Creators", str(summary.total_creators)],
            ["Active Creators", str(summary.active_creators)],
            ["Paid Pages", str(summary.paid_pages)],
            ["Free Pages", str(summary.free_pages)],
        ],
        align=["left", "right"],
    ))
    lines.append("")

    # Revenue Breakdown
    lines.append("## Revenue Breakdown")
    lines.append("")
    lines.append(format_table(
        headers=["Revenue Source", "Amount", "% of Total"],
        rows=[
            [
                "Messages",
                _format_currency(summary.total_message_revenue),
                _format_percentage(summary.total_message_revenue / summary.total_portfolio_earnings * 100) if summary.total_portfolio_earnings > 0 else "0%",
            ],
            [
                "Subscriptions",
                _format_currency(summary.total_subscription_revenue),
                _format_percentage(summary.total_subscription_revenue / summary.total_portfolio_earnings * 100) if summary.total_portfolio_earnings > 0 else "0%",
            ],
            ["**Total Portfolio**", f"**{_format_currency(summary.total_portfolio_earnings)}**", "**100%**"],
        ],
        align=["left", "right", "right"],
    ))
    lines.append("")
    lines.append(f"**Avg Earnings/Creator:** {_format_currency(summary.avg_earnings_per_creator)}")
    lines.append(f"**Avg Fans/Creator:** {summary.avg_fans_per_creator:,.0f}")
    lines.append(f"**Avg Purchase Rate:** {_format_percentage(summary.avg_purchase_rate)}")
    lines.append(f"**Avg View Rate:** {_format_percentage(summary.avg_view_rate)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Tier Distribution
    if summary.tier_distribution:
        lines.append("## Tier Distribution")
        lines.append("")
        tier_rows = []
        for tier in sorted(summary.tier_distribution.keys()):
            count = summary.tier_distribution[tier]
            pct = (count / summary.active_creators * 100) if summary.active_creators > 0 else 0
            tier_rows.append([f"Tier {tier}", str(count), _format_percentage(pct)])
        lines.append(format_table(
            headers=["Tier", "Count", "% of Portfolio"],
            rows=tier_rows,
            align=["left", "right", "right"],
        ))
        lines.append("")

    # Volume Distribution
    if summary.volume_distribution:
        lines.append("## Volume Distribution")
        lines.append("")
        vol_rows = []
        for level, count in summary.volume_distribution.items():
            pct = (count / summary.active_creators * 100) if summary.active_creators > 0 else 0
            vol_rows.append([level, str(count), _format_percentage(pct)])
        lines.append(format_table(
            headers=["Volume Level", "Count", "% of Portfolio"],
            rows=vol_rows,
            align=["left", "right", "right"],
        ))
        lines.append("")

    lines.append("---")
    lines.append("")

    # Top Performers
    lines.append("## Top Performers")
    lines.append("")

    # Top 5 by Revenue
    if summary.top_5_by_revenue:
        lines.append("### Top 5 by Revenue")
        lines.append("")
        rev_rows = []
        for cr in summary.top_5_by_revenue:
            rev_rows.append([f"#{cr.rank}", cr.display_name or cr.page_name, _format_currency(cr.value)])
        lines.append(format_table(
            headers=["Rank", "Creator", "Earnings"],
            rows=rev_rows,
            align=["right", "left", "right"],
        ))
        lines.append("")

    # Top 5 by Fans
    if summary.top_5_by_fans:
        lines.append("### Top 5 by Fans")
        lines.append("")
        fans_rows = []
        for cr in summary.top_5_by_fans:
            fans_rows.append([f"#{cr.rank}", cr.display_name or cr.page_name, f"{cr.value:,.0f}"])
        lines.append(format_table(
            headers=["Rank", "Creator", "Fans"],
            rows=fans_rows,
            align=["right", "left", "right"],
        ))
        lines.append("")

    # Top 5 by Efficiency
    if summary.top_5_by_efficiency:
        lines.append("### Top 5 by Efficiency (Earnings/Fan)")
        lines.append("")
        eff_rows = []
        for cr in summary.top_5_by_efficiency:
            eff_rows.append([f"#{cr.rank}", cr.display_name or cr.page_name, _format_currency(cr.value)])
        lines.append(format_table(
            headers=["Rank", "Creator", "$/Fan"],
            rows=eff_rows,
            align=["right", "left", "right"],
        ))
        lines.append("")

    # Bottom 5 by Revenue
    if summary.bottom_5_by_revenue:
        lines.append("### Bottom 5 by Revenue")
        lines.append("")
        bottom_rows = []
        for cr in summary.bottom_5_by_revenue:
            bottom_rows.append([f"#{cr.rank}", cr.display_name or cr.page_name, _format_currency(cr.value)])
        lines.append(format_table(
            headers=["Rank", "Creator", "Earnings"],
            rows=bottom_rows,
            align=["right", "left", "right"],
        ))
        lines.append("")

    lines.append("---")
    lines.append("")

    # Creators Needing Attention
    if summary.needs_attention:
        lines.append("## Creators Needing Attention")
        lines.append("")
        for creator in summary.needs_attention:
            severity_indicator = "-" if creator.severity == "critical" else ("~" if creator.severity == "high" else "")
            lines.append(f"### {severity_indicator} {creator.display_name or creator.page_name}")
            lines.append(f"- **Reason:** {creator.reason}")
            lines.append(f"- **Severity:** {creator.severity.capitalize()}")
            if creator.metrics:
                lines.append("- **Metrics:**")
                for key, value in creator.metrics.items():
                    if isinstance(value, float):
                        lines.append(f"  - {key}: {value:.2f}")
                    else:
                        lines.append(f"  - {key}: {value}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Caption Health Portfolio-Wide
    lines.append("## Caption Health (Portfolio-Wide)")
    lines.append("")
    lines.append(format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Total Captions", f"{summary.total_captions:,}"],
            ["Fresh Captions", f"{summary.fresh_captions:,}"],
            ["Stale Captions", f"{summary.stale_captions:,}"],
            ["Avg Freshness", f"{summary.avg_freshness:.1f}"],
        ],
        align=["left", "right"],
    ))
    lines.append("")

    # Fresh/stale ratio
    if summary.total_captions > 0:
        fresh_pct = summary.fresh_captions / summary.total_captions * 100
        stale_pct = summary.stale_captions / summary.total_captions * 100
        lines.append(f"**Fresh Rate:** {_format_percentage(fresh_pct)}")
        lines.append(f"**Stale Rate:** {_format_percentage(stale_pct)}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Processing Stats
    lines.append("## Processing Statistics")
    lines.append("")
    lines.append(format_table(
        headers=["Metric", "Value"],
        rows=[
            ["Successful Analyses", str(summary.successful_analyses)],
            ["Failed Analyses", str(summary.failed_analyses)],
            ["Success Rate", _format_percentage(summary.successful_analyses / (summary.successful_analyses + summary.failed_analyses) * 100) if (summary.successful_analyses + summary.failed_analyses) > 0 else "N/A"],
            ["Total Duration", f"{summary.total_duration_seconds:.1f}s"],
        ],
        align=["left", "right"],
    ))
    lines.append("")

    # Error Log
    if summary.errors:
        lines.append("## Error Log")
        lines.append("")
        for error in summary.errors:
            lines.append(f"- **{error.page_name}** ({error.phase}): {error.error_type} - {error.error_message}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by EROS Schedule Generator - Portfolio Executive Dashboard*")

    return "\n".join(lines)


def format_portfolio_summary_json(summary: PortfolioSummary) -> str:
    """
    Format portfolio summary as pretty-printed JSON.

    Args:
        summary: PortfolioSummary dataclass instance.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(summary.to_dict(), indent=2, default=str)


# =============================================================================
# PHASE 7: FILE I/O AND BATCH PROCESSING
# =============================================================================


def create_output_folder(base_path: Path | None = None) -> Path:
    """
    Create timestamped output folder on Desktop.

    Creates a uniquely-named folder for storing all analysis output files,
    using the format: EROS_Creator_Analysis_YYYY-MM-DD_HHMMSS

    Args:
        base_path: Optional base path (defaults to ~/Desktop)

    Returns:
        Path to created folder.

    Raises:
        OSError: If folder creation fails.
    """
    if base_path is None:
        base_path = Path.home() / "Desktop"

    # Generate timestamped folder name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder_name = f"EROS_Creator_Analysis_{timestamp}"
    output_dir = base_path / folder_name

    # Create the directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output folder: {output_dir}")
    except OSError as e:
        logger.error(f"Failed to create output folder: {e}")
        raise

    return output_dir


def sanitize_folder_name(name: str) -> str:
    """
    Convert creator name to valid folder name.

    Transforms a creator name into a filesystem-safe folder name by:
    - Converting to lowercase
    - Replacing spaces with underscores
    - Removing special characters
    - Limiting length to 50 characters

    Args:
        name: Creator name to sanitize.

    Returns:
        Sanitized folder name string.

    Examples:
        >>> sanitize_folder_name("Miss Alexa")
        'miss_alexa'
        >>> sanitize_folder_name("Creator@123!")
        'creator123'
    """
    # Convert to lowercase
    sanitized = name.lower()

    # Replace spaces with underscores
    sanitized = sanitized.replace(" ", "_")

    # Remove special characters (keep alphanumeric and underscores)
    sanitized = re.sub(r"[^a-z0-9_]", "", sanitized)

    # Remove consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Strip leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Limit length
    max_length = 50
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")

    # Ensure non-empty
    if not sanitized:
        sanitized = "creator"

    return sanitized


def save_creator_analysis(
    output_dir: Path,
    creator_name: str,
    quick_result: QuickAnalysisResult | None,
    deep_result: DeepAnalysisResult | None,
    mode: AnalysisMode = AnalysisMode.FULL
) -> None:
    """
    Save all analysis files for a single creator.

    Creates a subfolder for the creator and saves both Markdown and JSON
    format files for each analysis type that was performed.

    Folder structure:
        output_dir/
            [creator_name]/
                quick_analysis.md
                quick_analysis.json
                deep_analysis.md
                deep_analysis.json

    Args:
        output_dir: Base output directory path.
        creator_name: Creator's page name for folder naming.
        quick_result: Quick analysis result (may be None).
        deep_result: Deep analysis result (may be None).
        mode: Analysis mode that was used.

    Raises:
        OSError: If file writing fails.
    """
    # Create sanitized creator folder
    folder_name = sanitize_folder_name(creator_name)
    creator_dir = output_dir / folder_name
    creator_dir.mkdir(parents=True, exist_ok=True)

    # Save quick analysis files
    if quick_result is not None:
        # Markdown format
        quick_md_path = creator_dir / "quick_analysis.md"
        try:
            quick_md_content = format_quick_analysis_markdown(quick_result)
            quick_md_path.write_text(quick_md_content, encoding="utf-8")
            logger.debug(f"Saved quick analysis MD: {quick_md_path}")
        except Exception as e:
            logger.error(f"Failed to save quick_analysis.md for {creator_name}: {e}")

        # JSON format
        quick_json_path = creator_dir / "quick_analysis.json"
        try:
            quick_json_content = format_quick_analysis_json(quick_result)
            quick_json_path.write_text(quick_json_content, encoding="utf-8")
            logger.debug(f"Saved quick analysis JSON: {quick_json_path}")
        except Exception as e:
            logger.error(f"Failed to save quick_analysis.json for {creator_name}: {e}")

    # Save deep analysis files
    if deep_result is not None:
        # Markdown format
        deep_md_path = creator_dir / "deep_analysis.md"
        try:
            deep_md_content = format_deep_analysis_markdown(deep_result)
            deep_md_path.write_text(deep_md_content, encoding="utf-8")
            logger.debug(f"Saved deep analysis MD: {deep_md_path}")
        except Exception as e:
            logger.error(f"Failed to save deep_analysis.md for {creator_name}: {e}")

        # JSON format
        deep_json_path = creator_dir / "deep_analysis.json"
        try:
            deep_json_content = format_deep_analysis_json(deep_result)
            deep_json_path.write_text(deep_json_content, encoding="utf-8")
            logger.debug(f"Saved deep analysis JSON: {deep_json_path}")
        except Exception as e:
            logger.error(f"Failed to save deep_analysis.json for {creator_name}: {e}")

    logger.info(f"Saved analysis files for {creator_name} to {creator_dir}")


def calculate_portfolio_summary(
    quick_results: list[QuickAnalysisResult],
    deep_results: list[DeepAnalysisResult],
    errors: list[AnalysisError],
    start_time: float,
    end_time: float
) -> PortfolioSummary:
    """
    Calculate aggregate portfolio statistics from all creator analyses.

    Aggregates data from both quick and deep analysis results to produce
    comprehensive portfolio-level metrics including:
    - Total earnings, fans, creators
    - Tier distribution
    - Top/bottom performers
    - Caption health portfolio-wide
    - Processing statistics

    Args:
        quick_results: List of successful quick analysis results.
        deep_results: List of successful deep analysis results.
        errors: List of analysis errors encountered.
        start_time: Batch processing start time (time.perf_counter()).
        end_time: Batch processing end time (time.perf_counter()).

    Returns:
        PortfolioSummary dataclass with aggregate metrics.
    """
    summary = PortfolioSummary()
    summary.total_duration_seconds = round(end_time - start_time, 2)
    summary.successful_analyses = len(quick_results) + len(deep_results)
    summary.failed_analyses = len(errors)
    summary.errors = errors

    # Track creators to avoid double-counting
    processed_creators: set[str] = set()

    # Aggregate from quick results (primary source for basic metrics)
    total_earnings = 0.0
    total_message_revenue = 0.0
    total_subscription_revenue = 0.0
    total_fans = 0
    tier_distribution: dict[int, int] = {}
    volume_distribution: dict[str, int] = {}

    revenue_rankings: list[tuple[str, str, str, float]] = []  # (id, page, display, value)
    fan_rankings: list[tuple[str, str, str, int]] = []
    efficiency_rankings: list[tuple[str, str, str, float]] = []

    for qr in quick_results:
        if qr.creator_id in processed_creators:
            continue
        processed_creators.add(qr.creator_id)

        if qr.brief:
            # Revenue metrics
            earnings = qr.brief.total_earnings if hasattr(qr.brief, 'total_earnings') else 0.0
            total_earnings += earnings

            # Fan metrics
            fans = qr.brief.active_fans if hasattr(qr.brief, 'active_fans') else 0
            total_fans += fans

            # Revenue breakdown (from brief if available)
            if hasattr(qr.brief, 'message_net'):
                total_message_revenue += qr.brief.message_net
            if hasattr(qr.brief, 'subscription_net'):
                total_subscription_revenue += qr.brief.subscription_net

            # Volume level distribution
            vol_level = qr.brief.volume_level if hasattr(qr.brief, 'volume_level') else "unknown"
            volume_distribution[vol_level] = volume_distribution.get(vol_level, 0) + 1

            # Rankings data
            revenue_rankings.append((qr.creator_id, qr.page_name, qr.display_name, earnings))
            fan_rankings.append((qr.creator_id, qr.page_name, qr.display_name, fans))

            # Efficiency (earnings per fan)
            efficiency = earnings / fans if fans > 0 else 0.0
            efficiency_rankings.append((qr.creator_id, qr.page_name, qr.display_name, efficiency))

        if qr.benchmarks:
            # Tier distribution
            tier = qr.benchmarks.performance_tier if hasattr(qr.benchmarks, 'performance_tier') else 0
            tier_distribution[tier] = tier_distribution.get(tier, 0) + 1

    # Aggregate from deep results (for caption health and detailed metrics)
    total_captions = 0
    total_fresh = 0
    total_stale = 0
    freshness_scores: list[float] = []

    paid_pages = 0
    free_pages = 0

    # Track creators needing attention
    attention_list: list[CreatorAttention] = []

    for dr in deep_results:
        # Caption health aggregation
        if dr.captions:
            total_captions += dr.captions.total_captions
            total_fresh += dr.captions.fresh_count
            total_stale += dr.captions.stale_count
            if dr.captions.avg_freshness > 0:
                freshness_scores.append(dr.captions.avg_freshness)

            # Check for critical caption health
            if dr.captions.caption_health_rating == "Critical":
                attention_list.append(CreatorAttention(
                    creator_id=dr.creator_id,
                    page_name=dr.page_name,
                    display_name=dr.display_name,
                    reason="Critical caption health - stale captions need refresh",
                    severity="critical",
                    metrics={
                        "avg_freshness": dr.captions.avg_freshness,
                        "critical_stale_count": dr.captions.critical_stale_count,
                    }
                ))

        # Revenue warnings
        if dr.revenue:
            if dr.revenue.msg_sub_rating == "POOR":
                attention_list.append(CreatorAttention(
                    creator_id=dr.creator_id,
                    page_name=dr.page_name,
                    display_name=dr.display_name,
                    reason="Poor message:subscription ratio - PPV underperforming",
                    severity="high",
                    metrics={
                        "msg_sub_ratio": dr.revenue.msg_sub_ratio,
                        "msg_pct": dr.revenue.msg_pct,
                    }
                ))

        # Portfolio position warnings
        if dr.portfolio_position:
            if dr.portfolio_position.earnings_percentile < 25:
                attention_list.append(CreatorAttention(
                    creator_id=dr.creator_id,
                    page_name=dr.page_name,
                    display_name=dr.display_name,
                    reason="Bottom quartile earnings - growth opportunity",
                    severity="medium",
                    metrics={
                        "earnings_rank": dr.portfolio_position.earnings_rank,
                        "earnings_percentile": dr.portfolio_position.earnings_percentile,
                    }
                ))

        # Health score warnings
        if dr.health_score < 40:
            # Avoid duplicate if already flagged
            if not any(a.creator_id == dr.creator_id and a.severity == "critical" for a in attention_list):
                attention_list.append(CreatorAttention(
                    creator_id=dr.creator_id,
                    page_name=dr.page_name,
                    display_name=dr.display_name,
                    reason=f"Low health score ({dr.health_score}/100) - needs strategic review",
                    severity="high",
                    metrics={
                        "health_score": dr.health_score,
                        "health_rating": dr.health_rating,
                    }
                ))

    # Calculate creator counts
    summary.total_creators = len(processed_creators)
    summary.active_creators = len(processed_creators)  # All analyzed are active
    summary.paid_pages = paid_pages  # Would need page_type from database
    summary.free_pages = free_pages

    # Portfolio financials
    summary.total_portfolio_earnings = total_earnings
    summary.total_message_revenue = total_message_revenue
    summary.total_subscription_revenue = total_subscription_revenue

    # Averages
    if summary.active_creators > 0:
        summary.avg_earnings_per_creator = total_earnings / summary.active_creators
        summary.avg_fans_per_creator = total_fans / summary.active_creators

    # Distributions
    summary.tier_distribution = tier_distribution
    summary.volume_distribution = volume_distribution

    # Sort and create rankings
    revenue_rankings.sort(key=lambda x: x[3], reverse=True)
    fan_rankings.sort(key=lambda x: x[3], reverse=True)
    efficiency_rankings.sort(key=lambda x: x[3], reverse=True)

    # Top 5 by revenue
    summary.top_5_by_revenue = [
        CreatorRanking(
            creator_id=r[0],
            page_name=r[1],
            display_name=r[2],
            value=r[3],
            rank=i + 1
        )
        for i, r in enumerate(revenue_rankings[:5])
    ]

    # Top 5 by fans
    summary.top_5_by_fans = [
        CreatorRanking(
            creator_id=r[0],
            page_name=r[1],
            display_name=r[2],
            value=float(r[3]),
            rank=i + 1
        )
        for i, r in enumerate(fan_rankings[:5])
    ]

    # Top 5 by efficiency
    summary.top_5_by_efficiency = [
        CreatorRanking(
            creator_id=r[0],
            page_name=r[1],
            display_name=r[2],
            value=r[3],
            rank=i + 1
        )
        for i, r in enumerate(efficiency_rankings[:5])
    ]

    # Bottom 5 by revenue
    summary.bottom_5_by_revenue = [
        CreatorRanking(
            creator_id=r[0],
            page_name=r[1],
            display_name=r[2],
            value=r[3],
            rank=len(revenue_rankings) - i
        )
        for i, r in enumerate(reversed(revenue_rankings[-5:]))
    ]

    # Needs attention (sorted by severity)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    attention_list.sort(key=lambda x: severity_order.get(x.severity, 4))
    summary.needs_attention = attention_list

    # Caption health portfolio-wide
    summary.total_captions = total_captions
    summary.fresh_captions = total_fresh
    summary.stale_captions = total_stale
    summary.avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0

    return summary


def run_batch_analysis(
    db: DatabaseManager,
    output_dir: Path,
    mode: AnalysisMode = AnalysisMode.FULL,
    creators: list[str] | None = None,
    verbose: bool = False,
    progress_callback: Callable[[int, int, str, str], None] | None = None
) -> BatchAnalysisResult:
    """
    Main batch processing loop for portfolio analysis.

    Processes all (or specified) active creators, running quick and/or deep
    analysis based on the mode, and saves all results incrementally.

    Processing steps:
    1. Get list of active creators from database
    2. Filter to specific creators if provided
    3. For each creator:
        a. Run quick analysis (if mode allows)
        b. Run deep analysis (if mode allows)
        c. Save files immediately (incremental)
        d. Track results and errors
    4. Generate portfolio summary
    5. Save portfolio summary files
    6. Return BatchAnalysisResult

    Args:
        db: DatabaseManager instance with active connection.
        output_dir: Output directory path for all files.
        mode: Analysis mode (QUICK, DEEP, or FULL).
        creators: Optional list of specific creator page_names to process.
        verbose: Show detailed progress output.
        progress_callback: Optional callback(current, total, creator_name, status)
            for custom progress reporting.

    Returns:
        BatchAnalysisResult containing all results, errors, and summary.

    Example:
        >>> with DatabaseManager(db_path) as db:
        ...     output = create_output_folder()
        ...     result = run_batch_analysis(db, output, mode=AnalysisMode.FULL)
        ...     print(f"Processed {len(result.quick_analyses)} creators")
    """
    start_time = time.perf_counter()
    started_at = datetime.now().isoformat()

    # Initialize result containers
    quick_results: list[QuickAnalysisResult] = []
    deep_results: list[DeepAnalysisResult] = []
    errors: list[AnalysisError] = []

    # Get all active creators
    all_creators = db.get_all_active_creators()
    logger.info(f"Found {len(all_creators)} active creators in database")

    # Filter to specific creators if requested
    if creators:
        creator_set = set(c.lower() for c in creators)
        all_creators = [c for c in all_creators if c["page_name"].lower() in creator_set]
        logger.info(f"Filtered to {len(all_creators)} specified creators")

    total = len(all_creators)

    if verbose:
        print("\nEROS Portfolio Analysis")
        print("=" * 60)
        print(f"Analyzing {total} active creators...")
        print(f"Mode: {mode.value}")
        print(f"Output: {output_dir}")
        print("")

    # Process each creator
    for idx, creator_data in enumerate(all_creators, 1):
        creator_id = creator_data["creator_id"]
        page_name = creator_data["page_name"]
        display_name = creator_data.get("display_name", "")

        if verbose:
            print(f"[{idx}/{total}] {page_name}")

        if progress_callback:
            progress_callback(idx, total, page_name, "starting")

        quick_result: QuickAnalysisResult | None = None
        deep_result: DeepAnalysisResult | None = None

        # Run quick analysis
        if mode in (AnalysisMode.QUICK, AnalysisMode.FULL):
            try:
                if verbose:
                    print("  - Quick analysis...", end=" ", flush=True)

                quick_start = time.perf_counter()
                quick_result = run_quick_analysis(
                    db=db,
                    creator_id=creator_id,
                    creator_name=page_name,
                    display_name=display_name,
                )
                quick_duration = int((time.perf_counter() - quick_start) * 1000)

                if verbose:
                    print(f"Done ({quick_duration}ms)")

                quick_results.append(quick_result)

            except Exception as e:
                error_msg = str(e)
                if verbose:
                    print(f"FAILED: {error_msg}")

                errors.append(AnalysisError(
                    creator_id=creator_id,
                    page_name=page_name,
                    phase="quick_analysis",
                    error_type=type(e).__name__,
                    error_message=error_msg,
                    timestamp=datetime.now().isoformat(),
                ))

        # Run deep analysis
        if mode in (AnalysisMode.DEEP, AnalysisMode.FULL):
            try:
                if verbose:
                    print("  - Deep analysis...", end=" ", flush=True)

                deep_start = time.perf_counter()
                deep_result = run_deep_analysis(
                    db=db,
                    creator_id=creator_id,
                    creator_name=page_name,
                    display_name=display_name,
                )
                deep_duration = int((time.perf_counter() - deep_start) * 1000)

                if verbose:
                    print(f"Done ({deep_duration}ms)")

                deep_results.append(deep_result)

            except Exception as e:
                error_msg = str(e)
                if verbose:
                    print(f"FAILED: {error_msg}")

                errors.append(AnalysisError(
                    creator_id=creator_id,
                    page_name=page_name,
                    phase="deep_analysis",
                    error_type=type(e).__name__,
                    error_message=error_msg,
                    timestamp=datetime.now().isoformat(),
                ))

        # Save files immediately (incremental save)
        try:
            save_creator_analysis(
                output_dir=output_dir,
                creator_name=page_name,
                quick_result=quick_result,
                deep_result=deep_result,
                mode=mode,
            )
            if verbose:
                print("  - Files saved")
        except Exception as e:
            logger.error(f"Failed to save files for {page_name}: {e}")
            if verbose:
                print(f"  - File save FAILED: {e}")

        if progress_callback:
            progress_callback(idx, total, page_name, "completed")

    # Calculate batch end time
    end_time = time.perf_counter()
    completed_at = datetime.now().isoformat()

    # Generate portfolio summary
    if verbose:
        print("\nGenerating portfolio summary...")

    portfolio_summary = calculate_portfolio_summary(
        quick_results=quick_results,
        deep_results=deep_results,
        errors=errors,
        start_time=start_time,
        end_time=end_time,
    )

    # Save portfolio summary files
    try:
        # Markdown summary
        summary_md_path = output_dir / "PORTFOLIO_SUMMARY.md"
        summary_md_content = format_portfolio_summary_markdown(portfolio_summary)
        summary_md_path.write_text(summary_md_content, encoding="utf-8")

        # JSON summary
        summary_json_path = output_dir / "portfolio_summary.json"
        summary_json_content = format_portfolio_summary_json(portfolio_summary)
        summary_json_path.write_text(summary_json_content, encoding="utf-8")

        if verbose:
            print(f"Portfolio summary saved to {output_dir}")

    except Exception as e:
        logger.error(f"Failed to save portfolio summary: {e}")
        if verbose:
            print(f"Portfolio summary save FAILED: {e}")

    # Build final result
    result = BatchAnalysisResult(
        quick_analyses=quick_results,
        deep_analyses=deep_results,
        portfolio_summary=portfolio_summary,
        analysis_mode=mode.value,
        started_at=started_at,
        completed_at=completed_at,
        total_duration_seconds=round(end_time - start_time, 2),
    )

    # Save complete batch result JSON
    try:
        batch_json_path = output_dir / "batch_result.json"
        batch_json_path.write_text(result.to_json(), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save batch result JSON: {e}")

    if verbose:
        print("\n" + "=" * 60)
        print("Batch Analysis Complete")
        print("=" * 60)
        print(f"Quick analyses: {len(quick_results)}")
        print(f"Deep analyses: {len(deep_results)}")
        print(f"Errors: {len(errors)}")
        print(f"Duration: {result.total_duration_seconds:.1f}s")
        print(f"Output: {output_dir}")

    return result


# =============================================================================
# CLI INTERFACE
# =============================================================================

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_COMPLETE_FAILURE = 2
EXIT_INVALID_ARGS = 3


class TerminalColors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"

    @classmethod
    def supports_color(cls) -> bool:
        """Check if the terminal supports colors."""
        # Check if stdout is a tty
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False

        # Check for NO_COLOR environment variable
        if os.environ.get("NO_COLOR"):
            return False

        # Check for TERM
        term = os.environ.get("TERM", "")
        if term == "dumb":
            return False

        # Platform-specific checks
        if sys.platform == "win32":
            # Windows 10+ supports ANSI codes
            return os.environ.get("ANSICON") or os.environ.get("WT_SESSION")

        return True


def _get_colors() -> TerminalColors | None:
    """Get color codes if terminal supports them, else None."""
    if TerminalColors.supports_color():
        return TerminalColors()
    return None


def print_progress(
    current: int,
    total: int,
    width: int = 40,
    show_percentage: bool = True
) -> None:
    """
    Print a text-based progress bar that updates in-place.

    Args:
        current: Current progress count.
        total: Total items to process.
        width: Width of the progress bar in characters.
        show_percentage: Whether to show percentage.
    """
    if total == 0:
        return

    pct = current / total
    filled = int(width * pct)
    bar = "\u2588" * filled + "\u2591" * (width - filled)

    if show_percentage:
        status = f"{current}/{total} {pct*100:.0f}%"
    else:
        status = f"{current}/{total}"

    print(f"\r[{bar}] {status}", end="", flush=True)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


class CLIOutput:
    """Handle CLI output with optional color support."""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.verbose = verbose
        self.quiet = quiet
        self.colors = _get_colors()

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if supported."""
        if self.colors:
            return f"{color}{text}{TerminalColors.RESET}"
        return text

    def header(self, text: str) -> None:
        """Print header text."""
        if self.quiet:
            return
        if self.colors:
            print(f"{TerminalColors.BOLD}{TerminalColors.CYAN}{text}{TerminalColors.RESET}")
        else:
            print(text)

    def info(self, text: str) -> None:
        """Print info text."""
        if self.quiet:
            return
        print(text)

    def success(self, text: str) -> None:
        """Print success message."""
        if self.quiet:
            return
        print(self._colorize(text, TerminalColors.GREEN if self.colors else ""))

    def warning(self, text: str) -> None:
        """Print warning message."""
        if self.quiet:
            return
        print(self._colorize(text, TerminalColors.YELLOW if self.colors else ""))

    def error(self, text: str) -> None:
        """Print error message (always shown, even in quiet mode)."""
        err_text = f"[ERROR] {text}"
        if self.colors:
            print(self._colorize(err_text, TerminalColors.RED), file=sys.stderr)
        else:
            print(err_text, file=sys.stderr)

    def detail(self, text: str) -> None:
        """Print detail text (only in verbose mode)."""
        if self.verbose and not self.quiet:
            if self.colors:
                print(f"{TerminalColors.DIM}{text}{TerminalColors.RESET}")
            else:
                print(text)

    def separator(self, char: str = "=", width: int = 60) -> None:
        """Print separator line."""
        if self.quiet:
            return
        print(char * width)


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    # Custom formatter for better help text
    class CustomFormatter(
        argparse.RawDescriptionHelpFormatter,
        argparse.ArgumentDefaultsHelpFormatter
    ):
        pass

    parser = argparse.ArgumentParser(
        prog="batch_portfolio_analysis.py",
        description="EROS Portfolio Analysis - Comprehensive OnlyFans creator analytics",
        formatter_class=CustomFormatter,
        epilog="""
Examples:
  %(prog)s                                    Full analysis, all creators
  %(prog)s --mode quick                       Quick analysis only
  %(prog)s --mode deep                        Deep analysis only
  %(prog)s --creators missalexa maya_hill     Specific creators
  %(prog)s --output ~/reports                 Custom output directory
  %(prog)s --verbose                          Detailed progress
  %(prog)s --test                             Test mode (single creator)
  %(prog)s --test --test-creator missalexa    Test with specific creator
  %(prog)s --dry-run                          Preview what would be done

Exit codes:
  0  Success
  1  Partial success (some creators failed)
  2  Complete failure
  3  Invalid arguments
        """,
    )

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    # Analysis mode group
    mode_group = parser.add_argument_group("Analysis Options")
    mode_group.add_argument(
        "--mode",
        type=str,
        choices=["full", "quick", "deep"],
        default="full",
        metavar="MODE",
        help="Analysis mode: full (quick+deep), quick (7-step), deep (9-phase)",
    )
    mode_group.add_argument(
        "--creators",
        nargs="+",
        metavar="NAME",
        help="Specific creator page_names to analyze (default: all active)",
    )
    mode_group.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        dest="output_dir",
        help="Output directory (default: ~/Desktop/EROS_Creator_Analysis_TIMESTAMP)",
    )
    mode_group.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        metavar="PATH",
        help="Path to EROS database",
    )

    # Output control group
    output_group = parser.add_argument_group("Output Control")
    verbosity = output_group.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress output",
    )
    verbosity.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (errors only)",
    )

    # Test and dry-run group
    test_group = parser.add_argument_group("Testing")
    test_group.add_argument(
        "--test",
        action="store_true",
        help="Test mode: analyze one creator and display results",
    )
    test_group.add_argument(
        "--test-creator",
        type=str,
        metavar="NAME",
        help="Creator for test mode (default: first active creator)",
    )
    test_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )

    return parser


def run_test_mode(
    db_path: Path,
    test_creator: str | None,
    output: CLIOutput
) -> int:
    """
    Run test mode: analyze single creator and display results.

    Args:
        db_path: Path to the database.
        test_creator: Optional specific creator name.
        output: CLI output handler.

    Returns:
        Exit code.
    """
    output.header(f"\nEROS Portfolio Analysis v{VERSION} - Test Mode")
    output.separator()

    try:
        with DatabaseManager(db_path) as db:
            # Get creators
            creators = db.get_all_active_creators()
            if not creators:
                output.error("No active creators found in database")
                return EXIT_COMPLETE_FAILURE

            # Select test creator
            if test_creator:
                creator_data = next(
                    (c for c in creators if c["page_name"].lower() == test_creator.lower()),
                    None
                )
                if not creator_data:
                    output.error(f"Creator '{test_creator}' not found")
                    output.info(f"Available creators: {', '.join(c['page_name'] for c in creators[:5])}...")
                    return EXIT_INVALID_ARGS
            else:
                creator_data = creators[0]

            creator_id = creator_data["creator_id"]
            page_name = creator_data["page_name"]
            display_name = creator_data.get("display_name", "")

            output.info(f"\nTesting with creator: {page_name}")
            output.info(f"Database: {db_path}")
            output.separator("-", 40)

            # Run quick analysis
            output.info("\n[1/2] Running quick analysis...")
            try:
                quick_start = time.perf_counter()
                quick_result = run_quick_analysis(
                    db=db,
                    creator_id=creator_id,
                    creator_name=page_name,
                    display_name=display_name,
                )
                quick_duration = (time.perf_counter() - quick_start) * 1000

                output.success(f"  Quick analysis: Done ({quick_duration:.0f}ms)")
                if quick_result.brief:
                    output.detail(f"    Volume level: {quick_result.brief.volume_level}")
                    output.detail(f"    Active fans: {quick_result.brief.active_fans:,}")
                    output.detail(f"    PPV/day: {quick_result.brief.ppv_per_day}")
                if quick_result.benchmarks:
                    output.detail(f"    Percentile: {quick_result.benchmarks.overall_percentile}th")
            except Exception as e:
                output.error(f"Quick analysis failed: {e}")

            # Run deep analysis
            output.info("\n[2/2] Running deep analysis...")
            try:
                deep_start = time.perf_counter()
                deep_result = run_deep_analysis(
                    db=db,
                    creator_id=creator_id,
                    creator_name=page_name,
                    display_name=display_name,
                )
                deep_duration = (time.perf_counter() - deep_start) * 1000

                output.success(f"  Deep analysis: Done ({deep_duration:.0f}ms)")
                output.detail(f"    Health score: {deep_result.health_score}/100 ({deep_result.health_rating})")
                if deep_result.revenue:
                    output.detail(f"    Total earnings: ${deep_result.revenue.total_earnings:,.2f}")
            except Exception as e:
                output.error(f"Deep analysis failed: {e}")

            output.info("")
            output.separator()
            output.success("Test completed successfully")
            return EXIT_SUCCESS

    except DatabaseError as e:
        output.error(f"Database error: {e}")
        return EXIT_COMPLETE_FAILURE
    except Exception as e:
        output.error(f"Unexpected error: {e}")
        logger.exception("Test mode failed")
        return EXIT_COMPLETE_FAILURE


def run_dry_run(
    db_path: Path,
    mode: AnalysisMode,
    creators: list[str] | None,
    output_dir: Path | None,
    output: CLIOutput
) -> int:
    """
    Show what would be done without executing.

    Args:
        db_path: Path to the database.
        mode: Analysis mode.
        creators: Optional list of specific creators.
        output_dir: Output directory.
        output: CLI output handler.

    Returns:
        Exit code.
    """
    output.header(f"\nEROS Portfolio Analysis v{VERSION} - Dry Run")
    output.separator()

    try:
        with DatabaseManager(db_path) as db:
            all_creators = db.get_all_active_creators()

            if creators:
                creator_set = set(c.lower() for c in creators)
                target_creators = [c for c in all_creators if c["page_name"].lower() in creator_set]
            else:
                target_creators = all_creators

            # Resolve output directory
            if output_dir:
                resolved_output = output_dir
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                resolved_output = Path.home() / "Desktop" / f"EROS_Creator_Analysis_{timestamp}"

            output.info(f"\nMode: {mode.value}")
            output.info(f"Database: {db_path}")
            output.info(f"Output directory: {resolved_output}")
            output.info(f"Creators to analyze: {len(target_creators)}")

            if target_creators:
                output.info("\nCreators:")
                for i, c in enumerate(target_creators, 1):
                    output.info(f"  {i}. {c['page_name']}")

            output.info("\nAnalysis steps per creator:")
            if mode in (AnalysisMode.QUICK, AnalysisMode.FULL):
                output.info("  - Quick analysis (7-step)")
            if mode in (AnalysisMode.DEEP, AnalysisMode.FULL):
                output.info("  - Deep analysis (9-phase)")

            output.info("\nOutput files per creator:")
            if mode in (AnalysisMode.QUICK, AnalysisMode.FULL):
                output.info("  - quick_analysis.md")
                output.info("  - quick_analysis.json")
            if mode in (AnalysisMode.DEEP, AnalysisMode.FULL):
                output.info("  - deep_analysis.md")
                output.info("  - deep_analysis.json")

            output.info("\nPortfolio-level output:")
            output.info("  - PORTFOLIO_SUMMARY.md")
            output.info("  - portfolio_summary.json")
            output.info("  - batch_result.json")

            output.info("")
            output.separator()
            output.info("Dry run complete. No files were created.")
            return EXIT_SUCCESS

    except DatabaseError as e:
        output.error(f"Database error: {e}")
        return EXIT_COMPLETE_FAILURE


def run_batch_mode(
    db_path: Path,
    mode: AnalysisMode,
    creators: list[str] | None,
    output_dir: Path | None,
    output: CLIOutput
) -> int:
    """
    Run batch analysis on portfolio.

    Args:
        db_path: Path to the database.
        mode: Analysis mode.
        creators: Optional list of specific creators.
        output_dir: Output directory.
        output: CLI output handler.

    Returns:
        Exit code.
    """
    output.header(f"\nEROS Portfolio Analysis v{VERSION}")
    output.separator()

    try:
        with DatabaseManager(db_path) as db:
            # Get creator count for display
            all_creators = db.get_all_active_creators()
            if creators:
                creator_set = set(c.lower() for c in creators)
                target_creators = [c for c in all_creators if c["page_name"].lower() in creator_set]
                creator_count = len(target_creators)
            else:
                creator_count = len(all_creators)

            # Create output directory
            if output_dir:
                resolved_output = output_dir
                resolved_output.mkdir(parents=True, exist_ok=True)
            else:
                resolved_output = create_output_folder()

            # Display configuration
            output.info(f"\nMode: {mode.value.capitalize()} Analysis")
            output.info(f"Creators: {creator_count} active")
            output.info(f"Output: {resolved_output}/")
            output.info("")

            # Progress tracking
            processed = 0
            errors_list: list[str] = []

            def progress_callback(current: int, total: int, name: str, status: str) -> None:
                nonlocal processed
                if status == "completed":
                    processed = current
                if not output.quiet and not output.verbose:
                    print_progress(current, total)

            # Run analysis
            output.info("Processing...")
            start_time = time.perf_counter()

            result = run_batch_analysis(
                db=db,
                output_dir=resolved_output,
                mode=mode,
                creators=creators,
                verbose=output.verbose,
                progress_callback=None if output.verbose else progress_callback,
            )

            duration = time.perf_counter() - start_time

            # Clear progress bar line
            if not output.quiet and not output.verbose:
                print()  # New line after progress bar

            # Calculate success/failure counts
            total_processed = len(result.quick_analyses) + len(result.deep_analyses)
            error_count = len(result.portfolio_summary.errors) if result.portfolio_summary else 0
            success_count = creator_count - error_count

            # Summary output
            output.info("")
            output.header("Complete!")
            output.separator("-", 40)

            if success_count == creator_count:
                output.success(f"Successful: {success_count}")
            else:
                output.info(f"Successful: {success_count}")

            if error_count > 0:
                output.warning(f"Failed: {error_count} (see portfolio_summary.json for details)")
            else:
                output.info(f"Failed: 0")

            output.info(f"Duration: {format_duration(duration)}")

            if result.portfolio_summary:
                output.detail(f"\nPortfolio earnings: ${result.portfolio_summary.total_portfolio_earnings:,.2f}")
                if result.portfolio_summary.needs_attention:
                    output.detail(f"Creators needing attention: {len(result.portfolio_summary.needs_attention)}")

            output.info(f"\nOutput saved to: {resolved_output}/")

            # Determine exit code
            if error_count == 0:
                return EXIT_SUCCESS
            elif error_count < creator_count:
                return EXIT_PARTIAL_FAILURE
            else:
                return EXIT_COMPLETE_FAILURE

    except DatabaseError as e:
        output.error(f"Database error: {e}")
        return EXIT_COMPLETE_FAILURE
    except Exception as e:
        output.error(f"Unexpected error: {e}")
        logger.exception("Batch analysis failed")
        return EXIT_COMPLETE_FAILURE


def main() -> None:
    """
    Main entry point for batch portfolio analysis CLI.

    Provides a production-ready command-line interface for running batch analysis
    on the EROS creator portfolio. Supports multiple modes, progress tracking,
    and comprehensive error handling.

    Exit Codes:
        0: Success
        1: Partial success (some creators failed)
        2: Complete failure
        3: Invalid arguments
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validate arguments
    if args.test_creator and not args.test:
        parser.error("--test-creator requires --test")

    # Create output handler
    output = CLIOutput(verbose=args.verbose, quiet=args.quiet)

    # Validate database path
    if not args.db.exists():
        output.error(f"Database not found: {args.db}")
        output.info("Set EROS_DATABASE_PATH environment variable or use --db option")
        sys.exit(EXIT_INVALID_ARGS)

    # Parse analysis mode
    mode_map = {
        "quick": AnalysisMode.QUICK,
        "deep": AnalysisMode.DEEP,
        "full": AnalysisMode.FULL,
    }
    analysis_mode = mode_map[args.mode]

    # Route to appropriate handler
    if args.test:
        exit_code = run_test_mode(
            db_path=args.db,
            test_creator=args.test_creator,
            output=output,
        )
    elif args.dry_run:
        exit_code = run_dry_run(
            db_path=args.db,
            mode=analysis_mode,
            creators=args.creators,
            output_dir=args.output_dir,
            output=output,
        )
    else:
        exit_code = run_batch_mode(
            db_path=args.db,
            mode=analysis_mode,
            creators=args.creators,
            output_dir=args.output_dir,
            output=output,
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
