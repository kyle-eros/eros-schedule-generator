"""
Font Format Validator for EROS Schedule Generator.

Validates that captions follow readability rules by limiting excessive
formatting (bold, italic, strikethrough, etc.) which can appear spammy
and reduce perceived authenticity.

Wave 4 Task 4.2.5 (Gap 2.6): Font Format Validator
Rule: Max 2 highlighted elements in long captions (250+ chars)
"""

import re
from dataclasses import dataclass
from typing import Dict, List

from python.logging_config import get_logger
from python.exceptions import ValidationError

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FontValidationResult:
    """Immutable result of font format validation."""
    is_valid: bool
    highlighted_count: int
    max_allowed: int
    issues: tuple[dict, ...]
    recommendation: str


class FontFormatValidator:
    """
    Validate font formatting follows readability rules.
    Rule: Max 2 highlighted elements in long captions (Gap 2.6)

    Over-formatting (bold, italic, etc.) makes captions look spammy
    and reduces perceived authenticity.
    """

    MAX_HIGHLIGHTED_ELEMENTS = 2

    # Patterns for highlighted/formatted text
    HIGHLIGHT_PATTERNS = [
        (r'\*\*[^*]+\*\*', 'bold_markdown'),      # **bold**
        (r'__[^_]+__', 'bold_underscore'),        # __bold__
        (r'\*[^*]+\*', 'italic_markdown'),        # *italic*
        (r'_[^_]+_', 'italic_underscore'),        # _italic_
        (r'~~[^~]+~~', 'strikethrough'),          # ~~strikethrough~~
        (r'`[^`]+`', 'code'),                     # `code`
        (r'\[[^\]]+\]\([^)]+\)', 'link'),         # [link](url)
    ]

    # Unicode special formatting (mathematical alphanumeric symbols)
    UNICODE_BOLD_RANGES = [
        (0x1D400, 0x1D433),  # Mathematical Bold
        (0x1D5D4, 0x1D607),  # Mathematical Sans-Serif Bold
        (0x1D63C, 0x1D66F),  # Mathematical Sans-Serif Bold Italic
    ]

    UNICODE_ITALIC_RANGES = [
        (0x1D434, 0x1D467),  # Mathematical Italic
        (0x1D608, 0x1D63B),  # Mathematical Sans-Serif Italic
    ]

    def validate(self, caption: str) -> FontValidationResult:
        """
        Validate font formatting in caption.

        Args:
            caption: The caption text to validate

        Returns:
            FontValidationResult with validation status

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

        highlighted_elements: List[Dict] = []
        issues: List[Dict] = []

        # Check markdown-style formatting
        for pattern, format_type in self.HIGHLIGHT_PATTERNS:
            matches = re.findall(pattern, caption)
            for match in matches:
                highlighted_elements.append({
                    'type': format_type,
                    'text': match,
                    'source': 'markdown'
                })

        # Check Unicode special characters
        unicode_highlights = self._count_unicode_formatting(caption)
        highlighted_elements.extend(unicode_highlights)

        total_highlights = len(highlighted_elements)

        # Long captions (250+ chars) should have limited formatting
        caption_length = len(caption)
        max_allowed = self.MAX_HIGHLIGHTED_ELEMENTS

        # For shorter captions, be more lenient
        if caption_length < 100:
            max_allowed = 3
        elif caption_length < 250:
            max_allowed = 2

        is_valid = total_highlights <= max_allowed

        if not is_valid:
            issues.append({
                'type': 'over_formatting',
                'severity': 'MEDIUM',
                'message': f'Too many highlighted elements ({total_highlights} found, max {max_allowed})',
                'elements': highlighted_elements[:5],  # Show first 5
                'recommendation': f'Reduce to {max_allowed} highlighted elements for authenticity'
            })
            logger.warning(f"Over-formatting detected: {total_highlights} highlighted elements")

        recommendation = 'Formatting is appropriate' if is_valid else f'Reduce highlighted elements to {max_allowed}'

        return FontValidationResult(
            is_valid=is_valid,
            highlighted_count=total_highlights,
            max_allowed=max_allowed,
            issues=tuple(issues),
            recommendation=recommendation
        )

    def _count_unicode_formatting(self, text: str) -> List[Dict]:
        """Count Unicode mathematical/styled characters."""
        elements = []
        current_run = []
        current_type = None

        for char in text:
            code = ord(char)
            char_type = None

            # Check if in bold ranges
            for start, end in self.UNICODE_BOLD_RANGES:
                if start <= code <= end:
                    char_type = 'unicode_bold'
                    break

            # Check if in italic ranges
            if char_type is None:
                for start, end in self.UNICODE_ITALIC_RANGES:
                    if start <= code <= end:
                        char_type = 'unicode_italic'
                        break

            if char_type:
                if char_type == current_type:
                    current_run.append(char)
                else:
                    if current_run:
                        elements.append({
                            'type': current_type,
                            'text': ''.join(current_run),
                            'source': 'unicode'
                        })
                    current_run = [char]
                    current_type = char_type
            else:
                if current_run:
                    elements.append({
                        'type': current_type,
                        'text': ''.join(current_run),
                        'source': 'unicode'
                    })
                    current_run = []
                    current_type = None

        # Don't forget the last run
        if current_run:
            elements.append({
                'type': current_type,
                'text': ''.join(current_run),
                'source': 'unicode'
            })

        return elements
