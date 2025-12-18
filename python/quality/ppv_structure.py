"""PPV Structure Validator for EROS Schedule Generator.

Validates PPV captions follow proven high-converting structures:
- Winner PPV: 4-step formula (Clickbait, Exclusivity, Value Anchor, CTA)
- Bundle PPV: Itemization, value anchoring, urgency
- Wall Campaign: 3-step structure (Title, Body with Setting, Short Wrap)

Version: 1.0.0
Wave 4 Task 4.2
"""

import re
from typing import Dict, List

from python.logging_config import get_logger
from python.exceptions import ValidationError

logger = get_logger(__name__)


class PPVStructureValidator:
    """
    Validate PPV captions follow proven high-converting structures.

    This validator ensures captions follow research-backed structures that
    maximize conversion rates for different PPV types (winner, bundle, wall).

    Structures validated:
        - Winner PPV: 4-step formula (Clickbait, Exclusivity, Value Anchor, CTA)
        - Bundle PPV: Itemization, value anchoring, urgency
        - Wall Campaign: 3-step structure (Title, Body with Setting, Short Wrap)

    All validation methods require non-empty string captions and will raise
    ValidationError for invalid input.

    Examples:
        >>> validator = PPVStructureValidator()
        >>> result = validator.validate_winner_ppv(
        ...     "CONGRATS! You're the only winner of this exclusive never-before-seen "
        ...     "$500 worth bundle for just $19.99! LMK which vid is ur fav"
        ... )
        >>> result['is_valid']
        True
        >>> result['structure_score']
        1.0

        >>> result = validator.validate_wall_campaign(
        ...     "OMG you won't believe what happened\\n\\n"
        ...     "I was getting ready for bed when I felt so turned on... "
        ...     "I couldn't resist touching myself\\n\\n"
        ...     "Unlock to see the full video"
        ... )
        >>> result['is_valid']
        True
    """

    # Step 1: Clickbait indicators
    CLICKBAIT_PATTERNS = [
        r'congrats',
        r'you\s*won',
        r'winner',
        r'special',
        r'lucky',
        r'chosen',
        r'only\s*one',
        r'first\s*to',
    ]

    # Step 2: Exclusivity keywords
    EXCLUSIVITY_KEYWORDS = [
        'only winner', 'exclusive', 'never seen before',
        'first time', 'just for you', 'special for you',
        'only you', 'private', 'secret', 'unreleased',
        'never shared', 'only person'
    ]

    # Step 3: Value anchor patterns
    VALUE_ANCHOR_PATTERNS = [
        r'\$[\d,]+\s*(worth|value)',
        r'worth\s*\$[\d,]+',
        r'\$[\d,]+\s*(for|only)\s*(only\s*)?\$\d+',
        r'usually\s*\$\d+',
        r'normally\s*\$\d+',
    ]

    # Step 4: Call to action patterns
    CTA_PATTERNS = [
        r'lmk|let\s*me\s*know',
        r'tell\s*me|message\s*me|dm\s*me',
        r'which.*fav',
        r'open.*see',
        r'claim.*now',
        r'don\'?t\s*miss',
        r'hurry',
        r'before\s*it\'?s\s*gone',
        r'what\s*do\s*you\s*think',
    ]

    def validate_winner_ppv(self, caption: str) -> Dict:
        """Validate winner PPV follows 4-step structure.

        Args:
            caption: The PPV caption to validate

        Returns:
            Validation result dict with:
                - is_valid: bool (True if >= 3/4 elements present)
                - structure_score: float (0.0-1.0)
                - elements: dict of bool values for each element
                - missing_elements: list of missing element names
                - issues: list of issue dicts with step, element, message
                - recommendation: str with action to take

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

        logger.debug(f"Validating winner PPV structure ({len(caption)} chars)")

        caption_lower = caption.lower()
        scores = {}
        issues = []

        # Step 1: Clickbait (check first 100 chars primarily)
        opening = caption_lower[:100]
        scores['clickbait'] = any(
            re.search(pattern, opening)
            for pattern in self.CLICKBAIT_PATTERNS
        )
        if not scores['clickbait']:
            issues.append({
                'step': 1,
                'element': 'clickbait',
                'message': 'Missing attention-grabbing opener (CONGRATS/WON/WINNER)'
            })

        # Step 2: Exclusivity
        scores['exclusivity'] = any(
            keyword in caption_lower
            for keyword in self.EXCLUSIVITY_KEYWORDS
        )
        if not scores['exclusivity']:
            issues.append({
                'step': 2,
                'element': 'exclusivity',
                'message': 'Missing exclusivity element ("only winner", "never seen before")'
            })

        # Step 3: Value anchor
        scores['value_anchor'] = any(
            re.search(pattern, caption_lower)
            for pattern in self.VALUE_ANCHOR_PATTERNS
        )
        if not scores['value_anchor']:
            issues.append({
                'step': 3,
                'element': 'value_anchor',
                'message': 'Missing value anchor ("$X worth for $Y")'
            })

        # Step 4: Call to Action
        scores['cta'] = any(
            re.search(pattern, caption_lower)
            for pattern in self.CTA_PATTERNS
        )
        if not scores['cta']:
            issues.append({
                'step': 4,
                'element': 'cta',
                'message': 'Missing call-to-action ("lmk which vid is ur fav")'
            })

        # Calculate structure score
        elements_present = sum(scores.values())
        structure_score = elements_present / 4

        # Log validation results
        if issues:
            logger.warning(
                f"Winner PPV structure incomplete: {elements_present}/4 elements",
                extra={'missing': [e['element'] for e in issues], 'score': structure_score}
            )
        else:
            logger.debug("Winner PPV structure complete (4/4 elements)")

        return {
            'is_valid': structure_score >= 0.75,  # At least 3/4 elements
            'structure_score': structure_score,
            'elements': scores,
            'missing_elements': [e['element'] for e in issues],
            'issues': issues,
            'recommendation': 'Add missing elements for optimal conversion' if issues else 'Structure complete'
        }

    def validate_bundle_ppv(self, caption: str) -> Dict:
        """Validate bundle PPV structure.

        Args:
            caption: The bundle PPV caption to validate

        Returns:
            Validation result dict with:
                - is_valid: bool (True if >= 50% elements present)
                - structure_score: float (0.0-1.0)
                - elements: dict of bool values for each element
                - issues: list of issue dicts with element and message

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

        logger.debug(f"Validating bundle PPV structure ({len(caption)} chars)")

        caption_lower = caption.lower()
        scores = {}
        issues = []

        # Check for itemization (list of items)
        has_list = bool(re.search(r'(\d+\s*(vid|pic|min)|•|►|-\s*\d)', caption_lower))
        scores['itemization'] = has_list
        if not has_list:
            issues.append({
                'element': 'itemization',
                'message': 'Bundle should list items (e.g., "5 vids, 10 pics")'
            })

        # Check for value anchor
        scores['value_anchor'] = any(
            re.search(pattern, caption_lower)
            for pattern in self.VALUE_ANCHOR_PATTERNS
        )

        # Check for urgency/scarcity
        urgency_patterns = [r'limited', r'only\s*\d+', r'won\'?t\s*last', r'hurry']
        scores['urgency'] = any(
            re.search(p, caption_lower)
            for p in urgency_patterns
        )

        structure_score = sum(scores.values()) / len(scores)

        # Log validation results
        if structure_score < 0.5:
            logger.warning(
                f"Bundle PPV structure weak: {sum(scores.values())}/{len(scores)} elements",
                extra={'issues': [i['element'] for i in issues], 'score': structure_score}
            )
        else:
            logger.debug(f"Bundle PPV structure valid (score: {structure_score:.2f})")

        return {
            'is_valid': structure_score >= 0.5,
            'structure_score': structure_score,
            'elements': scores,
            'issues': issues
        }

    def validate_wall_campaign(self, caption: str) -> Dict:
        """
        Validate Wall Campaign follows 3-step structure (Gap 2.3):
        1. Clickbait Title - Attention grabber in first line
        2. Body with Setting - Descriptive fantasy/scenario
        3. Short Wrap - Brief closing/CTA

        Args:
            caption: The wall campaign caption to validate

        Returns:
            Validation result dict with:
                - is_valid: bool (True if >= 2/3 elements present)
                - structure_score: float (0.0-1.0)
                - elements: dict of bool values for each element
                - missing_elements: list of missing element names
                - issues: list of issue dicts with step, element, message
                - recommendation: str with action to take

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

        logger.debug(f"Validating wall campaign structure ({len(caption)} chars)")

        caption_lower = caption.lower()
        lines = [line.strip() for line in caption.split('\n') if line.strip()]
        scores = {}
        issues = []

        # Step 1: Clickbait Title (first line, should be attention-grabbing)
        if lines:
            first_line = lines[0].lower()
            title_patterns = [
                r'new', r'just', r'omg', r'wait', r'you', r'can\'t believe',
                r'finally', r'exclusive', r'never', r'first time',
                r'\?', r'!', r'\.\.\.'
            ]
            scores['clickbait_title'] = any(
                re.search(pattern, first_line) for pattern in title_patterns
            )
            # Title should be relatively short (under 100 chars)
            if len(lines[0]) > 100:
                scores['clickbait_title'] = False
                issues.append({
                    'step': 1,
                    'element': 'clickbait_title',
                    'message': 'Title too long - should be punchy and under 100 chars'
                })
        else:
            scores['clickbait_title'] = False
            issues.append({
                'step': 1,
                'element': 'clickbait_title',
                'message': 'Missing clickbait title line'
            })

        if not scores.get('clickbait_title', False) and 'clickbait_title' not in [i['element'] for i in issues]:
            issues.append({
                'step': 1,
                'element': 'clickbait_title',
                'message': 'Title lacks attention-grabbing elements'
            })

        # Step 2: Body with Setting (middle content, descriptive)
        body_lines = lines[1:-1] if len(lines) > 2 else lines[1:] if len(lines) > 1 else []
        body_text = ' '.join(body_lines).lower()

        setting_indicators = [
            r'was', r'when', r'while', r'after', r'before', r'during',
            r'caught', r'found', r'decided', r'wanted', r'couldn\'t',
            r'started', r'began', r'felt', r'needed', r'had to',
            r'myself', r'imagined', r'never'  # Added missing indicators (Gap C-1)
        ]
        has_narrative = any(re.search(p, body_text) for p in setting_indicators)

        # Body should have some length (at least 45 chars for a proper setting)
        has_substance = len(body_text) >= 45

        scores['body_with_setting'] = has_narrative and has_substance
        if not scores['body_with_setting']:
            if not has_substance:
                issues.append({
                    'step': 2,
                    'element': 'body_with_setting',
                    'message': 'Body too short - needs descriptive fantasy/scenario (45+ chars)'
                })
            elif not has_narrative:
                issues.append({
                    'step': 2,
                    'element': 'body_with_setting',
                    'message': 'Body lacks narrative/setting elements'
                })

        # Step 3: Short Wrap (last line, brief closing)
        if len(lines) >= 2:
            last_line = lines[-1]
            # Short wrap should be concise (under 80 chars)
            is_short = len(last_line) < 80
            # Should have CTA or closing feel
            wrap_patterns = [
                r'unlock', r'open', r'see', r'watch', r'click', r'tap',
                r'enjoy', r'hope', r'love', r'want', r'\?', r'!'
            ]
            has_wrap_vibe = any(re.search(p, last_line.lower()) for p in wrap_patterns)
            scores['short_wrap'] = is_short and has_wrap_vibe
        else:
            scores['short_wrap'] = False

        if not scores.get('short_wrap', False):
            issues.append({
                'step': 3,
                'element': 'short_wrap',
                'message': 'Missing short wrap/closing (brief CTA under 80 chars)'
            })

        # Calculate structure score
        elements_present = sum(scores.values())
        structure_score = elements_present / 3

        # Log validation results
        if issues:
            logger.warning(
                f"Wall campaign structure incomplete: {elements_present}/3 elements",
                extra={'missing': [e['element'] for e in issues], 'score': structure_score}
            )
        else:
            logger.debug("Wall campaign structure complete (3/3 elements)")

        return {
            'is_valid': structure_score >= 0.67,  # At least 2/3 elements
            'structure_score': structure_score,
            'elements': scores,
            'missing_elements': [e['element'] for e in issues],
            'issues': issues,
            'recommendation': 'Add missing elements for optimal wall campaign' if issues else 'Structure complete'
        }
