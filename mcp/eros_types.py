"""
EROS MCP Server Type Definitions

TypedDict definitions for all tool return types and data structures.
Provides type safety and documentation for MCP API responses.
"""

from typing import TypedDict, Optional, List, Dict, Any


# ============================================================================
# Creator Data Types
# ============================================================================

class CreatorInfo(TypedDict):
    """Basic creator information."""
    creator_id: str
    page_name: str
    display_name: str
    page_type: str  # "paid" | "free"
    subscription_price: Optional[float]
    timezone: str
    creator_group: Optional[str]
    current_active_fans: int
    current_total_earnings: float
    performance_tier: int  # 1-5
    persona_type: Optional[str]
    is_active: int


class AnalyticsSummary(TypedDict):
    """Analytics summary for a creator."""
    creator_id: str
    period_type: str  # "7d" | "14d" | "30d"
    total_sends: int
    total_earnings: float
    avg_earnings_per_send: float
    avg_purchase_rate: float
    avg_view_rate: float


class VolumeAssignment(TypedDict):
    """Volume assignment configuration for a creator."""
    volume_level: str  # "Low" | "Mid" | "High" | "Ultra"
    ppv_per_day: int
    bump_per_day: int
    revenue_items_per_day: Optional[int]
    engagement_items_per_day: Optional[int]
    retention_items_per_day: Optional[int]
    bundle_per_week: Optional[int]
    game_per_week: Optional[int]
    followup_per_day: Optional[int]
    assigned_at: Optional[str]
    assigned_reason: Optional[str]


class ContentTypeRanking(TypedDict):
    """Content type performance ranking."""
    content_type: str
    rank: int
    send_count: int
    total_earnings: float
    avg_earnings: float
    avg_purchase_rate: float
    avg_rps: float
    performance_tier: str  # "TOP" | "MID" | "LOW" | "AVOID"
    recommendation: str
    confidence_score: float


class CreatorProfile(TypedDict):
    """Complete creator profile with analytics and performance data."""
    creator: CreatorInfo
    analytics_summary: Optional[AnalyticsSummary]
    volume_assignment: VolumeAssignment
    top_content_types: List[ContentTypeRanking]


class CreatorListItem(TypedDict):
    """Creator information in list view."""
    creator_id: str
    page_name: str
    display_name: str
    page_type: str
    subscription_price: Optional[float]
    timezone: str
    creator_group: Optional[str]
    current_active_fans: int
    current_total_earnings: float
    performance_tier: int
    persona_type: Optional[str]
    primary_tone: Optional[str]
    emoji_frequency: Optional[str]
    slang_level: Optional[str]


class ActiveCreatorsResponse(TypedDict):
    """Response from get_active_creators."""
    creators: List[CreatorListItem]
    count: int


class PersonaData(TypedDict):
    """Creator persona information."""
    persona_id: int
    primary_tone: str
    secondary_tone: Optional[str]
    emoji_frequency: str
    favorite_emojis: Optional[str]
    slang_level: str
    avg_sentiment: Optional[float]
    avg_caption_length: Optional[int]
    last_analyzed: Optional[str]
    created_at: str
    updated_at: str


class PersonaProfile(TypedDict):
    """Complete persona profile."""
    creator: Dict[str, Any]
    persona: Optional[PersonaData]
    voice_samples: Dict[str, Any]


# ============================================================================
# Performance & Analytics Types
# ============================================================================

class PerformanceTrends(TypedDict):
    """Performance trends and saturation analysis."""
    tracking_date: str
    tracking_period: str  # "7d" | "14d" | "30d"
    avg_daily_volume: float
    total_messages_sent: int
    avg_revenue_per_send: float
    avg_view_rate: float
    avg_purchase_rate: float
    total_earnings: float
    revenue_per_send_trend: Optional[str]
    view_rate_trend: Optional[str]
    purchase_rate_trend: Optional[str]
    earnings_volatility: Optional[float]
    saturation_score: Optional[float]  # 0-100
    opportunity_score: Optional[float]  # 0-100
    recommended_volume_delta: Optional[int]
    calculated_at: str


class ContentTypeRankingsResponse(TypedDict):
    """Content type rankings response."""
    rankings: List[ContentTypeRanking]
    top_types: List[str]
    mid_types: List[str]
    low_types: List[str]
    avoid_types: List[str]
    analysis_date: str


class TimingHour(TypedDict):
    """Best posting hour data."""
    hour: int  # 0-23
    avg_earnings: float
    message_count: int
    total_earnings: float


class TimingDay(TypedDict):
    """Best posting day data."""
    day_of_week: int  # 0-6 (Sunday-Saturday)
    day_name: str
    avg_earnings: float
    message_count: int
    total_earnings: float


class BestTimingResponse(TypedDict):
    """Optimal timing analysis response."""
    timezone: str
    best_hours: List[TimingHour]
    best_days: List[TimingDay]
    analysis_period_days: int


# ============================================================================
# Content & Caption Types
# ============================================================================

class CaptionData(TypedDict):
    """Caption with performance and freshness scoring."""
    caption_id: int
    caption_text: str
    schedulable_type: str
    caption_type: str
    content_type_id: Optional[int]
    tone: Optional[str]
    is_paid_page_only: int
    performance_score: float
    content_type_name: Optional[str]
    times_used: Optional[int]
    caption_total_earnings: Optional[float]
    caption_avg_earnings: Optional[float]
    caption_avg_purchase_rate: Optional[float]
    caption_avg_view_rate: Optional[float]
    creator_performance_score: Optional[float]
    first_used_date: Optional[str]
    last_used_date: Optional[str]
    freshness_score: float  # 0-100
    send_type_priority: Optional[int]


class TopCaptionsResponse(TypedDict):
    """Response from get_top_captions."""
    captions: List[CaptionData]
    count: int
    send_type_key: Optional[str]


class SendTypeCaptionsResponse(TypedDict):
    """Response from get_send_type_captions."""
    captions: List[CaptionData]
    count: int
    send_type_key: str


class VaultItem(TypedDict):
    """Vault content availability item."""
    vault_id: int
    content_type_id: int
    has_content: int
    quantity_available: int
    quality_rating: Optional[float]
    notes: Optional[str]
    updated_at: str
    type_name: str
    type_category: str
    description: str
    priority_tier: int
    is_explicit: int


class VaultAvailabilityResponse(TypedDict):
    """Vault availability response."""
    available_content: List[VaultItem]
    content_types: List[str]
    total_items: int


# ============================================================================
# Send Type Configuration Types
# ============================================================================

class SendTypeData(TypedDict):
    """Complete send type configuration."""
    send_type_id: int
    send_type_key: str
    category: str  # "revenue" | "engagement" | "retention"
    display_name: str
    description: str
    purpose: str
    strategy: str
    requires_media: int
    requires_flyer: int
    requires_price: int
    requires_link: int
    has_expiration: int
    default_expiration_hours: Optional[int]
    can_have_followup: int
    followup_delay_minutes: Optional[int]
    page_type_restriction: str  # "paid" | "free" | "both"
    caption_length: str
    emoji_recommendation: str
    max_per_day: Optional[int]
    max_per_week: Optional[int]
    min_hours_between: Optional[int]
    sort_order: int
    is_active: int
    created_at: str


class SendTypesResponse(TypedDict):
    """Response from get_send_types."""
    send_types: List[SendTypeData]
    count: int


class CaptionRequirement(TypedDict):
    """Caption type requirement for a send type."""
    caption_type: str
    priority: int
    notes: Optional[str]


class SendTypeDetailsResponse(TypedDict):
    """Detailed send type information with caption requirements."""
    send_type: SendTypeData
    caption_requirements: List[CaptionRequirement]


class VolumeConfigResponse(TypedDict):
    """Extended volume configuration response."""
    # Legacy fields (backward compatible)
    volume_level: str
    ppv_per_day: int
    bump_per_day: int
    # Category volumes
    revenue_items_per_day: int
    engagement_items_per_day: int
    retention_items_per_day: int
    # Type-specific limits
    bundle_per_week: int
    game_per_week: int
    followup_per_day: int
    # Optimized volume fields (if available)
    weekly_distribution: Optional[List[int]]
    content_allocations: Optional[Dict[str, int]]
    confidence_score: Optional[float]
    elasticity_capped: Optional[bool]
    caption_warnings: Optional[List[str]]
    dow_multipliers_used: Optional[List[float]]
    adjustments_applied: Optional[List[str]]
    fused_saturation: Optional[float]
    fused_opportunity: Optional[float]
    prediction_id: Optional[str]
    divergence_detected: Optional[bool]
    message_count: Optional[int]
    total_weekly_volume: Optional[int]
    has_warnings: Optional[bool]
    is_high_confidence: Optional[bool]
    # Metadata
    calculation_source: str  # "optimized" | "dynamic"
    fan_count: int
    page_type: str
    saturation_score: float
    opportunity_score: float
    revenue_trend: float
    data_source: str
    tracking_date: Optional[str]
    fallback_reason: Optional[str]


# ============================================================================
# Targeting & Channel Types
# ============================================================================

class ChannelData(TypedDict):
    """Distribution channel configuration."""
    channel_id: int
    channel_key: str
    display_name: str
    description: str
    supports_targeting: int
    targeting_options: Optional[Dict[str, bool]]
    platform_feature: str
    requires_manual_send: int
    is_active: int
    created_at: str


class ChannelsResponse(TypedDict):
    """Response from get_channels."""
    channels: List[ChannelData]
    count: int


# ============================================================================
# Schedule Operations Types
# ============================================================================

class ScheduleItem(TypedDict):
    """Schedule item for save_schedule."""
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str  # HH:MM
    item_type: str
    channel: str
    send_type_key: Optional[str]
    channel_key: Optional[str]
    caption_id: Optional[int]
    caption_text: Optional[str]
    suggested_price: Optional[float]
    content_type_id: Optional[int]
    flyer_required: Optional[int]
    priority: Optional[int]
    linked_post_url: Optional[str]
    expires_at: Optional[str]
    followup_delay_minutes: Optional[int]
    media_type: Optional[str]  # "none" | "picture" | "gif" | "video" | "flyer"
    campaign_goal: Optional[float]
    parent_item_id: Optional[int]


class SaveScheduleResponse(TypedDict):
    """Response from save_schedule."""
    success: bool
    template_id: int
    items_created: int
    week_start: str
    week_end: str
    warnings: Optional[List[str]]


# ============================================================================
# Query Execution Types
# ============================================================================

class QueryExecutionResponse(TypedDict):
    """Response from execute_query."""
    results: List[Dict[str, Any]]
    count: int
    columns: List[str]


# ============================================================================
# Error Response Type
# ============================================================================

class ErrorResponse(TypedDict):
    """Standard error response."""
    error: str
