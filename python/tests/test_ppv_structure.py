"""Tests for PPV Structure Validator.

Tests the three main validation methods:
- validate_winner_ppv: 4-step formula validation
- validate_bundle_ppv: Bundle structure validation
- validate_wall_campaign: 3-step wall campaign validation
"""

import re
import pytest
from python.quality.ppv_structure import PPVStructureValidator


@pytest.fixture
def validator():
    """Create validator instance for tests."""
    return PPVStructureValidator()


class TestWinnerPPVValidation:
    """Test winner PPV 4-step structure validation."""

    def test_complete_winner_ppv(self, validator):
        """Test caption with all 4 elements present."""
        caption = """CONGRATS! You won my special giveaway!

        You're the only winner of this exclusive content pack - never seen before by anyone else!

        This bundle is worth $150 but you're getting it for just $25!

        LMK which vid is ur fav babe 💕"""

        result = validator.validate_winner_ppv(caption)

        assert result['is_valid'] is True
        assert result['structure_score'] == 1.0
        assert result['elements']['clickbait'] is True
        assert result['elements']['exclusivity'] is True
        assert result['elements']['value_anchor'] is True
        assert result['elements']['cta'] is True
        assert len(result['issues']) == 0
        assert result['recommendation'] == 'Structure complete'

    def test_missing_clickbait(self, validator):
        """Test caption missing clickbait element."""
        caption = """Here's an exclusive content pack never seen before!

        Worth $150 but only $25 for you!

        LMK which vid is ur fav babe 💕"""

        result = validator.validate_winner_ppv(caption)

        assert result['elements']['clickbait'] is False
        assert 'clickbait' in result['missing_elements']
        assert any(issue['element'] == 'clickbait' for issue in result['issues'])

    def test_missing_exclusivity(self, validator):
        """Test caption missing exclusivity element."""
        caption = """CONGRATS! You won!

        This bundle is worth $150 but you're getting it for just $25!

        LMK which vid is ur fav babe 💕"""

        result = validator.validate_winner_ppv(caption)

        assert result['elements']['exclusivity'] is False
        assert 'exclusivity' in result['missing_elements']

    def test_missing_value_anchor(self, validator):
        """Test caption missing value anchor."""
        caption = """CONGRATS! You won my special giveaway!

        You're the only winner of this exclusive content pack!

        LMK which vid is ur fav babe 💕"""

        result = validator.validate_winner_ppv(caption)

        assert result['elements']['value_anchor'] is False
        assert 'value_anchor' in result['missing_elements']

    def test_missing_cta(self, validator):
        """Test caption missing call-to-action."""
        caption = """CONGRATS! You won my special giveaway!

        You're the only winner of this exclusive content pack!

        This bundle is worth $150 but you're getting it for just $25!"""

        result = validator.validate_winner_ppv(caption)

        assert result['elements']['cta'] is False
        assert 'cta' in result['missing_elements']

    def test_partial_structure_valid(self, validator):
        """Test caption with 3/4 elements (still valid)."""
        caption = """CONGRATS! You won!

        You're the only winner - never seen before!

        LMK which vid is ur fav! 💕"""

        result = validator.validate_winner_ppv(caption)

        assert result['is_valid'] is True  # 3/4 = 0.75 >= 0.75 threshold
        assert result['structure_score'] == 0.75

    def test_partial_structure_invalid(self, validator):
        """Test caption with only 1/4 elements (invalid)."""
        caption = """CONGRATS! You won!

        Here's a special content pack for you!"""

        result = validator.validate_winner_ppv(caption)

        assert result['is_valid'] is False  # 1/4 = 0.25 < 0.75 threshold
        assert result['structure_score'] == 0.25


class TestBundlePPVValidation:
    """Test bundle PPV structure validation."""

    def test_complete_bundle(self, validator):
        """Test bundle with all elements."""
        caption = """FLASH BUNDLE! 🔥

        5 vids + 10 pics + 15 mins of content!

        Usually $100 but only $30 today!

        Limited to first 10 buyers - won't last! ⏰"""

        result = validator.validate_bundle_ppv(caption)

        assert result['is_valid'] is True
        assert result['structure_score'] == 1.0
        assert result['elements']['itemization'] is True
        assert result['elements']['value_anchor'] is True
        assert result['elements']['urgency'] is True

    def test_bundle_missing_itemization(self, validator):
        """Test bundle without proper itemization."""
        caption = """FLASH BUNDLE! 🔥

        Amazing content pack!

        Usually $100 but only $30 today!

        Limited time only!"""

        result = validator.validate_bundle_ppv(caption)

        assert result['elements']['itemization'] is False
        assert any(issue['element'] == 'itemization' for issue in result['issues'])

    def test_bundle_with_bullets(self, validator):
        """Test bundle with bullet-point itemization."""
        caption = """MEGA BUNDLE:
        • 3 full vids
        • 20 exclusive pics
        • Behind the scenes

        Worth $150, now $35! Hurry!"""

        result = validator.validate_bundle_ppv(caption)

        assert result['elements']['itemization'] is True
        assert result['elements']['urgency'] is True


class TestWallCampaignValidation:
    """Test wall campaign 3-step structure validation."""

    def test_complete_wall_campaign(self, validator):
        """Test wall campaign with all 3 elements."""
        caption = """OMG you won't believe what happened! 😱

        I was at the gym yesterday when this cute guy caught me taking mirror selfies.
        I felt so embarrassed but he wanted to help me get the perfect angle.
        Things got pretty steamy in the locker room after...

        Unlock to see what happened next! 🔥"""

        result = validator.validate_wall_campaign(caption)

        assert result['is_valid'] is True
        assert result['structure_score'] == 1.0
        assert result['elements']['clickbait_title'] is True
        assert result['elements']['body_with_setting'] is True
        assert result['elements']['short_wrap'] is True
        assert len(result['issues']) == 0

    def test_missing_clickbait_title(self, validator):
        """Test wall campaign without attention-grabbing title."""
        caption = """Here is my post.

        I was at the gym yesterday when something interesting happened.
        It was quite the experience.

        Check it out"""

        result = validator.validate_wall_campaign(caption)

        assert result['elements']['clickbait_title'] is False
        assert 'clickbait_title' in result['missing_elements']

    def test_title_too_long(self, validator):
        """Test wall campaign with overly long title."""
        caption = """This is a really really really really long title that goes on and on and on without being punchy or attention-grabbing at all and definitely exceeds 100 characters.

        I was at the gym when something happened.

        Unlock to see!"""

        result = validator.validate_wall_campaign(caption)

        assert result['elements']['clickbait_title'] is False
        assert any('too long' in issue['message'] for issue in result['issues'])

    def test_missing_narrative_body(self, validator):
        """Test wall campaign without proper narrative/setting."""
        caption = """OMG you won't believe this! 😱

        It's really hot.

        Unlock to see! 🔥"""

        result = validator.validate_wall_campaign(caption)

        assert result['elements']['body_with_setting'] is False
        assert 'body_with_setting' in result['missing_elements']

    def test_body_too_short(self, validator):
        """Test wall campaign with insufficient body content."""
        caption = """OMG you won't believe this! 😱

        I was there.

        Unlock to see! 🔥"""

        result = validator.validate_wall_campaign(caption)

        assert result['elements']['body_with_setting'] is False
        assert any('too short' in issue['message'] for issue in result['issues'])

    def test_missing_short_wrap(self, validator):
        """Test wall campaign without proper closing."""
        caption = """OMG you won't believe this! 😱

        I was at the gym yesterday when this cute guy caught me taking mirror selfies.
        I felt so embarrassed but he wanted to help me get the perfect angle.
        Things got pretty steamy in the locker room after and I couldn't believe what happened next!"""

        result = validator.validate_wall_campaign(caption)

        assert result['elements']['short_wrap'] is False
        assert 'short_wrap' in result['missing_elements']

    def test_partial_wall_campaign_valid(self, validator):
        """Test wall campaign with 2/3 elements (still valid)."""
        caption = """OMG you won't believe what happened! 😱

        I was at the gym yesterday when this cute guy caught me taking selfies.
        I felt so embarrassed but things got pretty steamy after that moment and I wanted more.

        Hope you enjoy babe!"""

        result = validator.validate_wall_campaign(caption)

        assert result['is_valid'] is True  # 2/3 = 0.67 >= 0.67 threshold
        assert result['structure_score'] >= 0.67

    def test_narrative_indicators(self, validator):
        """Test detection of various narrative indicators."""
        narrative_examples = [
            "I was feeling adventurous when I decided to try something new",
            "After the party ended, I couldn't resist calling him over",
            "During my morning workout, something unexpected happened",
            "I found myself in a situation I never imagined",
            "Before anyone could notice, I started recording everything",
        ]

        for caption_body in narrative_examples:
            full_caption = f"""OMG! 🔥\n\n{caption_body}\n\nUnlock now!"""
            result = validator.validate_wall_campaign(full_caption)
            assert result['elements']['body_with_setting'] is True, \
                f"Failed to detect narrative in: {caption_body}"


class TestRegexPatterns:
    """Test individual regex pattern matching."""

    def test_clickbait_patterns(self, validator):
        """Test clickbait pattern detection."""
        clickbait_examples = [
            "CONGRATS babe!",
            "You won my giveaway!",
            "Winner announcement!",
            "Special surprise for you!",
            "You're so lucky!",
            "You've been chosen!",
            "You're the only one!",
            "First to see this!",
        ]

        for text in clickbait_examples:
            assert any(re.search(p, text.lower()) for p in validator.CLICKBAIT_PATTERNS), \
                f"Failed to match clickbait: {text}"

    def test_exclusivity_keywords(self, validator):
        """Test exclusivity keyword detection."""
        exclusivity_examples = [
            "You're the only winner",
            "This is exclusive content",
            "Never seen before",
            "First time showing this",
            "Just for you babe",
            "Special for you",
            "Only you get this",
            "Private content",
            "Secret video",
            "Unreleased footage",
        ]

        for text in exclusivity_examples:
            assert any(keyword in text.lower() for keyword in validator.EXCLUSIVITY_KEYWORDS), \
                f"Failed to match exclusivity: {text}"

    def test_value_anchor_patterns(self, validator):
        """Test value anchor pattern detection."""
        import re

        value_examples = [
            "$150 worth of content",
            "Worth $200 value",
            "$100 for only $25",
            "Usually $50",
            "Normally $75",
        ]

        for text in value_examples:
            assert any(re.search(p, text.lower()) for p in validator.VALUE_ANCHOR_PATTERNS), \
                f"Failed to match value anchor: {text}"

    def test_cta_patterns(self, validator):
        """Test call-to-action pattern detection."""
        import re

        cta_examples = [
            "LMK what you think",
            "Let me know your fav",
            "Tell me which one",
            "Message me babe",
            "DM me your choice",
            "Which vid is ur fav?",
            "Open to see more",
            "Claim it now",
            "Don't miss this",
            "Hurry before it's gone",
            "What do you think?",
        ]

        for text in cta_examples:
            assert any(re.search(p, text.lower()) for p in validator.CTA_PATTERNS), \
                f"Failed to match CTA: {text}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
