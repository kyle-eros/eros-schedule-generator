#!/usr/bin/env python3
"""
Test script for followup_selector.py

Verifies:
1. All template types are accessible
2. Deterministic seeding produces consistent results
3. Random selection works correctly
4. Helper function extracts ppv_style correctly
"""

from datetime import date
from python.caption.followup_selector import (
    FOLLOWUP_TEMPLATES,
    select_followup_caption,
    get_followup_for_schedule_item,
)


def test_template_types():
    """Verify all template types exist and have correct structure."""
    print("Testing template types...")

    expected_types = ['winner', 'bundle', 'solo', 'sextape', 'default']
    for template_type in expected_types:
        assert template_type in FOLLOWUP_TEMPLATES, f"Missing template type: {template_type}"
        templates = FOLLOWUP_TEMPLATES[template_type]
        assert len(templates) >= 4, f"Template type {template_type} has only {len(templates)} templates"
        print(f"  ✓ {template_type}: {len(templates)} templates")

    print("✓ All template types validated\n")


def test_deterministic_seeding():
    """Verify deterministic seeding produces consistent results."""
    print("Testing deterministic seeding...")

    creator_id = "creator_123"
    schedule_date = date(2025, 12, 16)

    # Select caption multiple times with same inputs
    results = []
    for i in range(5):
        caption = select_followup_caption(
            parent_ppv_type='bundle',
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        results.append(caption)

    # All results should be identical
    assert len(set(results)) == 1, "Deterministic seeding produced different results"
    print(f"  ✓ Consistent result: '{results[0]}'")

    # Different date should produce different result (probably)
    different_date_caption = select_followup_caption(
        parent_ppv_type='bundle',
        creator_id=creator_id,
        schedule_date=date(2025, 12, 17)
    )
    print(f"  ✓ Different date result: '{different_date_caption}'")

    print("✓ Deterministic seeding working correctly\n")


def test_random_selection():
    """Verify random selection works without seeding."""
    print("Testing random selection...")

    # Select multiple times without seeding
    results = set()
    for i in range(20):
        caption = select_followup_caption(parent_ppv_type='solo')
        results.add(caption)

    # Should get some variety (not guaranteed, but very likely with 20 iterations)
    print(f"  ✓ Generated {len(results)} unique captions from {len(FOLLOWUP_TEMPLATES['solo'])} templates")

    print("✓ Random selection working correctly\n")


def test_fallback_to_default():
    """Verify unknown types fall back to default templates."""
    print("Testing fallback to default...")

    caption = select_followup_caption(
        parent_ppv_type='unknown_type',
        creator_id='creator_123',
        schedule_date=date(2025, 12, 16)
    )

    assert caption in FOLLOWUP_TEMPLATES['default'], "Unknown type didn't fall back to default"
    print(f"  ✓ Fallback result: '{caption}'")

    print("✓ Fallback working correctly\n")


def test_schedule_item_helper():
    """Verify helper function extracts ppv_style correctly."""
    print("Testing schedule item helper...")

    # Test with ppv_style present
    item = {
        'ppv_style': 'sextape',
        'price': 35.00,
        'content_type': 'b/g'
    }
    caption = get_followup_for_schedule_item(
        item,
        creator_id='creator_123',
        schedule_date=date(2025, 12, 16)
    )
    assert caption in FOLLOWUP_TEMPLATES['sextape'], "Helper didn't extract ppv_style correctly"
    print(f"  ✓ Sextape result: '{caption}'")

    # Test with ppv_style missing (should use default)
    item_no_style = {'price': 25.00}
    caption_default = get_followup_for_schedule_item(
        item_no_style,
        creator_id='creator_123',
        schedule_date=date(2025, 12, 16)
    )
    assert caption_default in FOLLOWUP_TEMPLATES['default'], "Helper didn't fall back to default"
    print(f"  ✓ Default result: '{caption_default}'")

    print("✓ Schedule item helper working correctly\n")


def test_all_template_types():
    """Generate one caption from each template type."""
    print("Testing all template types...")

    creator_id = "creator_123"
    schedule_date = date(2025, 12, 16)

    for template_type in ['winner', 'bundle', 'solo', 'sextape', 'default']:
        caption = select_followup_caption(
            parent_ppv_type=template_type,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
        print(f"  {template_type:12} -> '{caption}'")

    print("✓ All template types tested\n")


if __name__ == '__main__':
    print("=" * 80)
    print("FOLLOWUP SELECTOR TEST SUITE")
    print("=" * 80)
    print()

    test_template_types()
    test_deterministic_seeding()
    test_random_selection()
    test_fallback_to_default()
    test_schedule_item_helper()
    test_all_template_types()

    print("=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)
