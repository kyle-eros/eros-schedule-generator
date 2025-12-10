"""
Mock caption data for testing.

Provides sample captions for each pool type (PROVEN, GLOBAL_EARNER, DISCOVERY)
and helper functions to create captions with specific attributes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add scripts to path for imports
TESTS_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# =============================================================================
# CAPTION DATACLASS (matches select_captions.Caption)
# =============================================================================


@dataclass(slots=True)
class MockCaption:
    """Mock caption data for testing (matches select_captions.Caption structure)."""

    caption_id: int
    caption_text: str
    caption_type: str = "ppv"
    content_type_id: int | None = 1
    content_type_name: str | None = "solo"
    performance_score: float = 50.0
    freshness_score: float = 80.0
    tone: str | None = "playful"
    emoji_style: str | None = "moderate"
    slang_level: str | None = "light"
    is_universal: bool = False
    pool_type: str = "DISCOVERY"
    creator_avg_earnings: float | None = None
    global_avg_earnings: float | None = None
    creator_times_used: int = 0
    global_times_used: int = 0
    source: str = "internal"
    imported_at: str | None = None
    combined_score: float = 0.0
    persona_boost: float = 1.0
    final_weight: float = 0.0
    hook_type: Any = None
    hook_confidence: float = 0.0


# =============================================================================
# PROVEN POOL CAPTIONS (creator-tested, high earnings)
# =============================================================================

MOCK_CAPTIONS_PROVEN: list[MockCaption] = [
    MockCaption(
        caption_id=1001,
        caption_text="I've been thinking about you all day, baby... want to see what happens next?",
        caption_type="ppv",
        content_type_id=1,
        content_type_name="solo",
        performance_score=85.0,
        freshness_score=75.0,
        tone="playful",
        emoji_style="moderate",
        slang_level="light",
        pool_type="PROVEN",
        creator_avg_earnings=95.50,
        global_avg_earnings=72.30,
        creator_times_used=12,
        global_times_used=45,
    ),
    MockCaption(
        caption_id=1002,
        caption_text="Just finished filming something special for you... wanna see more?",
        caption_type="ppv",
        content_type_id=2,
        content_type_name="sextape",
        performance_score=92.0,
        freshness_score=68.0,
        tone="seductive",
        emoji_style="light",
        slang_level="none",
        pool_type="PROVEN",
        creator_avg_earnings=125.00,
        global_avg_earnings=98.50,
        creator_times_used=8,
        global_times_used=32,
    ),
    MockCaption(
        caption_id=1003,
        caption_text="hehe come play with me! I promise you won't regret it",
        caption_type="ppv",
        content_type_id=1,
        content_type_name="solo",
        performance_score=78.0,
        freshness_score=82.0,
        tone="playful",
        emoji_style="heavy",
        slang_level="light",
        pool_type="PROVEN",
        creator_avg_earnings=68.25,
        global_avg_earnings=55.00,
        creator_times_used=5,
        global_times_used=28,
    ),
]


# =============================================================================
# GLOBAL_EARNER POOL CAPTIONS (globally proven, untested for creator)
# =============================================================================

MOCK_CAPTIONS_GLOBAL_EARNER: list[MockCaption] = [
    MockCaption(
        caption_id=2001,
        caption_text="You won't believe what I just did for you...",
        caption_type="ppv",
        content_type_id=3,
        content_type_name="bg",
        performance_score=88.0,
        freshness_score=90.0,
        tone="playful",
        emoji_style="moderate",
        slang_level="light",
        pool_type="GLOBAL_EARNER",
        creator_avg_earnings=None,
        global_avg_earnings=145.00,
        creator_times_used=0,
        global_times_used=67,
    ),
    MockCaption(
        caption_id=2002,
        caption_text="This is exclusive content just for my loyal fans...",
        caption_type="ppv",
        content_type_id=1,
        content_type_name="solo",
        performance_score=75.0,
        freshness_score=95.0,
        tone="sweet",
        emoji_style="light",
        slang_level="none",
        pool_type="GLOBAL_EARNER",
        creator_avg_earnings=None,
        global_avg_earnings=82.50,
        creator_times_used=1,
        global_times_used=42,
    ),
    MockCaption(
        caption_id=2003,
        caption_text="I was thinking about you earlier and made this...",
        caption_type="ppv",
        content_type_id=2,
        content_type_name="sextape",
        performance_score=82.0,
        freshness_score=88.0,
        tone="sweet",
        emoji_style="moderate",
        slang_level="light",
        pool_type="GLOBAL_EARNER",
        creator_avg_earnings=None,
        global_avg_earnings=110.00,
        creator_times_used=2,
        global_times_used=55,
    ),
]


# =============================================================================
# DISCOVERY POOL CAPTIONS (new imports, untested)
# =============================================================================

MOCK_CAPTIONS_DISCOVERY: list[MockCaption] = [
    MockCaption(
        caption_id=3001,
        caption_text="Just recorded this and had to share with you!",
        caption_type="ppv",
        content_type_id=1,
        content_type_name="solo",
        performance_score=50.0,
        freshness_score=100.0,
        tone=None,
        emoji_style=None,
        slang_level=None,
        pool_type="DISCOVERY",
        creator_avg_earnings=None,
        global_avg_earnings=None,
        creator_times_used=0,
        global_times_used=0,
        source="external_import",
        imported_at="2025-01-01T12:00:00",
    ),
    MockCaption(
        caption_id=3002,
        caption_text="ngl this is gonna be fire af no cap",
        caption_type="ppv",
        content_type_id=2,
        content_type_name="sextape",
        performance_score=45.0,
        freshness_score=100.0,
        tone=None,
        emoji_style=None,
        slang_level=None,
        pool_type="DISCOVERY",
        creator_avg_earnings=None,
        global_avg_earnings=None,
        creator_times_used=0,
        global_times_used=1,
        source="external_import",
        imported_at="2025-01-05T10:00:00",
    ),
    MockCaption(
        caption_id=3003,
        caption_text="Buy this now.",
        caption_type="ppv",
        content_type_id=1,
        content_type_name="solo",
        performance_score=40.0,
        freshness_score=100.0,
        tone="direct",
        emoji_style="none",
        slang_level="none",
        pool_type="DISCOVERY",
        creator_avg_earnings=None,
        global_avg_earnings=25.00,
        creator_times_used=0,
        global_times_used=2,
    ),
]

# Combined list of all mock captions
MOCK_CAPTIONS: list[MockCaption] = (
    MOCK_CAPTIONS_PROVEN + MOCK_CAPTIONS_GLOBAL_EARNER + MOCK_CAPTIONS_DISCOVERY
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_mock_caption(
    caption_id: int,
    caption_text: str = "Test caption text",
    pool_type: str = "DISCOVERY",
    freshness_score: float = 80.0,
    performance_score: float = 50.0,
    content_type_id: int = 1,
    content_type_name: str = "solo",
    tone: str | None = "playful",
    emoji_style: str | None = "moderate",
    slang_level: str | None = "light",
    creator_avg_earnings: float | None = None,
    global_avg_earnings: float | None = None,
    creator_times_used: int = 0,
    global_times_used: int = 0,
) -> MockCaption:
    """Create a mock caption with specified attributes."""
    return MockCaption(
        caption_id=caption_id,
        caption_text=caption_text,
        pool_type=pool_type,
        freshness_score=freshness_score,
        performance_score=performance_score,
        content_type_id=content_type_id,
        content_type_name=content_type_name,
        tone=tone,
        emoji_style=emoji_style,
        slang_level=slang_level,
        creator_avg_earnings=creator_avg_earnings,
        global_avg_earnings=global_avg_earnings,
        creator_times_used=creator_times_used,
        global_times_used=global_times_used,
    )


@dataclass
class MockStratifiedPools:
    """Mock StratifiedPools for testing (mirrors select_captions.StratifiedPools)."""

    content_type_id: int
    type_name: str
    proven: list[MockCaption] = field(default_factory=list)
    global_earners: list[MockCaption] = field(default_factory=list)
    discovery: list[MockCaption] = field(default_factory=list)
    content_type_avg_earnings: float = 50.0

    @property
    def total_count(self) -> int:
        """Total captions across all pools."""
        return len(self.proven) + len(self.global_earners) + len(self.discovery)

    @property
    def has_proven(self) -> bool:
        """Whether this content type has proven performers."""
        return len(self.proven) > 0

    @property
    def content_type_name(self) -> str:
        """Alias for type_name."""
        return self.type_name

    @property
    def global_earner(self) -> list[MockCaption]:
        """Alias for global_earners."""
        return self.global_earners

    def get_expected_earnings(self) -> float:
        """Get expected earnings for this content type."""
        if self.proven:
            earnings = [
                c.creator_avg_earnings
                for c in self.proven
                if c.creator_avg_earnings is not None
            ]
            if earnings:
                return sum(earnings) / len(earnings)

        if self.global_earners:
            earnings = [
                c.global_avg_earnings
                for c in self.global_earners
                if c.global_avg_earnings is not None
            ]
            if earnings:
                return sum(earnings) / len(earnings) * 0.8

        return 50.0

    def get_all_captions(self) -> list[MockCaption]:
        """Return all captions from all pools."""
        return self.proven + self.global_earners + self.discovery


def create_mock_stratified_pools(
    content_type_id: int = 1,
    type_name: str = "solo",
    num_proven: int = 2,
    num_global_earner: int = 2,
    num_discovery: int = 3,
) -> MockStratifiedPools:
    """Create mock stratified pools for testing."""
    pools = MockStratifiedPools(content_type_id=content_type_id, type_name=type_name)

    # Generate proven captions
    for i in range(num_proven):
        pools.proven.append(
            create_mock_caption(
                caption_id=1000 + i,
                caption_text=f"Proven caption {i} for {type_name}",
                pool_type="PROVEN",
                content_type_id=content_type_id,
                content_type_name=type_name,
                freshness_score=70.0 + i * 5,
                performance_score=80.0 + i * 3,
                creator_avg_earnings=80.0 + i * 10,
                global_avg_earnings=60.0 + i * 5,
                creator_times_used=5 + i,
                global_times_used=20 + i * 5,
            )
        )

    # Generate global earner captions
    for i in range(num_global_earner):
        pools.global_earners.append(
            create_mock_caption(
                caption_id=2000 + i,
                caption_text=f"Global earner caption {i} for {type_name}",
                pool_type="GLOBAL_EARNER",
                content_type_id=content_type_id,
                content_type_name=type_name,
                freshness_score=85.0 + i * 3,
                performance_score=70.0 + i * 5,
                creator_avg_earnings=None,
                global_avg_earnings=90.0 + i * 15,
                creator_times_used=1,
                global_times_used=30 + i * 10,
            )
        )

    # Generate discovery captions
    for i in range(num_discovery):
        pools.discovery.append(
            create_mock_caption(
                caption_id=3000 + i,
                caption_text=f"Discovery caption {i} for {type_name}",
                pool_type="DISCOVERY",
                content_type_id=content_type_id,
                content_type_name=type_name,
                freshness_score=95.0 + i,
                performance_score=50.0,
                creator_avg_earnings=None,
                global_avg_earnings=None,
                creator_times_used=0,
                global_times_used=i,
            )
        )

    return pools
