---
name: helpers
description: Shared helper functions and constants used across all EROS schedule generator agents
version: 2.2.0
last_updated: 2025-12-17
---

# Schedule Generator Helper Functions

> Comprehensive library of utility functions, data structures, and constants used across all EROS schedule generator agents. These helpers ensure consistency, reduce code duplication, and provide production-ready implementations of common operations.

## Location Note

**This File**: `.claude/skills/eros-schedule-generator/HELPERS.md`

These helper functions are **documentation-only** - they define the API contract and usage patterns for helper functions used across all agents. The actual Python implementation is distributed across modules:

- **Pricing**: `python/pricing/`
- **Matching**: `python/matching/`
- **Validation**: `python/validation/`
- **Optimization**: `python/optimization/`
- **Orchestration**: `python/orchestration/`

This documentation serves as the **single source of truth** for helper function signatures, parameters, return types, and usage examples.

## Table of Contents

1. [Constants](#constants)
2. [Pricing Functions](#pricing-functions)
3. [Media Functions](#media-functions)
4. [Time Functions](#time-functions)
5. [Data Grouping Functions](#data-grouping-functions)
6. [Selection Functions](#selection-functions)
7. [Validation Functions](#validation-functions)
8. [Scoring Functions](#scoring-functions)
9. [Classification Functions](#classification-functions)
10. [Pattern Functions](#pattern-functions)

---

## Constants

### DEFAULT_PRICES

Default price points for revenue send types based on content type and send type combination.

```python
DEFAULT_PRICES = {
    # PPV Unlock pricing by content type
    "ppv_unlock": {
        "solo": 15.00,
        "lingerie": 12.00,
        "tease": 10.00,
        "bj": 25.00,
        "bg": 35.00,
        "gg": 30.00,
        "anal": 40.00,
        "toy": 20.00,
        "shower": 18.00,
        "outdoor": 15.00,
        "custom": 50.00,
        "default": 20.00
    },

    # PPV Wall pricing (FREE pages only)
    "ppv_wall": {
        "solo": 12.00,
        "lingerie": 10.00,
        "tease": 8.00,
        "bj": 20.00,
        "bg": 30.00,
        "gg": 25.00,
        "anal": 35.00,
        "toy": 15.00,
        "shower": 15.00,
        "outdoor": 12.00,
        "custom": 45.00,
        "default": 15.00
    },

    # Bundle pricing (multiple items) with value framing
    "bundle": {
        "default": 50.00,
        "small": 30.00,      # 3-5 items
        "medium": 50.00,     # 6-10 items
        "large": 75.00,      # 11-20 items
        "mega": 100.00,      # 20+ items
        # Value framing: show "$X worth for $Y" to enhance perceived value
        "value_framing": {
            "small": {"items": 4, "retail_value": 60.00, "bundle_price": 30.00, "savings_pct": 50},
            "medium": {"items": 8, "retail_value": 120.00, "bundle_price": 50.00, "savings_pct": 58},
            "large": {"items": 15, "retail_value": 225.00, "bundle_price": 75.00, "savings_pct": 67},
            "mega": {"items": 25, "retail_value": 375.00, "bundle_price": 100.00, "savings_pct": 73}
        }
    },

    # Flash bundle pricing (urgency-based)
    "flash_bundle": {
        "default": 40.00,
        "discount_pct": 0.20  # 20% off regular bundle price
    },

    # Game post pricing
    "game_post": {
        "default": 10.00,
        "spin_wheel": 10.00,
        "mystery_box": 15.00,
        "contest": 5.00
    },

    # First to tip pricing - Variable pool rotation ($20-$60 range)
    "first_to_tip": {
        "default": 25.00,
        "pool": [20.00, 25.00, 30.00, 35.00, 40.00, 50.00, 60.00],  # Weekly rotation pool
        "low": 20.00,     # Entry-level threshold
        "medium": 35.00,  # Standard threshold
        "high": 60.00,    # Premium threshold
        "day_rotation": {  # Rotate amounts by day-of-week for variety
            0: 25.00,  # Monday - medium
            1: 30.00,  # Tuesday - mid-high
            2: 20.00,  # Wednesday - low (mid-week value)
            3: 35.00,  # Thursday - higher anticipation
            4: 40.00,  # Friday - payday premium
            5: 50.00,  # Saturday - weekend premium
            6: 30.00   # Sunday - moderate
        }
    },

    # VIP program pricing (fixed)
    "vip_program": {
        "default": 200.00,
        "tier_1": 100.00,
        "tier_2": 200.00,
        "tier_3": 500.00
    },

    # Snapchat bundle pricing
    "snapchat_bundle": {
        "default": 35.00
    },

    # Tip goal amounts (PAID pages only)
    "tip_goal": {
        "goal_based": 500.00,     # Community goal
        "individual": 25.00,       # Per-person threshold
        "competitive": 100.00      # Race to first
    }
}
```

### MEDIA_TYPE_REQUIREMENTS

Media type requirements per send type.

```python
MEDIA_TYPE_REQUIREMENTS = {
    # Revenue types
    "ppv_unlock": "video_or_photo",
    "ppv_wall": "video_or_photo",
    "tip_goal": "photo_or_gif",
    "bundle": "video_or_photo",
    "flash_bundle": "photo_or_gif",
    "game_post": "gif",
    "first_to_tip": "photo_or_gif",
    "vip_program": "photo_or_gif",
    "snapchat_bundle": "photo",

    # Engagement types
    "link_drop": "none",  # Auto-preview
    "wall_link_drop": "photo_or_gif",
    "bump_normal": "photo",
    "bump_descriptive": "photo",
    "bump_text_only": "none",
    "bump_flyer": "gif_or_flyer",
    "dm_farm": "photo_or_gif",
    "like_farm": "photo_or_gif",
    "live_promo": "flyer",

    # Retention types
    "renew_on_post": "photo_or_gif",
    "renew_on_message": "photo_or_gif",
    "ppv_followup": "none",
    "expired_winback": "photo_or_gif"
}
```

### EXPIRATION_RULES

Default expiration times for send types that require expiration.

```python
EXPIRATION_RULES = {
    "link_drop": {
        "hours": 24,
        "reason": "OnlyFans platform requirement"
    },
    "wall_link_drop": {
        "hours": 24,
        "reason": "OnlyFans platform requirement"
    },
    "game_post": {
        "hours": 24,
        "reason": "Maintain urgency"
    },
    "flash_bundle": {
        "hours": 24,
        "reason": "Flash sale urgency"
    },
    "first_to_tip": {
        "hours": 48,
        "min_hours": 24,
        "max_hours": 72,
        "reason": "Competition window"
    },
    "tip_goal": {
        "goal_based": 72,      # 3 days for community goals
        "individual": 48,       # 2 days for individual
        "competitive": 24,      # 1 day for competition
        "reason": "Mode-specific urgency"
    },
    "live_promo": {
        "hours": "until_stream_time",
        "reason": "Event-based expiration"
    }
}
```

---

## Pricing Functions

### calculate_price()

Calculate appropriate price for a schedule item based on send type and content type.

**Signature:**
```python
def calculate_price(
    item: dict,
    content_type: str = None,
    bundle_size: int = None,
    mode: str = None
) -> float
```

**Parameters:**
- `item` (dict): Schedule item containing send_type_key and optional metadata
- `content_type` (str, optional): Content type identifier (solo, lingerie, bj, etc.)
- `bundle_size` (int, optional): Number of items in bundle (for bundle pricing)
- `mode` (str, optional): Mode for send types with variants (e.g., tip_goal modes)

**Returns:**
- `float`: Suggested price in USD

**Pseudocode:**
```python
def calculate_price(item, content_type=None, bundle_size=None, mode=None):
    """
    Calculate appropriate price for schedule item.

    Examples:
        >>> calculate_price({"send_type_key": "ppv_unlock"}, content_type="solo")
        15.00

        >>> calculate_price({"send_type_key": "bundle"}, bundle_size=8)
        50.00

        >>> calculate_price({"send_type_key": "tip_goal", "tip_goal_mode": "individual"})
        25.00
    """
    send_type_key = item.get("send_type_key")

    # Check if send type requires price
    if not requires_price(send_type_key):
        return None

    # Get base pricing structure for send type
    price_struct = DEFAULT_PRICES.get(send_type_key, {})

    # Handle different send type pricing logic
    if send_type_key in ["ppv_unlock", "ppv_wall"]:
        # Content-type based pricing
        if content_type:
            return price_struct.get(content_type, price_struct.get("default", 20.00))
        return price_struct.get("default", 20.00)

    elif send_type_key == "bundle":
        # Bundle size-based pricing
        if bundle_size is None:
            return price_struct.get("default", 50.00)

        if bundle_size <= 5:
            return price_struct.get("small", 30.00)
        elif bundle_size <= 10:
            return price_struct.get("medium", 50.00)
        elif bundle_size <= 20:
            return price_struct.get("large", 75.00)
        else:
            return price_struct.get("mega", 100.00)

    elif send_type_key == "flash_bundle":
        # Apply discount to bundle price
        base_bundle_price = calculate_price(
            {"send_type_key": "bundle"},
            bundle_size=bundle_size
        )
        discount = price_struct.get("discount_pct", 0.20)
        return round(base_bundle_price * (1 - discount), 2)

    elif send_type_key == "tip_goal":
        # Mode-based pricing
        mode = mode or item.get("tip_goal_mode", "goal_based")
        return price_struct.get(mode, price_struct.get("default", 500.00))

    elif send_type_key == "game_post":
        # Game type-based pricing
        game_type = item.get("game_type", "default")
        return price_struct.get(game_type, price_struct.get("default", 10.00))

    elif send_type_key == "first_to_tip":
        # Tier-based pricing
        tier = item.get("tier", "medium")
        return price_struct.get(tier, price_struct.get("default", 25.00))

    else:
        # Default pricing
        if isinstance(price_struct, dict):
            return price_struct.get("default", 20.00)
        return price_struct if isinstance(price_struct, (int, float)) else 20.00


def requires_price(send_type_key: str) -> bool:
    """Check if send type requires a price."""
    PRICE_REQUIRED = [
        "ppv_unlock", "ppv_wall", "bundle", "flash_bundle",
        "game_post", "first_to_tip", "snapchat_bundle"
    ]
    return send_type_key in PRICE_REQUIRED


def apply_confidence_dampening(
    base_price: float,
    confidence_score: float,
    send_type_key: str
) -> dict:
    """
    Apply confidence-based dampening to pricing recommendations.

    Low-confidence predictions should use more conservative (lower) prices
    to minimize risk while learning about the creator's audience.

    Args:
        base_price: The base calculated price
        confidence_score: 0.0-1.0 from volume_config
        send_type_key: Send type for context-specific adjustments

    Returns:
        dict with adjusted_price, confidence_level, and adjustment_notes

    Examples:
        >>> apply_confidence_dampening(50.00, 0.85, "ppv_unlock")
        {'adjusted_price': 50.00, 'confidence_level': 'HIGH', 'dampening_applied': 1.0}

        >>> apply_confidence_dampening(50.00, 0.35, "ppv_unlock")
        {'adjusted_price': 40.00, 'confidence_level': 'LOW', 'dampening_applied': 0.8}
    """
    # Confidence dampening multipliers
    DAMPENING_MATRIX = {
        "HIGH": 1.0,     # >= 0.75: Full price, high confidence
        "MEDIUM": 0.9,   # 0.5-0.74: 10% reduction, moderate confidence
        "LOW": 0.8       # < 0.5: 20% reduction, conservative pricing
    }

    # Special handling for high-risk send types in low confidence
    HIGH_RISK_TYPES = ["bundle", "flash_bundle", "vip_program", "snapchat_bundle"]

    # Classify confidence
    if confidence_score >= 0.75:
        confidence_level = "HIGH"
    elif confidence_score >= 0.5:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    # Get base dampening
    dampening = DAMPENING_MATRIX[confidence_level]

    # Apply extra dampening for high-risk types in low confidence
    if confidence_level == "LOW" and send_type_key in HIGH_RISK_TYPES:
        dampening *= 0.9  # Additional 10% reduction for bundles in low confidence

    # Calculate adjusted price
    adjusted_price = round(base_price * dampening, 2)

    # Generate notes
    notes = []
    if confidence_level != "HIGH":
        notes.append(f"Price reduced from ${base_price:.2f} due to {confidence_level} confidence")
    if send_type_key in HIGH_RISK_TYPES and confidence_level == "LOW":
        notes.append("Additional reduction applied for high-value send type")

    return {
        "adjusted_price": adjusted_price,
        "original_price": base_price,
        "confidence_level": confidence_level,
        "confidence_score": confidence_score,
        "dampening_applied": dampening,
        "notes": notes
    }


def calculate_price_with_confidence(
    item: dict,
    content_type: str = None,
    bundle_size: int = None,
    mode: str = None,
    confidence_score: float = 1.0
) -> dict:
    """
    Calculate price with confidence-based dampening applied.

    Args:
        item: Schedule item with send_type_key
        content_type: Optional content type for PPV pricing
        bundle_size: Optional bundle size for bundle pricing
        mode: Optional mode for send types with variants
        confidence_score: Prediction confidence from volume_config (0.0-1.0)

    Returns:
        dict with final price and metadata

    Examples:
        >>> item = {"send_type_key": "ppv_unlock"}
        >>> calculate_price_with_confidence(item, content_type="bg", confidence_score=0.85)
        {'suggested_price': 35.00, 'confidence_level': 'HIGH', ...}

        >>> calculate_price_with_confidence(item, content_type="bg", confidence_score=0.4)
        {'suggested_price': 28.00, 'confidence_level': 'LOW', ...}
    """
    # Get base price using existing function
    base_price = calculate_price(item, content_type, bundle_size, mode)

    if base_price is None:
        return {"suggested_price": None, "requires_price": False}

    # Apply confidence dampening
    result = apply_confidence_dampening(
        base_price=base_price,
        confidence_score=confidence_score,
        send_type_key=item.get("send_type_key")
    )

    return {
        "suggested_price": result["adjusted_price"],
        "original_price": result["original_price"],
        "confidence_level": result["confidence_level"],
        "dampening_applied": result["dampening_applied"],
        "requires_price": True,
        "notes": result["notes"]
    }


def calculate_bundle_value_framing(bundle_size: int) -> dict:
    """
    Calculate bundle value framing for enhanced conversion.

    Shows "$X worth for $Y" messaging to communicate savings and value.
    This value framing enhances conversion by clearly articulating the deal.

    Args:
        bundle_size: Number of items in the bundle

    Returns:
        dict with value framing details for caption enhancement

    Examples:
        >>> calculate_bundle_value_framing(8)
        {
            'tier': 'medium',
            'retail_value': 120.00,
            'bundle_price': 50.00,
            'savings_amount': 70.00,
            'savings_pct': 58,
            'value_message': '$120 worth of content for only $50!'
        }
    """
    # Determine bundle tier
    if bundle_size <= 5:
        tier = "small"
    elif bundle_size <= 10:
        tier = "medium"
    elif bundle_size <= 20:
        tier = "large"
    else:
        tier = "mega"

    # Get value framing from constants
    framing = DEFAULT_PRICES["bundle"]["value_framing"][tier]

    # Calculate savings
    retail_value = framing["retail_value"]
    bundle_price = framing["bundle_price"]
    savings_amount = retail_value - bundle_price
    savings_pct = framing["savings_pct"]

    # Generate value message variations
    value_messages = [
        f"${retail_value:.0f} worth of content for only ${bundle_price:.0f}!",
        f"Save {savings_pct}%! ${retail_value:.0f} worth for ${bundle_price:.0f}",
        f"Over ${savings_amount:.0f} in savings - ${retail_value:.0f} value for ${bundle_price:.0f}",
        f"{framing['items']} pieces worth ${retail_value:.0f}, yours for ${bundle_price:.0f}"
    ]

    return {
        "tier": tier,
        "items_typical": framing["items"],
        "actual_items": bundle_size,
        "retail_value": retail_value,
        "bundle_price": bundle_price,
        "savings_amount": savings_amount,
        "savings_pct": savings_pct,
        "value_message": value_messages[0],  # Default message
        "message_variants": value_messages    # All variants for A/B testing
    }


def calculate_first_to_tip_amount(
    day_of_week: int,
    creator_id: str = None,
    custom_tier: str = None
) -> dict:
    """
    Calculate first-to-tip amount with day-of-week rotation.

    Provides variety in tip amounts throughout the week to prevent
    predictability and optimize for different engagement patterns.

    Args:
        day_of_week: 0=Monday, 6=Sunday
        creator_id: Optional creator ID for personalized rotation
        custom_tier: Optional override for specific tier (low/medium/high)

    Returns:
        dict with amount, tier, and rotation metadata

    Examples:
        >>> calculate_first_to_tip_amount(4)  # Friday
        {'amount': 40.00, 'tier': 'premium', 'day': 'Friday', 'rationale': 'Payday premium'}

        >>> calculate_first_to_tip_amount(2)  # Wednesday
        {'amount': 20.00, 'tier': 'value', 'day': 'Wednesday', 'rationale': 'Mid-week value'}
    """
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = DAY_NAMES[day_of_week]

    # Day-of-week rotation with rationales
    DOW_ROTATION = {
        0: {"amount": 25.00, "tier": "standard", "rationale": "Week start - accessible"},
        1: {"amount": 30.00, "tier": "mid", "rationale": "Building momentum"},
        2: {"amount": 20.00, "tier": "value", "rationale": "Mid-week value - entry point"},
        3: {"amount": 35.00, "tier": "elevated", "rationale": "Weekend anticipation"},
        4: {"amount": 40.00, "tier": "premium", "rationale": "Payday premium"},
        5: {"amount": 50.00, "tier": "peak", "rationale": "Weekend peak engagement"},
        6: {"amount": 30.00, "tier": "moderate", "rationale": "Sunday moderate wind-down"}
    }

    # Override with custom tier if provided
    if custom_tier:
        tier_amounts = {
            "low": 20.00,
            "medium": 35.00,
            "high": 60.00
        }
        amount = tier_amounts.get(custom_tier, 35.00)
        return {
            "amount": amount,
            "tier": custom_tier,
            "day": day_name,
            "day_of_week": day_of_week,
            "rationale": f"Custom tier override: {custom_tier}",
            "rotation_source": "custom"
        }

    # Apply creator-specific offset for variety between creators
    if creator_id:
        offset = hash(creator_id) % 7
        effective_day = (day_of_week + offset) % 7
        rotation = DOW_ROTATION[effective_day]
        return {
            "amount": rotation["amount"],
            "tier": rotation["tier"],
            "day": day_name,
            "day_of_week": day_of_week,
            "effective_rotation_day": effective_day,
            "rationale": rotation["rationale"],
            "rotation_source": "creator_offset"
        }

    # Standard day-of-week rotation
    rotation = DOW_ROTATION[day_of_week]
    return {
        "amount": rotation["amount"],
        "tier": rotation["tier"],
        "day": day_name,
        "day_of_week": day_of_week,
        "rationale": rotation["rationale"],
        "rotation_source": "standard"
    }


def get_weekly_first_to_tip_variety(creator_id: str = None) -> dict:
    """
    Get complete weekly first-to-tip amount schedule.

    Ensures variety throughout the week with no consecutive duplicates.

    Args:
        creator_id: Optional creator ID for personalized rotation

    Returns:
        dict with weekly schedule and variety metrics

    Examples:
        >>> get_weekly_first_to_tip_variety("alexia")
        {
            'schedule': {
                'Monday': 30.00,
                'Tuesday': 35.00,
                'Wednesday': 25.00,
                ...
            },
            'unique_amounts': 6,
            'variety_score': 0.86
        }
    """
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    schedule = {}
    amounts_used = []

    for day_of_week in range(7):
        result = calculate_first_to_tip_amount(day_of_week, creator_id)
        day_name = DAY_NAMES[day_of_week]
        schedule[day_name] = {
            "amount": result["amount"],
            "tier": result["tier"],
            "rationale": result["rationale"]
        }
        amounts_used.append(result["amount"])

    # Calculate variety metrics
    unique_amounts = len(set(amounts_used))
    variety_score = unique_amounts / 7  # 7 possible unique values

    return {
        "schedule": schedule,
        "amounts_used": amounts_used,
        "unique_amounts": unique_amounts,
        "variety_score": variety_score,
        "total_weekly_value": sum(amounts_used)
    }
```

**Usage Examples:**
```python
# PPV with content type
price = calculate_price(
    item={"send_type_key": "ppv_unlock"},
    content_type="bg"
)
# Returns: 35.00

# Bundle with size
price = calculate_price(
    item={"send_type_key": "bundle"},
    bundle_size=15
)
# Returns: 75.00

# Tip goal with mode
price = calculate_price(
    item={
        "send_type_key": "tip_goal",
        "tip_goal_mode": "competitive"
    }
)
# Returns: 100.00
```

---

## Media Functions

### determine_media_type()

Determine required media type for a send type.

**Signature:**
```python
def determine_media_type(send_type_key: str) -> str
```

**Parameters:**
- `send_type_key` (str): Send type identifier

**Returns:**
- `str`: Media type requirement (video_or_photo, photo, gif, none, etc.)

**Pseudocode:**
```python
def determine_media_type(send_type_key):
    """
    Determine required media type for send type.

    Examples:
        >>> determine_media_type("ppv_unlock")
        'video_or_photo'

        >>> determine_media_type("bump_text_only")
        'none'

        >>> determine_media_type("game_post")
        'gif'
    """
    return MEDIA_TYPE_REQUIREMENTS.get(send_type_key, "photo")


def media_type_satisfies_requirement(provided: str, required: str) -> bool:
    """
    Check if provided media type satisfies requirement.

    Examples:
        >>> media_type_satisfies_requirement("video", "video_or_photo")
        True

        >>> media_type_satisfies_requirement("photo", "gif")
        False
    """
    if required == "none":
        return True

    if required == "video_or_photo":
        return provided in ["video", "photo"]

    if required == "photo_or_gif":
        return provided in ["photo", "gif"]

    if required == "gif_or_flyer":
        return provided in ["gif", "flyer"]

    # Exact match required
    return provided == required
```

**Usage Examples:**
```python
# Check media requirement
media_type = determine_media_type("bump_normal")
# Returns: "photo"

# Validate media type
is_valid = media_type_satisfies_requirement(
    provided="video",
    required="video_or_photo"
)
# Returns: True
```

---

## Time Functions

### calculate_expiration()

Calculate expiration timestamp for send types that require expiration.

**Signature:**
```python
def calculate_expiration(
    item: dict,
    scheduled_datetime: datetime = None
) -> str
```

**Parameters:**
- `item` (dict): Schedule item containing send_type_key and optional mode
- `scheduled_datetime` (datetime, optional): When item is scheduled (defaults to now)

**Returns:**
- `str`: ISO 8601 timestamp or None if no expiration required

**Pseudocode:**
```python
from datetime import datetime, timedelta

def calculate_expiration(item, scheduled_datetime=None):
    """
    Calculate expiration timestamp for item.

    Examples:
        >>> item = {"send_type_key": "link_drop"}
        >>> scheduled = datetime(2025, 12, 17, 9, 0)
        >>> calculate_expiration(item, scheduled)
        '2025-12-18T09:00:00'

        >>> item = {"send_type_key": "tip_goal", "tip_goal_mode": "competitive"}
        >>> calculate_expiration(item, scheduled)
        '2025-12-18T09:00:00'
    """
    send_type_key = item.get("send_type_key")

    # Check if expiration is required
    if send_type_key not in EXPIRATION_RULES:
        return None

    if scheduled_datetime is None:
        scheduled_datetime = datetime.now()

    rule = EXPIRATION_RULES[send_type_key]

    # Handle special cases
    if send_type_key == "live_promo":
        # Expire when livestream starts
        stream_time = item.get("stream_time")
        if stream_time:
            return stream_time
        # Default to 4 hours if no stream time specified
        return (scheduled_datetime + timedelta(hours=4)).isoformat()

    elif send_type_key == "tip_goal":
        # Mode-specific expiration
        mode = item.get("tip_goal_mode", "goal_based")
        hours = rule.get(mode, 72)
        return (scheduled_datetime + timedelta(hours=hours)).isoformat()

    elif send_type_key == "first_to_tip":
        # Variable expiration based on goal amount
        goal_amount = item.get("goal_amount", 25.00)
        if goal_amount < 20:
            hours = rule.get("min_hours", 24)
        elif goal_amount > 50:
            hours = rule.get("max_hours", 72)
        else:
            hours = rule.get("hours", 48)
        return (scheduled_datetime + timedelta(hours=hours)).isoformat()

    else:
        # Standard expiration
        hours = rule.get("hours", 24)
        return (scheduled_datetime + timedelta(hours=hours)).isoformat()


def calculate_followup_time(parent_time: str, delay: int = 20) -> str:
    """
    Calculate followup time based on parent item time.

    Args:
        parent_time: ISO time string (HH:MM:SS) or datetime
        delay: Minutes to delay (default 20)

    Returns:
        ISO time string for followup

    Examples:
        >>> calculate_followup_time("14:30:00", delay=20)
        '14:50:00'

        >>> calculate_followup_time("23:50:00", delay=20)
        '00:10:00'  # Wraps to next day
    """
    from datetime import datetime, timedelta

    # Parse parent time
    if isinstance(parent_time, str):
        if ":" in parent_time:
            # Time only format
            time_parts = parent_time.split(":")
            base_time = datetime.now().replace(
                hour=int(time_parts[0]),
                minute=int(time_parts[1]),
                second=int(time_parts[2]) if len(time_parts) > 2 else 0
            )
        else:
            # ISO datetime format
            base_time = datetime.fromisoformat(parent_time)
    else:
        base_time = parent_time

    # Add delay
    followup_time = base_time + timedelta(minutes=delay)

    # Return time only (date handled separately in schedule)
    return followup_time.strftime("%H:%M:%S")


def hours_between(time1: str, time2: str) -> float:
    """
    Calculate hours between two time strings.

    Args:
        time1: ISO time string (HH:MM:SS)
        time2: ISO time string (HH:MM:SS)

    Returns:
        Hours between times (absolute value)

    Examples:
        >>> hours_between("09:00:00", "14:30:00")
        5.5

        >>> hours_between("23:00:00", "01:00:00")
        2.0
    """
    from datetime import datetime

    # Parse times
    t1 = datetime.strptime(time1, "%H:%M:%S")
    t2 = datetime.strptime(time2, "%H:%M:%S")

    # Calculate difference
    diff = abs((t2 - t1).total_seconds() / 3600)

    # Handle wrap-around (crossing midnight)
    if diff > 12:
        diff = 24 - diff

    return diff


def add_minutes(time_str: str, minutes: int) -> str:
    """
    Add minutes to a time string.

    Args:
        time_str: ISO time string (HH:MM:SS)
        minutes: Minutes to add

    Returns:
        New time string

    Examples:
        >>> add_minutes("14:30:00", 20)
        '14:50:00'
    """
    from datetime import datetime, timedelta

    time_obj = datetime.strptime(time_str, "%H:%M:%S")
    new_time = time_obj + timedelta(minutes=minutes)
    return new_time.strftime("%H:%M:%S")


def parse_time(time_str: str) -> datetime:
    """
    Parse various time string formats into datetime object.

    Args:
        time_str: Time string in format "HH:MM:SS", "HH:MM", or ISO datetime

    Returns:
        datetime object with parsed time

    Examples:
        >>> parse_time("14:30:00")
        datetime(1900, 1, 1, 14, 30, 0)

        >>> parse_time("14:30")
        datetime(1900, 1, 1, 14, 30, 0)

        >>> parse_time("2025-12-17T14:30:00")
        datetime(2025, 12, 17, 14, 30, 0)
    """
    from datetime import datetime

    if not time_str:
        raise ValueError("Time string cannot be empty")

    # Try ISO datetime format first
    if "T" in time_str:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    # Try HH:MM:SS format
    if time_str.count(":") == 2:
        return datetime.strptime(time_str, "%H:%M:%S")

    # Try HH:MM format
    if time_str.count(":") == 1:
        return datetime.strptime(time_str, "%H:%M")

    raise ValueError(f"Cannot parse time string: {time_str}")
```

**Usage Examples:**
```python
# Calculate expiration for link drop
from datetime import datetime

item = {
    "send_type_key": "link_drop",
    "scheduled_date": "2025-12-17",
    "scheduled_time": "09:00:00"
}
expires_at = calculate_expiration(
    item,
    datetime(2025, 12, 17, 9, 0)
)
# Returns: '2025-12-18T09:00:00'

# Calculate followup time
followup_time = calculate_followup_time("14:30:00", delay=20)
# Returns: '14:50:00'

# Parse time strings
time1 = parse_time("14:30:00")
# Returns: datetime(1900, 1, 1, 14, 30, 0)

time2 = parse_time("14:30")
# Returns: datetime(1900, 1, 1, 14, 30, 0)

time3 = parse_time("2025-12-17T14:30:00")
# Returns: datetime(2025, 12, 17, 14, 30, 0)
```

---

## Data Grouping Functions

### group_by()

Group list of items by a specified key.

**Signature:**
```python
def group_by(items: list, key: str) -> dict
```

**Parameters:**
- `items` (list): List of dictionaries to group
- `key` (str): Dictionary key to group by

**Returns:**
- `dict`: Dictionary mapping key values to lists of items

**Pseudocode:**
```python
def group_by(items, key):
    """
    Group items by specified key.

    Examples:
        >>> items = [
        ...     {"date": "2025-12-17", "type": "ppv"},
        ...     {"date": "2025-12-17", "type": "bump"},
        ...     {"date": "2025-12-18", "type": "ppv"}
        ... ]
        >>> group_by(items, "date")
        {
            '2025-12-17': [
                {"date": "2025-12-17", "type": "ppv"},
                {"date": "2025-12-17", "type": "bump"}
            ],
            '2025-12-18': [
                {"date": "2025-12-18", "type": "ppv"}
            ]
        }
    """
    grouped = {}

    for item in items:
        key_value = item.get(key)

        if key_value not in grouped:
            grouped[key_value] = []

        grouped[key_value].append(item)

    return grouped


def group_by_multiple(items: list, keys: list) -> dict:
    """
    Group items by multiple keys (creates nested dictionaries).

    Args:
        items: List of dictionaries
        keys: List of keys to group by (in order)

    Returns:
        Nested dictionary structure

    Examples:
        >>> items = [
        ...     {"date": "2025-12-17", "category": "revenue", "type": "ppv"},
        ...     {"date": "2025-12-17", "category": "revenue", "type": "bundle"},
        ...     {"date": "2025-12-17", "category": "engagement", "type": "bump"}
        ... ]
        >>> group_by_multiple(items, ["date", "category"])
        {
            '2025-12-17': {
                'revenue': [...],
                'engagement': [...]
            }
        }
    """
    if not keys:
        return items

    first_key = keys[0]
    remaining_keys = keys[1:]

    grouped = {}
    for item in items:
        key_value = item.get(first_key)

        if key_value not in grouped:
            grouped[key_value] = []

        grouped[key_value].append(item)

    # Recursively group by remaining keys
    if remaining_keys:
        for key_value in grouped:
            grouped[key_value] = group_by_multiple(
                grouped[key_value],
                remaining_keys
            )

    return grouped
```

**Usage Examples:**
```python
# Group schedule items by date
items_by_date = group_by(final_items, "scheduled_date")

# Group by send type
items_by_type = group_by(final_items, "send_type_key")

# Multiple grouping
items_by_date_and_category = group_by_multiple(
    final_items,
    ["scheduled_date", "category"]
)
```

---

### count_items_by_day()

Count items per day from a schedule.

**Signature:**
```python
def count_items_by_day(schedule: dict) -> dict
```

**Parameters:**
- `schedule` (dict): Schedule containing items with scheduled_date

**Returns:**
- `dict`: Mapping of day_of_week (0-6) to item count

**Pseudocode:**
```python
from datetime import datetime

def count_items_by_day(schedule):
    """
    Count items per day of week.

    Args:
        schedule: Dict with "items" list containing scheduled_date

    Returns:
        Dict mapping day_of_week (0=Monday, 6=Sunday) to count

    Examples:
        >>> schedule = {
        ...     "items": [
        ...         {"scheduled_date": "2025-12-15"},  # Monday
        ...         {"scheduled_date": "2025-12-15"},
        ...         {"scheduled_date": "2025-12-16"},  # Tuesday
        ...     ]
        ... }
        >>> count_items_by_day(schedule)
        {0: 2, 1: 1}
    """
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}

    items = schedule.get("items", [])

    for item in items:
        date_str = item.get("scheduled_date")
        if not date_str:
            continue

        # Parse date and get day of week
        date_obj = datetime.fromisoformat(date_str)
        day_of_week = date_obj.weekday()  # 0=Monday, 6=Sunday

        counts[day_of_week] += 1

    return counts


def count_by_type(schedule: dict, send_type_key: str) -> int:
    """
    Count occurrences of send type in schedule.

    Args:
        schedule: Schedule dict with items
        send_type_key: Send type to count

    Returns:
        Total count across all days

    Examples:
        >>> count_by_type(schedule, "ppv_unlock")
        12
    """
    items = schedule.get("items", [])
    return sum(1 for item in items if item.get("send_type_key") == send_type_key)


def count_by_type_and_date(schedule: dict, send_type_key: str, date: str) -> int:
    """
    Count occurrences of send type on specific date.

    Args:
        schedule: Schedule dict with items
        send_type_key: Send type to count
        date: ISO date string

    Returns:
        Count for that date

    Examples:
        >>> count_by_type_and_date(schedule, "ppv_unlock", "2025-12-17")
        2
    """
    items = schedule.get("items", [])
    return sum(
        1 for item in items
        if item.get("send_type_key") == send_type_key
        and item.get("scheduled_date") == date
    )
```

**Usage Examples:**
```python
# Count items per day
day_counts = count_items_by_day(schedule)
# Returns: {0: 11, 1: 10, 2: 10, 3: 11, 4: 12, 5: 13, 6: 11}

# Count specific type
ppv_count = count_by_type(schedule, "ppv_unlock")
# Returns: 12

# Count type on specific date
ppv_on_monday = count_by_type_and_date(
    schedule,
    "ppv_unlock",
    "2025-12-16"
)
# Returns: 2
```

---

## Selection Functions

### weighted_select()

Select item from pool using weighted random selection with avoidance.

**Signature:**
```python
def weighted_select(
    pool: list,
    weights: dict = None,
    avoid: str = None
) -> str
```

**Parameters:**
- `pool` (list): List of items to select from
- `weights` (dict, optional): Weight per item (default: equal weights)
- `avoid` (str, optional): Item to exclude from selection

**Returns:**
- `str`: Selected item

**Pseudocode:**
```python
import random

def weighted_select(pool, weights=None, avoid=None):
    """
    Select item from pool with optional weighting and avoidance.

    Args:
        pool: List of items to select from
        weights: Optional dict of item -> weight
        avoid: Optional item to exclude

    Returns:
        Selected item from pool

    Examples:
        >>> pool = ["ppv_unlock", "bundle", "game_post"]
        >>> weights = {"ppv_unlock": 3.0, "bundle": 2.0, "game_post": 1.0}
        >>> weighted_select(pool, weights, avoid="ppv_unlock")
        'bundle'  # or 'game_post', but not 'ppv_unlock'
    """
    # Filter out avoided item
    available = [item for item in pool if item != avoid]

    if not available:
        # If all items avoided, use full pool
        available = pool

    if not weights:
        # Equal probability
        return random.choice(available)

    # Build weighted list
    weighted_pool = []
    for item in available:
        weight = weights.get(item, 1.0)
        weighted_pool.append((item, weight))

    # Weighted random selection
    total_weight = sum(w for _, w in weighted_pool)
    r = random.uniform(0, total_weight)

    cumulative = 0
    for item, weight in weighted_pool:
        cumulative += weight
        if r <= cumulative:
            return item

    # Fallback to last item
    return weighted_pool[-1][0]


def weighted_random_select(weighted_pool: list) -> str:
    """
    Select from pre-weighted pool.

    Args:
        weighted_pool: List of (item, weight) tuples

    Returns:
        Selected item

    Examples:
        >>> pool = [("ppv", 3.0), ("bundle", 2.0), ("game", 1.0)]
        >>> weighted_random_select(pool)
        'ppv'  # Most likely due to highest weight
    """
    import random

    total_weight = sum(w for _, w in weighted_pool)
    r = random.uniform(0, total_weight)

    cumulative = 0
    for item, weight in weighted_pool:
        cumulative += weight
        if r <= cumulative:
            return item

    return weighted_pool[-1][0]
```

**Usage Examples:**
```python
# Simple selection with avoidance
revenue_pool = ["ppv_unlock", "bundle", "flash_bundle", "game_post"]
selected = weighted_select(revenue_pool, avoid="ppv_unlock")

# Weighted selection
weights = {
    "ppv_unlock": 3.0,
    "bundle": 2.0,
    "flash_bundle": 1.5,
    "game_post": 1.0
}
selected = weighted_select(revenue_pool, weights=weights)

# Pre-weighted pool
pool = [
    ("ppv_unlock", 3.0),
    ("bundle", 2.0),
    ("game_post", 1.0)
]
selected = weighted_random_select(pool)
```

---

### interleave_categories()

Interleave items from different categories to ensure variety.

**Signature:**
```python
def interleave_categories(day_allocation: list) -> list
```

**Parameters:**
- `day_allocation` (list): List of items with "category" field

**Returns:**
- `list`: Reordered items with categories interleaved

**Pseudocode:**
```python
def interleave_categories(day_allocation):
    """
    Interleave items by category to prevent clustering.

    Args:
        day_allocation: List of items with "category" field

    Returns:
        Reordered list with categories distributed

    Examples:
        >>> items = [
        ...     {"category": "revenue", "type": "ppv"},
        ...     {"category": "revenue", "type": "bundle"},
        ...     {"category": "engagement", "type": "bump"},
        ...     {"category": "engagement", "type": "link"}
        ... ]
        >>> interleaved = interleave_categories(items)
        >>> [item["category"] for item in interleaved]
        ['revenue', 'engagement', 'revenue', 'engagement']
    """
    # Group by category
    by_category = {}
    for item in day_allocation:
        category = item.get("category", "unknown")
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(item)

    # Convert to lists for easier interleaving
    categories = list(by_category.keys())
    pools = [by_category[cat] for cat in categories]

    # Interleave items
    interleaved = []
    category_index = 0

    while any(pools):
        # Round-robin through categories
        pool = pools[category_index % len(pools)]

        if pool:
            interleaved.append(pool.pop(0))

        category_index += 1

        # Remove empty pools
        pools = [p for p in pools if p]

    return interleaved


def shuffle_within_priority(items: list) -> list:
    """
    Shuffle items while maintaining priority order.

    Args:
        items: List of items with "priority" field

    Returns:
        Shuffled list maintaining priority groups

    Examples:
        >>> items = [
        ...     {"priority": 1, "type": "ppv_1"},
        ...     {"priority": 1, "type": "ppv_2"},
        ...     {"priority": 2, "type": "bump_1"},
        ...     {"priority": 2, "type": "bump_2"}
        ... ]
        >>> shuffled = shuffle_within_priority(items)
        # PPV items may swap, bump items may swap, but PPVs stay before bumps
    """
    import random

    # Group by priority
    by_priority = {}
    for item in items:
        priority = item.get("priority", 99)
        if priority not in by_priority:
            by_priority[priority] = []
        by_priority[priority].append(item)

    # Shuffle within each priority group
    result = []
    for priority in sorted(by_priority.keys()):
        group = by_priority[priority]
        random.shuffle(group)
        result.extend(group)

    return result
```

**Usage Examples:**
```python
# Interleave categories
day_items = [
    {"category": "revenue", "send_type_key": "ppv_unlock"},
    {"category": "revenue", "send_type_key": "bundle"},
    {"category": "engagement", "send_type_key": "bump_normal"},
    {"category": "engagement", "send_type_key": "link_drop"},
    {"category": "retention", "send_type_key": "renew_on_message"}
]
interleaved = interleave_categories(day_items)
# Result: revenue, engagement, retention, revenue, engagement

# Shuffle within priority
shuffled = shuffle_within_priority(day_items)
# Priority 1 items shuffled among themselves, priority 2 shuffled among themselves
```

---

## Validation Functions

### validate_time_uniqueness()

Validate that scheduled times are sufficiently varied.

**Signature:**
```python
def validate_time_uniqueness(final_items: list) -> list
```

**Parameters:**
- `final_items` (list): Schedule items with scheduled_time

**Returns:**
- `list`: List of validation violations (empty if valid)

**Pseudocode:**
```python
from collections import Counter

def validate_time_uniqueness(final_items):
    """
    Ensure times don't repeat excessively across week.

    Args:
        final_items: List of schedule items with scheduled_time

    Returns:
        List of violation messages (empty if valid)

    Examples:
        >>> items = [
        ...     {"scheduled_time": "09:00:00"},
        ...     {"scheduled_time": "09:00:00"},
        ...     {"scheduled_time": "09:00:00"}  # Too many
        ... ]
        >>> validate_time_uniqueness(items)
        ['Time 09:00:00 used 3x (max 2)']
    """
    violations = []

    # Count time occurrences
    time_counts = Counter(item["scheduled_time"] for item in final_items)

    # Check for excessive repeats
    for time, count in time_counts.items():
        if count > 2:
            violations.append(f"Time {time} used {count}x (max 2)")

    # Check for round minutes (should be rare)
    round_minutes = [":00", ":15", ":30", ":45"]
    round_count = sum(
        1 for item in final_items
        if any(item["scheduled_time"].endswith(m) for m in round_minutes)
    )

    total_items = len(final_items)
    if total_items > 0 and round_count > total_items * 0.1:
        violations.append(
            f"{round_count} items on round minutes (should be <10%)"
        )

    return violations


def validate_pattern_uniqueness(final_items: list) -> list:
    """
    Ensure each day has different send_type pattern.

    Args:
        final_items: Schedule items with scheduled_date and send_type_key

    Returns:
        List of violation messages

    Examples:
        >>> validate_pattern_uniqueness(items)
        ['2025-12-17 has identical pattern to 2025-12-16']
    """
    violations = []

    # Group by date
    items_by_date = group_by(final_items, "scheduled_date")

    # Extract patterns
    day_patterns = {}
    for date, items in items_by_date.items():
        # Sort by time and extract send_type sequence
        sorted_items = sorted(items, key=lambda x: x["scheduled_time"])
        pattern = tuple(item["send_type_key"] for item in sorted_items)
        day_patterns[date] = pattern

    # Check for duplicate patterns
    seen_patterns = {}
    for date, pattern in day_patterns.items():
        pattern_key = str(pattern)
        if pattern_key in seen_patterns:
            violations.append(
                f"{date} has identical pattern to {seen_patterns[pattern_key]}"
            )
        seen_patterns[pattern_key] = date

    return violations


def validate_strategy_diversity(strategy_metadata: dict) -> list:
    """
    Verify at least 3 different strategies used across week.

    Args:
        strategy_metadata: Dict mapping date -> strategy info

    Returns:
        List of violation messages

    Examples:
        >>> metadata = {
        ...     "2025-12-16": {"strategy_used": "balanced_spread"},
        ...     "2025-12-17": {"strategy_used": "balanced_spread"},
        ...     "2025-12-18": {"strategy_used": "balanced_spread"}
        ... }
        >>> validate_strategy_diversity(metadata)
        ['Only 1 strategies used (need 3+): {balanced_spread}']
    """
    strategies_used = set(
        day["strategy_used"]
        for day in strategy_metadata.values()
        if "strategy_used" in day
    )

    if len(strategies_used) < 3:
        return [
            f"Only {len(strategies_used)} strategies used (need 3+): {strategies_used}"
        ]

    return []
```

**Usage Examples:**
```python
# Validate time uniqueness
time_violations = validate_time_uniqueness(final_items)
if time_violations:
    print("Time uniqueness issues:", time_violations)

# Validate pattern uniqueness
pattern_violations = validate_pattern_uniqueness(final_items)
if pattern_violations:
    print("Pattern issues:", pattern_violations)

# Validate strategy diversity
strategy_violations = validate_strategy_diversity(strategy_metadata)
if strategy_violations:
    print("Strategy diversity issues:", strategy_violations)
```

---

## Scoring Functions

### calculate_score()

Calculate composite score for caption selection.

**Signature:**
```python
def calculate_score(caption: dict, send_type_key: str) -> float
```

**Parameters:**
- `caption` (dict): Caption with freshness_score, performance_score, etc.
- `send_type_key` (str): Send type for compatibility scoring

**Returns:**
- `float`: Composite score (0-100)

**Pseudocode:**
```python
def calculate_score(caption, send_type_key):
    """
    Calculate composite caption score.

    Scoring weights:
        - Freshness: 40%
        - Performance: 35%
        - Type compatibility: 15%
        - Diversity: 5%
        - Persona: 5%

    Args:
        caption: Dict with scoring fields
        send_type_key: Send type for compatibility check

    Returns:
        Composite score (0-100)

    Examples:
        >>> caption = {
        ...     "freshness_score": 80,
        ...     "performance_score": 70,
        ...     "type_priority": 90,
        ...     "diversity_score": 85,
        ...     "persona_match": 75
        ... }
        >>> calculate_score(caption, "ppv_unlock")
        78.0
    """
    # Extract component scores
    freshness = caption.get("freshness_score", 50)
    performance = caption.get("performance_score", 50)
    type_priority = caption.get("type_priority", 50)
    diversity = caption.get("diversity_score", 50)
    persona = caption.get("persona_match", 50)

    # Apply weights
    score = (
        freshness * 0.40 +
        performance * 0.35 +
        type_priority * 0.15 +
        diversity * 0.05 +
        persona * 0.05
    )

    # Clamp to 0-100
    return max(0.0, min(100.0, score))


def calculate_freshness_score(days_since_last_use: int) -> float:
    """
    Calculate freshness score based on days since last use.

    Args:
        days_since_last_use: Days since caption was last used (None = never used)

    Returns:
        Freshness score (0-100)

    Examples:
        >>> calculate_freshness_score(None)  # Never used
        100.0

        >>> calculate_freshness_score(30)
        40.0

        >>> calculate_freshness_score(60)
        0.0
    """
    if days_since_last_use is None:
        # Never used = maximum freshness
        return 100.0

    # Linear decay: 100 - (days * 2)
    score = 100 - (days_since_last_use * 2)

    # Clamp to 0-100
    return max(0.0, min(100.0, score))


def calculate_performance(caption: dict) -> float:
    """
    Calculate performance score for a caption based on historical metrics.

    Args:
        caption: Dict containing performance metrics like:
                 - revenue_generated: Total revenue from caption
                 - conversion_rate: Click-to-purchase rate
                 - engagement_rate: Like/comment rate
                 - sample_size: Number of times used

    Returns:
        Performance score (0-100)

    Examples:
        >>> caption = {
        ...     "revenue_generated": 500.00,
        ...     "conversion_rate": 0.15,
        ...     "engagement_rate": 0.25,
        ...     "sample_size": 50
        ... }
        >>> calculate_performance(caption)
        78.5

        >>> caption = {"performance_score": 85}  # Pre-calculated
        >>> calculate_performance(caption)
        85.0
    """
    # If pre-calculated performance_score exists, use it
    if "performance_score" in caption:
        return float(caption["performance_score"])

    # Calculate from component metrics
    revenue = caption.get("revenue_generated", 0)
    conversion = caption.get("conversion_rate", 0)
    engagement = caption.get("engagement_rate", 0)
    sample_size = caption.get("sample_size", 1)

    # Normalize revenue (assuming $1000 is excellent)
    revenue_score = min(100, (revenue / 1000) * 100)

    # Convert rates to scores
    conversion_score = min(100, conversion * 500)  # 20% = 100
    engagement_score = min(100, engagement * 400)  # 25% = 100

    # Apply sample size confidence factor
    confidence_factor = min(1.0, sample_size / 30)  # Full confidence at 30+ uses

    # Weighted average
    base_score = (
        revenue_score * 0.4 +
        conversion_score * 0.35 +
        engagement_score * 0.25
    )

    # Dampen by confidence if low sample size
    final_score = base_score * (0.7 + 0.3 * confidence_factor)

    return round(max(0.0, min(100.0, final_score)), 1)
```

**Usage Examples:**
```python
# Calculate caption score
caption = {
    "caption_id": 123,
    "freshness_score": 85,
    "performance_score": 72,
    "type_priority": 90,
    "diversity_score": 80,
    "persona_match": 70
}
score = calculate_score(caption, "ppv_unlock")
# Returns: 81.15

# Calculate freshness
freshness = calculate_freshness_score(days_since_last_use=15)
# Returns: 70.0

# Calculate performance from metrics
caption_metrics = {
    "revenue_generated": 500.00,
    "conversion_rate": 0.15,
    "engagement_rate": 0.25,
    "sample_size": 50
}
performance = calculate_performance(caption_metrics)
# Returns: 78.5

# Use pre-calculated performance score
caption_precalc = {"performance_score": 85}
performance = calculate_performance(caption_precalc)
# Returns: 85.0
```

---

## Classification Functions

### classify_confidence()

Classify confidence score into human-readable level.

**Signature:**
```python
def classify_confidence(score: float) -> str
```

**Parameters:**
- `score` (float): Confidence score (0.0-1.0)

**Returns:**
- `str`: Classification (HIGH, MEDIUM, LOW)

**Pseudocode:**
```python
def classify_confidence(score):
    """
    Classify confidence score.

    Args:
        score: Float between 0.0 and 1.0

    Returns:
        'HIGH', 'MEDIUM', or 'LOW'

    Examples:
        >>> classify_confidence(0.85)
        'HIGH'

        >>> classify_confidence(0.65)
        'MEDIUM'

        >>> classify_confidence(0.35)
        'LOW'
    """
    if score >= 0.8:
        return "HIGH"
    elif score >= 0.5:
        return "MEDIUM"
    else:
        return "LOW"


def classify_emoji_level(caption_text: str) -> str:
    """
    Classify emoji usage level in caption.

    Args:
        caption_text: Caption text to analyze

    Returns:
        'heavy', 'moderate', 'light', or 'none'

    Examples:
        >>> classify_emoji_level("Hey babe 😘💋🔥")
        'moderate'

        >>> classify_emoji_level("Check this out")
        'none'
    """
    import re

    # Count emoji characters (Unicode emoji ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )

    emoji_count = len(emoji_pattern.findall(caption_text))

    if emoji_count == 0:
        return "none"
    elif emoji_count <= 2:
        return "light"
    elif emoji_count <= 4:
        return "moderate"
    else:
        return "heavy"
```

**Usage Examples:**
```python
# Classify confidence
level = classify_confidence(0.75)
# Returns: 'MEDIUM'

# Classify emoji usage
emoji_level = classify_emoji_level("Hey daddy 😘💋🔥😈💦")
# Returns: 'heavy'
```

---

## Pattern Functions

### count_true_indicators()

Count number of true conditions in indicator list.

**Signature:**
```python
def count_true_indicators(indicators: dict) -> int
```

**Parameters:**
- `indicators` (dict): Dictionary of indicator_name -> boolean

**Returns:**
- `int`: Count of true indicators

**Pseudocode:**
```python
def count_true_indicators(indicators):
    """
    Count true indicators.

    Args:
        indicators: Dict mapping indicator names to boolean values

    Returns:
        Count of true indicators

    Examples:
        >>> indicators = {
        ...     "high_revenue_decline": True,
        ...     "low_engagement": False,
        ...     "caption_exhaustion": True
        ... }
        >>> count_true_indicators(indicators)
        2
    """
    return sum(1 for value in indicators.values() if value)


def calculate_anti_pattern_score(
    time_violations: list,
    pattern_violations: list,
    strategy_violations: list,
    total_items: int
) -> int:
    """
    Calculate anti-pattern score (0-100).

    Score components:
        - +25: No time repeats >2x weekly
        - +25: <10% round minute times
        - +25: All 7 days have unique patterns
        - +25: 3+ strategies used

    Args:
        time_violations: List of time violation messages
        pattern_violations: List of pattern violation messages
        strategy_violations: List of strategy violation messages
        total_items: Total schedule items

    Returns:
        Score 0-100 (higher is better)

    Examples:
        >>> calculate_anti_pattern_score([], [], [], 70)
        100

        >>> calculate_anti_pattern_score(["time repeat"], [], [], 70)
        75
    """
    score = 100

    # Time violations (-25 for any violation)
    if time_violations:
        score -= 25

    # Pattern violations (-25 for any violation)
    if pattern_violations:
        score -= 25

    # Strategy violations (-25 for any violation)
    if strategy_violations:
        score -= 25

    return max(0, score)
```

**Usage Examples:**
```python
# Count indicators
saturation_indicators = {
    "high_revenue_decline": True,
    "engagement_plateau": False,
    "content_fatigue": True,
    "ppv_saturation": True
}
saturation_level = count_true_indicators(saturation_indicators)
# Returns: 3

# Calculate anti-pattern score
score = calculate_anti_pattern_score(
    time_violations=[],
    pattern_violations=[],
    strategy_violations=[],
    total_items=70
)
# Returns: 100
```

---

## Usage Across Agents

### Agent Function Map

| Agent | Functions Used |
|-------|---------------|
| **schedule-assembler** | `calculate_price()`, `calculate_price_with_confidence()`, `calculate_bundle_value_framing()`, `calculate_first_to_tip_amount()`, `determine_media_type()`, `calculate_expiration()`, `group_by()`, `classify_confidence()`, `validate_time_uniqueness()`, `validate_pattern_uniqueness()`, `validate_strategy_diversity()` |
| **send-type-allocator** | `weighted_select()`, `weighted_random_select()`, `interleave_categories()`, `group_by()`, `calculate_first_to_tip_amount()`, `get_weekly_first_to_tip_variety()` |
| **quality-validator** | `count_items_by_day()`, `count_by_type()`, `count_by_type_and_date()`, `classify_confidence()`, `group_by()`, `apply_confidence_dampening()` |
| **content-curator** | `calculate_score()`, `calculate_freshness_score()`, `calculate_performance()` |
| **followup-generator** | `calculate_followup_time()`, `add_minutes()`, `parse_time()` |
| **timing-optimizer** | `group_by()`, `hours_between()`, `parse_time()` |
| **performance-analyst** | `classify_confidence()`, `count_true_indicators()` |
| **caption-optimizer** | `classify_emoji_level()`, `calculate_bundle_value_framing()` |

### Import Example

```python
# In agent implementation - actual module locations
from python.pricing.confidence_pricing import (
    apply_confidence_dampening,
    calculate_price_with_confidence
)
from python.pricing.first_to_tip import calculate_first_to_tip_price
from python.volume.score_calculator import calculate_performance
from python.matching.caption_matcher import CaptionMatcher, calculate_score
from python.validators import validate_time_uniqueness
from python.orchestration.timing_optimizer import apply_time_jitter
from python.volume.confidence import classify_confidence

# Use in agent logic
matcher = CaptionMatcher(persona_profile=persona)
score = calculate_score(caption, send_type="ppv_unlock")
performance_score = calculate_performance(caption)
confidence_level = classify_confidence(0.85)  # Returns "HIGH"
```

---

## Testing Examples

### Unit Test Template

```python
import unittest
from python.volume.score_calculator import calculate_performance
from python.matching.caption_matcher import calculate_freshness_score
from python.volume.confidence import classify_confidence
from python.orchestration.timing_optimizer import parse_time

class TestHelpers(unittest.TestCase):

    def test_calculate_price_ppv(self):
        item = {"send_type_key": "ppv_unlock"}
        price = calculate_price(item, content_type="bg")
        self.assertEqual(price, 35.00)

    def test_calculate_price_bundle(self):
        item = {"send_type_key": "bundle"}
        price = calculate_price(item, bundle_size=15)
        self.assertEqual(price, 75.00)

    def test_determine_media_type(self):
        media = determine_media_type("bump_text_only")
        self.assertEqual(media, "none")

    def test_group_by(self):
        items = [
            {"date": "2025-12-17", "type": "ppv"},
            {"date": "2025-12-17", "type": "bump"},
            {"date": "2025-12-18", "type": "ppv"}
        ]
        grouped = group_by(items, "date")
        self.assertEqual(len(grouped["2025-12-17"]), 2)
        self.assertEqual(len(grouped["2025-12-18"]), 1)

    def test_classify_confidence(self):
        self.assertEqual(classify_confidence(0.85), "HIGH")
        self.assertEqual(classify_confidence(0.65), "MEDIUM")
        self.assertEqual(classify_confidence(0.35), "LOW")

    def test_calculate_freshness_score(self):
        self.assertEqual(calculate_freshness_score(None), 100.0)
        self.assertEqual(calculate_freshness_score(30), 40.0)
        self.assertEqual(calculate_freshness_score(60), 0.0)

    def test_calculate_performance(self):
        # Test with pre-calculated score
        caption1 = {"performance_score": 85}
        self.assertEqual(calculate_performance(caption1), 85.0)

        # Test with metrics
        caption2 = {
            "revenue_generated": 500.00,
            "conversion_rate": 0.15,
            "engagement_rate": 0.25,
            "sample_size": 50
        }
        score = calculate_performance(caption2)
        self.assertGreater(score, 70.0)
        self.assertLess(score, 85.0)

    def test_parse_time(self):
        from datetime import datetime

        # Test HH:MM:SS format
        t1 = parse_time("14:30:00")
        self.assertEqual(t1.hour, 14)
        self.assertEqual(t1.minute, 30)

        # Test HH:MM format
        t2 = parse_time("14:30")
        self.assertEqual(t2.hour, 14)
        self.assertEqual(t2.minute, 30)

        # Test ISO datetime format
        t3 = parse_time("2025-12-17T14:30:00")
        self.assertEqual(t3.year, 2025)
        self.assertEqual(t3.month, 12)
        self.assertEqual(t3.day, 17)

        # Test empty string raises error
        with self.assertRaises(ValueError):
            parse_time("")

if __name__ == "__main__":
    unittest.main()
```

---

## Implementation Notes

### Production Considerations

1. **Error Handling**: All functions should include try-except blocks for production use
2. **Type Validation**: Add runtime type checking for critical functions
3. **Logging**: Add logging statements for debugging and audit trails
4. **Performance**: Consider caching for frequently called functions like `group_by()`
5. **Thread Safety**: Ensure functions are stateless and thread-safe

### Python Implementation Location

Helper functions are distributed across the existing module structure:

```
python/
├── pricing/                     # Pricing functions
│   ├── confidence_pricing.py    # apply_confidence_dampening, calculate_price_with_confidence
│   └── first_to_tip.py          # calculate_first_to_tip_price
├── volume/                      # Volume and scoring
│   ├── score_calculator.py      # calculate_performance, scoring algorithms
│   ├── confidence.py            # classify_confidence
│   └── tier_config.py           # DEFAULT_PRICES, tier configurations
├── matching/                    # Caption matching
│   └── caption_matcher.py       # CaptionMatcher, calculate_score, calculate_freshness_score
├── orchestration/               # Orchestration helpers
│   ├── timing_optimizer.py      # apply_time_jitter, parse_time, time calculations
│   ├── followup_generator.py    # calculate_expiration, followup logic
│   └── quality_validator.py     # validate_time_uniqueness, validation functions
├── allocation/                  # Allocation functions
│   └── send_type_allocator.py   # weighted_select, interleave_categories, group_by
├── validators.py                # Shared validation functions
└── models/                      # Domain models and constants
    └── send_type.py             # MEDIA_TYPE_REQUIREMENTS, determine_media_type
```

### Claude Agent Access

Agents can reference these functions in pseudocode knowing they exist in the Python implementation:

```markdown
## Step 3: Calculate Prices

For each revenue item:
```python
price = calculate_price(
    item=item,
    content_type=item.content_type_id,
    bundle_size=item.bundle_size if applicable
)
item["suggested_price"] = price
```
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.2.0 | 2025-12-17 | Initial comprehensive helper documentation |

---

## References

- **Agent Definitions**: `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/.claude/agents/`
- **ORCHESTRATION.md**: Pipeline phase documentation
- **SEND_TYPE_REFERENCE.md**: Send type details and requirements
- **Python Implementation**: `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/python/` (distributed across modules)

---

*This helper library ensures consistency across all 8 specialized agents and provides production-ready implementations for common operations in the EROS schedule generation pipeline.*
