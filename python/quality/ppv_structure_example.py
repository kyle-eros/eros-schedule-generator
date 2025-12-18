"""Example usage of PPV Structure Validator.

Demonstrates how to validate different PPV caption types.
"""

from ppv_structure import PPVStructureValidator


def main():
    """Run example validations."""
    validator = PPVStructureValidator()

    print("=" * 80)
    print("PPV STRUCTURE VALIDATOR - USAGE EXAMPLES")
    print("=" * 80)

    # Example 1: Winner PPV
    print("\n1. WINNER PPV VALIDATION")
    print("-" * 80)
    winner_caption = """CONGRATS! You won my special giveaway! 🎉

    You're the only winner of this exclusive content pack - never seen before by anyone else!

    This bundle is worth $150 but you're getting it for just $25!

    LMK which vid is ur fav babe 💕"""

    result = validator.validate_winner_ppv(winner_caption)
    print(f"Caption preview: {winner_caption[:100]}...")
    print(f"\nIs Valid: {result['is_valid']}")
    print(f"Structure Score: {result['structure_score']:.2%}")
    print(f"Elements Present:")
    for element, present in result['elements'].items():
        print(f"  - {element}: {'✓' if present else '✗'}")
    if result['issues']:
        print(f"\nIssues Found:")
        for issue in result['issues']:
            print(f"  - Step {issue['step']}: {issue['message']}")
    print(f"Recommendation: {result['recommendation']}")

    # Example 2: Bundle PPV
    print("\n\n2. BUNDLE PPV VALIDATION")
    print("-" * 80)
    bundle_caption = """FLASH BUNDLE! 🔥

    5 vids + 10 pics + 15 mins of exclusive content!

    Usually $100 but only $30 today!

    Limited to first 10 buyers - won't last! ⏰"""

    result = validator.validate_bundle_ppv(bundle_caption)
    print(f"Caption preview: {bundle_caption[:100]}...")
    print(f"\nIs Valid: {result['is_valid']}")
    print(f"Structure Score: {result['structure_score']:.2%}")
    print(f"Elements Present:")
    for element, present in result['elements'].items():
        print(f"  - {element}: {'✓' if present else '✗'}")
    if result['issues']:
        print(f"\nIssues Found:")
        for issue in result['issues']:
            print(f"  - {issue['message']}")

    # Example 3: Wall Campaign
    print("\n\n3. WALL CAMPAIGN VALIDATION")
    print("-" * 80)
    wall_caption = """OMG you won't believe what happened! 😱

    I was at the gym yesterday when this cute guy caught me taking mirror selfies.
    I felt so embarrassed but he wanted to help me get the perfect angle.
    Things got pretty steamy in the locker room after that moment...

    Unlock to see what happened next! 🔥"""

    result = validator.validate_wall_campaign(wall_caption)
    print(f"Caption preview: {wall_caption[:100]}...")
    print(f"\nIs Valid: {result['is_valid']}")
    print(f"Structure Score: {result['structure_score']:.2%}")
    print(f"Elements Present:")
    for element, present in result['elements'].items():
        print(f"  - {element}: {'✓' if present else '✗'}")
    if result['issues']:
        print(f"\nIssues Found:")
        for issue in result['issues']:
            print(f"  - Step {issue['step']}: {issue['message']}")
    print(f"Recommendation: {result['recommendation']}")

    # Example 4: Invalid Winner PPV (missing elements)
    print("\n\n4. INVALID WINNER PPV (Missing Elements)")
    print("-" * 80)
    invalid_caption = """Hey babe! Here's a special video for you!"""

    result = validator.validate_winner_ppv(invalid_caption)
    print(f"Caption: {invalid_caption}")
    print(f"\nIs Valid: {result['is_valid']}")
    print(f"Structure Score: {result['structure_score']:.2%}")
    print(f"Missing Elements: {', '.join(result['missing_elements'])}")
    print(f"\nIssues Found:")
    for issue in result['issues']:
        print(f"  - Step {issue['step']} ({issue['element']}): {issue['message']}")
    print(f"Recommendation: {result['recommendation']}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
