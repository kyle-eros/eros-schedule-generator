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
# Error Response Types
# ============================================================================


class ErrorCode:
    """Standard error codes for all MCP tools and agents.

    Error codes are organized by category using ranges:
    - 1000-1999: Input validation errors
    - 2000-2999: Not found errors
    - 3000-3999: Database/connection errors
    - 4000-4999: Rate limiting errors
    - 5000-5999: Pipeline/agent errors
    - 6000-6999: Circuit breaker errors
    """

    # Validation errors (1000-1999)
    INVALID_INPUT = "ERR_1000_INVALID_INPUT"
    INVALID_CREATOR_ID = "ERR_1001_INVALID_CREATOR_ID"
    INVALID_SEND_TYPE = "ERR_1002_INVALID_SEND_TYPE"
    INVALID_CONTENT_TYPE = "ERR_1003_INVALID_CONTENT_TYPE"
    INVALID_DATE_RANGE = "ERR_1004_INVALID_DATE_RANGE"
    INVALID_PRICE = "ERR_1005_INVALID_PRICE"
    INVALID_CAPTION_ID = "ERR_1006_INVALID_CAPTION_ID"
    INVALID_JSON = "ERR_1007_INVALID_JSON"

    # Not found errors (2000-2999)
    CREATOR_NOT_FOUND = "ERR_2000_CREATOR_NOT_FOUND"
    SEND_TYPE_NOT_FOUND = "ERR_2001_SEND_TYPE_NOT_FOUND"
    CAPTION_NOT_FOUND = "ERR_2002_CAPTION_NOT_FOUND"
    SCHEDULE_NOT_FOUND = "ERR_2003_SCHEDULE_NOT_FOUND"
    CONTENT_TYPE_NOT_FOUND = "ERR_2004_CONTENT_TYPE_NOT_FOUND"
    PERSONA_NOT_FOUND = "ERR_2005_PERSONA_NOT_FOUND"
    EXPERIMENT_NOT_FOUND = "ERR_2006_EXPERIMENT_NOT_FOUND"

    # Database errors (3000-3999)
    DATABASE_ERROR = "ERR_3000_DATABASE_ERROR"
    CONNECTION_FAILED = "ERR_3001_CONNECTION_FAILED"
    QUERY_TIMEOUT = "ERR_3002_QUERY_TIMEOUT"
    TRANSACTION_FAILED = "ERR_3003_TRANSACTION_FAILED"
    INTEGRITY_ERROR = "ERR_3004_INTEGRITY_ERROR"

    # Rate limiting errors (4000-4999)
    RATE_LIMIT_EXCEEDED = "ERR_4000_RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_TOOL = "ERR_4001_RATE_LIMIT_TOOL"
    RATE_LIMIT_GLOBAL = "ERR_4002_RATE_LIMIT_GLOBAL"

    # Pipeline/Agent errors (5000-5999)
    PIPELINE_BLOCKED = "ERR_5000_PIPELINE_BLOCKED"
    PREFLIGHT_FAILED = "ERR_5001_PREFLIGHT_FAILED"
    VALIDATION_FAILED = "ERR_5002_VALIDATION_FAILED"
    VAULT_VIOLATION = "ERR_5003_VAULT_VIOLATION"
    AVOID_TIER_VIOLATION = "ERR_5004_AVOID_TIER_VIOLATION"
    INSUFFICIENT_DIVERSITY = "ERR_5005_INSUFFICIENT_DIVERSITY"
    QUALITY_THRESHOLD_NOT_MET = "ERR_5006_QUALITY_THRESHOLD_NOT_MET"
    CAPTION_POOL_EXHAUSTED = "ERR_5007_CAPTION_POOL_EXHAUSTED"
    TIMING_CONFLICT = "ERR_5008_TIMING_CONFLICT"
    CATEGORY_IMBALANCE = "ERR_5009_CATEGORY_IMBALANCE"
    MCP_CONNECTION_REQUIRED = "ERR_5010_MCP_CONNECTION_REQUIRED"

    # Circuit breaker errors (6000-6999)
    CIRCUIT_BREAKER_OPEN = "ERR_6000_CIRCUIT_BREAKER_OPEN"
    CIRCUIT_BREAKER_HALF_OPEN = "ERR_6001_CIRCUIT_BREAKER_HALF_OPEN"


class ErrorResponse(TypedDict, total=False):
    """Standardized error response format for all MCP tools and agents.

    All error responses MUST include 'error' field. The 'error_code' field
    is strongly recommended for programmatic error handling.

    Attributes:
        error: Human-readable error message (required)
        error_code: Machine-readable error code from ErrorCode class
        recoverable: Whether the error can be recovered from (e.g., retry)
        retry_after: Seconds until retry is allowed (for rate limits)
        details: Additional error context (e.g., invalid values, thresholds)
        remediation: List of suggested fixes or next steps

    Example:
        {
            "error": "Creator not found: invalid_creator",
            "error_code": "ERR_2000_CREATOR_NOT_FOUND",
            "recoverable": false,
            "details": {"creator_id": "invalid_creator"},
            "remediation": ["Check creator_id spelling", "Run get_active_creators()"]
        }
    """

    error: str
    error_code: str
    recoverable: bool
    retry_after: Optional[float]
    details: Optional[Dict[str, Any]]
    remediation: Optional[List[str]]


def create_error_response(
    message: str,
    error_code: str,
    recoverable: bool = False,
    retry_after: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    remediation: Optional[List[str]] = None
) -> ErrorResponse:
    """Factory function to create standardized error responses.

    Args:
        message: Human-readable error description
        error_code: Machine-readable code from ErrorCode class
        recoverable: Whether the operation can be retried
        retry_after: Seconds to wait before retry (for rate limits)
        details: Additional context about the error
        remediation: Suggested fixes or next steps

    Returns:
        ErrorResponse dictionary with all provided fields

    Example:
        >>> error = create_error_response(
        ...     message="Creator not found: test_creator",
        ...     error_code=ErrorCode.CREATOR_NOT_FOUND,
        ...     recoverable=False,
        ...     details={"creator_id": "test_creator"},
        ...     remediation=["Check creator_id spelling"]
        ... )
        >>> error["error_code"]
        'ERR_2000_CREATOR_NOT_FOUND'
    """
    response: ErrorResponse = {
        "error": message,
        "error_code": error_code,
        "recoverable": recoverable,
    }

    if retry_after is not None:
        response["retry_after"] = retry_after
    if details is not None:
        response["details"] = details
    if remediation is not None:
        response["remediation"] = remediation

    return response


def is_error_response(response: Any) -> bool:
    """Check if a response dictionary is an error response.

    Args:
        response: Any response object to check

    Returns:
        True if response is a dict with 'error' key
    """
    if not isinstance(response, dict):
        return False
    return "error" in response


# Mapping of error codes to default remediation suggestions
DEFAULT_REMEDIATION: Dict[str, List[str]] = {
    ErrorCode.INVALID_CREATOR_ID: [
        "Check creator_id format (alphanumeric, underscore, hyphen only)",
        "Verify creator_id length is under 100 characters",
        "Run get_active_creators() to list valid IDs",
    ],
    ErrorCode.CREATOR_NOT_FOUND: [
        "Run get_active_creators() to list valid creator IDs",
        "Check for typos in creator_id",
    ],
    ErrorCode.VAULT_VIOLATION: [
        "Check vault_matrix for creator's available content types",
        "Run get_vault_availability() to see valid content",
        "This is a HARD GATE - cannot be overridden",
    ],
    ErrorCode.AVOID_TIER_VIOLATION: [
        "Run get_content_type_rankings() to check tier classification",
        "Exclude AVOID tier content types from selection",
        "This is a HARD GATE - cannot be overridden",
    ],
    ErrorCode.INSUFFICIENT_DIVERSITY: [
        "Add captions for underused send types",
        "Relax freshness threshold from 30 to 20 days",
        "Check vault_matrix for missing content types",
    ],
    ErrorCode.CAPTION_POOL_EXHAUSTED: [
        "Add more captions for this send type",
        "Relax freshness threshold to include older captions",
        "Check if vault_matrix restricts available content",
    ],
    ErrorCode.RATE_LIMIT_EXCEEDED: [
        "Wait for the retry_after period",
        "Reduce request frequency",
        "Check if requests are being batched efficiently",
    ],
    ErrorCode.CIRCUIT_BREAKER_OPEN: [
        "Wait for circuit breaker timeout (default 60s)",
        "Check database connection health",
        "Review recent error logs for root cause",
    ],
}


def get_default_remediation(error_code: str) -> List[str]:
    """Get default remediation suggestions for an error code.

    Args:
        error_code: An error code from ErrorCode class

    Returns:
        List of remediation suggestions, or empty list if none defined
    """
    return DEFAULT_REMEDIATION.get(error_code, [])
