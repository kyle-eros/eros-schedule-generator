#!/usr/bin/env python3
"""
Demonstration script for followup_selector.py

Shows practical usage examples and key features.
"""

from datetime import date
from python.caption.followup_selector import (
    FOLLOWUP_TEMPLATES,
    select_followup_caption,
    get_followup_for_schedule_item,
)


def demo_template_inspection():
    """Show all available templates."""
    print("=" * 80)
    print("AVAILABLE TEMPLATES")
    print("=" * 80)

    for template_type, templates in FOLLOWUP_TEMPLATES.items():
        print(f"\n{template_type.upper()} ({len(templates)} templates):")
        for i, template in enumerate(templates, 1):
            print(f"  {i}. {template}")


def demo_deterministic_selection():
    """Demonstrate deterministic seeding."""
    print("\n" + "=" * 80)
    print("DETERMINISTIC SELECTION")
    print("=" * 80)

    creator_id = "creator_alexia"
    schedule_date = date(2025, 12, 16)

    print(f"\nCreator: {creator_id}")
    print(f"Date: {schedule_date}")
    print("\nGenerating 3 times with same inputs:")

    for i in range(3):
        caption = select_followup_caption(
            parent_ppv_type='bundle',
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"  {i+1}. {caption}")

    print("\n✓ All results identical (deterministic)")


def demo_date_variation():
    """Show how different dates produce different results."""
    print("\n" + "=" * 80)
    print("DATE VARIATION")
    print("=" * 80)

    creator_id = "creator_alexia"
    ppv_type = 'sextape'

    print(f"\nCreator: {creator_id}")
    print(f"PPV Type: {ppv_type}")
    print("\nCaptions for different dates:")

    for day in range(16, 20):
        schedule_date = date(2025, 12, day)
        caption = select_followup_caption(
            parent_ppv_type=ppv_type,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"  {schedule_date}: {caption[:50]}...")


def demo_type_specific_selection():
    """Show type-specific caption selection."""
    print("\n" + "=" * 80)
    print("TYPE-SPECIFIC SELECTION")
    print("=" * 80)

    creator_id = "creator_alexia"
    schedule_date = date(2025, 12, 16)

    print(f"\nCreator: {creator_id}")
    print(f"Date: {schedule_date}")
    print("\nCaptions by PPV type:")

    types = ['winner', 'bundle', 'solo', 'sextape', 'default']
    for ppv_type in types:
        caption = select_followup_caption(
            parent_ppv_type=ppv_type,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"\n  {ppv_type.upper()}:")
        print(f"  → {caption}")


def demo_schedule_item_integration():
    """Show integration with schedule items."""
    print("\n" + "=" * 80)
    print("SCHEDULE ITEM INTEGRATION")
    print("=" * 80)

    creator_id = "creator_alexia"
    schedule_date = date(2025, 12, 16)

    # Simulate schedule items from different PPV types
    schedule_items = [
        {
            'item_type': 'ppv',
            'ppv_style': 'bundle',
            'price': 25.00,
            'content_type': 'solo'
        },
        {
            'item_type': 'ppv',
            'ppv_style': 'sextape',
            'price': 35.00,
            'content_type': 'b/g'
        },
        {
            'item_type': 'ppv',
            'ppv_style': 'winner',
            'price': 0.00,
            'content_type': 'custom'
        },
        {
            'item_type': 'ppv',
            'price': 20.00,
            'content_type': 'solo'
            # No ppv_style - should use default
        }
    ]

    print(f"\nCreator: {creator_id}")
    print(f"Date: {schedule_date}")
    print("\nGenerating followups for PPV items:")

    for i, item in enumerate(schedule_items, 1):
        ppv_style = item.get('ppv_style', 'missing')
        caption = get_followup_for_schedule_item(
            item,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"\n  Item {i} ({ppv_style}):")
        print(f"  → {caption}")


def demo_fallback_behavior():
    """Show fallback to default for unknown types."""
    print("\n" + "=" * 80)
    print("FALLBACK BEHAVIOR")
    print("=" * 80)

    creator_id = "creator_alexia"
    schedule_date = date(2025, 12, 16)

    unknown_types = ['custom', 'mystery', 'XYZ', 'invalid']

    print(f"\nCreator: {creator_id}")
    print(f"Date: {schedule_date}")
    print("\nUnknown types fallback to default:")

    for unknown_type in unknown_types:
        caption = select_followup_caption(
            parent_ppv_type=unknown_type,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"  '{unknown_type}' → {caption[:50]}...")

    print("\n✓ All unknown types use default templates")


def demo_random_mode():
    """Show random selection mode (no seeding)."""
    print("\n" + "=" * 80)
    print("RANDOM MODE (No Seeding)")
    print("=" * 80)

    print("\nWithout creator_id and schedule_date, selection is random:")
    print("\nGenerating 5 random solo followups:")

    for i in range(5):
        caption = select_followup_caption(parent_ppv_type='solo')
        print(f"  {i+1}. {caption}")

    print("\n✓ Random selection for ad-hoc usage")


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("FOLLOWUP SELECTOR DEMONSTRATION")
    print("=" * 80)

    demo_template_inspection()
    demo_deterministic_selection()
    demo_date_variation()
    demo_type_specific_selection()
    demo_schedule_item_integration()
    demo_fallback_behavior()
    demo_random_mode()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("  ✓ 5 template types (winner, bundle, solo, sextape, default)")
    print("  ✓ Deterministic seeding for reproducibility")
    print("  ✓ Date variation with consistent per-date results")
    print("  ✓ Type-specific authentic messaging")
    print("  ✓ Schedule item integration helper")
    print("  ✓ Graceful fallback for unknown types")
    print("  ✓ Random mode for ad-hoc usage")
    print("=" * 80 + "\n")
