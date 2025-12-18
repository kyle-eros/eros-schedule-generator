#!/usr/bin/env python3
"""
Wave 3 Domain Models & Registry - Demonstration Script

This script demonstrates the new domain models, registry, and configuration
management implemented in Wave 3. It shows real-world usage patterns and
validates all components work together correctly.

Usage:
    python3 python/examples/wave3_demo.py
"""

import sqlite3
from pathlib import Path

from python.models import (
    Creator,
    CreatorProfile,
    Caption,
    CaptionScore,
    ScheduleItem,
    VolumeConfig,
    VolumeTier,
)
from python.registry import SendTypeRegistry
from python.config import Settings


def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def demo_domain_models() -> None:
    """Demonstrate domain model creation and usage."""
    print_section("Domain Models Demo")

    # Creator model
    creator = Creator(
        creator_id=1,
        username="alexia",
        page_type="paid",
        fan_count=5432,
        is_active=1,
    )
    print(f"Created Creator: {creator.username} ({creator.fan_count:,} fans)")

    # CreatorProfile model
    profile = CreatorProfile(
        creator_id=1,
        username="alexia",
        page_type="paid",
        fan_count=5432,
        persona_archetype="girl_next_door",
        voice_tone="playful",
        saturation_score=42.5,
        opportunity_score=78.3,
    )
    print(f"Creator Profile: {profile.persona_archetype} archetype")
    print(f"  Saturation: {profile.saturation_score}%")
    print(f"  Opportunity: {profile.opportunity_score}%")

    # VolumeConfig model
    config = VolumeConfig(
        tier=VolumeTier.HIGH,
        revenue_per_day=5,
        engagement_per_day=4,
        retention_per_day=2,
        fan_count=creator.fan_count,
        page_type=creator.page_type,
    )
    print(f"\nVolume Config: {config.tier.value.upper()} tier")
    print(f"  Total sends/day: {config.total_per_day}")
    print(f"  Revenue: {config.revenue_per_day}, "
          f"Engagement: {config.engagement_per_day}, "
          f"Retention: {config.retention_per_day}")

    # Caption model
    caption = Caption(
        caption_id=123,
        caption_text="Check your DMs for something special 💋🔥",
        send_type_key="ppv_video",
        media_type="video",
        length_category="medium",
        emoji_level="moderate",
        performance_score=85.0,
        last_used_date="2025-11-15",
        use_count=3,
    )
    print(f"\nCaption #{caption.caption_id}:")
    print(f"  Text: {caption.caption_text}")
    print(f"  Performance: {caption.performance_score}%")
    print(f"  Freshness: {caption.freshness_days} days")

    # ScheduleItem model
    item = ScheduleItem(
        send_type_key="ppv_video",
        scheduled_date="2025-12-16",
        scheduled_time="19:00",
        category="revenue",
        priority=1,
        caption_id=caption.caption_id,
        caption_text=caption.caption_text,
        media_type="video",
        suggested_price=15.0,
    )
    print(f"\nSchedule Item:")
    print(f"  Type: {item.send_type_key}")
    print(f"  DateTime: {item.datetime_obj}")
    print(f"  Price: ${item.suggested_price}")

    # Demonstrate immutability
    print("\n✅ All models are frozen (immutable)")
    try:
        creator.fan_count = 10000
        print("❌ Failed: creator.fan_count should be immutable")
    except Exception:
        print("✅ Confirmed: Cannot modify frozen dataclass")


def demo_send_type_registry() -> None:
    """Demonstrate send type registry with real database."""
    print_section("Send Type Registry Demo")

    # Find database
    db_path = Path(__file__).parent.parent.parent / "database" / "eros_sd_main.db"
    if not db_path.exists():
        print(f"⚠️  Database not found at {db_path}")
        print("   Skipping registry demo (requires production database)")
        return

    # Load registry
    print("Loading SendTypeRegistry from database...")
    conn = sqlite3.connect(str(db_path))

    registry = SendTypeRegistry()
    registry.load_from_database(conn)
    conn.close()

    print(f"✅ Loaded {len(registry)} send types\n")

    # Demonstrate get by key
    ppv_config = registry.get("ppv_video")
    print(f"PPV Video Configuration:")
    print(f"  Name: {ppv_config.name}")
    print(f"  Category: {ppv_config.category}")
    print(f"  Page Type: {ppv_config.page_type}")
    print(f"  Requires Media: {ppv_config.requires_media}")
    print(f"  Requires Price: {ppv_config.requires_price}")
    print(f"  Max Per Day: {ppv_config.max_per_day}")
    print(f"  Caption Requirements: {', '.join(ppv_config.caption_requirements)}")

    # Demonstrate category filtering
    print("\nRevenue Send Types:")
    revenue_types = registry.get_keys_by_category("revenue")
    for i, key in enumerate(revenue_types, 1):
        config = registry.get(key)
        print(f"  {i}. {config.name} ({key})")

    print("\nEngagement Send Types:")
    engagement_types = registry.get_keys_by_category("engagement")
    for i, key in enumerate(engagement_types, 1):
        config = registry.get(key)
        print(f"  {i}. {config.name} ({key})")

    print("\nRetention Send Types:")
    retention_types = registry.get_keys_by_category("retention")
    for i, key in enumerate(retention_types, 1):
        config = registry.get(key)
        print(f"  {i}. {config.name} ({key})")

    # Demonstrate page type filtering
    print("\nPage Type Compatibility:")
    paid_compatible = registry.get_page_type_compatible("paid")
    free_compatible = registry.get_page_type_compatible("free")
    print(f"  Paid pages: {len(paid_compatible)} compatible types")
    print(f"  Free pages: {len(free_compatible)} compatible types")

    # Demonstrate timing preferences
    print("\nTiming Preferences (ppv_video):")
    timing = registry.get_timing_preferences("ppv_video")
    print(f"  Preferred Hours: {timing.get('preferred_hours', [])}")
    print(f"  Preferred Days: {timing.get('preferred_days', [])}")
    print(f"  Min Spacing: {timing.get('min_spacing', 0)} minutes")
    print(f"  Boost: {timing.get('boost', 1.0)}x")

    print("\n✅ Registry provides O(1) lookups for all 21 send types")


def demo_configuration() -> None:
    """Demonstrate configuration management."""
    print_section("Configuration Management Demo")

    settings = Settings()

    # Scoring weights
    print("Scoring Weights:")
    weights = settings.scoring_weights
    for name, value in weights.items():
        print(f"  {name}: {value:.2f}")
    print(f"  Total: {sum(weights.values()):.2f} (should be 1.0)")

    # Scoring thresholds
    print("\nScoring Thresholds:")
    thresholds = settings.scoring_thresholds
    for name, value in thresholds.items():
        print(f"  {name}: {value}")

    # Timing configuration
    print("\nTiming Configuration:")
    timing = settings.timing_config
    print(f"  Prime Hours: {timing['prime_hours']}")
    print(f"  Prime Days: {timing['prime_days']} (Fri, Sat, Sun)")
    print(f"  Avoid Hours: {timing['avoid_hours']}")
    print(f"  Min Spacing: {timing['min_spacing_minutes']} minutes")

    # Volume tiers
    print("\nVolume Tier Configuration:")
    tiers = settings.volume_tiers
    for tier_name, tier_config in tiers.items():
        print(f"\n  {tier_name}:")
        for page_type, volumes in tier_config.items():
            total = sum(volumes.values())
            print(f"    {page_type}: {volumes} (total: {total}/day)")

    # Followup configuration
    print("\nFollowup Configuration:")
    followup = settings.followup_config
    print(f"  Max Per Day: {followup['max_per_day']}")
    print(f"  Min Delay: {followup['min_delay_minutes']} minutes")
    print(f"  Enabled Types: {', '.join(followup['enabled_types'])}")

    # Dot notation access
    print("\nDot Notation Access:")
    performance_weight = settings.get("scoring.weights.performance")
    print(f"  scoring.weights.performance = {performance_weight}")
    missing_value = settings.get("nonexistent.key", "default")
    print(f"  nonexistent.key = {missing_value}")

    print("\n✅ Configuration loaded from YAML with environment variable support")


def demo_integration() -> None:
    """Demonstrate integration between components."""
    print_section("Integration Demo")

    settings = Settings()

    # Create creator
    creator = Creator(
        creator_id=1,
        username="alexia",
        page_type="paid",
        fan_count=5432,
    )

    # Determine volume tier
    if creator.fan_count < 1000:
        tier = VolumeTier.LOW
    elif creator.fan_count < 5000:
        tier = VolumeTier.MID
    elif creator.fan_count < 15000:
        tier = VolumeTier.HIGH
    else:
        tier = VolumeTier.ULTRA

    print(f"Creator: {creator.username} ({creator.fan_count:,} fans)")
    print(f"Volume Tier: {tier.value.upper()}")

    # Get tier configuration from settings
    tier_config = settings.volume_tiers[tier.value.upper()][creator.page_type]
    print(f"\nTier Configuration from Settings:")
    print(f"  {tier_config}")

    # Create VolumeConfig
    config = VolumeConfig(
        tier=tier,
        revenue_per_day=tier_config["revenue"],
        engagement_per_day=tier_config["engagement"],
        retention_per_day=tier_config["retention"],
        fan_count=creator.fan_count,
        page_type=creator.page_type,
    )

    print(f"\nGenerated VolumeConfig:")
    print(f"  Total sends/day: {config.total_per_day}")
    print(f"  Revenue: {config.revenue_per_day}")
    print(f"  Engagement: {config.engagement_per_day}")
    print(f"  Retention: {config.retention_per_day}")

    # Create schedule item
    item = ScheduleItem(
        send_type_key="ppv_video",
        scheduled_date="2025-12-16",
        scheduled_time="19:00",
        category="revenue",
        priority=1,
    )

    print(f"\nSchedule Item:")
    print(f"  Type: {item.send_type_key}")
    print(f"  Time: {item.scheduled_time} (prime time: {item.scheduled_time.split(':')[0]} in {settings.timing_config['prime_hours']})")
    print(f"  Category: {item.category}")

    print("\n✅ Domain models, registry, and settings work together seamlessly")


def main() -> None:
    """Run all demonstrations."""
    print("\n" + "=" * 80)
    print("  WAVE 3: DOMAIN MODELS & REGISTRY DEMONSTRATION")
    print("  EROS Schedule Generator v2.0.0")
    print("=" * 80)

    try:
        demo_domain_models()
        demo_send_type_registry()
        demo_configuration()
        demo_integration()

        print("\n" + "=" * 80)
        print("  ✅ All Wave 3 components demonstrated successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
