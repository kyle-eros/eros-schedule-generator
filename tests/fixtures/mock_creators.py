"""
Mock creator and persona data for testing.

Provides sample creator profiles and persona profiles for testing
persona matching and schedule generation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# Add scripts to path for imports
TESTS_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# =============================================================================
# CREATOR PROFILE MOCK
# =============================================================================


@dataclass(slots=True)
class MockCreatorProfile:
    """Mock creator profile for testing."""

    creator_id: str
    page_name: str
    display_name: str
    page_type: str
    active_fans: int
    volume_level: str
    primary_tone: str
    emoji_frequency: str
    slang_level: str
    avg_sentiment: float
    best_hours: list[int] = field(default_factory=list)
    vault_types: list[int] = field(default_factory=list)
    content_notes: dict = field(default_factory=dict)
    filter_keywords: set = field(default_factory=set)
    price_modifiers: dict = field(default_factory=dict)


# =============================================================================
# PERSONA PROFILE MOCK
# =============================================================================


@dataclass(frozen=True, slots=True)
class MockPersonaProfile:
    """Mock persona profile for testing (mirrors models.PersonaProfile)."""

    creator_id: str
    page_name: str
    primary_tone: str
    secondary_tone: str | None = None
    emoji_frequency: str = "moderate"
    favorite_emojis: tuple[str, ...] = ()
    slang_level: str = "light"
    avg_sentiment: float = 0.5
    avg_caption_length: int = 100


# =============================================================================
# SAMPLE CREATOR PROFILES
# =============================================================================

MOCK_CREATOR_PAID = MockCreatorProfile(
    creator_id="test-creator-001",
    page_name="testcreator",
    display_name="Test Creator",
    page_type="paid",
    active_fans=5000,
    volume_level="Scale",
    primary_tone="playful",
    emoji_frequency="moderate",
    slang_level="light",
    avg_sentiment=0.7,
    best_hours=[10, 14, 18, 21],
    vault_types=[1, 2, 3, 4],
    content_notes={"prefers_solo": True, "avoids_bg": False},
    filter_keywords=set(),
    price_modifiers={"solo": 1.0, "sextape": 1.2, "bg": 1.5},
)

MOCK_CREATOR_FREE = MockCreatorProfile(
    creator_id="test-creator-002",
    page_name="freecreator",
    display_name="Free Creator",
    page_type="free",
    active_fans=12000,
    volume_level="High",
    primary_tone="seductive",
    emoji_frequency="heavy",
    slang_level="none",
    avg_sentiment=0.65,
    best_hours=[11, 15, 19, 22],
    vault_types=[1, 2, 5],
    content_notes={"focus_ppv": True},
    filter_keywords={"competitor_name"},
    price_modifiers={"solo": 0.8, "sextape": 1.0},
)

MOCK_PERSONA = MockPersonaProfile(
    creator_id="test-creator-001",
    page_name="testcreator",
    primary_tone="playful",
    secondary_tone="sweet",
    emoji_frequency="moderate",
    favorite_emojis=("heart", "fire", "wink"),
    slang_level="light",
    avg_sentiment=0.7,
    avg_caption_length=120,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_mock_creator_profile(
    creator_id: str = "mock-creator",
    page_name: str = "mockcreator",
    display_name: str = "Mock Creator",
    page_type: str = "paid",
    active_fans: int = 3000,
    volume_level: str = "Mid",
    primary_tone: str = "playful",
    emoji_frequency: str = "moderate",
    slang_level: str = "light",
    avg_sentiment: float = 0.6,
    best_hours: list[int] | None = None,
    vault_types: list[int] | None = None,
) -> MockCreatorProfile:
    """Create a mock creator profile with specified attributes."""
    return MockCreatorProfile(
        creator_id=creator_id,
        page_name=page_name,
        display_name=display_name,
        page_type=page_type,
        active_fans=active_fans,
        volume_level=volume_level,
        primary_tone=primary_tone,
        emoji_frequency=emoji_frequency,
        slang_level=slang_level,
        avg_sentiment=avg_sentiment,
        best_hours=best_hours or [10, 14, 18, 21],
        vault_types=vault_types or [1, 2, 3],
    )


def create_mock_persona_profile(
    creator_id: str = "mock-creator",
    page_name: str = "mockcreator",
    primary_tone: str = "playful",
    secondary_tone: str | None = "sweet",
    emoji_frequency: str = "moderate",
    slang_level: str = "light",
    avg_sentiment: float = 0.6,
) -> MockPersonaProfile:
    """Create a mock persona profile with specified attributes."""
    return MockPersonaProfile(
        creator_id=creator_id,
        page_name=page_name,
        primary_tone=primary_tone,
        secondary_tone=secondary_tone,
        emoji_frequency=emoji_frequency,
        slang_level=slang_level,
        avg_sentiment=avg_sentiment,
    )


# =============================================================================
# PERSONA MATCHING TEST DATA
# =============================================================================

# Personas for different tone types
MOCK_PERSONAS_BY_TONE: dict[str, MockPersonaProfile] = {
    "playful": MockPersonaProfile(
        creator_id="tone-playful",
        page_name="playful_creator",
        primary_tone="playful",
        secondary_tone="sweet",
        emoji_frequency="heavy",
        slang_level="light",
        avg_sentiment=0.75,
    ),
    "aggressive": MockPersonaProfile(
        creator_id="tone-aggressive",
        page_name="aggressive_creator",
        primary_tone="aggressive",
        secondary_tone="dominant",
        emoji_frequency="none",
        slang_level="none",
        avg_sentiment=0.45,
    ),
    "sweet": MockPersonaProfile(
        creator_id="tone-sweet",
        page_name="sweet_creator",
        primary_tone="sweet",
        secondary_tone="playful",
        emoji_frequency="moderate",
        slang_level="light",
        avg_sentiment=0.85,
    ),
    "seductive": MockPersonaProfile(
        creator_id="tone-seductive",
        page_name="seductive_creator",
        primary_tone="seductive",
        secondary_tone="direct",
        emoji_frequency="light",
        slang_level="none",
        avg_sentiment=0.65,
    ),
}
