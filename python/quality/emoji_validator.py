"""
Emoji Blending Validator for Caption Quality Control.

Validates emoji usage follows blending rules to prevent emoji overload and
maintain visual appeal. Implements Unicode 15.0+ emoji detection with comprehensive
range coverage.

Rule: NEVER 3+ yellow face emojis in a row
"""
import re
from dataclasses import dataclass
from typing import Dict, List

from python.logging_config import get_logger
from python.exceptions import ValidationError

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmojiValidationResult:
    """Immutable result of emoji validation."""
    is_valid: bool
    emoji_count: int
    emoji_density: float
    issues: tuple[dict, ...]


class EmojiValidator:
    """
    Validate emoji usage follows blending rules.
    Rule: NEVER 3+ yellow face emojis in a row
    """

    # Yellow/skin-tone face emojis
    YELLOW_FACE_EMOJIS = {
        # Smileys
        '\U0001F600', '\U0001F603', '\U0001F604', '\U0001F601', '\U0001F606',
        '\U0001F605', '\U0001F923', '\U0001F602', '\U0001F642', '\U0001F643',
        '\U0001F609', '\U0001F60A', '\U0001F607',
        # Love faces
        '\U0001F970', '\U0001F60D', '\U0001F929', '\U0001F618', '\U0001F617',
        '\U0000263A', '\U0001F61A', '\U0001F619',
        # Playful
        '\U0001F60B', '\U0001F61B', '\U0001F61C', '\U0001F92A', '\U0001F61D',
        '\U0001F911',
        # Other yellow faces
        '\U0001F633', '\U0001F644', '\U0001F62C', '\U0001F910', '\U0001F974',
    }

    # Pattern to match emojis
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )

    def validate(self, caption: str) -> Dict:
        """
        Validate emoji blending rules.

        Args:
            caption: The caption text to validate

        Returns:
            Validation result dict with issues if any

        Raises:
            ValidationError: If caption is empty or not a string
        """
        # Input validation (SECURITY)
        if not caption:
            raise ValidationError(
                message="Caption cannot be empty",
                field="caption",
                value=caption
            )
        if not isinstance(caption, str):
            raise ValidationError(
                message="Caption must be string",
                field="caption",
                value=type(caption).__name__
            )

        # Extract all emojis from caption
        emojis_found = []
        for char in caption:
            if self._is_emoji(char):
                emojis_found.append(char)

        # Calculate emoji density for all captions
        emoji_density = len(emojis_found) / len(caption) if caption else 0

        if len(emojis_found) < 3:
            return {
                'is_valid': True,
                'emoji_count': len(emojis_found),
                'emoji_density': emoji_density,
                'issues': []
            }

        issues = []

        # Check for 3+ consecutive yellow faces in the original text
        # We need to check character by character in the original caption
        consecutive_yellow = 0
        yellow_sequence = []

        for char in caption:
            if self._is_emoji(char):
                if char in self.YELLOW_FACE_EMOJIS:
                    consecutive_yellow += 1
                    yellow_sequence.append(char)
                    if consecutive_yellow >= 3:
                        issues.append({
                            'type': 'emoji_vomit',
                            'severity': 'MEDIUM',
                            'message': f"3+ yellow face emojis in a row detected",
                            'emojis': yellow_sequence[-3:],
                            'recommendation': 'Vary emoji colors for better visual blend'
                        })
                        break
                else:
                    # Non-yellow emoji breaks the sequence
                    consecutive_yellow = 0
                    yellow_sequence = []
            else:
                # Non-emoji character breaks the sequence
                consecutive_yellow = 0
                yellow_sequence = []

        # Check emoji density - dynamic based on caption length
        # Dynamic density based on length
        if len(caption) < 100:
            max_density = 0.10  # 1 per 10 chars for short captions
        elif len(caption) < 250:
            max_density = 0.07  # 1 per ~14 chars
        else:
            max_density = 0.05  # 1 per 20 chars for long captions

        if emoji_density > max_density:
            issues.append({
                'type': 'high_density',
                'severity': 'LOW',
                'message': f"Too many emojis ({len(emojis_found)} in {len(caption)} chars)",
                'density': str(emoji_density),  # Convert to string for consistent type
                'recommendation': f'Reduce to max {int(len(caption) * max_density)} emojis'
            })

        return {
            'is_valid': not any(i['severity'] == 'MEDIUM' for i in issues),
            'emoji_count': len(emojis_found),
            'emoji_density': emoji_density,
            'issues': issues
        }

    def _is_emoji(self, char: str) -> bool:
        """
        Check if character is an emoji.

        Updated for Unicode 15.0+ with comprehensive emoji ranges including:
        - Traditional emoticons and symbols
        - Skin tone modifiers (Fitzpatrick scale)
        - Extended pictographs (Unicode 13.0+)
        - Symbols and pictographs extended-A/B (Unicode 14.0/15.0)

        Note: Excludes bare digits (0-9), # and * as these are only emojis
        when combined with variation selectors in keycap sequences.
        """
        code = ord(char)
        # Cover all major emoji ranges (updated for Unicode 15.0+)
        return (
            # Core emoji ranges
            0x1F600 <= code <= 0x1F64F or  # Emoticons
            0x1F300 <= code <= 0x1F5FF or  # Symbols & Pictographs
            0x1F680 <= code <= 0x1F6FF or  # Transport & Map
            0x1F1E0 <= code <= 0x1F1FF or  # Flags (regional indicators)

            # Misc symbols and dingbats
            0x2600 <= code <= 0x26FF or    # Misc symbols
            0x2700 <= code <= 0x27BF or    # Dingbats

            # Variation selectors (used to modify emoji presentation)
            0xFE00 <= code <= 0xFE0F or    # Variation selectors

            # Supplemental symbols and pictographs
            0x1F900 <= code <= 0x1F9FF or  # Supplemental symbols

            # Extended emoji (Unicode 13.0+)
            0x1FA00 <= code <= 0x1FA6F or  # Chess symbols, extended-A
            0x1FA70 <= code <= 0x1FAFF or  # Extended-B (Unicode 14.0/15.0)

            # Skin tone modifiers (Fitzpatrick scale)
            0x1F3FB <= code <= 0x1F3FF or  # Skin tones (light to dark)

            # Additional miscellaneous symbols
            0x231A <= code <= 0x231B or    # Watch, hourglass
            0x23E9 <= code <= 0x23F3 or    # Various media controls
            0x23F8 <= code <= 0x23FA or    # Various media controls

            # People and body parts
            0x1F385 <= code <= 0x1F3C4 or  # Holiday and sports figures
            0x1F466 <= code <= 0x1F487 or  # People

            # Animals and nature extended
            0x1FAB0 <= code <= 0x1FAB6 or  # Animals (Unicode 13.0+)
            0x1FAC0 <= code <= 0x1FAC2 or  # Face partials (Unicode 13.0+)
            0x1FAD0 <= code <= 0x1FAD6 or  # Food items (Unicode 13.0+)
            0x1FAE0 <= code <= 0x1FAE7 or  # Face emojis (Unicode 14.0+)
            0x1FAF0 <= code <= 0x1FAF6     # Hand gestures (Unicode 14.0+)

            # Note: Keycap sequences (0-9, #, *) excluded as they need
            # variation selectors to be considered emojis
        )

    def _is_skin_tone_modifier(self, char: str) -> bool:
        """Check if character is a skin tone modifier (Fitzpatrick scale)."""
        code = ord(char)
        return 0x1F3FB <= code <= 0x1F3FF  # Light to dark skin tones
