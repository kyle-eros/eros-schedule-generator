"""
Daily Flavor Rotation System for schedule generation.

Provides day-of-week based flavor profiles that boost specific send types
and content categories to create authentic variation across the week.

Gap 3.4: Daily Flavor Rotation - Different emphasis each day creates
authentic variation in schedule content and tone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict


class FlavorBoosts(TypedDict):
    """Type definition for flavor boost configuration."""

    boost_types: list[str]
    boost_multiplier: float


@dataclass(frozen=True, slots=True)
class FlavorProfile:
    """Immutable flavor profile for a specific day of the week.

    Attributes:
        name: Human-readable flavor name (e.g., "Playful", "Seductive").
        emphasis: Content emphasis description for the day.
        boost_types: List of send_type_keys that receive boost.
        boost_multiplier: Multiplier applied to boosted send types.
        preferred_tone: Caption tone preference for filtering.
        boost_categories: Content categories to emphasize.
    """

    name: str
    emphasis: str
    boost_types: list[str] = field(default_factory=list)
    boost_multiplier: float = 1.0
    preferred_tone: str = "neutral"
    boost_categories: list[str] = field(default_factory=list)


# Day of week flavor profiles (0=Monday, 6=Sunday)
DAILY_FLAVORS: dict[int, FlavorProfile] = {
    0: FlavorProfile(
        name="Playful",
        emphasis="games",
        boost_types=["game_wheel", "game_post", "first_to_tip"],
        boost_multiplier=1.5,
        preferred_tone="playful",
        boost_categories=["interactive", "games", "tips"],
    ),
    1: FlavorProfile(
        name="Seductive",
        emphasis="solo",
        boost_types=["ppv_solo", "bump_descriptive"],
        boost_multiplier=1.4,
        preferred_tone="seductive",
        boost_categories=["solo", "tease", "sensual"],
    ),
    2: FlavorProfile(
        name="Wild",
        emphasis="explicit",
        boost_types=["ppv_sextape", "ppv_b_g"],
        boost_multiplier=1.4,
        preferred_tone="explicit",
        boost_categories=["explicit", "b_g", "hardcore"],
    ),
    3: FlavorProfile(
        name="Throwback",
        emphasis="bundles",
        boost_types=["ppv_bundle", "bundle_wall"],
        boost_multiplier=1.5,
        preferred_tone="nostalgic",
        boost_categories=["bundles", "compilations", "vault"],
    ),
    4: FlavorProfile(
        name="Freaky",
        emphasis="fetish",
        boost_types=["ppv_special", "niche_content"],
        boost_multiplier=1.3,
        preferred_tone="adventurous",
        boost_categories=["fetish", "niche", "special"],
    ),
    5: FlavorProfile(
        name="Sext",
        emphasis="drip",
        boost_types=["bump_drip", "drip_set"],
        boost_multiplier=1.5,
        preferred_tone="flirty",
        boost_categories=["drip", "teasing", "buildup"],
    ),
    6: FlavorProfile(
        name="Self-Care",
        emphasis="gfe",
        boost_types=["gfe_message", "engagement_post"],
        boost_multiplier=1.4,
        preferred_tone="intimate",
        boost_categories=["gfe", "personal", "connection"],
    ),
}


def get_daily_flavor(date: datetime) -> dict:
    """Get the flavor profile for a given date based on weekday.

    Args:
        date: The datetime to get the flavor profile for.

    Returns:
        Dictionary containing the flavor profile with keys:
            - name: Flavor name
            - emphasis: Content emphasis
            - boost_types: List of send types to boost
            - boost_multiplier: Multiplier for boosted types
            - preferred_tone: Preferred caption tone
            - boost_categories: Categories to emphasize
            - day_of_week: Integer day (0=Monday)

    Example:
        >>> from datetime import datetime
        >>> flavor = get_daily_flavor(datetime(2025, 12, 15))  # Monday
        >>> flavor['name']
        'Playful'
        >>> flavor['boost_multiplier']
        1.5
    """
    day_of_week = date.weekday()
    profile = DAILY_FLAVORS[day_of_week]

    return {
        "name": profile.name,
        "emphasis": profile.emphasis,
        "boost_types": list(profile.boost_types),
        "boost_multiplier": profile.boost_multiplier,
        "preferred_tone": profile.preferred_tone,
        "boost_categories": list(profile.boost_categories),
        "day_of_week": day_of_week,
    }


def weight_send_types_by_flavor(
    allocation: dict[str, float],
    date: datetime,
) -> dict[str, float]:
    """Apply flavor-based weighting to send type allocations.

    Boosts the allocation for send types that match the day's flavor profile
    while normalizing the result to maintain the original total allocation.

    Args:
        allocation: Dictionary mapping send_type_key to allocation value.
        date: The datetime to determine which flavor to apply.

    Returns:
        New dictionary with flavor-weighted allocations normalized to
        maintain the same total as the input allocation.

    Example:
        >>> from datetime import datetime
        >>> alloc = {"game_post": 2.0, "ppv_unlock": 3.0, "bump_normal": 1.0}
        >>> weighted = weight_send_types_by_flavor(alloc, datetime(2025, 12, 15))
        >>> # Monday boosts game_post by 1.5x, then normalizes
        >>> weighted["game_post"] > alloc["game_post"] / sum(alloc.values()) * sum(weighted.values())
        True
    """
    if not allocation:
        return {}

    flavor = get_daily_flavor(date)
    boost_types = set(flavor["boost_types"])
    boost_multiplier = flavor["boost_multiplier"]

    # Calculate original total for normalization
    original_total = sum(allocation.values())
    if original_total == 0:
        return dict(allocation)

    # Apply boosts to matching send types
    weighted: dict[str, float] = {}
    for send_type, value in allocation.items():
        if send_type in boost_types:
            weighted[send_type] = value * boost_multiplier
        else:
            weighted[send_type] = value

    # Calculate new total after boosts
    boosted_total = sum(weighted.values())
    if boosted_total == 0:
        return dict(allocation)

    # Normalize to maintain original total allocation
    normalization_factor = original_total / boosted_total
    normalized: dict[str, float] = {
        send_type: value * normalization_factor
        for send_type, value in weighted.items()
    }

    return normalized


def get_daily_caption_filter(date: datetime) -> dict:
    """Get caption filtering criteria based on daily flavor.

    Returns filtering parameters that can be used to select captions
    that match the day's thematic emphasis.

    Args:
        date: The datetime to get caption filter criteria for.

    Returns:
        Dictionary containing caption filter criteria:
            - flavor_name: Name of the day's flavor
            - preferred_tone: Tone to prefer in caption selection
            - boost_categories: Content categories to emphasize
            - emphasis: The day's content emphasis theme

    Example:
        >>> from datetime import datetime
        >>> filters = get_daily_caption_filter(datetime(2025, 12, 16))  # Tuesday
        >>> filters['preferred_tone']
        'seductive'
        >>> filters['emphasis']
        'solo'
    """
    flavor = get_daily_flavor(date)

    return {
        "flavor_name": flavor["name"],
        "preferred_tone": flavor["preferred_tone"],
        "boost_categories": flavor["boost_categories"],
        "emphasis": flavor["emphasis"],
    }


def get_flavor_for_week(start_date: datetime) -> list[dict]:
    """Get flavor profiles for an entire week starting from a given date.

    Utility function to preview the flavor rotation for schedule planning.

    Args:
        start_date: The starting datetime for the week.

    Returns:
        List of 7 flavor profile dictionaries, one for each day.

    Example:
        >>> from datetime import datetime, timedelta
        >>> week = get_flavor_for_week(datetime(2025, 12, 15))  # Monday
        >>> len(week)
        7
        >>> week[0]['name']
        'Playful'
    """
    from datetime import timedelta

    return [
        get_daily_flavor(start_date + timedelta(days=i))
        for i in range(7)
    ]
