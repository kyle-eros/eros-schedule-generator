#!/usr/bin/env python3
"""
Send Type Classifier for EROS Schedule Generator

Classifies text content into one of 22 send types using structural detection rules,
keyword patterns, and length-based heuristics.

Send Types (22 total):
- Revenue (9): ppv_unlock, ppv_wall, tip_goal, bundle, flash_bundle, game_post,
               first_to_tip, vip_program, snapchat_bundle
- Engagement (9): link_drop, wall_link_drop, bump_normal, bump_descriptive,
                  bump_text_only, bump_flyer, dm_farm, like_farm, live_promo
- Retention (4): renew_on_post, renew_on_message, ppv_followup, expired_winback

Usage:
    from classify_send_types import SendTypeClassifier

    classifier = SendTypeClassifier()
    send_type, confidence = classifier.classify("unlock this exclusive video!", price=9.99)
    print(f"Classified as: {send_type} (confidence: {confidence:.2f})")

Version: 1.0.0
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClassificationResult:
    """Result of a send type classification."""
    send_type_key: str
    confidence: float
    category: str
    caption_type: str
    matched_patterns: list[str] = field(default_factory=list)
    length_hint: Optional[str] = None


class SendTypeClassifier:
    """
    Classifies text content into EROS send types.

    Uses a priority-based classification system:
    1. Structural detection (price, links)
    2. Keyword pattern matching
    3. Length-based heuristics
    """

    # Send type to caption_type mapping
    SEND_TYPE_TO_CAPTION_TYPE: dict[str, str] = {
        # Revenue types
        "ppv_unlock": "ppv_unlock",
        "ppv_wall": "ppv_unlock",
        "tip_goal": "tip_request",
        "bundle": "ppv_unlock",
        "flash_bundle": "ppv_unlock",
        "game_post": "engagement_hook",
        "first_to_tip": "tip_request",
        "vip_program": "exclusive_offer",
        "snapchat_bundle": "ppv_unlock",
        # Engagement types
        "link_drop": "engagement_hook",
        "wall_link_drop": "engagement_hook",
        "bump_normal": "flirty_opener",
        "bump_descriptive": "descriptive_tease",
        "bump_text_only": "flirty_opener",
        "bump_flyer": "descriptive_tease",
        "dm_farm": "engagement_hook",
        "like_farm": "engagement_hook",
        "live_promo": "engagement_hook",
        # Retention types
        "renew_on_post": "renewal_pitch",
        "renew_on_message": "renewal_pitch",
        "ppv_followup": "ppv_followup",
        "expired_winback": "renewal_pitch",
    }

    # Send type categories
    SEND_TYPE_CATEGORIES: dict[str, str] = {
        # Revenue
        "ppv_unlock": "revenue",
        "ppv_wall": "revenue",
        "tip_goal": "revenue",
        "bundle": "revenue",
        "flash_bundle": "revenue",
        "game_post": "revenue",
        "first_to_tip": "revenue",
        "vip_program": "revenue",
        "snapchat_bundle": "revenue",
        # Engagement
        "link_drop": "engagement",
        "wall_link_drop": "engagement",
        "bump_normal": "engagement",
        "bump_descriptive": "engagement",
        "bump_text_only": "engagement",
        "bump_flyer": "engagement",
        "dm_farm": "engagement",
        "like_farm": "engagement",
        "live_promo": "engagement",
        # Retention
        "renew_on_post": "retention",
        "renew_on_message": "retention",
        "ppv_followup": "retention",
        "expired_winback": "retention",
    }

    # Keyword patterns for each send type (compiled regex patterns)
    PATTERNS: dict[str, list[re.Pattern]] = {}

    def __init__(self) -> None:
        """Initialize the classifier with compiled regex patterns."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for efficient matching."""
        pattern_definitions: dict[str, list[str]] = {
            # Revenue types (in priority order)
            "ppv_unlock": [
                r"\bunlock\b",
                r"\bppv\b",
                r"buy\s+to\s+see",
                r"purchase\s+to\s+(see|view|watch)",
                r"tip\s+to\s+unlock",
                r"unlock\s+(this|my|the)",
                r"exclusive\s+(video|content|clip)",
                r"\$\d+\s*(to|for)\s*(unlock|see|view)",
            ],
            "bundle": [
                r"\bbundle\b",
                r"\bpack\b",
                r"\bcollection\b",
                r"\d+\s*(vids?|videos?|pics?|photos?|clips?)",
                r"(mega|ultimate|complete)\s+(bundle|pack|collection)",
                r"\d+\s+(for|@)\s+\$\d+",
            ],
            "flash_bundle": [
                r"(limited|flash)\s*(time|sale|offer|bundle)",
                r"today\s+only",
                r"\bhurry\b",
                r"(ends?|expires?)\s+(soon|today|tonight|midnight)",
                r"(first|next)\s+\d+\s+(only|buyers?)",
                r"(quick|fast|rapid)\s+(sale|deal)",
                r"(won't|wont)\s+last",
            ],
            "tip_goal": [
                r"tip\s+\$?\d+",
                r"tip\s+goal",
                r"\$\d+\s+to\s+unlock",
                r"goal\s*:\s*\$?\d+",
                r"reach(ing)?\s+(the\s+)?goal",
                r"help\s+(me\s+)?reach",
                r"community\s+goal",
            ],
            "game_post": [
                r"\bspin\b",
                r"\bwheel\b",
                r"\bgame\b",
                r"pick\s+a\s+(number|card|option)",
                r"choose\s+(a\s+)?(number|card)",
                r"mystery\s+(box|prize|reward)",
                r"roll\s+(the\s+)?dice",
                r"play\s+(with\s+me|now|today)",
            ],
            "first_to_tip": [
                r"first\s+to\s+tip",
                r"(fastest|quickest)\s+(tip|tipper)",
                r"race\s+to\s+tip",
                r"be\s+the\s+first",
                r"winner\s+(gets?|receives?|wins?)",
                r"compete\s+to\s+(win|tip)",
            ],
            "vip_program": [
                r"\bvip\b",
                r"\$200\s+tip",
                r"exclusive\s+tier",
                r"(premium|elite|vip)\s+(access|tier|member)",
                r"inner\s+circle",
                r"(top|best)\s+(fan|supporter|tipper)",
                r"lifetime\s+(access|member)",
            ],
            "snapchat_bundle": [
                r"\bsnapchat\b",
                r"\bsnap\b",
                r"throwback\s+(snap|content|pic)",
                r"sc\s+(content|bundle|pics?)",
                r"from\s+my\s+snap",
                r"(old|vintage|classic)\s+snap",
            ],
            # Engagement types
            "link_drop": [
                r"https?://",
                r"\blink\b",
                r"check\s+(this|it)\s+out",
                r"click\s+(here|below|the\s+link)",
                r"tap\s+(here|the\s+link)",
                r"see\s+(more|it)\s+(here|below)",
            ],
            "wall_link_drop": [
                r"(wall|feed)\s+(post|link|content)",
                r"on\s+(my\s+)?(wall|feed)",
                r"check\s+(my\s+)?(wall|feed|profile)",
                r"posted\s+on\s+(my\s+)?(wall|feed)",
                r"(new|latest)\s+on\s+(my\s+)?wall",
            ],
            "bump_flyer": [
                r"\bflyer\b",
                r"\bgif\b",
                r"(announcement|promo)\s+(flyer|gif)",
                r"special\s+(announcement|promo)",
                r"(new|big)\s+announcement",
            ],
            "dm_farm": [
                r"dm\s+me",
                r"message\s+me",
                r"slide\s+(in|into)",
                r"(send|drop)\s+(me\s+)?(a\s+)?dm",
                r"hit\s+(me\s+)?up",
                r"in\s+my\s+dms?",
                r"reply\s+to\s+this",
            ],
            "like_farm": [
                r"like\s+(this|all|my)",
                r"like\s+all\s+(my\s+)?(posts?|content)",
                r"\bheart\b",
                r"double\s+tap",
                r"show\s+(some\s+)?love",
                r"(hit|press)\s+the\s+heart",
                r"like\s+if\s+you",
            ],
            "live_promo": [
                r"\blive\b",
                r"going\s+live",
                r"\bstream(ing)?\b",
                r"live\s+(show|stream|session)",
                r"join\s+(me\s+)?(live|the\s+stream)",
                r"(tonight|today)\s+at\s+\d+",
                r"broadcast(ing)?",
            ],
            # Retention types
            "renew_on_post": [
                r"\brenew\b",
                r"enable\s+(auto)?renew",
                r"turn\s+on\s+renew",
                r"subscription\s+renew",
                r"stay\s+subscribed",
            ],
            "renew_on_message": [
                r"\brenew\b",
                r"(your\s+)?subscription\s+(is\s+)?(expir|end|about\s+to)",
                r"don't\s+(let|miss)\s+(it\s+)?expire",
                r"keep\s+(your\s+)?access",
                r"(renew|stay)\s+(to|and)\s+(keep|continue)",
                r"about\s+to\s+expire",
                r"expiring\s+soon",
            ],
            "ppv_followup": [
                r"did\s+you\s+(see|check|watch|open)",
                r"still\s+available",
                r"(haven't|havent)\s+(seen|opened|watched)",
                r"(waiting|looking)\s+for\s+(you|your)",
                r"(last|final)\s+chance",
                r"reminder\s*(:|to|about)",
                r"in\s+case\s+you\s+missed",
                r"sent\s+(you\s+)?(earlier|before|this\s+morning)",
            ],
            "expired_winback": [
                r"miss\s+(you|having\s+you)",
                r"come\s+back",
                r"\bexpired\b",
                r"(re)?subscribe",
                r"(been|it's\s+been)\s+(a\s+)?while",
                r"where\s+(have\s+)?you\s+been",
                r"(welcome|come)\s+back",
                r"we\s+miss\s+you",
            ],
        }

        # Compile all patterns (case-insensitive)
        self.PATTERNS = {
            send_type: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for send_type, patterns in pattern_definitions.items()
        }

        # Bump patterns need special handling based on length
        self._bump_normal_patterns = [
            re.compile(r"(hey|hi|hello|hii+|heyy+)", re.IGNORECASE),
            re.compile(r"(babe|baby|daddy|hun|sweetie)", re.IGNORECASE),
            re.compile(r"(horny|wet|turned\s+on|thinking\s+of\s+you)", re.IGNORECASE),
            re.compile(r"(wyd|what('?s|\s+are)\s+you\s+doing)", re.IGNORECASE),
            re.compile(r"(miss(ing)?\s+you|want\s+you)", re.IGNORECASE),
            re.compile(r"\?\s*$", re.IGNORECASE),  # Ends with question mark
        ]

        self._bump_descriptive_patterns = [
            re.compile(r"(imagine|picture\s+this|let\s+me\s+tell)", re.IGNORECASE),
            re.compile(r"(fantasy|dream|scenario)", re.IGNORECASE),
            re.compile(r"(story|about\s+last|remember\s+when)", re.IGNORECASE),
            re.compile(r"(slowly|gently|softly|firmly)", re.IGNORECASE),  # Descriptive adverbs
            re.compile(r"(body|skin|lips|hands|touch|running)", re.IGNORECASE),
            re.compile(r"(undress|strip|take\s+off|removing)", re.IGNORECASE),
            re.compile(r"(as\s+you\s+watch|while\s+you|for\s+you)", re.IGNORECASE),
        ]

    def _match_patterns(
        self,
        text: str,
        patterns: list[re.Pattern],
    ) -> tuple[int, list[str]]:
        """
        Count pattern matches and return matched pattern strings.

        Args:
            text: Text to search.
            patterns: List of compiled patterns.

        Returns:
            Tuple of (match_count, list_of_matched_patterns).
        """
        matched = []
        for pattern in patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)
        return len(matched), matched

    def _calculate_length_hint(self, text_length: int) -> str:
        """
        Determine length category for bump type heuristics.

        Args:
            text_length: Length of text in characters.

        Returns:
            Length category string.
        """
        if text_length < 60:
            return "very_short"
        elif text_length < 100:
            return "short"
        elif text_length < 200:
            return "medium"
        else:
            return "long"

    def _detect_bump_type(
        self,
        text: str,
        text_length: int,
    ) -> tuple[str, float, list[str]]:
        """
        Determine which bump type best matches the text.

        Args:
            text: The text to classify.
            text_length: Pre-computed text length.

        Returns:
            Tuple of (bump_type, confidence, matched_patterns).
        """
        # Check for flyer/gif mentions first (highest priority for bump_flyer)
        flyer_count, flyer_matched = self._match_patterns(
            text, self.PATTERNS.get("bump_flyer", [])
        )
        if flyer_count > 0:
            return "bump_flyer", min(0.85 + (flyer_count * 0.05), 0.95), flyer_matched

        # Check descriptive patterns
        desc_count, desc_matched = self._match_patterns(
            text, self._bump_descriptive_patterns
        )

        # Check normal bump patterns
        normal_count, normal_matched = self._match_patterns(
            text, self._bump_normal_patterns
        )

        # Length-based classification
        if text_length < 60:
            # Very short = text_only
            return "bump_text_only", 0.80, ["length<60"]
        elif text_length < 100:
            # Short = normal bump (flirty question/statement)
            if normal_count > 0:
                return "bump_normal", 0.75 + (normal_count * 0.05), normal_matched
            return "bump_normal", 0.65, ["length:60-100"]
        elif text_length < 200:
            # Medium length - could be descriptive or normal
            if desc_count >= 2:
                return "bump_descriptive", 0.75 + (desc_count * 0.05), desc_matched
            elif normal_count > desc_count:
                return "bump_normal", 0.65, normal_matched
            else:
                return "bump_descriptive", 0.60, desc_matched or ["length:100-200"]
        else:
            # Long = descriptive bump
            if desc_count > 0:
                return "bump_descriptive", 0.80 + (desc_count * 0.03), desc_matched
            return "bump_descriptive", 0.70, ["length>200"]

    def classify(
        self,
        text: str,
        price: Optional[float] = None,
        has_link: bool = False,
    ) -> tuple[str, float]:
        """
        Classify text into a send type.

        Args:
            text: The caption/message text to classify.
            price: Optional price (> 0 indicates PPV content).
            has_link: Whether the message contains a link.

        Returns:
            Tuple of (send_type_key, confidence_score).
        """
        result = self.classify_detailed(text, price, has_link)
        return result.send_type_key, result.confidence

    def classify_detailed(
        self,
        text: str,
        price: Optional[float] = None,
        has_link: bool = False,
    ) -> ClassificationResult:
        """
        Classify text with detailed result information.

        Args:
            text: The caption/message text to classify.
            price: Optional price (> 0 indicates PPV content).
            has_link: Whether the message contains a link.

        Returns:
            ClassificationResult with full classification details.
        """
        text = text.strip()
        text_length = len(text)
        text_lower = text.lower()
        length_hint = self._calculate_length_hint(text_length)

        # Track best match
        best_type: str = "bump_normal"  # Default
        best_confidence: float = 0.0
        best_patterns: list[str] = []

        # =================================================================
        # Priority 1: Structural detection (price, links)
        # =================================================================

        # Price > 0 strongly indicates PPV content
        if price is not None and price > 0:
            # Check for bundle patterns
            bundle_count, bundle_matched = self._match_patterns(
                text, self.PATTERNS["bundle"]
            )
            flash_count, flash_matched = self._match_patterns(
                text, self.PATTERNS["flash_bundle"]
            )

            if flash_count > 0 and bundle_count > 0:
                return ClassificationResult(
                    send_type_key="flash_bundle",
                    confidence=0.95,
                    category="revenue",
                    caption_type="ppv_unlock",
                    matched_patterns=flash_matched + bundle_matched,
                    length_hint=length_hint,
                )
            elif bundle_count > 0:
                return ClassificationResult(
                    send_type_key="bundle",
                    confidence=0.90,
                    category="revenue",
                    caption_type="ppv_unlock",
                    matched_patterns=bundle_matched,
                    length_hint=length_hint,
                )
            else:
                # Default to ppv_unlock for priced content
                ppv_count, ppv_matched = self._match_patterns(
                    text, self.PATTERNS["ppv_unlock"]
                )
                return ClassificationResult(
                    send_type_key="ppv_unlock",
                    confidence=0.90 if ppv_count > 0 else 0.85,
                    category="revenue",
                    caption_type="ppv_unlock",
                    matched_patterns=ppv_matched or ["price>0"],
                    length_hint=length_hint,
                )

        # =================================================================
        # Priority 2: Revenue types (in order of specificity)
        # =================================================================

        # Check VIP program first (very specific)
        vip_count, vip_matched = self._match_patterns(
            text, self.PATTERNS["vip_program"]
        )
        if vip_count >= 2 or (vip_count == 1 and "$200" in text):
            return ClassificationResult(
                send_type_key="vip_program",
                confidence=min(0.80 + (vip_count * 0.05), 0.95),
                category="revenue",
                caption_type="exclusive_offer",
                matched_patterns=vip_matched,
                length_hint=length_hint,
            )

        # Check snapchat bundle (specific)
        snap_count, snap_matched = self._match_patterns(
            text, self.PATTERNS["snapchat_bundle"]
        )
        if snap_count >= 1:
            return ClassificationResult(
                send_type_key="snapchat_bundle",
                confidence=min(0.80 + (snap_count * 0.05), 0.95),
                category="revenue",
                caption_type="ppv_unlock",
                matched_patterns=snap_matched,
                length_hint=length_hint,
            )

        # Check first_to_tip
        first_count, first_matched = self._match_patterns(
            text, self.PATTERNS["first_to_tip"]
        )
        if first_count >= 1:
            return ClassificationResult(
                send_type_key="first_to_tip",
                confidence=min(0.80 + (first_count * 0.05), 0.95),
                category="revenue",
                caption_type="tip_request",
                matched_patterns=first_matched,
                length_hint=length_hint,
            )

        # Check game_post
        game_count, game_matched = self._match_patterns(
            text, self.PATTERNS["game_post"]
        )
        if game_count >= 2 or (game_count == 1 and "spin" in text_lower):
            return ClassificationResult(
                send_type_key="game_post",
                confidence=min(0.75 + (game_count * 0.05), 0.95),
                category="revenue",
                caption_type="engagement_hook",
                matched_patterns=game_matched,
                length_hint=length_hint,
            )

        # Check flash_bundle (urgency + bundle)
        flash_count, flash_matched = self._match_patterns(
            text, self.PATTERNS["flash_bundle"]
        )
        bundle_count, bundle_matched = self._match_patterns(
            text, self.PATTERNS["bundle"]
        )
        if flash_count > 0 and bundle_count > 0:
            return ClassificationResult(
                send_type_key="flash_bundle",
                confidence=min(0.85 + (flash_count * 0.03), 0.95),
                category="revenue",
                caption_type="ppv_unlock",
                matched_patterns=flash_matched + bundle_matched,
                length_hint=length_hint,
            )

        # Check bundle
        if bundle_count >= 2 or (bundle_count == 1 and re.search(r"\d+\s*(vids?|videos?|pics?)", text_lower)):
            return ClassificationResult(
                send_type_key="bundle",
                confidence=min(0.75 + (bundle_count * 0.05), 0.90),
                category="revenue",
                caption_type="ppv_unlock",
                matched_patterns=bundle_matched,
                length_hint=length_hint,
            )

        # Check tip_goal
        tip_count, tip_matched = self._match_patterns(
            text, self.PATTERNS["tip_goal"]
        )
        if tip_count >= 1:
            return ClassificationResult(
                send_type_key="tip_goal",
                confidence=min(0.80 + (tip_count * 0.05), 0.95),
                category="revenue",
                caption_type="tip_request",
                matched_patterns=tip_matched,
                length_hint=length_hint,
            )

        # Check ppv_unlock
        ppv_count, ppv_matched = self._match_patterns(
            text, self.PATTERNS["ppv_unlock"]
        )
        if ppv_count >= 2:
            return ClassificationResult(
                send_type_key="ppv_unlock",
                confidence=min(0.80 + (ppv_count * 0.03), 0.95),
                category="revenue",
                caption_type="ppv_unlock",
                matched_patterns=ppv_matched,
                length_hint=length_hint,
            )

        # =================================================================
        # Priority 3: Retention types
        # =================================================================

        # Check expired_winback
        winback_count, winback_matched = self._match_patterns(
            text, self.PATTERNS["expired_winback"]
        )
        if winback_count >= 2 or (winback_count == 1 and "miss" in text_lower):
            return ClassificationResult(
                send_type_key="expired_winback",
                confidence=min(0.80 + (winback_count * 0.05), 0.95),
                category="retention",
                caption_type="renewal_pitch",
                matched_patterns=winback_matched,
                length_hint=length_hint,
            )

        # Check renew_on_message BEFORE ppv_followup (subscription expiration context)
        renew_msg_count, renew_msg_matched = self._match_patterns(
            text, self.PATTERNS["renew_on_message"]
        )
        # Specific subscription/expiration indicators
        subscription_indicators = ["subscription", "expire", "expiring", "about to"]
        has_subscription_context = any(ind in text_lower for ind in subscription_indicators)

        if renew_msg_count >= 1 and has_subscription_context:
            return ClassificationResult(
                send_type_key="renew_on_message",
                confidence=min(0.80 + (renew_msg_count * 0.05), 0.95),
                category="retention",
                caption_type="renewal_pitch",
                matched_patterns=renew_msg_matched,
                length_hint=length_hint,
            )

        # Check ppv_followup
        followup_count, followup_matched = self._match_patterns(
            text, self.PATTERNS["ppv_followup"]
        )
        if followup_count >= 1:
            return ClassificationResult(
                send_type_key="ppv_followup",
                confidence=min(0.75 + (followup_count * 0.05), 0.90),
                category="retention",
                caption_type="ppv_followup",
                matched_patterns=followup_matched,
                length_hint=length_hint,
            )

        # Check renew_on_post
        renew_post_count, renew_post_matched = self._match_patterns(
            text, self.PATTERNS["renew_on_post"]
        )

        # If has personal/DM context indicators, use renew_on_message
        dm_indicators = ["your", "you", "don't let", "keep your"]
        has_dm_context = any(ind in text_lower for ind in dm_indicators)

        if renew_msg_count >= 1 and has_dm_context:
            return ClassificationResult(
                send_type_key="renew_on_message",
                confidence=min(0.75 + (renew_msg_count * 0.05), 0.90),
                category="retention",
                caption_type="renewal_pitch",
                matched_patterns=renew_msg_matched,
                length_hint=length_hint,
            )
        elif renew_post_count >= 1:
            return ClassificationResult(
                send_type_key="renew_on_post",
                confidence=min(0.70 + (renew_post_count * 0.05), 0.85),
                category="retention",
                caption_type="renewal_pitch",
                matched_patterns=renew_post_matched,
                length_hint=length_hint,
            )

        # =================================================================
        # Priority 4: Engagement types
        # =================================================================

        # Check live_promo (specific)
        live_count, live_matched = self._match_patterns(
            text, self.PATTERNS["live_promo"]
        )
        if live_count >= 1:
            return ClassificationResult(
                send_type_key="live_promo",
                confidence=min(0.80 + (live_count * 0.05), 0.95),
                category="engagement",
                caption_type="engagement_hook",
                matched_patterns=live_matched,
                length_hint=length_hint,
            )

        # Check like_farm
        like_count, like_matched = self._match_patterns(
            text, self.PATTERNS["like_farm"]
        )
        if like_count >= 1:
            return ClassificationResult(
                send_type_key="like_farm",
                confidence=min(0.75 + (like_count * 0.05), 0.90),
                category="engagement",
                caption_type="engagement_hook",
                matched_patterns=like_matched,
                length_hint=length_hint,
            )

        # Check dm_farm
        dm_count, dm_matched = self._match_patterns(
            text, self.PATTERNS["dm_farm"]
        )
        if dm_count >= 1:
            return ClassificationResult(
                send_type_key="dm_farm",
                confidence=min(0.75 + (dm_count * 0.05), 0.90),
                category="engagement",
                caption_type="engagement_hook",
                matched_patterns=dm_matched,
                length_hint=length_hint,
            )

        # Check wall_link_drop (wall context + link)
        wall_count, wall_matched = self._match_patterns(
            text, self.PATTERNS["wall_link_drop"]
        )
        link_count, link_matched = self._match_patterns(
            text, self.PATTERNS["link_drop"]
        )

        if wall_count >= 1:
            return ClassificationResult(
                send_type_key="wall_link_drop",
                confidence=min(0.75 + (wall_count * 0.05), 0.90),
                category="engagement",
                caption_type="engagement_hook",
                matched_patterns=wall_matched,
                length_hint=length_hint,
            )

        # Check link_drop (short + has link)
        if has_link or link_count >= 1:
            # Short link drops
            if text_length < 100:
                return ClassificationResult(
                    send_type_key="link_drop",
                    confidence=0.80 if link_count > 0 else 0.70,
                    category="engagement",
                    caption_type="engagement_hook",
                    matched_patterns=link_matched or ["has_link"],
                    length_hint=length_hint,
                )

        # =================================================================
        # Priority 5: Bump types (length-based heuristics)
        # =================================================================

        # First check for explicit bump_flyer patterns
        flyer_count, flyer_matched = self._match_patterns(
            text, self.PATTERNS.get("bump_flyer", [])
        )
        if flyer_count > 0:
            return ClassificationResult(
                send_type_key="bump_flyer",
                confidence=min(0.80 + (flyer_count * 0.05), 0.95),
                category="engagement",
                caption_type="descriptive_tease",
                matched_patterns=flyer_matched,
                length_hint=length_hint,
            )

        # Use bump type detection logic
        bump_type, bump_conf, bump_matched = self._detect_bump_type(text, text_length)

        return ClassificationResult(
            send_type_key=bump_type,
            confidence=bump_conf,
            category="engagement",
            caption_type=self.SEND_TYPE_TO_CAPTION_TYPE.get(bump_type, "flirty_opener"),
            matched_patterns=bump_matched,
            length_hint=length_hint,
        )

    def classify_batch(
        self,
        texts: list[str],
        prices: Optional[list[Optional[float]]] = None,
        has_links: Optional[list[bool]] = None,
    ) -> list[tuple[str, float]]:
        """
        Classify multiple texts in batch.

        Args:
            texts: List of texts to classify.
            prices: Optional list of prices (same length as texts).
            has_links: Optional list of link indicators (same length as texts).

        Returns:
            List of (send_type_key, confidence) tuples.
        """
        if prices is None:
            prices = [None] * len(texts)
        if has_links is None:
            has_links = [False] * len(texts)

        if len(texts) != len(prices) or len(texts) != len(has_links):
            raise ValueError(
                "texts, prices, and has_links must have the same length"
            )

        results = []
        for text, price, has_link in zip(texts, prices, has_links):
            result = self.classify(text, price, has_link)
            results.append(result)

        return results

    def classify_batch_detailed(
        self,
        texts: list[str],
        prices: Optional[list[Optional[float]]] = None,
        has_links: Optional[list[bool]] = None,
    ) -> list[ClassificationResult]:
        """
        Classify multiple texts with detailed results.

        Args:
            texts: List of texts to classify.
            prices: Optional list of prices (same length as texts).
            has_links: Optional list of link indicators (same length as texts).

        Returns:
            List of ClassificationResult objects.
        """
        if prices is None:
            prices = [None] * len(texts)
        if has_links is None:
            has_links = [False] * len(texts)

        if len(texts) != len(prices) or len(texts) != len(has_links):
            raise ValueError(
                "texts, prices, and has_links must have the same length"
            )

        results = []
        for text, price, has_link in zip(texts, prices, has_links):
            result = self.classify_detailed(text, price, has_link)
            results.append(result)

        return results

    def get_caption_type(self, send_type_key: str) -> str:
        """
        Get the corresponding caption_type for a send_type_key.

        Args:
            send_type_key: The send type key.

        Returns:
            The caption_type for database insertion.
        """
        return self.SEND_TYPE_TO_CAPTION_TYPE.get(send_type_key, "flirty_opener")

    def get_category(self, send_type_key: str) -> str:
        """
        Get the category for a send_type_key.

        Args:
            send_type_key: The send type key.

        Returns:
            Category: "revenue", "engagement", or "retention".
        """
        return self.SEND_TYPE_CATEGORIES.get(send_type_key, "engagement")


# =============================================================================
# Convenience functions
# =============================================================================

_default_classifier: Optional[SendTypeClassifier] = None


def get_classifier() -> SendTypeClassifier:
    """Get or create the default classifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = SendTypeClassifier()
    return _default_classifier


def classify_send_type(
    text: str,
    price: Optional[float] = None,
    has_link: bool = False,
) -> tuple[str, float]:
    """
    Convenience function to classify a single text.

    Args:
        text: The text to classify.
        price: Optional price.
        has_link: Whether the text contains a link.

    Returns:
        Tuple of (send_type_key, confidence).
    """
    return get_classifier().classify(text, price, has_link)


def classify_send_type_detailed(
    text: str,
    price: Optional[float] = None,
    has_link: bool = False,
) -> ClassificationResult:
    """
    Convenience function to classify with detailed result.

    Args:
        text: The text to classify.
        price: Optional price.
        has_link: Whether the text contains a link.

    Returns:
        ClassificationResult with full details.
    """
    return get_classifier().classify_detailed(text, price, has_link)


# =============================================================================
# CLI and testing
# =============================================================================

def _run_tests() -> None:
    """Run basic classification tests."""
    classifier = SendTypeClassifier()

    test_cases = [
        # Revenue types
        ("Unlock this exclusive video! $15 to see", 15.0, False, "ppv_unlock"),
        ("Limited time only! First 10 buyers get 50% off this bundle!", None, False, "flash_bundle"),
        ("Spin the wheel to win prizes! $5 to play", None, False, "game_post"),
        ("Tip $25 to unlock this special content", None, False, "tip_goal"),
        ("First to tip $50 wins a custom video!", None, False, "first_to_tip"),
        ("Join my VIP tier - $200 tip for lifetime access", None, False, "vip_program"),
        ("Throwback snap bundle! My old snapchat pics", None, False, "snapchat_bundle"),
        ("Get this bundle: 10 vids + 20 pics for $30", None, False, "bundle"),
        # Engagement types
        ("Check this out! https://example.com", None, True, "link_drop"),
        ("DM me for a free surprise!", None, False, "dm_farm"),
        ("Like all my posts for a special reward!", None, False, "like_farm"),
        ("Going live tonight at 9pm!", None, False, "live_promo"),
        ("New post on my wall - check it out!", None, False, "wall_link_drop"),
        ("hey babe wyd?", None, False, "bump_text_only"),
        ("What are you doing tonight daddy? I'm so horny and thinking of you...", None, False, "bump_normal"),
        ("Imagine me slowly undressing for you, running my hands over my body as you watch. My fingers trace along my curves, teasing you, making you want more. I can feel your eyes on me, watching every move...", None, False, "bump_descriptive"),
        # Retention types
        ("Turn on auto-renew to never miss my content!", None, False, "renew_on_post"),
        ("Your subscription is about to expire! Don't miss out", None, False, "renew_on_message"),
        ("Did you see the video I sent earlier? Still available!", None, False, "ppv_followup"),
        ("I miss you so much! Come back and see what you've been missing", None, False, "expired_winback"),
    ]

    print("=" * 70)
    print("SEND TYPE CLASSIFIER - TEST RESULTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for text, price, has_link, expected in test_cases:
        result = classifier.classify_detailed(text, price, has_link)
        status = "PASS" if result.send_type_key == expected else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"\n{status}: Expected '{expected}', Got '{result.send_type_key}'")
        print(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Category: {result.category}")
        print(f"  Caption Type: {result.caption_type}")
        if result.matched_patterns:
            print(f"  Patterns: {', '.join(result.matched_patterns[:3])}")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _run_tests()
    elif len(sys.argv) > 1:
        # Classify provided text
        text = " ".join(sys.argv[1:])
        classifier = SendTypeClassifier()
        result = classifier.classify_detailed(text)

        print(f"\nText: {text}")
        print(f"Send Type: {result.send_type_key}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Category: {result.category}")
        print(f"Caption Type: {result.caption_type}")
        print(f"Length Hint: {result.length_hint}")
        if result.matched_patterns:
            print(f"Matched Patterns: {', '.join(result.matched_patterns)}")
    else:
        print("EROS Send Type Classifier")
        print("\nUsage:")
        print("  python classify_send_types.py --test           Run test suite")
        print("  python classify_send_types.py <text>           Classify text")
        print("\nExample:")
        print('  python classify_send_types.py "Unlock this exclusive video for $15!"')
