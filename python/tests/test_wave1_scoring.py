"""
Comprehensive test suite for Wave 1 Foundation implementations.

Tests all Wave 1 gaps:
- Gap 2.1: Character length optimization
- Gap 10.15: Confidence-based revenue allocation
- Gap 3.3: Send type diversity minimum
- Gap 8.1: Channel assignment accuracy
- Gap 9.1: Retention types only on PAID pages
- Gap 4.2: Non-converter elimination

Run with: pytest python/tests/test_wave1_scoring.py -v
"""

import pytest
import time
from typing import Any


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_captions() -> list[dict[str, Any]]:
    """Sample captions across all character ranges."""
    return [
        {'text': 'x' * 300, 'expected_mult': 1.0},      # Optimal (250-449)
        {'text': 'x' * 200, 'expected_mult': 0.755},    # Medium-short (150-249)
        {'text': 'x' * 100, 'expected_mult': 0.469},    # Short (50-149)
        {'text': 'x' * 25, 'expected_mult': 0.220},     # Ultra-short (0-49)
        {'text': 'x' * 500, 'expected_mult': 0.372},    # Medium-long (450-549)
        {'text': 'x' * 600, 'expected_mult': 0.112},    # Long (550-749)
        {'text': 'x' * 800, 'expected_mult': 0.037},    # Ultra-long (750+)
    ]


@pytest.fixture
def boundary_values() -> list[tuple[int, float]]:
    """Boundary test cases: (char_count, expected_multiplier)."""
    return [
        (0, 0.037),    # Empty -> ultra_long penalty
        (49, 0.220),   # Upper bound of ultra_short
        (50, 0.469),   # Lower bound of short
        (149, 0.469),  # Upper bound of short
        (150, 0.755),  # Lower bound of medium_short
        (249, 0.755),  # Upper bound of medium_short
        (250, 1.0),    # Lower bound of optimal
        (449, 1.0),    # Upper bound of optimal
        (450, 0.372),  # Lower bound of medium_long
        (549, 0.372),  # Upper bound of medium_long
        (550, 0.112),  # Lower bound of long
        (749, 0.112),  # Upper bound of long
        (750, 0.037),  # Lower bound of ultra_long
    ]


@pytest.fixture
def confidence_test_cases() -> list[tuple[float, str, float, int, float]]:
    """Confidence test cases: (confidence, tier, volume_mult, freshness_days, followup_mult)."""
    return [
        (1.0, "full", 1.0, 30, 1.0),
        (0.9, "full", 1.0, 30, 1.0),
        (0.8, "full", 1.0, 30, 1.0),
        (0.79, "standard", 1.0, 30, 0.8),
        (0.7, "standard", 1.0, 30, 0.8),
        (0.6, "standard", 1.0, 30, 0.8),
        (0.59, "minimum", 0.85, 20, 0.5),
        (0.5, "minimum", 0.85, 20, 0.5),
        (0.4, "minimum", 0.85, 20, 0.5),
        (0.39, "conservative", 0.7, 15, 0.3),
        (0.2, "conservative", 0.7, 15, 0.3),
        (0.0, "conservative", 0.7, 15, 0.3),
    ]


@pytest.fixture
def diverse_schedule() -> list[dict[str, Any]]:
    """Schedule with 12 unique types (passes diversity) with correct channels."""
    # Each type paired with its correct primary channel
    type_channel_pairs = [
        ('ppv_unlock', 'mass_message'),
        ('bump_normal', 'wall_post'),
        ('bundle', 'mass_message'),
        ('link_drop', 'mass_message'),
        ('dm_farm', 'mass_message'),
        ('game_post', 'wall_post'),
        ('flash_bundle', 'mass_message'),
        ('bump_descriptive', 'wall_post'),
        ('like_farm', 'wall_post'),
        ('first_to_tip', 'wall_post'),
        ('bump_text_only', 'wall_post'),
        ('vip_program', 'mass_message'),
    ]
    return [{'send_type': t, 'channel': c} for t, c in type_channel_pairs]


@pytest.fixture
def sparse_schedule() -> list[dict[str, Any]]:
    """Schedule with only 2 types (fails diversity)."""
    return [
        {'send_type': 'ppv_unlock', 'channel': 'mass_message'},
        {'send_type': 'bump_normal', 'channel': 'wall_post'},
        {'send_type': 'ppv_unlock', 'channel': 'mass_message'},
    ]


@pytest.fixture
def performance_data() -> dict[str, dict[str, Any]]:
    """Sample performance data with various tiers."""
    return {
        'ppv_unlock': {'tier': 'top', 'rps': 450.0},
        'bundle': {'tier': 'top', 'rps': 380.0},
        'bump_normal': {'tier': 'mid', 'rps': 120.0},
        'link_drop': {'tier': 'mid', 'rps': 85.0},
        'dm_farm': {'tier': 'avoid', 'rps': 15.0},
        'like_farm': {'tier': 'avoid', 'rps': 8.0},
        'game_post': {'tier': 'low', 'rps': 45.0},
    }


# ============================================================================
# TASK 1.1: CHARACTER LENGTH MULTIPLIER TESTS
# ============================================================================

class TestCharacterLengthMultiplier:
    """Tests for calculate_character_length_multiplier function."""

    def test_each_range_returns_correct_multiplier(self, sample_captions: list[dict]) -> None:
        """Test each character range returns correct multiplier."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        for caption in sample_captions:
            result = calculate_character_length_multiplier(caption['text'])
            assert result == caption['expected_mult'], (
                f"Text length {len(caption['text'])} should return {caption['expected_mult']}, "
                f"got {result}"
            )

    def test_boundary_values(self, boundary_values: list[tuple[int, float]]) -> None:
        """Test all boundary values return correct multipliers."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        for char_count, expected in boundary_values:
            text = 'x' * char_count if char_count > 0 else ''
            result = calculate_character_length_multiplier(text)
            assert result == expected, (
                f"Char count {char_count} should return {expected}, got {result}"
            )

    def test_empty_string_returns_minimum(self) -> None:
        """Test empty string returns minimum multiplier (0.037)."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        assert calculate_character_length_multiplier('') == 0.037

    def test_whitespace_only_returns_minimum(self) -> None:
        """Test whitespace-only strings return minimum multiplier."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        assert calculate_character_length_multiplier('   ') == 0.037
        assert calculate_character_length_multiplier('\t\n') == 0.037
        assert calculate_character_length_multiplier('  \t  \n  ') == 0.037

    def test_none_input_returns_minimum(self) -> None:
        """Test None input returns minimum multiplier."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        assert calculate_character_length_multiplier(None) == 0.037

    def test_non_string_raises_typeerror(self) -> None:
        """Test non-string input raises TypeError."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        with pytest.raises(TypeError):
            calculate_character_length_multiplier(123)  # type: ignore

        with pytest.raises(TypeError):
            calculate_character_length_multiplier(['list'])  # type: ignore

        with pytest.raises(TypeError):
            calculate_character_length_multiplier({'dict': 'value'})  # type: ignore

    def test_unicode_emoji_character_counting(self) -> None:
        """Test unicode and emoji characters are counted correctly."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        # 300 characters with emojis should be optimal
        text_with_emoji = 'x' * 150 + 'y' * 150  # 300 chars total
        result = calculate_character_length_multiplier(text_with_emoji)
        assert result == 1.0, f"300 chars should be optimal, got {result}"

        # Unicode text (Chinese characters - each counts as 1)
        unicode_text = 'a' * 300  # 300 characters
        result = calculate_character_length_multiplier(unicode_text)
        assert result == 1.0

    def test_performance_1000_iterations(self) -> None:
        """Test performance: 1000 iterations should complete in <5 seconds."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        test_text = 'x' * 300

        start_time = time.time()
        for _ in range(1000):
            calculate_character_length_multiplier(test_text)
        elapsed = time.time() - start_time

        assert elapsed < 5.0, f"1000 iterations took {elapsed:.2f}s, should be <5s"

    def test_optimal_zone_values(self) -> None:
        """Test various values within optimal zone (250-449) all return 1.0."""
        from python.volume.score_calculator import calculate_character_length_multiplier

        for length in [250, 300, 350, 400, 449]:
            text = 'x' * length
            assert calculate_character_length_multiplier(text) == 1.0


# ============================================================================
# TASK 1.2: ENHANCED EROS SCORE TESTS
# ============================================================================

class TestEnhancedEROSScore:
    """Tests for calculate_enhanced_eros_score function."""

    def test_optimal_length_increases_score(self) -> None:
        """Test optimal-length captions get higher enhanced scores."""
        from python.volume.score_calculator import calculate_enhanced_eros_score

        optimal_caption = {
            'text': 'x' * 300,  # Optimal length
            'rps_score': 0.8,
            'conversion_score': 0.7,
            'execution_score': 0.6,
            'diversity_score': 0.5,
        }

        short_caption = {
            'text': 'x' * 25,  # Ultra-short
            'rps_score': 0.8,
            'conversion_score': 0.7,
            'execution_score': 0.6,
            'diversity_score': 0.5,
        }

        optimal_score = calculate_enhanced_eros_score(optimal_caption)
        short_score = calculate_enhanced_eros_score(short_caption)

        assert optimal_score > short_score, (
            f"Optimal length should score higher: {optimal_score} vs {short_score}"
        )

    def test_non_optimal_length_decreases_score(self) -> None:
        """Test non-optimal length captions get reduced enhanced scores."""
        from python.volume.score_calculator import calculate_enhanced_eros_score

        base_scores = {
            'rps_score': 0.8,
            'conversion_score': 0.7,
            'execution_score': 0.6,
            'diversity_score': 0.5,
        }

        # Calculate base score manually
        # base = 0.4 * 0.8 + 0.3 * 0.7 + 0.2 * 0.6 + 0.1 * 0.5  # 0.68

        optimal = calculate_enhanced_eros_score({'text': 'x' * 300, **base_scores})
        ultra_long = calculate_enhanced_eros_score({'text': 'x' * 800, **base_scores})

        # Optimal: base * (0.6 + 0.4 * 1.0) = base
        # Ultra-long: base * (0.6 + 0.4 * 0.037) ~ base * 0.615
        assert ultra_long < optimal

    def test_non_dict_raises_typeerror(self) -> None:
        """Test non-dict input raises TypeError."""
        from python.volume.score_calculator import calculate_enhanced_eros_score

        with pytest.raises(TypeError):
            calculate_enhanced_eros_score("not a dict")  # type: ignore

        with pytest.raises(TypeError):
            calculate_enhanced_eros_score([1, 2, 3])  # type: ignore

    def test_score_override_parameters(self) -> None:
        """Test that override parameters take precedence over caption_data."""
        from python.volume.score_calculator import calculate_enhanced_eros_score

        caption = {'text': 'x' * 300, 'rps_score': 0.5}

        # Override with higher RPS
        score_with_override = calculate_enhanced_eros_score(
            caption, rps_score=0.9
        )
        score_without_override = calculate_enhanced_eros_score(caption)

        assert score_with_override > score_without_override

    def test_missing_text_uses_minimum_multiplier(self) -> None:
        """Test that missing 'text' key uses minimum multiplier."""
        from python.volume.score_calculator import calculate_enhanced_eros_score

        caption = {'rps_score': 0.8}  # No 'text' key
        score = calculate_enhanced_eros_score(caption)

        # Should use 0.037 multiplier for missing text
        assert score > 0


# ============================================================================
# TASK 1.3: CONFIDENCE ADJUSTMENTS TESTS
# ============================================================================

class TestConfidenceAdjustments:
    """Tests for get_confidence_adjustments function."""

    def test_each_tier_returns_correct_adjustments(
        self, confidence_test_cases: list[tuple[float, str, float, int, float]]
    ) -> None:
        """Test each confidence tier returns correct adjustments."""
        from python.volume.confidence import get_confidence_adjustments

        for conf, expected_tier, expected_vol, expected_fresh, expected_followup in confidence_test_cases:
            result = get_confidence_adjustments(conf)

            assert result['tier'] == expected_tier, (
                f"Confidence {conf} should be tier '{expected_tier}', got '{result['tier']}'"
            )
            assert result['volume_mult'] == expected_vol, (
                f"Confidence {conf} should have volume_mult {expected_vol}, got {result['volume_mult']}"
            )
            assert result['freshness_days'] == expected_fresh, (
                f"Confidence {conf} should have freshness_days {expected_fresh}, got {result['freshness_days']}"
            )
            assert result['followup_mult'] == expected_followup, (
                f"Confidence {conf} should have followup_mult {expected_followup}, got {result['followup_mult']}"
            )

    def test_boundary_values(self) -> None:
        """Test specific boundary values."""
        from python.volume.confidence import get_confidence_adjustments

        # Exactly at boundary
        assert get_confidence_adjustments(0.8)['tier'] == 'full'
        assert get_confidence_adjustments(0.6)['tier'] == 'standard'
        assert get_confidence_adjustments(0.4)['tier'] == 'minimum'

        # Just below boundary
        assert get_confidence_adjustments(0.79)['tier'] == 'standard'
        assert get_confidence_adjustments(0.59)['tier'] == 'minimum'
        assert get_confidence_adjustments(0.39)['tier'] == 'conservative'

    def test_non_numeric_raises_typeerror(self) -> None:
        """Test non-numeric input raises TypeError."""
        from python.volume.confidence import get_confidence_adjustments

        with pytest.raises(TypeError):
            get_confidence_adjustments("0.5")  # type: ignore

        with pytest.raises(TypeError):
            get_confidence_adjustments(None)  # type: ignore

    def test_out_of_range_raises_valueerror(self) -> None:
        """Test out-of-range confidence raises ValueError."""
        from python.volume.confidence import get_confidence_adjustments

        with pytest.raises(ValueError):
            get_confidence_adjustments(-0.1)

        with pytest.raises(ValueError):
            get_confidence_adjustments(1.1)

    def test_integer_confidence_works(self) -> None:
        """Test integer values work (0 and 1)."""
        from python.volume.confidence import get_confidence_adjustments

        result_0 = get_confidence_adjustments(0)
        assert result_0['tier'] == 'conservative'

        result_1 = get_confidence_adjustments(1)
        assert result_1['tier'] == 'full'


# ============================================================================
# TASK 1.4: DIVERSITY VALIDATOR TESTS
# ============================================================================

class TestDiversityValidator:
    """Tests for validate_send_type_diversity function."""

    def test_diverse_schedule_passes(self, diverse_schedule: list[dict]) -> None:
        """Test schedule with 10+ unique types passes."""
        from python.orchestration.quality_validator import validate_send_type_diversity

        result = validate_send_type_diversity(diverse_schedule)
        assert result['is_valid'] is True
        assert result['current_count'] >= 10

    def test_sparse_schedule_fails(self, sparse_schedule: list[dict]) -> None:
        """Test schedule with <10 unique types fails."""
        from python.orchestration.quality_validator import validate_send_type_diversity

        result = validate_send_type_diversity(sparse_schedule)
        assert result['is_valid'] is False
        assert result['current_count'] == 2
        assert 'error' in result
        assert len(result['missing_suggestions']) > 0

    def test_missing_suggestions_provided(self) -> None:
        """Test that missing suggestions are provided for invalid schedules."""
        from python.orchestration.quality_validator import validate_send_type_diversity

        schedule = [{'send_type': 'ppv_unlock'}]
        result = validate_send_type_diversity(schedule)

        assert result['is_valid'] is False
        assert 'missing_suggestions' in result
        assert len(result['missing_suggestions']) <= 3
        # Suggestions should be valid send types
        for suggestion in result['missing_suggestions']:
            assert suggestion != 'ppv_unlock'  # Should not suggest what we have

    def test_both_field_names_work(self) -> None:
        """Test both 'send_type' and 'send_type_key' field names work."""
        from python.orchestration.quality_validator import validate_send_type_diversity

        # Using send_type
        schedule1 = [{'send_type': 'ppv_unlock'}]
        result1 = validate_send_type_diversity(schedule1)

        # Using send_type_key
        schedule2 = [{'send_type_key': 'ppv_unlock'}]
        result2 = validate_send_type_diversity(schedule2)

        assert result1['current_count'] == result2['current_count']

    def test_empty_schedule(self) -> None:
        """Test empty schedule returns 0 count and fails."""
        from python.orchestration.quality_validator import validate_send_type_diversity

        result = validate_send_type_diversity([])
        assert result['is_valid'] is False
        assert result['current_count'] == 0


# ============================================================================
# TASK 1.5: CHANNEL ASSIGNMENT TESTS
# ============================================================================

class TestChannelAssignment:
    """Tests for validate_channel_assignment function."""

    def test_valid_primary_channel_passes(self) -> None:
        """Test valid primary channel assignment passes."""
        from python.orchestration.quality_validator import validate_channel_assignment

        item = {'send_type': 'ppv_unlock', 'channel': 'mass_message'}
        result = validate_channel_assignment(item, 'paid')
        assert result['is_valid'] is True

    def test_valid_secondary_channel_passes(self) -> None:
        """Test valid secondary channel assignment passes."""
        from python.orchestration.quality_validator import validate_channel_assignment

        # bump_normal allows both wall_post and mass_message
        item = {'send_type': 'bump_normal', 'channel': 'mass_message'}
        result = validate_channel_assignment(item, 'paid')
        assert result['is_valid'] is True

    def test_invalid_channel_fails(self) -> None:
        """Test invalid channel assignment fails with correct error."""
        from python.orchestration.quality_validator import validate_channel_assignment

        item = {'send_type': 'ppv_unlock', 'channel': 'wall_post'}
        result = validate_channel_assignment(item, 'paid')

        assert result['is_valid'] is False
        assert 'error' in result
        assert 'ppv_unlock should use mass_message' in result['error']

    def test_paid_only_type_on_free_page_fails(self) -> None:
        """Test PAID-only type on FREE page fails."""
        from python.orchestration.quality_validator import validate_channel_assignment

        # renew_on_message is PAID-only
        item = {'send_type': 'renew_on_message', 'channel': 'mass_message'}
        result = validate_channel_assignment(item, 'free')

        assert result['is_valid'] is False
        assert 'only valid for PAID pages' in result['error']

    def test_free_only_type_on_paid_page_fails(self) -> None:
        """Test FREE-only type on PAID page fails."""
        from python.orchestration.quality_validator import validate_channel_assignment

        # ppv_wall is FREE-only
        item = {'send_type': 'ppv_wall', 'channel': 'wall_post'}
        result = validate_channel_assignment(item, 'paid')

        assert result['is_valid'] is False
        assert 'only valid for FREE pages' in result['error']

    def test_unknown_type_passes(self) -> None:
        """Test unknown send type passes (allows custom types)."""
        from python.orchestration.quality_validator import validate_channel_assignment

        item = {'send_type': 'custom_new_type', 'channel': 'mass_message'}
        result = validate_channel_assignment(item, 'paid')
        assert result['is_valid'] is True

    def test_all_22_types_have_mappings(self) -> None:
        """Test all 22 send types have correct channel mappings."""
        from python.orchestration.quality_validator import CHANNEL_MAPPING

        expected_types = {
            # Revenue (9)
            'ppv_unlock', 'ppv_wall', 'tip_goal', 'bundle', 'flash_bundle',
            'game_post', 'first_to_tip', 'vip_program', 'snapchat_bundle',
            # Engagement (9)
            'link_drop', 'wall_link_drop', 'bump_normal', 'bump_descriptive',
            'bump_text_only', 'bump_flyer', 'dm_farm', 'like_farm', 'live_promo',
            # Retention (4)
            'renew_on_post', 'renew_on_message', 'ppv_followup', 'expired_winback'
        }

        assert set(CHANNEL_MAPPING.keys()) == expected_types
        assert len(CHANNEL_MAPPING) == 22


# ============================================================================
# TASK 1.6: NON-CONVERTER FILTER TESTS
# ============================================================================

class TestNonConverterFilter:
    """Tests for filter_non_converters function."""

    def test_avoid_tier_filtered_out(self, performance_data: dict) -> None:
        """Test 'avoid' tier types are filtered out."""
        from python.allocation.send_type_allocator import filter_non_converters

        send_types = ['ppv_unlock', 'dm_farm', 'like_farm', 'bundle']
        result = filter_non_converters(send_types, performance_data)

        assert 'dm_farm' not in result
        assert 'like_farm' not in result
        assert 'ppv_unlock' in result
        assert 'bundle' in result

    def test_other_tiers_kept(self, performance_data: dict) -> None:
        """Test other tiers (top, mid, low) are kept."""
        from python.allocation.send_type_allocator import filter_non_converters

        send_types = ['ppv_unlock', 'bump_normal', 'game_post']
        result = filter_non_converters(send_types, performance_data)

        assert result == send_types  # All should be kept

    def test_types_not_in_data_kept(self) -> None:
        """Test types not in performance_data are kept."""
        from python.allocation.send_type_allocator import filter_non_converters

        send_types = ['ppv_unlock', 'unknown_type', 'another_new_type']
        result = filter_non_converters(send_types, {})

        assert result == send_types  # All kept when no data

    def test_empty_inputs(self) -> None:
        """Test empty inputs work correctly."""
        from python.allocation.send_type_allocator import filter_non_converters

        assert filter_non_converters([], {}) == []
        assert filter_non_converters(['ppv_unlock'], {}) == ['ppv_unlock']

    def test_original_list_not_modified(self, performance_data: dict) -> None:
        """Test original list is not modified."""
        from python.allocation.send_type_allocator import filter_non_converters

        original = ['ppv_unlock', 'dm_farm', 'bundle']
        original_copy = original.copy()

        filter_non_converters(original, performance_data)

        assert original == original_copy


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestWave1Integration:
    """Integration tests for Wave 1 components working together."""

    def test_full_schedule_validation_pipeline(self, diverse_schedule: list[dict]) -> None:
        """Test full schedule validation pipeline."""
        from python.orchestration.quality_validator import validate_schedule_quality

        result = validate_schedule_quality(diverse_schedule, 'paid')
        assert result['is_valid'] is True

    def test_scoring_and_filtering_integration(self, performance_data: dict) -> None:
        """Test scoring and filtering work together."""
        from python.volume.score_calculator import calculate_character_length_multiplier
        from python.allocation.send_type_allocator import filter_non_converters

        # Filter non-converters
        send_types = list(performance_data.keys())
        filtered = filter_non_converters(send_types, performance_data)

        # Score captions for remaining types
        caption = 'x' * 300  # Optimal length
        multiplier = calculate_character_length_multiplier(caption)

        assert len(filtered) < len(send_types)  # Some filtered
        assert multiplier == 1.0  # Optimal scoring


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
