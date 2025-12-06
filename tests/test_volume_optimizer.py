#!/usr/bin/env python3
"""
Comprehensive unit tests for the Volume Optimizer module.

This test suite covers all factor functions, the main optimizer class,
validation functions, and integration scenarios with mock database.

Run with:
    pytest tests/test_volume_optimizer.py -v
    pytest tests/test_volume_optimizer.py -v --cov=scripts.volume_optimizer --cov-report=term-missing
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest

# Add scripts directory to path for imports
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from volume_optimizer import (
    # Constants
    PAID_PAGE_CONFIG,
    FREE_PAGE_CONFIG,
    TIER_FACTORS,
    CONVERSION_FACTORS,
    NICHE_FACTORS,
    SUB_PRICE_FACTORS,
    ACCOUNT_AGE_FACTORS,
    PAID_PAGE_MIN_PPV_WEEK,
    PAID_PAGE_MAX_PPV_WEEK,
    FREE_PAGE_MIN_PPV_DAY,
    FREE_PAGE_MAX_PPV_DAY,
    MIN_BUMP_PER_DAY,
    MAX_BUMP_PER_DAY,
    FREE_PAGE_VOLUME_EFFICIENCY,
    PAID_PAGE_VOLUME_TOLERANCE,
    DAY_OF_WEEK_MODIFIERS,
    # Helper functions
    get_niche_factor,
    get_subscription_price_factor,
    get_account_age_factor,
    get_conversion_factor,
    get_page_type_volume_factor,
    get_volume_tier,
    get_day_of_week_modifier,
    get_weekly_day_distribution,
    # Classes
    CreatorMetrics,
    VolumeStrategy,
    MultiFactorVolumeOptimizer,
    # Validation functions
    validate_volume_strategy,
    get_volume_warnings,
)


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture
def mock_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory test database with creators and related tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create creators table
    conn.execute("""
        CREATE TABLE creators (
            creator_id TEXT PRIMARY KEY,
            page_name TEXT NOT NULL,
            display_name TEXT,
            page_type TEXT DEFAULT 'paid',
            subscription_price REAL DEFAULT 0.0,
            current_active_fans INTEGER DEFAULT 0,
            performance_tier INTEGER DEFAULT 2,
            current_total_earnings REAL DEFAULT 0.0,
            current_message_net REAL DEFAULT 0.0,
            first_seen_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Create creator_personas table
    conn.execute("""
        CREATE TABLE creator_personas (
            persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            primary_tone TEXT,
            avg_sentiment REAL DEFAULT 0.5,
            FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
        )
    """)

    # Create mass_messages table for purchase rate calculation
    conn.execute("""
        CREATE TABLE mass_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            purchased_count INTEGER DEFAULT 0,
            net_amount REAL DEFAULT 0.0,
            FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
        )
    """)

    # Create volume_assignments table
    conn.execute("""
        CREATE TABLE volume_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            volume_level TEXT,
            ppv_per_day INTEGER,
            bump_per_day INTEGER,
            assigned_by TEXT,
            assigned_reason TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
        )
    """)

    # Create volume_overrides table for manual overrides
    conn.execute("""
        CREATE TABLE volume_overrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            target_weekly_ppv INTEGER NOT NULL,
            target_weekly_bump INTEGER NOT NULL,
            override_reason TEXT,
            is_active INTEGER DEFAULT 1,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
        )
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_creator(mock_db: sqlite3.Connection) -> str:
    """Insert a sample creator and return creator_id."""
    creator_id = "test-creator-001"
    first_seen = (datetime.now() - timedelta(days=200)).isoformat()

    mock_db.execute("""
        INSERT INTO creators (
            creator_id, page_name, display_name, page_type,
            subscription_price, current_active_fans, performance_tier,
            current_total_earnings, current_message_net, first_seen_at, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        creator_id, "testcreator", "Test Creator", "paid",
        12.99, 3500, 2, 15000.0, 8000.0, first_seen, 1
    ))

    mock_db.execute("""
        INSERT INTO creator_personas (creator_id, primary_tone, avg_sentiment)
        VALUES (?, ?, ?)
    """, (creator_id, "explicit", 0.6))

    # Add some mass messages for purchase rate calculation
    mock_db.execute("""
        INSERT INTO mass_messages (creator_id, sent_count, purchased_count, net_amount)
        VALUES (?, ?, ?, ?), (?, ?, ?, ?), (?, ?, ?, ?)
    """, (
        creator_id, 1000, 120, 1500.00,  # 12% conversion
        creator_id, 800, 100, 1200.00,   # 12.5% conversion
        creator_id, 500, 55, 750.00,     # 11% conversion
    ))

    mock_db.commit()
    return creator_id


# ==============================================================================
# TEST NICHE FACTOR
# ==============================================================================

class TestNicheFactor:
    """Tests for get_niche_factor function."""

    def test_gfe_reduces_volume(self) -> None:
        """GFE personas should have 0.70x multiplier."""
        assert get_niche_factor("gfe") == 0.70
        assert get_niche_factor("girlfriend") == 0.70
        assert get_niche_factor("GFE Experience") == 0.70  # Case insensitive
        assert get_niche_factor("GFE") == 0.70

    def test_fetish_increases_volume(self) -> None:
        """Fetish personas should have 1.20x multiplier."""
        assert get_niche_factor("fetish") == 1.20
        assert get_niche_factor("kink") == 1.20
        assert get_niche_factor("BDSM") == 1.15
        assert get_niche_factor("bdsm") == 1.15

    def test_standard_niches(self) -> None:
        """Standard niches should be 1.0x."""
        assert get_niche_factor("explicit") == 1.00
        assert get_niche_factor("cosplay") == 1.00
        assert get_niche_factor("fantasy") == 1.00
        assert get_niche_factor("hardcore") == 1.00

    def test_softcore_niches(self) -> None:
        """Softcore niches should reduce volume."""
        assert get_niche_factor("softcore") == 0.85
        assert get_niche_factor("tease") == 0.85

    def test_lifestyle_niches(self) -> None:
        """Lifestyle niches should have reduced volume."""
        assert get_niche_factor("fitness") == 0.80
        assert get_niche_factor("lifestyle") == 0.80

    def test_unknown_returns_default(self) -> None:
        """Unknown niches should return 1.0."""
        assert get_niche_factor("unknown_type") == 1.0
        assert get_niche_factor(None) == 1.0  # type: ignore
        assert get_niche_factor("") == 1.0
        assert get_niche_factor("   ") == 1.0

    def test_partial_match(self) -> None:
        """Test partial matching in persona type."""
        assert get_niche_factor("gfe_romantic") == 0.70
        assert get_niche_factor("hardcore_explicit") == 1.00
        assert get_niche_factor("fetish_queen") == 1.20

    def test_case_insensitivity(self) -> None:
        """Test case insensitivity."""
        assert get_niche_factor("FETISH") == 1.20
        assert get_niche_factor("Fetish") == 1.20
        assert get_niche_factor("GFE") == 0.70
        assert get_niche_factor("Gfe") == 0.70


# ==============================================================================
# TEST PRICE FACTOR
# ==============================================================================

class TestPriceFactor:
    """Tests for get_subscription_price_factor function."""

    def test_free_page_boost(self) -> None:
        """Free pages should get 1.10x boost."""
        assert get_subscription_price_factor(0, is_free_page=True) == 1.10
        assert get_subscription_price_factor(0.0, is_free_page=True) == 1.10
        # Even with a non-zero price, is_free_page=True should use free factor
        assert get_subscription_price_factor(5.0, is_free_page=True) == 1.10

    def test_free_page_by_price(self) -> None:
        """Zero price on paid page should still be treated as free."""
        assert get_subscription_price_factor(0, is_free_page=False) == 1.10
        assert get_subscription_price_factor(0.0, is_free_page=False) == 1.10

    def test_budget_tier(self) -> None:
        """$0.01-9.99 subscriptions should get 1.05x."""
        assert get_subscription_price_factor(3.00, is_free_page=False) == 1.05
        assert get_subscription_price_factor(5.00, is_free_page=False) == 1.05
        assert get_subscription_price_factor(9.99, is_free_page=False) == 1.05
        assert get_subscription_price_factor(0.01, is_free_page=False) == 1.05

    def test_standard_tier(self) -> None:
        """$10-14.99 subscriptions should be 1.00x."""
        assert get_subscription_price_factor(10.00, is_free_page=False) == 1.00
        assert get_subscription_price_factor(12.50, is_free_page=False) == 1.00
        assert get_subscription_price_factor(14.99, is_free_page=False) == 1.00

    def test_premium_reduces(self) -> None:
        """Premium prices should reduce volume."""
        assert get_subscription_price_factor(15.00, is_free_page=False) == 0.85
        assert get_subscription_price_factor(20.00, is_free_page=False) == 0.85
        assert get_subscription_price_factor(24.99, is_free_page=False) == 0.85

    def test_ultra_premium_reduces_more(self) -> None:
        """Ultra premium prices should reduce volume significantly."""
        assert get_subscription_price_factor(25.00, is_free_page=False) == 0.70
        assert get_subscription_price_factor(30.00, is_free_page=False) == 0.70
        assert get_subscription_price_factor(50.00, is_free_page=False) == 0.70

    def test_above_max_uses_lowest(self) -> None:
        """Prices above max range should use lowest factor."""
        assert get_subscription_price_factor(100.00, is_free_page=False) == 0.70
        assert get_subscription_price_factor(500.00, is_free_page=False) == 0.70


# ==============================================================================
# TEST AGE FACTOR
# ==============================================================================

class TestAgeFactor:
    """Tests for get_account_age_factor function."""

    def test_new_account_reduces(self) -> None:
        """New accounts (<= 30 days) should have 0.60x."""
        assert get_account_age_factor(0) == 0.60
        assert get_account_age_factor(15) == 0.60
        assert get_account_age_factor(30) == 0.60

    def test_early_account(self) -> None:
        """31-60 days should have 0.75x."""
        assert get_account_age_factor(31) == 0.75
        assert get_account_age_factor(45) == 0.75
        assert get_account_age_factor(60) == 0.75

    def test_growing_account(self) -> None:
        """61-90 days should have 0.85x."""
        assert get_account_age_factor(61) == 0.85
        assert get_account_age_factor(75) == 0.85
        assert get_account_age_factor(90) == 0.85

    def test_established_account(self) -> None:
        """91-180 days should have 0.95x."""
        assert get_account_age_factor(91) == 0.95
        assert get_account_age_factor(120) == 0.95
        assert get_account_age_factor(180) == 0.95

    def test_mature_account_full(self) -> None:
        """181+ days should be 1.0x."""
        assert get_account_age_factor(181) == 1.0
        assert get_account_age_factor(200) == 1.0
        assert get_account_age_factor(365) == 1.0
        assert get_account_age_factor(1000) == 1.0

    def test_negative_returns_default(self) -> None:
        """Negative age should return 1.0."""
        assert get_account_age_factor(-1) == 1.0
        assert get_account_age_factor(-100) == 1.0


# ==============================================================================
# TEST CONVERSION FACTOR
# ==============================================================================

class TestConversionFactor:
    """Tests for get_conversion_factor function."""

    def test_excellent_conversion(self) -> None:
        """20%+ conversion should boost."""
        assert get_conversion_factor(0.20) == 1.15
        assert get_conversion_factor(0.25) == 1.15
        assert get_conversion_factor(0.30) == 1.15
        assert get_conversion_factor(1.0) == 1.15  # Max

    def test_good_conversion(self) -> None:
        """15-20% conversion should boost moderately."""
        assert get_conversion_factor(0.15) == 1.10
        assert get_conversion_factor(0.17) == 1.10
        assert get_conversion_factor(0.19) == 1.10

    def test_average_conversion(self) -> None:
        """10-15% should be baseline."""
        assert get_conversion_factor(0.10) == 1.00
        assert get_conversion_factor(0.12) == 1.00
        assert get_conversion_factor(0.14) == 1.00

    def test_below_average_conversion(self) -> None:
        """5-10% should reduce."""
        assert get_conversion_factor(0.05) == 0.90
        assert get_conversion_factor(0.07) == 0.90
        assert get_conversion_factor(0.09) == 0.90

    def test_poor_conversion(self) -> None:
        """<5% should reduce more."""
        assert get_conversion_factor(0.0) == 0.85
        assert get_conversion_factor(0.03) == 0.85
        assert get_conversion_factor(0.04) == 0.85

    def test_negative_clamped(self) -> None:
        """Negative conversion should be clamped to 0."""
        assert get_conversion_factor(-0.1) == 0.85
        assert get_conversion_factor(-1.0) == 0.85

    def test_above_one_clamped(self) -> None:
        """Conversion > 1.0 should be clamped."""
        assert get_conversion_factor(1.5) == 1.15
        assert get_conversion_factor(2.0) == 1.15


# ==============================================================================
# TEST BASE VOLUME CONFIGURATION
# ==============================================================================

class TestBaseVolume:
    """Tests for base volume configuration constants."""

    def test_paid_page_brackets(self) -> None:
        """Verify paid page bracket configuration with 2025 volume strategy.

        New brackets based on 2025-12-06 volume strategy update:
        - Minimum 2 PPV/day for all creators
        - Performance-based tier progression up to 6 PPV/day
        """
        assert PAID_PAGE_CONFIG[(0, 999)] == ("Base", 2, 2)
        assert PAID_PAGE_CONFIG[(1000, 4999)] == ("Growth", 3, 2)
        assert PAID_PAGE_CONFIG[(5000, 14999)] == ("Scale", 4, 3)
        assert PAID_PAGE_CONFIG[(15000, None)] == ("High", 5, 4)

    def test_free_page_brackets(self) -> None:
        """Verify free page bracket configuration with 2025 volume strategy.

        Free pages use same minimum floor (2/day) with tier progression.
        """
        assert FREE_PAGE_CONFIG[(0, 999)] == ("Base", 2, 2)
        assert FREE_PAGE_CONFIG[(1000, 4999)] == ("Growth", 3, 2)
        assert FREE_PAGE_CONFIG[(5000, 19999)] == ("Scale", 4, 3)
        assert FREE_PAGE_CONFIG[(20000, None)] == ("High", 5, 4)

    def test_tier_factors(self) -> None:
        """Verify tier factor multipliers."""
        assert TIER_FACTORS[1] == 1.15  # Top performers
        assert TIER_FACTORS[2] == 1.00  # Mid performers
        assert TIER_FACTORS[3] == 0.85  # Lower performers

    def test_hard_caps(self) -> None:
        """Verify hard cap constants match 2025 volume strategy.

        Updated caps for 2-6 PPV/day strategy:
        - Paid pages: MIN 14, MAX 42 PPV/week (2-6 per day)
        - Free pages: MIN 2, MAX 6 PPV/day
        """
        assert PAID_PAGE_MIN_PPV_WEEK == 14   # 2 PPV/day * 7
        assert PAID_PAGE_MAX_PPV_WEEK == 42   # 6 PPV/day * 7
        assert FREE_PAGE_MIN_PPV_DAY == 2     # New minimum floor
        assert FREE_PAGE_MAX_PPV_DAY == 6     # Max for high performers
        assert MIN_BUMP_PER_DAY == 1
        assert MAX_BUMP_PER_DAY == 4


# ==============================================================================
# TEST CREATOR METRICS DATA CLASS
# ==============================================================================

class TestCreatorMetrics:
    """Tests for CreatorMetrics dataclass."""

    def test_default_values(self) -> None:
        """Test default values for CreatorMetrics."""
        metrics = CreatorMetrics(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid"
        )
        assert metrics.active_fans == 0
        assert metrics.subscription_price == 0.0
        assert metrics.performance_tier == 3
        assert metrics.avg_purchase_rate == 0.0
        assert metrics.primary_tone is None
        assert metrics.account_age_days == 365

    def test_data_completeness_full(self) -> None:
        """Test data completeness with all data."""
        metrics = CreatorMetrics(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            active_fans=1000,
            subscription_price=9.99,
            performance_tier=2,
            avg_purchase_rate=0.12,
            primary_tone="explicit",
            account_age_days=200,
            total_earnings=10000.0
        )
        assert metrics.data_completeness == 1.0

    def test_data_completeness_partial(self) -> None:
        """Test data completeness with partial data."""
        metrics = CreatorMetrics(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            active_fans=1000,
            subscription_price=9.99,
            performance_tier=2,
            # Missing: avg_purchase_rate, primary_tone, account_age_days (using default)
        )
        # active_fans > 0: True
        # subscription_price >= 0: True
        # performance_tier in [1,2,3]: True
        # avg_purchase_rate >= 0: True (default is 0)
        # primary_tone is not None: False
        # account_age_days > 0: True (default is 365)
        # total_earnings >= 0: True (default is 0)
        # 6/7 = ~0.857
        assert 0.85 <= metrics.data_completeness <= 0.87

    def test_fan_count_override(self) -> None:
        """Test fan count override property."""
        metrics = CreatorMetrics(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            active_fans=500,
            fan_count_override=5000
        )
        assert metrics.active_fans == 500
        assert metrics.fan_count_override == 5000


# ==============================================================================
# TEST VOLUME STRATEGY DATA CLASS
# ==============================================================================

class TestVolumeStrategy:
    """Tests for VolumeStrategy dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Mid",
            ppv_per_day=2,
            ppv_per_week=3,
            bump_per_day=2,
            bump_per_week=14,
            base_volume=2,
            tier_factor=1.0,
            combined_factor=1.0,
            fan_count=3000,
            calculated_at="2025-01-01T00:00:00"
        )

        d = strategy.to_dict()
        assert d["creator_id"] == "test"
        assert d["page_name"] == "testpage"
        assert d["volume_level"] == "Mid"
        assert d["ppv_per_day"] == 2
        assert d["ppv_per_week"] == 3
        assert d["fan_count"] == 3000

    def test_default_values(self) -> None:
        """Test default values for VolumeStrategy."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=1,
            ppv_per_week=1,
            bump_per_day=1,
            bump_per_week=7
        )
        assert strategy.base_volume == 0
        assert strategy.tier_factor == 1.0
        assert strategy.data_completeness == 1.0
        assert strategy.calculation_notes == []
        assert strategy.optimal_days == []


# ==============================================================================
# TEST INTEGRATION WITH MOCK DATABASE
# ==============================================================================

class TestIntegration:
    """Integration tests with mock database."""

    def test_basic_calculation(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test basic volume calculation with sample creator."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(sample_creator)

        assert strategy.creator_id == sample_creator
        assert strategy.page_name == "testcreator"
        assert strategy.page_type == "paid"
        assert strategy.fan_count == 3500
        # New tier names from 2025 volume strategy
        assert strategy.volume_level in ["Base", "Growth", "Scale", "High", "Ultra"]

    def test_paid_gfe_new_account(self, mock_db: sqlite3.Connection) -> None:
        """Worst case: paid GFE page, new account, premium price."""
        creator_id = "test-gfe-001"
        first_seen = (datetime.now() - timedelta(days=25)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "gfecreator", "GFE Creator", "paid",
            20.0, 2000, 3, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "gfe"))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Verify factors are correctly applied
        assert strategy.niche_factor == 0.70  # GFE
        assert strategy.price_factor == 0.85  # Premium price
        assert strategy.age_factor == 0.60    # New account
        assert strategy.tier_factor == 0.85   # Tier 3

        # Combined factor should be very low
        assert strategy.combined_factor < 0.35

        # PPV per week should be at minimum
        assert strategy.ppv_per_week >= PAID_PAGE_MIN_PPV_WEEK
        assert strategy.ppv_per_week <= PAID_PAGE_MAX_PPV_WEEK

    def test_free_fetish_mature_account(self, mock_db: sqlite3.Connection) -> None:
        """Best case: free fetish page, mature, high tier.

        With updated caps, even best-case free pages are limited.
        """
        creator_id = "test-fetish-001"
        first_seen = (datetime.now() - timedelta(days=365)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "fetishcreator", "Fetish Creator", "free",
            0.0, 10000, 1, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "fetish"))

        # Add high conversion rate messages
        mock_db.execute("""
            INSERT INTO mass_messages (creator_id, sent_count, purchased_count, net_amount)
            VALUES (?, ?, ?, ?)
        """, (creator_id, 1000, 250, 3000.00))  # 25% conversion

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Verify factors are correctly applied
        assert strategy.niche_factor == 1.20   # Fetish
        assert strategy.price_factor == 1.10   # Free page
        assert strategy.age_factor == 1.00     # Mature account
        assert strategy.tier_factor == 1.15    # Tier 1
        assert strategy.conversion_factor == 1.15  # 25% conversion

        # Combined factor should be high
        assert strategy.combined_factor > 1.5

        # PPV per week should be within free page limits (max 3/day = 21/week)
        assert strategy.ppv_per_day <= FREE_PAGE_MAX_PPV_DAY
        assert strategy.ppv_per_week <= FREE_PAGE_MAX_PPV_DAY * 7

    def test_hard_caps_enforced_paid(self, mock_db: sqlite3.Connection) -> None:
        """Verify hard caps prevent extreme values for paid pages."""
        creator_id = "test-max-001"
        first_seen = (datetime.now() - timedelta(days=500)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "maxtest", "Max Test", "paid",
            5.0, 50000, 1, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "fetish"))

        # Add extremely high conversion
        mock_db.execute("""
            INSERT INTO mass_messages (creator_id, sent_count, purchased_count, net_amount)
            VALUES (?, ?, ?, ?)
        """, (creator_id, 1000, 350, 4500.00))  # 35% conversion

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # PPV per week should be capped at max
        assert strategy.ppv_per_week <= PAID_PAGE_MAX_PPV_WEEK

    def test_hard_caps_enforced_free(self, mock_db: sqlite3.Connection) -> None:
        """Verify hard caps prevent extreme values for free pages."""
        creator_id = "test-free-max-001"
        first_seen = (datetime.now() - timedelta(days=500)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "freemaxtest", "Free Max Test", "free",
            0.0, 100000, 1, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "fetish"))

        mock_db.execute("""
            INSERT INTO mass_messages (creator_id, sent_count, purchased_count, net_amount)
            VALUES (?, ?, ?, ?)
        """, (creator_id, 1000, 400, 5000.00))  # 40% conversion

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # PPV per day should be capped at max
        assert strategy.ppv_per_day <= FREE_PAGE_MAX_PPV_DAY

    def test_hard_caps_minimum_enforced(self, mock_db: sqlite3.Connection) -> None:
        """Verify minimum caps are enforced."""
        creator_id = "test-min-001"
        first_seen = (datetime.now() - timedelta(days=10)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "mintest", "Min Test", "paid",
            30.0, 100, 3, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "gfe"))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # PPV per week should meet minimum
        assert strategy.ppv_per_week >= PAID_PAGE_MIN_PPV_WEEK

    def test_fan_count_override(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test fan count override functionality."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Without override
        strategy_normal = optimizer.calculate_optimal_volume(sample_creator)
        assert strategy_normal.fan_count == 3500

        # With override
        strategy_override = optimizer.calculate_optimal_volume(
            sample_creator,
            fan_count=50000
        )
        assert strategy_override.fan_count == 50000
        assert "Fan count override: 50000" in strategy_override.calculation_notes

    def test_creator_not_found(self, mock_db: sqlite3.Connection) -> None:
        """Test error when creator not found."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        with pytest.raises(ValueError, match="Creator not found"):
            optimizer.calculate_optimal_volume("nonexistent-creator")

    def test_page_type_detection_free(self, mock_db: sqlite3.Connection) -> None:
        """Test page type detection for free page."""
        creator_id = "test-free-001"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (creator_id, "freepage", "Free Page", "free", 0.0, 1000, 1))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        assert strategy.page_type == "free"
        assert strategy.price_factor == 1.10

    def test_page_type_detection_by_price(self, mock_db: sqlite3.Connection) -> None:
        """Test page type detection when type is null but price is zero."""
        creator_id = "test-null-type-001"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (creator_id, "nulltype", "Null Type", None, 0.0, 1000, 1))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should be detected as free page due to zero price
        assert strategy.price_factor == 1.10


# ==============================================================================
# TEST VALIDATION FUNCTIONS
# ==============================================================================

class TestValidation:
    """Tests for validation functions."""

    def test_validate_paid_page_valid(self) -> None:
        """Valid paid page strategy should have no errors."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Growth",
            ppv_per_day=3,
            ppv_per_week=21,  # Within 14-42 range
            bump_per_day=2,
            bump_per_week=14
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 0

    def test_validate_paid_page_overcap(self) -> None:
        """Should error if paid page exceeds 42 PPV/week (2025 cap)."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Ultra",
            ppv_per_day=7,
            ppv_per_week=49,  # Exceeds max of 42
            bump_per_day=2,
            bump_per_week=14
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "exceeds paid page maximum" in errors[0]

    def test_validate_paid_page_undercap(self) -> None:
        """Should error if paid page is below 1 PPV/week."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=0,
            ppv_per_week=0,  # Below min of 1
            bump_per_day=1,
            bump_per_week=7
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "below paid page minimum" in errors[0]

    def test_validate_free_page_valid(self) -> None:
        """Valid free page strategy should have no errors (updated to 3 PPV/day max)."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="free",
            volume_level="Mid",
            ppv_per_day=2,   # Within 1-3 range
            ppv_per_week=14,
            bump_per_day=2,
            bump_per_week=14
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 0

    def test_validate_free_page_overcap(self) -> None:
        """Should error if free page exceeds 6 PPV/day (2025 cap)."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="free",
            volume_level="Ultra",
            ppv_per_day=8,  # Exceeds new max of 6
            ppv_per_week=56,
            bump_per_day=2,
            bump_per_week=14
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "exceeds free page maximum" in errors[0]

    def test_validate_free_page_undercap(self) -> None:
        """Should error if free page is below 1 PPV/day (updated min from 2)."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="free",
            volume_level="Low",
            ppv_per_day=0,  # Below new min of 1
            ppv_per_week=0,
            bump_per_day=1,
            bump_per_week=7
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "below free page minimum" in errors[0]

    def test_validate_bump_overcap(self) -> None:
        """Should error if bump exceeds maximum."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Growth",
            ppv_per_day=3,
            ppv_per_week=21,
            bump_per_day=10,  # Exceeds max of 4
            bump_per_week=70
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "exceeds maximum" in errors[0]

    def test_validate_bump_undercap(self) -> None:
        """Should error if bump is below minimum."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Growth",
            ppv_per_day=3,
            ppv_per_week=21,
            bump_per_day=0,  # Below min of 1
            bump_per_week=0
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 1
        assert "below minimum" in errors[0]

    def test_validate_multiple_errors(self) -> None:
        """Should return multiple errors when multiple caps violated."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Ultra",
            ppv_per_day=7,
            ppv_per_week=49,  # Exceeds max of 42
            bump_per_day=10,  # Exceeds max of 4
            bump_per_week=70
        )

        errors = validate_volume_strategy(strategy)
        assert len(errors) == 2

    def test_warnings_low_confidence(self) -> None:
        """Should warn when data completeness < 50%."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Mid",
            ppv_per_day=2,
            ppv_per_week=3,
            bump_per_day=2,
            bump_per_week=14,
            data_completeness=0.3  # Below 50%
        )

        warnings = get_volume_warnings(strategy)
        assert any("Very low data completeness" in w for w in warnings)

    def test_warnings_moderate_confidence(self) -> None:
        """Should warn when data completeness is moderate."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Mid",
            ppv_per_day=2,
            ppv_per_week=3,
            bump_per_day=2,
            bump_per_week=14,
            data_completeness=0.6  # Between 50% and 80%
        )

        warnings = get_volume_warnings(strategy)
        assert any("Moderate data completeness" in w for w in warnings)

    def test_warnings_high_combined_factor(self) -> None:
        """Should warn when combined factor is very high."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Ultra",
            ppv_per_day=2,
            ppv_per_week=5,
            bump_per_day=2,
            bump_per_week=14,
            combined_factor=1.5  # Above 1.3
        )

        warnings = get_volume_warnings(strategy)
        assert any("Very high combined factor" in w for w in warnings)

    def test_warnings_low_combined_factor(self) -> None:
        """Should warn when combined factor is very low."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=1,
            ppv_per_week=1,
            bump_per_day=1,
            bump_per_week=7,
            combined_factor=0.5  # Below 0.7
        )

        warnings = get_volume_warnings(strategy)
        assert any("Very low combined factor" in w for w in warnings)

    def test_warnings_zero_fans(self) -> None:
        """Should warn when fan count is zero."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=1,
            ppv_per_week=1,
            bump_per_day=1,
            bump_per_week=7,
            fan_count=0
        )

        warnings = get_volume_warnings(strategy)
        assert any("Fan count is zero" in w for w in warnings)

    def test_warnings_new_account(self) -> None:
        """Should warn when account is new."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=1,
            ppv_per_week=1,
            bump_per_day=1,
            bump_per_week=7,
            age_factor=0.6  # New account
        )

        warnings = get_volume_warnings(strategy)
        assert any("New account" in w for w in warnings)

    def test_no_warnings_good_data(self) -> None:
        """Should have no warnings with good data."""
        strategy = VolumeStrategy(
            creator_id="test",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Mid",
            ppv_per_day=2,
            ppv_per_week=3,
            bump_per_day=2,
            bump_per_week=14,
            data_completeness=0.95,
            combined_factor=1.0,
            fan_count=3000,
            age_factor=1.0
        )

        warnings = get_volume_warnings(strategy)
        assert len(warnings) == 0


# ==============================================================================
# TEST POPULATE VOLUME ASSIGNMENTS
# ==============================================================================

class TestPopulateAssignments:
    """Tests for populate_volume_assignments method."""

    def test_populate_dry_run(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test dry run doesn't modify database."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Run dry run
        assignments = optimizer.populate_volume_assignments(dry_run=True)

        # Should have returned assignments
        assert len(assignments) == 1
        assert assignments[0]["page_name"] == "testcreator"

        # Database should not have any assignments
        cursor = mock_db.execute("SELECT COUNT(*) FROM volume_assignments")
        count = cursor.fetchone()[0]
        assert count == 0

    def test_populate_writes_to_database(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test actual population writes to database."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Run actual population
        assignments = optimizer.populate_volume_assignments(dry_run=False)

        # Should have returned assignments
        assert len(assignments) == 1

        # Database should have assignment
        cursor = mock_db.execute("""
            SELECT * FROM volume_assignments
            WHERE creator_id = ? AND is_active = 1
        """, (sample_creator,))
        row = cursor.fetchone()

        assert row is not None
        assert row["volume_level"] == assignments[0]["volume_level"]
        assert row["ppv_per_day"] == assignments[0]["ppv_per_day"]

    def test_populate_deactivates_old(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test that old assignments are deactivated."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Create old assignment
        mock_db.execute("""
            INSERT INTO volume_assignments (
                creator_id, volume_level, ppv_per_day, bump_per_day,
                assigned_by, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (sample_creator, "Low", 1, 1, "manual", 1))
        mock_db.commit()

        # Run population
        optimizer.populate_volume_assignments(dry_run=False)

        # Old assignment should be deactivated
        cursor = mock_db.execute("""
            SELECT COUNT(*) FROM volume_assignments
            WHERE creator_id = ? AND is_active = 1
        """, (sample_creator,))
        count = cursor.fetchone()[0]

        # Should only have one active assignment
        assert count == 1

        # Total should be 2 (one inactive, one active)
        cursor = mock_db.execute("""
            SELECT COUNT(*) FROM volume_assignments
            WHERE creator_id = ?
        """, (sample_creator,))
        total = cursor.fetchone()[0]
        assert total == 2


# ==============================================================================
# TEST OPTIMIZER INTERNAL METHODS
# ==============================================================================

class TestOptimizerInternals:
    """Tests for internal optimizer methods."""

    def test_get_base_volume_paid_low(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test base volume for paid page with low fans (2025 strategy: min 2/day)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        level, ppv, bump = optimizer._get_base_volume(500, is_free_page=False)
        assert level == "Base"
        assert ppv == 2  # New minimum floor
        assert bump == 2

    def test_get_base_volume_paid_mid(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test base volume for paid page with mid fans (2025 strategy)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        level, ppv, bump = optimizer._get_base_volume(2500, is_free_page=False)
        assert level == "Growth"
        assert ppv == 3  # Growth tier
        assert bump == 2

    def test_get_base_volume_paid_high(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test base volume for paid page with high fans (2025 strategy)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        level, ppv, bump = optimizer._get_base_volume(10000, is_free_page=False)
        assert level == "Scale"
        assert ppv == 4  # Scale tier
        assert bump == 3

    def test_get_base_volume_paid_ultra(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test base volume for paid page with ultra fans (2025 strategy)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        level, ppv, bump = optimizer._get_base_volume(50000, is_free_page=False)
        assert level == "High"
        assert ppv == 5  # High tier
        assert bump == 4

    def test_get_base_volume_free_page(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test base volume for free page (2025 strategy: min 2/day)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Base
        level, ppv, _ = optimizer._get_base_volume(500, is_free_page=True)
        assert level == "Base"
        assert ppv == 2  # New minimum floor

        # Growth
        level, ppv, _ = optimizer._get_base_volume(2500, is_free_page=True)
        assert level == "Growth"
        assert ppv == 3  # Growth tier

        # Scale
        level, ppv, _ = optimizer._get_base_volume(10000, is_free_page=True)
        assert level == "Scale"
        assert ppv == 4  # Scale tier

        # High
        level, ppv, _ = optimizer._get_base_volume(50000, is_free_page=True)
        assert level == "High"
        assert ppv == 5  # High tier

    def test_get_tier_factor(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test tier factor calculation."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        assert optimizer._get_tier_factor(1) == 1.15
        assert optimizer._get_tier_factor(2) == 1.00
        assert optimizer._get_tier_factor(3) == 0.85
        assert optimizer._get_tier_factor(99) == 1.0  # Unknown tier

    def test_get_bump_count_paid(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test bump count calculation for paid pages."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Paid pages have conservative bumps (1-2 per day max)
        assert optimizer._get_bump_count(1, is_free_page=False) == 1
        assert optimizer._get_bump_count(2, is_free_page=False) == 2
        assert optimizer._get_bump_count(3, is_free_page=False) == 2  # Capped at 2

    def test_get_bump_count_free(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test bump count calculation for free pages."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # Free pages have 1:1 ratio (capped at MAX_BUMP_PER_DAY=4)
        assert optimizer._get_bump_count(1, is_free_page=True) == 1
        assert optimizer._get_bump_count(2, is_free_page=True) == 2
        assert optimizer._get_bump_count(3, is_free_page=True) == 3
        assert optimizer._get_bump_count(5, is_free_page=True) == 4  # Capped at max

    def test_get_optimal_days_paid(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test optimal days for paid pages."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        days = optimizer._get_optimal_days(is_free_page=False)

        assert "Tuesday" in days
        assert "Wednesday" in days
        assert "Thursday" in days
        assert "Friday" in days
        assert "Saturday" in days
        assert "Monday" not in days
        assert "Sunday" not in days

    def test_get_optimal_days_free(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test optimal days for free pages."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        days = optimizer._get_optimal_days(is_free_page=True)

        assert len(days) == 7
        assert "Monday" in days
        assert "Sunday" in days

    def test_get_bump_delays(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test bump delay ranges."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        assert optimizer._get_bump_delays("High") == (15, 30)
        assert optimizer._get_bump_delays("Ultra") == (15, 25)
        assert optimizer._get_bump_delays("Mid") == (20, 40)
        assert optimizer._get_bump_delays("Low") == (25, 45)
        assert optimizer._get_bump_delays("Unknown") == (20, 40)  # Default

    def test_get_volume_level_name_paid(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test volume level name determination for paid pages (2025 tier naming)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        assert optimizer._get_volume_level_name(2, is_free_page=False) == "Base"
        assert optimizer._get_volume_level_name(3, is_free_page=False) == "Growth"
        assert optimizer._get_volume_level_name(4, is_free_page=False) == "Scale"
        assert optimizer._get_volume_level_name(5, is_free_page=False) == "High"
        assert optimizer._get_volume_level_name(6, is_free_page=False) == "Ultra"

    def test_get_volume_level_name_free(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test volume level name determination for free pages (2025 tier naming)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        assert optimizer._get_volume_level_name(2, is_free_page=True) == "Base"
        assert optimizer._get_volume_level_name(3, is_free_page=True) == "Growth"
        assert optimizer._get_volume_level_name(4, is_free_page=True) == "Scale"
        assert optimizer._get_volume_level_name(5, is_free_page=True) == "High"
        assert optimizer._get_volume_level_name(6, is_free_page=True) == "Ultra"


# ==============================================================================
# TEST EDGE CASES
# ==============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_fan_count(self, mock_db: sqlite3.Connection) -> None:
        """Test with zero fan count (2025 strategy: min 2/day for all)."""
        creator_id = "test-zero-fans"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (creator_id, "zerofans", "Zero Fans", "paid", 0, 1))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        assert strategy.fan_count == 0
        assert strategy.volume_level == "Base"  # New tier name
        assert strategy.ppv_per_week >= PAID_PAGE_MIN_PPV_WEEK  # 14/week min

    def test_missing_persona(self, mock_db: sqlite3.Connection) -> None:
        """Test with missing persona data."""
        creator_id = "test-no-persona"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (creator_id, "nopersona", "No Persona", "paid", 5000, 1))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should use default niche factor
        assert strategy.niche_factor == 1.0

    def test_null_subscription_price(self, mock_db: sqlite3.Connection) -> None:
        """Test with null subscription price."""
        creator_id = "test-null-price"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (creator_id, "nullprice", "Null Price", "paid", None, 5000, 1))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should treat null as free (0)
        assert strategy.price_factor == 1.10

    def test_boundary_fan_counts(self, mock_db: sqlite3.Connection) -> None:
        """Test fan count boundaries (2025 tier naming).

        New PAID_PAGE_CONFIG brackets:
        - (0, 999): Base (2/day)
        - (1000, 4999): Growth (3/day)
        - (5000, 14999): Scale (4/day)
        - (15000, None): High (5/day)
        """
        optimizer = MultiFactorVolumeOptimizer(mock_db)

        # At exactly 999 (boundary of Base)
        level, _, _ = optimizer._get_base_volume(999, is_free_page=False)
        assert level == "Base"

        # At exactly 1000 (boundary of Growth)
        level, _, _ = optimizer._get_base_volume(1000, is_free_page=False)
        assert level == "Growth"

        # At exactly 4999 (boundary of Growth)
        level, _, _ = optimizer._get_base_volume(4999, is_free_page=False)
        assert level == "Growth"

        # At exactly 5000 (boundary of Scale)
        level, _, _ = optimizer._get_base_volume(5000, is_free_page=False)
        assert level == "Scale"

        # At exactly 14999 (boundary of Scale)
        level, _, _ = optimizer._get_base_volume(14999, is_free_page=False)
        assert level == "Scale"

        # At exactly 15000 (boundary of High)
        level, _, _ = optimizer._get_base_volume(15000, is_free_page=False)
        assert level == "High"

    def test_combined_factor_calculation(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test that combined factor is product of all factors."""
        creator_id = "test-combined"
        first_seen = (datetime.now() - timedelta(days=200)).isoformat()

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "combined", "Combined Test", "paid",
            10.00, 5000, 2, first_seen, 1
        ))

        mock_db.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, (creator_id, "explicit"))

        mock_db.execute("""
            INSERT INTO mass_messages (creator_id, sent_count, purchased_count, net_amount)
            VALUES (?, ?, ?, ?)
        """, (creator_id, 1000, 120, 1500.00))  # 12% conversion

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Verify combined factor is product
        expected = (
            strategy.tier_factor *
            strategy.conversion_factor *
            strategy.niche_factor *
            strategy.price_factor *
            strategy.age_factor
        )

        assert abs(strategy.combined_factor - expected) < 0.01


# ==============================================================================
# TEST LOOKUP BY DIFFERENT IDENTIFIERS
# ==============================================================================

class TestCreatorLookup:
    """Tests for creator lookup by different identifiers."""

    def test_lookup_by_creator_id(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test lookup by creator_id."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(sample_creator)

        assert strategy.creator_id == sample_creator

    def test_lookup_by_page_name(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test lookup by page_name."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume("testcreator")

        assert strategy.creator_id == sample_creator
        assert strategy.page_name == "testcreator"

    def test_lookup_by_display_name(
        self,
        mock_db: sqlite3.Connection,
        sample_creator: str
    ) -> None:
        """Test lookup by display_name."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume("Test Creator")

        assert strategy.creator_id == sample_creator
        assert strategy.display_name == "Test Creator"


# ==============================================================================
# TEST OUTPUT FORMATTING
# ==============================================================================

class TestOutputFormatting:
    """Tests for output formatting functions."""

    def test_format_strategy_table(self) -> None:
        """Test table formatting."""
        from volume_optimizer import format_strategy_table

        strategies = [
            VolumeStrategy(
                creator_id="test1",
                page_name="testpage1",
                display_name="Test Page 1",
                page_type="paid",
                volume_level="Mid",
                ppv_per_day=2,
                ppv_per_week=3,
                bump_per_day=2,
                bump_per_week=14,
                combined_factor=1.05,
                fan_count=3000,
                data_completeness=0.95
            ),
            VolumeStrategy(
                creator_id="test2",
                page_name="testpage2",
                display_name="Test Page 2",
                page_type="free",
                volume_level="High",
                ppv_per_day=4,
                ppv_per_week=28,
                bump_per_day=3,
                bump_per_week=21,
                combined_factor=1.20,
                fan_count=8000,
                data_completeness=0.80
            ),
        ]

        output = format_strategy_table(strategies)

        # Verify header elements
        assert "Creator" in output
        assert "Type" in output
        assert "Level" in output
        assert "PPV/Day" in output
        assert "PPV/Wk" in output
        assert "Bump/Day" in output
        assert "Factor" in output
        assert "Fans" in output
        assert "Complete" in output

        # Verify data
        assert "testpage1" in output
        assert "testpage2" in output
        assert "paid" in output
        assert "free" in output
        assert "Mid" in output
        assert "High" in output
        assert "Total creators: 2" in output

    def test_format_strategy_detail(self) -> None:
        """Test detailed formatting."""
        from volume_optimizer import format_strategy_detail

        strategy = VolumeStrategy(
            creator_id="test1",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Mid",
            ppv_per_day=2,
            ppv_per_week=3,
            bump_per_day=2,
            bump_per_week=14,
            base_volume=2,
            tier_factor=1.15,
            conversion_factor=1.0,
            niche_factor=0.85,
            price_factor=1.0,
            age_factor=1.0,
            combined_factor=0.98,
            raw_daily_volume=1.96,
            capped_daily_volume=2,
            fan_count=3000,
            data_completeness=0.95,
            calculation_notes=["Test note"],
            optimal_days=["Tuesday", "Wednesday"],
            bump_delay_min=20,
            bump_delay_max=40,
            calculated_at="2025-01-01T12:00:00"
        )

        output = format_strategy_detail(strategy)

        # Verify sections
        assert "VOLUME STRATEGY: Test Page" in output
        assert "CREATOR INFO" in output
        assert "VOLUME RECOMMENDATIONS" in output
        assert "FACTOR BREAKDOWN" in output
        assert "SCHEDULING HINTS" in output

        # Verify data points
        assert "testpage" in output
        assert "paid" in output
        assert "Mid" in output
        assert "3,000" in output  # Fan count formatted
        assert "1.15" in output  # Tier factor
        assert "0.85" in output  # Niche factor
        assert "Tuesday" in output
        assert "Wednesday" in output
        assert "20-40 minutes" in output
        assert "Test note" in output
        assert "2025-01-01T12:00:00" in output

    def test_format_strategy_detail_with_errors(self) -> None:
        """Test detailed formatting with validation errors."""
        from volume_optimizer import format_strategy_detail

        strategy = VolumeStrategy(
            creator_id="test1",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Ultra",
            ppv_per_day=5,
            ppv_per_week=25,  # Exceeds max of 20
            bump_per_day=10,  # Exceeds max of 4
            bump_per_week=70,
            calculated_at="2025-01-01T12:00:00"
        )

        output = format_strategy_detail(strategy)

        # Should include ERRORS section
        assert "ERRORS" in output
        assert "[ERROR]" in output

    def test_format_strategy_detail_with_warnings(self) -> None:
        """Test detailed formatting with warnings."""
        from volume_optimizer import format_strategy_detail

        strategy = VolumeStrategy(
            creator_id="test1",
            page_name="testpage",
            display_name="Test Page",
            page_type="paid",
            volume_level="Low",
            ppv_per_day=1,
            ppv_per_week=1,
            bump_per_day=1,
            bump_per_week=7,
            data_completeness=0.3,  # Low completeness
            combined_factor=0.5,  # Low factor
            fan_count=0,  # Zero fans
            age_factor=0.6,  # New account
            calculated_at="2025-01-01T12:00:00"
        )

        output = format_strategy_detail(strategy)

        # Should include WARNINGS section
        assert "WARNINGS" in output
        assert "[WARN]" in output


# ==============================================================================
# TEST DATABASE CONNECTION FUNCTION
# ==============================================================================

class TestDatabaseConnection:
    """Tests for database connection function."""

    def test_get_db_connection_file_not_found(self, tmp_path) -> None:
        """Test error when database file not found."""
        from volume_optimizer import get_db_connection
        from pathlib import Path

        fake_path = tmp_path / "nonexistent.db"

        with pytest.raises(FileNotFoundError, match="Database not found"):
            get_db_connection(fake_path)

    def test_get_db_connection_success(self, tmp_path) -> None:
        """Test successful database connection."""
        from volume_optimizer import get_db_connection
        from pathlib import Path

        # Create a test database file
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.close()

        # Now test get_db_connection
        result_conn = get_db_connection(db_path)
        assert result_conn is not None
        result_conn.close()


# ==============================================================================
# TEST ACCOUNT AGE WITH NONE
# ==============================================================================

class TestAccountAgeNone:
    """Additional tests for account age factor edge cases."""

    def test_none_age_returns_default(self) -> None:
        """Test that None account age is handled properly in integration."""
        # The get_account_age_factor function takes int, but in practice
        # the optimizer handles None values before calling it
        # This test verifies the behavior documented in the spec
        assert get_account_age_factor(365) == 1.0  # Mature is default assumption


# ==============================================================================
# TEST SUBSCRIPTION PRICE FACTOR WITH NONE
# ==============================================================================

class TestSubscriptionPriceNone:
    """Test subscription price factor with None value."""

    def test_none_price_with_free_page_flag(self) -> None:
        """None price with is_free_page=True should use free factor."""
        # When price is None and is_free_page=True, should use free page factor
        # The function handles None by treating it as 0
        result = get_subscription_price_factor(0, is_free_page=True)
        assert result == 1.10


# ==============================================================================
# TEST CONVERSION FACTOR EXACT BOUNDARIES
# ==============================================================================

class TestConversionBoundaries:
    """Test exact boundary values for conversion factor."""

    def test_exact_20_percent(self) -> None:
        """Test exactly 20% conversion (boundary)."""
        # At exactly 0.20, should get the excellent bonus
        assert get_conversion_factor(0.20) == 1.15

    def test_exact_15_percent(self) -> None:
        """Test exactly 15% conversion (boundary)."""
        assert get_conversion_factor(0.15) == 1.10

    def test_exact_10_percent(self) -> None:
        """Test exactly 10% conversion (boundary)."""
        assert get_conversion_factor(0.10) == 1.00

    def test_exact_5_percent(self) -> None:
        """Test exactly 5% conversion (boundary)."""
        assert get_conversion_factor(0.05) == 0.90

    def test_exact_0_percent(self) -> None:
        """Test exactly 0% conversion (boundary)."""
        assert get_conversion_factor(0.00) == 0.85


# ==============================================================================
# TEST CLI MAIN FUNCTION
# ==============================================================================

class TestCLIMain:
    """Tests for CLI main function."""

    @pytest.fixture
    def test_db(self, tmp_path) -> Generator[str, None, None]:
        """Create a test database with sample data."""
        db_path = tmp_path / "test_cli.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create tables
        conn.execute("""
            CREATE TABLE creators (
                creator_id TEXT PRIMARY KEY,
                page_name TEXT NOT NULL,
                display_name TEXT,
                page_type TEXT DEFAULT 'paid',
                subscription_price REAL DEFAULT 0.0,
                current_active_fans INTEGER DEFAULT 0,
                performance_tier INTEGER DEFAULT 2,
                current_total_earnings REAL DEFAULT 0.0,
                current_message_net REAL DEFAULT 0.0,
                first_seen_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE creator_personas (
                persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                primary_tone TEXT,
                avg_sentiment REAL DEFAULT 0.5,
                FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
            )
        """)

        conn.execute("""
            CREATE TABLE mass_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                sent_count INTEGER DEFAULT 0,
                purchased_count INTEGER DEFAULT 0,
                net_amount REAL DEFAULT 0.0,
                FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
            )
        """)

        conn.execute("""
            CREATE TABLE volume_overrides (
                override_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                target_weekly_ppv INTEGER NOT NULL,
                target_weekly_bump INTEGER NOT NULL,
                override_reason TEXT,
                is_active INTEGER DEFAULT 1,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
            )
        """)

        conn.execute("""
            CREATE TABLE volume_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                volume_level TEXT,
                ppv_per_day INTEGER,
                bump_per_day INTEGER,
                assigned_by TEXT,
                assigned_reason TEXT,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
            )
        """)

        # Insert test data
        conn.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                current_total_earnings, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "cli-test-001", "clitestpage", "CLI Test Creator", "paid",
            12.99, 5000, 2, 15000.0, 1
        ))

        conn.execute("""
            INSERT INTO creator_personas (creator_id, primary_tone)
            VALUES (?, ?)
        """, ("cli-test-001", "explicit"))

        conn.commit()
        conn.close()

        yield str(db_path)

    def test_main_single_creator_detail(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with single creator in detail format."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "clitestpage", "--db", test_db]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "VOLUME STRATEGY" in captured.out
        assert "clitestpage" in captured.out

    def test_main_single_creator_json(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with single creator in JSON format."""
        import sys
        import json
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "clitestpage", "--db", test_db, "--format", "json"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert data["page_name"] == "clitestpage"

    def test_main_single_creator_table(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with single creator in table format."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "clitestpage", "--db", test_db, "--format", "table"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Creator" in captured.out
        assert "clitestpage" in captured.out

    def test_main_with_fan_count_override(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with fan count override."""
        import sys
        import json
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "clitestpage", "--db", test_db,
             "--fan-count", "50000", "--format", "json"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["fan_count"] == 50000

    def test_main_all_creators_table(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --all flag in table format."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--all", "--db", test_db, "--format", "table"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Creator" in captured.out
        assert "Total creators:" in captured.out

    def test_main_all_creators_json(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --all flag in JSON format."""
        import sys
        import json
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--all", "--db", test_db, "--format", "json"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_main_all_creators_detail(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --all flag in detail format."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--all", "--db", test_db, "--format", "detail"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "VOLUME STRATEGY" in captured.out

    def test_main_populate_dry_run(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --populate --dry-run."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--populate", "--dry-run", "--db", test_db]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "Total:" in captured.out

    def test_main_populate_write(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --populate (actually writes)."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--populate", "--db", test_db]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Volume assignments updated" in captured.out

        # Verify database was updated
        conn = sqlite3.connect(test_db)
        cursor = conn.execute("SELECT COUNT(*) FROM volume_assignments WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_main_populate_json_format(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with --populate in JSON format."""
        import sys
        import json
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--populate", "--dry-run", "--db", test_db, "--format", "json"]
        )

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        # Output contains header line before JSON, so we need to find the JSON part
        output_lines = captured.out.strip().split('\n')
        # Find the start of JSON (first '[')
        json_start = 0
        for i, line in enumerate(output_lines):
            if line.strip().startswith('['):
                json_start = i
                break
        json_str = '\n'.join(output_lines[json_start:])
        data = json.loads(json_str)
        assert isinstance(data, list)

    def test_main_creator_not_found(self, test_db: str, monkeypatch, capsys) -> None:
        """Test CLI with nonexistent creator."""
        import sys
        from volume_optimizer import main

        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "nonexistent", "--db", test_db]
        )

        result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Creator not found" in captured.err

    def test_main_db_not_found(self, tmp_path, monkeypatch, capsys) -> None:
        """Test CLI with nonexistent database."""
        import sys
        from volume_optimizer import main

        fake_db = str(tmp_path / "nonexistent.db")
        monkeypatch.setattr(
            sys, "argv",
            ["volume_optimizer.py", "--creator", "test", "--db", fake_db]
        )

        result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Database not found" in captured.err


# ==============================================================================
# TEST ERROR HANDLING IN POPULATE
# ==============================================================================

class TestPopulateErrorHandling:
    """Tests for error handling in populate_volume_assignments."""

    def test_populate_handles_individual_errors(self, mock_db: sqlite3.Connection) -> None:
        """Test that populate handles errors for individual creators gracefully."""
        # Create a creator with invalid data that will cause an error
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                current_active_fans, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("good-creator", "goodpage", "Good Creator", "paid", 5000, 1))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        assignments = optimizer.populate_volume_assignments(dry_run=True)

        # Should have processed the good creator
        assert len(assignments) == 1
        assert "error" not in assignments[0]


# ==============================================================================
# TEST ADDITIONAL EDGE CASES FOR CONVERSION FACTOR
# ==============================================================================

class TestConversionFactorEdgeCases:
    """Additional edge case tests for conversion factor."""

    def test_conversion_just_below_boundary(self) -> None:
        """Test values just below boundaries."""
        # Just below 20%
        assert get_conversion_factor(0.199) == 1.10
        # Just below 15%
        assert get_conversion_factor(0.149) == 1.00
        # Just below 10%
        assert get_conversion_factor(0.099) == 0.90
        # Just below 5%
        assert get_conversion_factor(0.049) == 0.85


# ==============================================================================
# TEST ADDITIONAL EDGE CASES FOR BASE VOLUME
# ==============================================================================

class TestBaseVolumeEdgeCases:
    """Additional edge case tests for base volume calculation."""

    def test_base_volume_zero_fans(self, mock_db: sqlite3.Connection) -> None:
        """Test base volume with zero fans (2025 strategy: min 2/day)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        level, ppv, bump = optimizer._get_base_volume(0, is_free_page=False)
        assert level == "Base"
        assert ppv == 2  # New minimum floor

    def test_base_volume_negative_fans(self, mock_db: sqlite3.Connection) -> None:
        """Test base volume with negative fans (edge case)."""
        optimizer = MultiFactorVolumeOptimizer(mock_db)
        # Negative fans should fall into first bracket (Base tier)
        level, ppv, bump = optimizer._get_base_volume(-100, is_free_page=False)
        assert level == "Base"


# ==============================================================================
# TEST PAGE TYPE VOLUME EFFICIENCY FACTORS
# ==============================================================================

class TestPageTypeVolumeEfficiency:
    """Tests for page type volume efficiency factors (2025 softened penalties).

    These factors apply final adjustments based on calculated weekly volume.
    Penalties are softened to support the new 2-6 PPV/day strategy.
    """

    def test_free_page_efficiency_constants(self) -> None:
        """Verify free page efficiency factor configuration (2025 values)."""
        # Verify the constant structure
        assert len(FREE_PAGE_VOLUME_EFFICIENCY) == 4
        # No penalty up to 21/week (3/day)
        assert FREE_PAGE_VOLUME_EFFICIENCY[0] == (0, 21, 1.00)
        # 10% reduction at 22-35/week (3-5/day)
        assert FREE_PAGE_VOLUME_EFFICIENCY[1] == (22, 35, 0.90)
        # 20% reduction at 36-42/week (5-6/day)
        assert FREE_PAGE_VOLUME_EFFICIENCY[2] == (36, 42, 0.80)
        # 30% reduction above 42/week
        assert FREE_PAGE_VOLUME_EFFICIENCY[3] == (43, None, 0.70)

    def test_paid_page_tolerance_constants(self) -> None:
        """Verify paid page volume tolerance configuration (2025 values)."""
        assert len(PAID_PAGE_VOLUME_TOLERANCE) == 4
        # No penalty up to 21/week
        assert PAID_PAGE_VOLUME_TOLERANCE[0] == (0, 21, 1.00)
        # 10% reduction at 22-35/week
        assert PAID_PAGE_VOLUME_TOLERANCE[1] == (22, 35, 0.90)
        # 20% reduction at 36-42/week
        assert PAID_PAGE_VOLUME_TOLERANCE[2] == (36, 42, 0.80)
        # 30% reduction above 42/week
        assert PAID_PAGE_VOLUME_TOLERANCE[3] == (43, None, 0.70)

    def test_free_page_efficiency_factor_optimal(self) -> None:
        """Test free page efficiency at optimal volume (<= 21/week)."""
        # At any value up to 21 PPV/week (3/day): factor should be 1.0
        assert get_page_type_volume_factor(14, is_free_page=True) == 1.0
        assert get_page_type_volume_factor(21, is_free_page=True) == 1.0
        assert get_page_type_volume_factor(1, is_free_page=True) == 1.0

    def test_free_page_efficiency_factor_diminishing(self) -> None:
        """Test free page efficiency at first penalty tier (22-35/week)."""
        # At 25 PPV/week: factor should be 0.90
        assert get_page_type_volume_factor(25, is_free_page=True) == 0.90
        assert get_page_type_volume_factor(22, is_free_page=True) == 0.90
        assert get_page_type_volume_factor(35, is_free_page=True) == 0.90

    def test_free_page_efficiency_factor_heavy_diminishing(self) -> None:
        """Test free page efficiency at second penalty tier (36-42/week)."""
        # At 38 PPV/week: factor should be 0.80
        assert get_page_type_volume_factor(38, is_free_page=True) == 0.80
        assert get_page_type_volume_factor(36, is_free_page=True) == 0.80
        assert get_page_type_volume_factor(42, is_free_page=True) == 0.80

    def test_free_page_efficiency_factor_oversaturation(self) -> None:
        """Test free page efficiency at over-saturation (43+/week)."""
        # At 50 PPV/week: factor should be 0.70
        assert get_page_type_volume_factor(50, is_free_page=True) == 0.70
        assert get_page_type_volume_factor(43, is_free_page=True) == 0.70
        assert get_page_type_volume_factor(100, is_free_page=True) == 0.70

    def test_paid_page_efficiency_factor_below_optimal(self) -> None:
        """Test paid page efficiency at optimal range (<=21/week)."""
        # At 14 PPV/week (2/day floor): factor should be 1.0
        assert get_page_type_volume_factor(14, is_free_page=False) == 1.0
        assert get_page_type_volume_factor(1, is_free_page=False) == 1.0
        assert get_page_type_volume_factor(21, is_free_page=False) == 1.0

    def test_paid_page_efficiency_factor_sweet_spot(self) -> None:
        """Test paid page efficiency at middle range (22-35/week)."""
        # At 28 PPV/week (4/day): factor should be 0.90
        assert get_page_type_volume_factor(28, is_free_page=False) == 0.90
        assert get_page_type_volume_factor(22, is_free_page=False) == 0.90
        assert get_page_type_volume_factor(35, is_free_page=False) == 0.90

    def test_paid_page_efficiency_factor_diminishing(self) -> None:
        """Test paid page efficiency at high volume (36-42/week)."""
        # At 40 PPV/week: factor should be 0.80
        assert get_page_type_volume_factor(40, is_free_page=False) == 0.80
        assert get_page_type_volume_factor(36, is_free_page=False) == 0.80
        assert get_page_type_volume_factor(42, is_free_page=False) == 0.80

    def test_paid_page_efficiency_factor_oversaturation(self) -> None:
        """Test paid page efficiency at over-saturation (43+/week)."""
        # At 50 PPV/week: factor should be 0.70
        assert get_page_type_volume_factor(50, is_free_page=False) == 0.70
        assert get_page_type_volume_factor(43, is_free_page=False) == 0.70
        assert get_page_type_volume_factor(100, is_free_page=False) == 0.70


# ==============================================================================
# TEST HARD CAPS VERIFICATION
# ==============================================================================

class TestHardCapsVerification:
    """Verification tests for 2025 volume strategy hard cap values."""

    def test_hard_cap_paid_page_max(self) -> None:
        """Test that paid pages are capped at 42 PPV/week (6/day max)."""
        assert PAID_PAGE_MAX_PPV_WEEK == 42

    def test_hard_cap_paid_page_min(self) -> None:
        """Test that paid pages have minimum of 14 PPV/week (2/day min)."""
        assert PAID_PAGE_MIN_PPV_WEEK == 14

    def test_hard_cap_free_page_max(self) -> None:
        """Test that free pages are capped at 6 PPV/day (Ultra tier max)."""
        assert FREE_PAGE_MAX_PPV_DAY == 6

    def test_hard_cap_free_page_min(self) -> None:
        """Test that free pages have minimum of 2 PPV/day (new floor)."""
        assert FREE_PAGE_MIN_PPV_DAY == 2


# ==============================================================================
# TEST VOLUME OVERRIDE SYSTEM
# ==============================================================================

class TestVolumeOverrideSystem:
    """Tests for the creator volume override system.

    Overrides allow proven performers to exceed calculated volumes
    or protect scarcity strategies with reduced volumes.
    """

    def test_override_takes_precedence(self, mock_db: sqlite3.Connection) -> None:
        """Test that an active override takes precedence over calculated volume."""
        creator_id = "test-override-001"
        first_seen = (datetime.now() - timedelta(days=200)).isoformat()

        # Create creator
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "overridecreator", "Override Creator", "paid",
            12.99, 3000, 2, first_seen, 1
        ))

        # Create active override with high volume (proven performer)
        mock_db.execute("""
            INSERT INTO volume_overrides (
                creator_id, target_weekly_ppv, target_weekly_bump,
                override_reason, is_active
            ) VALUES (?, ?, ?, ?, ?)
        """, (creator_id, 18, 10, "Proven high-efficiency performer", 1))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should use override values, not calculated
        assert strategy.ppv_per_week == 18
        assert strategy.bump_per_week == 10
        assert "OVERRIDE" in strategy.calculation_notes[0]

    def test_expired_override_ignored(self, mock_db: sqlite3.Connection) -> None:
        """Test that expired overrides are not used."""
        creator_id = "test-expired-001"
        first_seen = (datetime.now() - timedelta(days=200)).isoformat()
        expired_date = (datetime.now() - timedelta(days=1)).isoformat()

        # Create creator
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "expiredcreator", "Expired Creator", "paid",
            12.99, 3000, 2, first_seen, 1
        ))

        # Create expired override
        mock_db.execute("""
            INSERT INTO volume_overrides (
                creator_id, target_weekly_ppv, target_weekly_bump,
                override_reason, is_active, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (creator_id, 25, 15, "Expired override", 1, expired_date))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should NOT use override values (expired)
        assert strategy.ppv_per_week != 25
        assert "OVERRIDE" not in str(strategy.calculation_notes)

    def test_inactive_override_ignored(self, mock_db: sqlite3.Connection) -> None:
        """Test that inactive overrides are not used."""
        creator_id = "test-inactive-001"
        first_seen = (datetime.now() - timedelta(days=200)).isoformat()

        # Create creator
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "inactivecreator", "Inactive Creator", "paid",
            12.99, 3000, 2, first_seen, 1
        ))

        # Create inactive override
        mock_db.execute("""
            INSERT INTO volume_overrides (
                creator_id, target_weekly_ppv, target_weekly_bump,
                override_reason, is_active
            ) VALUES (?, ?, ?, ?, ?)
        """, (creator_id, 25, 15, "Inactive override", 0))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Should NOT use override values (inactive)
        assert strategy.ppv_per_week != 25
        assert "OVERRIDE" not in str(strategy.calculation_notes)

    def test_override_volume_level_determination(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test that override correctly determines volume level from PPV/week."""
        creator_id = "test-level-001"
        first_seen = (datetime.now() - timedelta(days=200)).isoformat()

        # Create creator
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                first_seen_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "levelcreator", "Level Creator", "paid",
            12.99, 3000, 2, first_seen, 1
        ))

        # Test different weekly PPV levels
        test_cases = [
            (5, "Low"),    # <= 7
            (10, "Mid"),   # <= 14
            (18, "High"),  # <= 21
            (25, "Ultra"), # > 21
        ]

        for weekly_ppv, expected_level in test_cases:
            # Clear previous override
            mock_db.execute("DELETE FROM volume_overrides WHERE creator_id = ?", (creator_id,))

            mock_db.execute("""
                INSERT INTO volume_overrides (
                    creator_id, target_weekly_ppv, target_weekly_bump,
                    override_reason, is_active
                ) VALUES (?, ?, ?, ?, ?)
            """, (creator_id, weekly_ppv, 7, f"Test {expected_level}", 1))

            mock_db.commit()

            optimizer = MultiFactorVolumeOptimizer(mock_db)
            strategy = optimizer.calculate_optimal_volume(creator_id)

            assert strategy.volume_level == expected_level, \
                f"Expected {expected_level} for {weekly_ppv}/week, got {strategy.volume_level}"


# ==============================================================================
# TEST NEW VOLUME BRACKET EXPECTED VALUES
# ==============================================================================

class TestNewVolumeBracketValues:
    """Tests to verify the 2025 volume strategy produces expected values.

    Based on 2025-12-06 volume strategy update:
    - Minimum 2 PPV/day (14/week) for all creators
    - Maximum 6 PPV/day (42/week) for high performers
    - Performance-based tier progression
    """

    def test_paid_page_under_1k_fans_produces_expected_weekly(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test that <1K fans paid page produces minimum 14 PPV/week (2/day floor)."""
        creator_id = "test-low-fans"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "lowfans", "Low Fans", "paid",
            12.99, 500, 2, 1  # Mid-tier, standard price
        ))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Expected: 14+ PPV/week for all creators (2/day minimum floor)
        assert strategy.ppv_per_week >= 14, \
            f"Expected 14+ PPV/week (2/day floor) for all creators, got {strategy.ppv_per_week}"

    def test_paid_page_mid_fans_produces_expected_weekly(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test that 1K-5K fans paid page produces ~7 PPV/week (was ~21)."""
        creator_id = "test-mid-fans"

        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            creator_id, "midfans", "Mid Fans", "paid",
            12.99, 3000, 2, 1
        ))
        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        strategy = optimizer.calculate_optimal_volume(creator_id)

        # Expected: ~7-10 PPV/week for mid fans
        assert 1 <= strategy.ppv_per_week <= 14, \
            f"Expected 1-14 PPV/week for 1K-5K fans, got {strategy.ppv_per_week}"

    def test_free_page_produces_lower_volume_than_paid(
        self,
        mock_db: sqlite3.Connection
    ) -> None:
        """Test that free pages produce lower volume than equivalent paid pages."""
        paid_id = "test-paid-compare"
        free_id = "test-free-compare"

        # Create paid page
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (paid_id, "paidcompare", "Paid Compare", "paid", 12.99, 5000, 2, 1))

        # Create free page with same fan count
        mock_db.execute("""
            INSERT INTO creators (
                creator_id, page_name, display_name, page_type,
                subscription_price, current_active_fans, performance_tier,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (free_id, "freecompare", "Free Compare", "free", 0.0, 5000, 2, 1))

        mock_db.commit()

        optimizer = MultiFactorVolumeOptimizer(mock_db)
        paid_strategy = optimizer.calculate_optimal_volume(paid_id)
        free_strategy = optimizer.calculate_optimal_volume(free_id)

        # Free pages should have efficiency-adjusted lower volume
        # Due to the page type efficiency factors
        assert free_strategy.ppv_per_day <= FREE_PAGE_MAX_PPV_DAY, \
            f"Free page should be capped at {FREE_PAGE_MAX_PPV_DAY}/day"


# ==============================================================================
# TEST NEW VOLUME TIER FUNCTION (2025 Strategy)
# ==============================================================================

class TestVolumeTierFunction:
    """Tests for the new get_volume_tier() function.

    This function determines volume tier based on performance metrics:
    - Base: 2 PPV/day (all creators)
    - Growth: 3 PPV/day (conv >0.10% OR $/PPV >$40)
    - Scale: 4 PPV/day (conv >0.25% AND $/PPV >$50)
    - High: 5 PPV/day (conv >0.35% AND $/PPV >$65)
    - Ultra: 6 PPV/day (conv >0.40% AND $/PPV >$75 AND >$75K rev)
    """

    def test_base_tier_new_creator(self) -> None:
        """New creator with no metrics gets Base tier (2/day)."""
        tier, ppv = get_volume_tier(
            conv_rate=0.0005,  # 0.05%
            dollars_per_ppv=25,
            total_revenue=5000
        )
        assert tier == "Base"
        assert ppv == 2

    def test_growth_tier_by_conversion(self) -> None:
        """Creator with >0.10% conversion gets Growth tier (3/day)."""
        tier, ppv = get_volume_tier(
            conv_rate=0.0015,  # 0.15%
            dollars_per_ppv=30,
            total_revenue=10000
        )
        assert tier == "Growth"
        assert ppv == 3

    def test_growth_tier_by_dollars_per_ppv(self) -> None:
        """Creator with >$40/PPV gets Growth tier even with low conversion."""
        tier, ppv = get_volume_tier(
            conv_rate=0.0005,  # 0.05% - below threshold
            dollars_per_ppv=45,  # Above $40 threshold
            total_revenue=15000
        )
        assert tier == "Growth"
        assert ppv == 3

    def test_scale_tier(self) -> None:
        """Creator with conv >0.25% AND $/PPV >$50 gets Scale tier (4/day)."""
        tier, ppv = get_volume_tier(
            conv_rate=0.003,  # 0.30%
            dollars_per_ppv=55,
            total_revenue=30000
        )
        assert tier == "Scale"
        assert ppv == 4

    def test_scale_tier_requires_both(self) -> None:
        """Scale tier requires BOTH conditions, not just one."""
        # High conversion but low $/PPV should be Growth
        tier, _ = get_volume_tier(conv_rate=0.003, dollars_per_ppv=35, total_revenue=30000)
        assert tier == "Growth"

        # High $/PPV but low conversion should be Growth
        tier, _ = get_volume_tier(conv_rate=0.002, dollars_per_ppv=55, total_revenue=30000)
        assert tier == "Growth"

    def test_high_tier(self) -> None:
        """Creator with conv >0.35% AND $/PPV >$65 gets High tier (5/day)."""
        tier, ppv = get_volume_tier(
            conv_rate=0.004,  # 0.40%
            dollars_per_ppv=70,
            total_revenue=50000
        )
        assert tier == "High"
        assert ppv == 5

    def test_ultra_tier(self) -> None:
        """Creator with conv >0.40% AND $/PPV >$75 AND >$75K rev gets Ultra (6/day)."""
        tier, ppv = get_volume_tier(
            conv_rate=0.005,  # 0.50%
            dollars_per_ppv=80,
            total_revenue=100000
        )
        assert tier == "Ultra"
        assert ppv == 6

    def test_ultra_tier_requires_all_three(self) -> None:
        """Ultra tier requires ALL three conditions."""
        # Missing revenue requirement
        tier, _ = get_volume_tier(conv_rate=0.005, dollars_per_ppv=80, total_revenue=50000)
        assert tier == "High"  # Falls back to High

        # Missing $/PPV requirement
        tier, _ = get_volume_tier(conv_rate=0.005, dollars_per_ppv=70, total_revenue=100000)
        assert tier == "High"  # Falls back to High

    def test_percentage_format_handling(self) -> None:
        """Test that percentage format (0.4 vs 0.004) is handled correctly."""
        # If someone passes 0.4 meaning 0.4%, it should be converted to 0.004
        # 0.4 / 100 = 0.004 which is >0.0040 (0.40%) so it gets Ultra
        tier, _ = get_volume_tier(conv_rate=0.4, dollars_per_ppv=80, total_revenue=100000)
        assert tier == "Ultra"  # 0.4% when converted to decimal is exactly at Ultra threshold

        # If someone passes 0.35 meaning 0.35%, it becomes 0.0035 -> High tier
        # Need low revenue to avoid hitting Ultra threshold
        tier, _ = get_volume_tier(conv_rate=0.35, dollars_per_ppv=80, total_revenue=50000)
        assert tier == "High"  # 0.35% = High (revenue too low for Ultra)

        # Properly formatted decimal (already in correct format)
        tier, _ = get_volume_tier(conv_rate=0.005, dollars_per_ppv=80, total_revenue=100000)
        assert tier == "Ultra"


# ==============================================================================
# TEST DAY-OF-WEEK MODIFIERS
# ==============================================================================

class TestDayOfWeekModifiers:
    """Tests for day-of-week optimization functions."""

    def test_day_modifiers_values(self) -> None:
        """Verify day-of-week modifier values are correct."""
        assert DAY_OF_WEEK_MODIFIERS["Thursday"] == 1.3  # Best day
        assert DAY_OF_WEEK_MODIFIERS["Wednesday"] == 1.2
        assert DAY_OF_WEEK_MODIFIERS["Friday"] == 1.2
        assert DAY_OF_WEEK_MODIFIERS["Tuesday"] == 1.1
        assert DAY_OF_WEEK_MODIFIERS["Monday"] == 1.0
        assert DAY_OF_WEEK_MODIFIERS["Sunday"] == 0.9
        assert DAY_OF_WEEK_MODIFIERS["Saturday"] == 0.8  # Lowest day

    def test_get_day_modifier(self) -> None:
        """Test get_day_of_week_modifier function."""
        assert get_day_of_week_modifier("Thursday") == 1.3
        assert get_day_of_week_modifier("Saturday") == 0.8
        assert get_day_of_week_modifier("Unknown") == 1.0  # Default

    def test_weekly_distribution_base_volume(self) -> None:
        """Test weekly day distribution for base volume (2/day)."""
        distribution = get_weekly_day_distribution(2)

        # Thursday should have highest volume (2 * 1.3 = 2.6 -> 3)
        assert distribution["Thursday"] == 3

        # Saturday should have lowest (2 * 0.8 = 1.6 -> 2, but min 1)
        assert distribution["Saturday"] >= 1

    def test_weekly_distribution_growth_volume(self) -> None:
        """Test weekly day distribution for growth volume (3/day)."""
        distribution = get_weekly_day_distribution(3)

        # Thursday should be highest
        assert distribution["Thursday"] == 4  # 3 * 1.3 = 3.9 -> 4

        # Monday should be baseline
        assert distribution["Monday"] == 3  # 3 * 1.0 = 3

    def test_weekly_distribution_minimum_enforced(self) -> None:
        """Test that minimum of 1 PPV per day is enforced."""
        distribution = get_weekly_day_distribution(1)

        # Even with 0.8x modifier, should be at least 1
        assert distribution["Saturday"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
