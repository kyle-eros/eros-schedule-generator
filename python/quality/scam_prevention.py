"""
Content Scam Prevention Validator.

SECURITY CRITICAL: Prevents account bans and chargebacks by detecting content
scam attempts where captions promise content not available in creator's vault.

This module implements Unicode-aware text normalization to prevent homoglyph
attacks and character substitution bypasses. All validation is performed using
normalized text to ensure consistent detection across all evasion attempts.

Rule: NEVER scam. PPVs must contain mentioned content. Exaggerate but never lie.

Usage:
    from python.quality.scam_prevention import validate_caption_vault_match

    result = validate_caption_vault_match(
        caption="watch me take it anal",
        vault_content={'solo', 'bj'}  # Missing 'anal'
    )

    if result.blocked:
        print(f"BLOCKED: {result.scam_risks[0].message}")
        print(f"Action: {result.scam_risks[0].action_required}")
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Set

from python.logging_config import get_logger
from python.exceptions import ValidationError

logger = get_logger(__name__)

# Severity level constants for blocking decisions
BLOCKING_SEVERITIES = {'MEDIUM', 'HIGH', 'CRITICAL'}


def normalize_text(text: str) -> str:
    """
    Normalize text for keyword matching, stripping evasion attempts.

    SECURITY CRITICAL: Prevents Unicode homoglyph attacks and common
    character substitution bypasses used to evade content filters.

    Defense layers:
        1. Cyrillic/Greek lookalike mapping - Explicit conversion (а→a, о→o)
        2. NFKD decomposition - Separates base chars from combining marks
        3. Zero-width removal - Strips invisible bypass attempts
        4. Combining char removal - Removes diacritical marks
        5. ASCII conversion - Strips remaining non-ASCII
        6. Leet-speak handling - Converts common substitutions (@→a, 0→o, 1→l)
        7. Space collapse - Prevents "a n a l" spacing bypass

    Args:
        text: Raw input text that may contain evasion attempts

    Returns:
        Normalized lowercase ASCII text safe for keyword matching

    Examples:
        >>> normalize_text("ANAL")
        'anal'
        >>> normalize_text("an@l")
        'anal'
        >>> normalize_text("a n a l")
        'anal'
        >>> normalize_text("аnаl")  # Cyrillic 'а'
        'anal'
    """
    # 1. Cyrillic and Greek lookalike mapping (must be done BEFORE ASCII conversion)
    # These characters look identical to Latin but have different Unicode points
    lookalike_map = str.maketrans({
        # Cyrillic lookalikes (most common)
        'а': 'a', 'А': 'a',  # U+0430, U+0410
        'е': 'e', 'Е': 'e',  # U+0435, U+0415
        'і': 'i', 'І': 'i',  # U+0456, U+0406
        'о': 'o', 'О': 'o',  # U+043E, U+041E
        'р': 'p', 'Р': 'p',  # U+0440, U+0420
        'с': 'c', 'С': 'c',  # U+0441, U+0421
        'у': 'y', 'У': 'y',  # U+0443, U+0423
        'х': 'x', 'Х': 'x',  # U+0445, U+0425
        # Greek lookalikes
        'α': 'a', 'Α': 'a',  # U+03B1, U+0391
        'ο': 'o', 'Ο': 'o',  # U+03BF, U+039F
        'ρ': 'p', 'Ρ': 'p',  # U+03C1, U+03A1
    })
    normalized = text.translate(lookalike_map)

    # 2. NFKD decomposition (separates base chars from combining marks)
    normalized = unicodedata.normalize('NFKD', normalized)

    # 3. Remove zero-width characters (invisible bypass attempts)
    zero_width = '\u200b\u200c\u200d\ufeff\u00ad'
    normalized = ''.join(c for c in normalized if c not in zero_width)

    # 4. Remove combining characters (diacritical marks)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))

    # 5. ASCII conversion (strips remaining non-ASCII characters)
    ascii_text = normalized.encode('ascii', errors='ignore').decode('ascii')

    # 6. Common leet-speak substitution handling
    ascii_text = re.sub(r'[@4]', 'a', ascii_text)
    ascii_text = re.sub(r'[0]', 'o', ascii_text)
    ascii_text = re.sub(r'[1!|]', 'i', ascii_text)  # Fixed: 1 → i (prevents "fac1al" → "faclal")
    ascii_text = re.sub(r'[3]', 'e', ascii_text)
    ascii_text = re.sub(r'[5$]', 's', ascii_text)
    ascii_text = re.sub(r'[7]', 't', ascii_text)

    # 7. Collapse multiple spaces (catches "a n a l" spacing bypass)
    ascii_text = re.sub(r'\s+', '', ascii_text)

    return ascii_text.lower()


@dataclass(frozen=True, slots=True)
class ScamRisk:
    """Immutable record of a detected scam risk.

    Attributes:
        act: The explicit act mentioned in caption (e.g., 'anal', 'squirt')
        matched_keywords: Tuple of specific keywords that triggered detection
        severity: Risk severity level (LOW, MEDIUM, HIGH, CRITICAL)
        message: Human-readable description of the risk
        action_required: Required action to resolve the risk
    """
    act: str
    matched_keywords: tuple[str, ...]  # tuple for immutability
    severity: str
    message: str
    action_required: str


@dataclass(frozen=True, slots=True)
class ContentValidationResult:
    """Immutable validation result with scam risk assessment.

    Attributes:
        is_authentic: True if caption matches vault content (no scam risks)
        scam_risks: Tuple of detected ScamRisk instances
        warnings: Tuple of non-blocking warnings (e.g., value claims)
        requires_manual_review: True if manual review needed before scheduling
        blocked: True if scam risks prevent automatic scheduling
        recommendation: Human-readable recommendation for next steps
    """
    is_authentic: bool
    scam_risks: tuple[ScamRisk, ...]
    warnings: tuple[dict, ...]
    requires_manual_review: bool
    blocked: bool
    recommendation: str


class ContentAuthenticityValidator:
    """
    Validate caption promises match vault content.

    CRITICAL: Prevents account bans and chargebacks by ensuring captions
    only mention content actually available in the creator's vault.

    Security Features:
        - Unicode normalization with homoglyph attack prevention
        - Zero-width character removal
        - Leet-speak substitution handling
        - NFKD decomposition
        - Cyrillic/Greek lookalike detection

    All validation uses normalized text to ensure consistent detection
    across all bypass attempts.
    """

    # Explicit act keywords that MUST be in vault if mentioned in caption
    EXPLICIT_ACT_KEYWORDS = {
        'anal': [
            'anal', 'ass fuck', 'backdoor', 'tight hole', 'tightest hole',
            'in my ass', 'fucked my ass', 'anal play'
        ],
        'creampie': [
            'creampie', 'cum inside', 'dripping', 'filled me', 'filled up',
            'cum dripping', 'pussy full of cum'
        ],
        'squirt': [
            'squirt', 'gushing', 'puddle', 'fountain', 'squirting',
            'made me squirt', 'squirted everywhere'
        ],
        'threesome': [
            'threesome', 'mmf', 'mfm', 'ffm', '3some', 'three of us',
            'two guys', 'two girls', 'shared me'
        ],
        'bbc': [
            'bbc', 'big black', 'hung black', 'black cock',
            'first bbc', 'bbc destroyed'
        ],
        'deepthroat': [
            'deepthroat', 'throat fuck', 'gagging deep', 'down my throat',
            'choking on', 'throat pie'
        ],
        'lesbian': [
            'g/g', 'girl on girl', 'lesbian', 'her tongue', 'she licked',
            'ate her', 'pussy eating', 'scissoring', 'tribbing'
        ],
        'facial': [
            'facial', 'cum on my face', 'cum all over my face',
            'face full of cum', 'covered my face'
        ],
        'double_penetration': [
            'dp', 'double penetration', 'both holes', 'filled both',
            'dvp', 'dap'
        ],
        'oral': [
            'blowjob', 'bj', 'sucking cock', 'head', 'giving head',
            'sucking him', 'mouth full', 'oral'
        ],
        'cumshot': [
            'cumshot', 'cum shot', 'money shot', 'huge load',
            'covered in cum', 'cum everywhere'
        ],
        'gangbang': [
            'gangbang', 'gang bang', 'multiple guys', 'group sex',
            'ran train', 'passed around'
        ],
    }

    def validate(
        self,
        caption: str,
        vault_content: Set[str]
    ) -> ContentValidationResult:
        """
        Check if caption promises content available in vault.

        SECURITY: All text matching uses normalized forms to prevent
        Unicode bypass attacks and character substitution evasion.

        Args:
            caption: The caption text to validate
            vault_content: Set of content types available in vault
                          (e.g., {'solo', 'bj', 'anal', 'creampie'})

        Returns:
            ContentValidationResult with validation status and any risks

        Raises:
            ValidationError: If caption is empty or not a string

        Examples:
            >>> validator = ContentAuthenticityValidator()
            >>> result = validator.validate(
            ...     "watch me squirt",
            ...     {'solo', 'squirt'}
            ... )
            >>> result.is_authentic
            True

            >>> result = validator.validate(
            ...     "anal video with creampie",
            ...     {'solo', 'bj'}
            ... )
            >>> result.blocked
            True
            >>> len(result.scam_risks)
            2
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

        logger.debug(
            f"Validating caption ({len(caption)} chars) against "
            f"vault with {len(vault_content)} content types"
        )

        # SECURITY: Normalize text to prevent Unicode bypass attacks
        caption_normalized = normalize_text(caption)
        warnings: list[dict] = []
        scam_risks: list[ScamRisk] = []

        for act, keywords in self.EXPLICIT_ACT_KEYWORDS.items():
            # Normalize keywords as well for consistent matching
            normalized_keywords = [normalize_text(kw) for kw in keywords]

            # Check if caption mentions this act (using normalized text)
            matched = [
                kw for kw, norm_kw in zip(keywords, normalized_keywords)
                if norm_kw in caption_normalized
            ]
            mentions_act = len(matched) > 0

            if mentions_act:
                # Check if vault has this content
                has_content = act in vault_content

                if not has_content:
                    scam_risks.append(ScamRisk(
                        act=act,
                        matched_keywords=tuple(matched),  # tuple for immutability
                        severity='CRITICAL',
                        message=f"Caption mentions '{act}' but vault has NO {act} content",
                        action_required=f"Either remove '{act}' mention OR add {act} content to vault"
                    ))
                    logger.warning(
                        f"SCAM RISK: Caption mentions '{act}' without vault content",
                        extra={
                            'act': act,
                            'matched_keywords': matched,
                            'vault_content': list(vault_content)
                        }
                    )

        # Check for numerical claims that might be misleading
        price_pattern = r'\$\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:worth|value)'
        price_matches = re.findall(price_pattern, caption.lower())
        if price_matches:
            warnings.append({
                'type': 'value_claim',
                'matches': price_matches,
                'severity': 'LOW',
                'message': 'Contains value claims - ensure they are reasonable exaggerations'
            })

        # Determine if blocking based on severity
        has_blocking_risk = any(
            risk.severity in BLOCKING_SEVERITIES
            for risk in scam_risks
        )

        # Log summary
        if scam_risks:
            logger.warning(
                f"Validation failed: {len(scam_risks)} scam risks detected",
                extra={
                    'scam_risk_count': len(scam_risks),
                    'blocked': has_blocking_risk,
                    'acts_mentioned': [risk.act for risk in scam_risks]
                }
            )
        else:
            logger.debug("Validation passed: caption is authentic")

        return ContentValidationResult(
            is_authentic=len(scam_risks) == 0,
            scam_risks=tuple(scam_risks),
            warnings=tuple(warnings),
            requires_manual_review=len(scam_risks) > 0,
            blocked=has_blocking_risk,
            recommendation='SAFE TO SCHEDULE' if len(scam_risks) == 0 else 'REQUIRES MANUAL REVIEW'
        )


def validate_caption_vault_match(
    caption: str,
    vault_content: Set[str]
) -> ContentValidationResult:
    """
    Convenience function for caption-vault validation.

    This is the recommended entry point for most use cases.

    Args:
        caption: The caption text to validate
        vault_content: Set of content types available in vault

    Returns:
        ContentValidationResult with validation status and risks

    Raises:
        ValidationError: If caption is empty or not a string

    Examples:
        >>> result = validate_caption_vault_match(
        ...     "watch me squirt everywhere",
        ...     {'solo', 'squirt'}
        ... )
        >>> result.is_authentic
        True

        >>> result = validate_caption_vault_match(
        ...     "anal and creampie",
        ...     {'solo', 'bj'}
        ... )
        >>> result.blocked
        True
    """
    validator = ContentAuthenticityValidator()
    return validator.validate(caption, vault_content)
