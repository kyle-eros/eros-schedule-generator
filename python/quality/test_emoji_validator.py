"""
Test script for EmojiValidator to verify emoji detection and validation rules.
"""
from emoji_validator import EmojiValidator


def test_emoji_detection():
    """Test comprehensive emoji detection across Unicode ranges."""
    validator = EmojiValidator()

    test_cases = [
        # Yellow face emojis (should detect)
        ("😀", True, "Basic smiley"),
        ("😍", True, "Heart eyes"),
        ("😊", True, "Smiling face"),

        # Other emojis (should detect)
        ("🔥", True, "Fire emoji"),
        ("💎", True, "Diamond emoji"),
        ("🎉", True, "Party popper"),
        ("❤", True, "Red heart"),  # Single char without variation selector
        ("👍", True, "Thumbs up"),

        # Regular characters (should NOT detect)
        ("a", False, "Letter a"),
        ("1", False, "Number 1"),
        ("!", False, "Exclamation"),
        (" ", False, "Space"),
    ]

    print("Testing emoji detection:")
    print("-" * 60)

    for char, expected, description in test_cases:
        result = validator._is_emoji(char)
        status = "✓" if result == expected else "✗"
        print(f"{status} {description:20} '{char}' -> {result} (expected {expected})")

    print()


def test_yellow_face_detection():
    """Test detection of 3+ consecutive yellow face emojis."""
    validator = EmojiValidator()

    test_cases = [
        # Valid: less than 3 yellow faces
        ("Hey babe 😘 how are you?", True, "Single yellow face"),
        ("Good morning 😊😘 ready for fun?", True, "Two yellow faces"),
        ("Mix it up 😊🔥😘 looks great", True, "Yellow faces separated by non-yellow"),

        # Invalid: 3+ consecutive yellow faces
        ("Hey babe 😊😘😍 this is too much", False, "Three consecutive yellow faces"),
        ("Good morning 😀😃😄😁 emoji overload", False, "Four consecutive yellow faces"),

        # Edge cases
        ("No emojis here", True, "No emojis at all"),
        ("🔥💎🎉 all non-yellow", True, "All non-yellow emojis"),
        ("😊 text 😘 text 😍", True, "Yellow faces separated by text"),
    ]

    print("Testing yellow face consecutive detection:")
    print("-" * 60)

    for caption, expected_valid, description in test_cases:
        result = validator.validate(caption)
        status = "✓" if result['is_valid'] == expected_valid else "✗"
        emoji_info = f"({result['emoji_count']} emojis)"
        issues_info = f"{len(result['issues'])} issues" if result['issues'] else "no issues"
        print(f"{status} {description:35} -> {result['is_valid']} | {emoji_info} {issues_info}")

        if result['issues']:
            for issue in result['issues']:
                print(f"    └─ {issue['severity']:6} {issue['type']:15} {issue['message']}")

    print()


def test_emoji_density():
    """Test emoji density validation for different caption lengths."""
    validator = EmojiValidator()

    test_cases = [
        # Short captions (<100 chars) - max 10% density
        ("Short 😊😘😍🔥💎 test", 100, "Short caption with 5 emojis"),
        ("A" * 50 + "😊", 100, "50 chars + 1 emoji (2% density)"),
        ("A" * 80 + "😊😘😍🔥💎🎉❤️👍🌟💋", 100, "80 chars + 10 emojis (11% density - too high)"),

        # Medium captions (100-250 chars) - max 7% density
        ("A" * 150 + "😊😘😍🔥💎", 150, "150 chars + 5 emojis (3% density)"),
        ("A" * 200 + "😊😘😍🔥💎🎉❤️👍🌟💋😈🍑🍆💦🔞", 200, "200 chars + 14 emojis (7% density)"),

        # Long captions (>250 chars) - max 5% density
        ("A" * 300 + "😊😘😍🔥💎", 300, "300 chars + 5 emojis (1.6% density)"),
        ("A" * 400 + "😊" * 25, 400, "400 chars + 25 emojis (6.25% density - too high)"),
    ]

    print("Testing emoji density validation:")
    print("-" * 60)

    for caption, expected_len, description in test_cases:
        result = validator.validate(caption)
        density_pct = result['emoji_density'] * 100
        density_issues = [i for i in result['issues'] if i['type'] == 'high_density']

        status = "✓" if not density_issues else "⚠"
        print(f"{status} {description:45} -> {density_pct:.1f}% density | {result['emoji_count']} emojis")

        for issue in density_issues:
            print(f"    └─ {issue['severity']:6} {issue['recommendation']}")

    print()


def test_comprehensive_validation():
    """Test complete validation with multiple rules."""
    validator = EmojiValidator()

    test_caption = "Good morning babe 😊😘😍 can't wait to show you something special 🔥💎"

    print("Comprehensive validation test:")
    print("-" * 60)
    print(f"Caption: {test_caption}")
    print()

    result = validator.validate(test_caption)

    print(f"Valid: {result['is_valid']}")
    print(f"Emoji count: {result['emoji_count']}")
    print(f"Emoji density: {result['emoji_density']:.2%}")
    print(f"Issues found: {len(result['issues'])}")
    print()

    if result['issues']:
        print("Issues:")
        for i, issue in enumerate(result['issues'], 1):
            print(f"  {i}. [{issue['severity']}] {issue['type']}")
            print(f"     Message: {issue['message']}")
            print(f"     Recommendation: {issue['recommendation']}")
            if 'emojis' in issue:
                print(f"     Emojis: {''.join(issue['emojis'])}")
            print()


if __name__ == "__main__":
    print("=" * 60)
    print("EMOJI VALIDATOR TEST SUITE")
    print("=" * 60)
    print()

    test_emoji_detection()
    test_yellow_face_detection()
    test_emoji_density()
    test_comprehensive_validation()

    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
