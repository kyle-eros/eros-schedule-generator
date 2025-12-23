#!/usr/bin/env python3
"""
Content Type Classifier for EROS System

Classifies caption text into one of 37 content types using keyword pattern matching.
Supports both single caption classification and batch processing for efficiency.

Content Type Categories (37 total):
- explicit (11 types): anal, creampie, squirt, boy_girl_girl, girl_girl_girl,
  girl_girl, deepthroat, blowjob, deepthroat_dildo, blowjob_dildo, boy_girl
- solo_explicit (4 types): solo, pussy_play, toy_play, tits_play
- interactive (2 types): joi, dick_rating
- fetish (2 types): dom_sub, feet
- themed (6 types): shower_bath, pool_outdoor, lingerie, story_roleplay, pov, gfe
- promotional (5 types): bundle_offer, flash_sale, exclusive_content, behind_scenes, live_stream
- engagement (3 types): teasing, tip_request, renewal_retention
- implied (4 types): implied_pussy_play, implied_solo, implied_tits_play, implied_toy_play

Classification Priority Order (most specific first):
explicit > solo_explicit > interactive > fetish > themed > promotional > engagement > implied

Usage:
    from classify_content_types import ContentTypeClassifier

    classifier = ContentTypeClassifier()
    content_type_id, confidence = classifier.classify("Watch me take it deep...")

    # Batch processing
    results = classifier.classify_batch(["caption1", "caption2", "caption3"])
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class PatternMatch:
    """Result of a pattern match with metadata."""

    pattern: str
    confidence_boost: float
    is_phrase: bool


@dataclass
class ClassificationResult:
    """Result of content type classification."""

    content_type_id: int
    content_type_name: str
    confidence: float
    category: str
    matched_patterns: list[str] = field(default_factory=list)

    def as_tuple(self) -> tuple[int, float]:
        """Return as simple tuple for backward compatibility."""
        return (self.content_type_id, self.confidence)


class ContentTypeClassifier:
    """
    Classifier for EROS 37 content types using keyword pattern matching.

    Uses a multi-tier confidence scoring system:
    - HIGH (0.90+): Explicit multi-word phrases with strong indicators
    - MEDIUM (0.75-0.89): Single strong keywords or double matches
    - LOW (0.60-0.74): Contextual keywords requiring more context

    Priority ordering ensures more specific content types are matched first,
    preventing general terms from overshadowing specific classifications.

    Attributes:
        CONTENT_TYPE_IDS: Mapping of content type names to database IDs
        CATEGORY_PRIORITY: Processing order for category groups
        PATTERNS: Keyword patterns for each content type
    """

    # Content type name to database ID mapping
    CONTENT_TYPE_IDS: dict[str, int] = {
        # Explicit (1-11)
        "anal": 1,
        "creampie": 2,
        "squirt": 3,
        "boy_girl_girl": 4,
        "girl_girl_girl": 5,
        "girl_girl": 6,
        "deepthroat": 7,
        "blowjob": 8,
        "deepthroat_dildo": 9,
        "blowjob_dildo": 10,
        "boy_girl": 11,
        # Interactive (12, 15)
        "joi": 12,
        "dick_rating": 15,
        # Fetish (13-14)
        "feet": 13,
        "dom_sub": 14,
        # Solo Explicit (16-19)
        "pussy_play": 16,
        "toy_play": 17,
        "tits_play": 18,
        "solo": 19,
        # Themed (20-25)
        "shower_bath": 20,
        "pool_outdoor": 21,
        "lingerie": 22,
        "story_roleplay": 23,
        "pov": 24,
        "gfe": 25,
        # Promotional (26-30)
        "bundle_offer": 26,
        "flash_sale": 27,
        "exclusive_content": 28,
        "behind_scenes": 29,
        "live_stream": 30,
        # Engagement (31-33)
        "teasing": 31,
        "tip_request": 32,
        "renewal_retention": 33,
        # Implied (34-37)
        "implied_pussy_play": 34,
        "implied_solo": 35,
        "implied_tits_play": 36,
        "implied_toy_play": 37,
    }

    # Reverse mapping for ID to name lookup
    CONTENT_TYPE_NAMES: dict[int, str] = {v: k for k, v in CONTENT_TYPE_IDS.items()}

    # Category for each content type
    CONTENT_TYPE_CATEGORIES: dict[str, str] = {
        "anal": "explicit", "creampie": "explicit", "squirt": "explicit",
        "boy_girl_girl": "explicit", "girl_girl_girl": "explicit", "girl_girl": "explicit",
        "deepthroat": "explicit", "blowjob": "explicit", "deepthroat_dildo": "explicit",
        "blowjob_dildo": "explicit", "boy_girl": "explicit",
        "joi": "interactive", "dick_rating": "interactive",
        "feet": "fetish", "dom_sub": "fetish",
        "pussy_play": "solo_explicit", "toy_play": "solo_explicit",
        "tits_play": "solo_explicit", "solo": "solo_explicit",
        "shower_bath": "themed", "pool_outdoor": "themed", "lingerie": "themed",
        "story_roleplay": "themed", "pov": "themed", "gfe": "themed",
        "bundle_offer": "promotional", "flash_sale": "promotional",
        "exclusive_content": "promotional", "behind_scenes": "promotional",
        "live_stream": "promotional",
        "teasing": "engagement", "tip_request": "engagement",
        "renewal_retention": "engagement",
        "implied_pussy_play": "implied", "implied_solo": "implied",
        "implied_tits_play": "implied", "implied_toy_play": "implied",
    }

    # Priority order for processing (most specific categories first)
    # This ensures explicit content is matched before generic engagement patterns
    CATEGORY_PRIORITY: list[str] = [
        "explicit",
        "solo_explicit",
        "interactive",
        "fetish",
        "themed",
        "promotional",
        "engagement",
        "implied",
    ]

    # Processing order within each category (more specific types first)
    # Types are ordered so that multi-person content matches before single-person
    TYPE_PRIORITY_ORDER: list[str] = [
        # Explicit - threesome/group first, then specific acts, then general couples
        # Dildo-specific types MUST come before generic types to avoid false matches
        "boy_girl_girl", "girl_girl_girl", "creampie", "anal", "squirt",
        "deepthroat_dildo", "blowjob_dildo", "deepthroat", "blowjob",
        "girl_girl", "boy_girl",
        # Solo Explicit - specific acts before general solo
        "pussy_play", "toy_play", "tits_play", "solo",
        # Interactive
        "joi", "dick_rating",
        # Fetish
        "dom_sub", "feet",
        # Themed
        "shower_bath", "pool_outdoor", "lingerie", "story_roleplay", "pov", "gfe",
        # Promotional
        "flash_sale", "bundle_offer", "exclusive_content", "behind_scenes", "live_stream",
        # Engagement
        "tip_request", "renewal_retention", "teasing",
        # Implied - specific before general
        "implied_pussy_play", "implied_toy_play", "implied_tits_play", "implied_solo",
    ]

    # Keyword patterns for each content type
    # Format: list of (pattern, confidence_weight, is_phrase)
    # - pattern: regex pattern to match
    # - confidence_weight: base confidence contribution (0.1-0.4)
    # - is_phrase: True if multi-word phrase (higher specificity)
    PATTERNS: dict[str, list[tuple[str, float, bool]]] = {
        # ============================================================
        # EXPLICIT CONTENT TYPES (11 types)
        # ============================================================

        "anal": [
            # HIGH CONFIDENCE - explicit phrases
            (r'\banal\s+(sex|fuck|fucking|vid|video|scene|pov|play)\b', 0.40, True),
            (r'\bass\s+(fuck|fucking|fucked|sex|pounding|pounded)\b', 0.40, True),
            (r'\bin\s+(my|her)\s+ass\b', 0.35, True),
            (r'\bfuck(ed|ing|s)?\s+(my|her)\s+ass\b', 0.40, True),
            (r'\bup\s+(my|her|the)\s+ass\b', 0.35, True),
            (r'\bbackdoor\s+(fun|action|sex|play)\b', 0.35, True),
            (r'\bbutt\s+(fuck|fucking|sex)\b', 0.35, True),
            (r'\btake(s)?\s+it\s+in\s+(my|her)\s+ass\b', 0.40, True),
            # MEDIUM CONFIDENCE - context-dependent
            (r'\banal\b(?!\s+ytics|\s+ysis)', 0.25, False),  # Avoid "analytics"
            (r'\bbooty\s+(fuck|fucking|pounded)\b', 0.30, True),
            (r'\brear\s+(entry|end)\s+(action|sex|fun)\b', 0.30, True),
        ],

        "creampie": [
            # HIGH CONFIDENCE - explicit phrases
            (r'\bcreampie\b', 0.40, False),
            (r'\bcream\s*pie\b', 0.40, True),
            (r'\bcum(ming|med|s)?\s+(in|inside)\s+(me|her|my|pussy)\b', 0.40, True),
            (r'\bfilled\s+(me|her|my\s+pussy)\s+up\b', 0.35, True),
            (r'\bfill(s|ed)?\s+(me|her)\s+(up\s+)?with\s+cum\b', 0.40, True),
            (r'\bbreed(s|ed|ing)?\s+(me|her)\b', 0.35, True),
            (r'\bload\s+inside\b', 0.35, True),
            (r'\bfinish(ed|es|ing)?\s+inside\b', 0.35, True),
            (r'\bdrop(s|ped)?\s+(his|a)\s+load\s+in\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bno\s+pull(ing)?\s+out\b', 0.30, True),
            (r'\bpussy\s+full\s+of\s+cum\b', 0.40, True),
            (r'\bdripping\s+cum\b', 0.30, True),
        ],

        "squirt": [
            # HIGH CONFIDENCE - explicit phrases
            (r'\bsquirt(s|ed|ing)?\b', 0.40, False),
            (r'\bsquirt(ing)?\s+(video|vid|clip|scene)\b', 0.40, True),
            (r'\bwatch\s+(me|her)\s+squirt\b', 0.40, True),
            (r'\bmake(s)?\s+(me|her)\s+squirt\b', 0.40, True),
            (r'\bsquirt(s|ed)?\s+everywhere\b', 0.35, True),
            (r'\bsquirt(s|ed)?\s+all\s+over\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bgush(es|ed|ing)?\b', 0.25, False),
            (r'\bsoak(s|ed|ing)?\s+the\s+(bed|sheets)\b', 0.30, True),
            (r'\bwet\s+mess\b', 0.20, True),
        ],

        "boy_girl_girl": [
            # HIGH CONFIDENCE - explicit group content
            (r'\bthreesome\b', 0.40, False),
            (r'\bbgg\b', 0.40, False),
            (r'\bffm\b', 0.40, False),
            (r'\b(two|2)\s+girls?\s+(and|with|&)\s+(a\s+)?(guy|man|boy|him|bf)\b', 0.40, True),
            (r'\b(me|us)\s+and\s+(my\s+)?(friend|bestie|gf)\s+(with|and)\s+(him|bf|guy)\b', 0.35, True),
            (r'\bsharing\s+(him|a\s+guy|my\s+bf)\b', 0.35, True),
            (r'\bwe\s+both\s+(fuck|suck|ride)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bthree\s*way\b', 0.30, True),
            (r'\bthird\s+(girl|chick|friend)\b', 0.25, True),
        ],

        "girl_girl_girl": [
            # HIGH CONFIDENCE
            (r'\bggg\b', 0.40, False),
            (r'\bfff\b', 0.40, False),
            (r'\b(three|3)\s+girls?\b', 0.40, True),
            (r'\b(three|3)\s+(of\s+us|way|some)\s+(girls?|ladies)\b', 0.40, True),
            (r'\ball\s+girls?\s+threesome\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\blesbian\s+threesome\b', 0.35, True),
            (r'\b(me|us)\s+and\s+(two|2)\s+(friends?|girls?)\b', 0.30, True),
        ],

        "girl_girl": [
            # HIGH CONFIDENCE
            (r'\bgirl\s+on\s+girl\b', 0.40, True),
            (r'\bg/g\s+(vid|video|sex|action|scene)\b', 0.40, True),
            (r'\blesbian\s+(sex|vid|video|scene|action|porn|content)\b', 0.40, True),
            (r'\beating\s+(her|another\s+girl)(\s+out)?\b', 0.35, True),
            (r'\blicking\s+(her|another\s+girl)\b', 0.35, True),
            (r'\b(she|her)\s+(licks|eats|fingers|fucks)\s+(me|my)\b', 0.35, True),
            (r'\b(me|i)\s+(lick|eat|finger|fuck)\s+her\b', 0.35, True),
            (r'\bscissor(s|ing)?\b', 0.35, False),
            # MEDIUM CONFIDENCE
            (r'\bwith\s+(my\s+)?(girlfriend|gf|bestie)\b(?=.*(sex|fuck|lick|eat))', 0.30, True),
            (r'\bsapphic\b', 0.25, False),
            (r'\bwlw\b', 0.25, False),
        ],

        "deepthroat": [
            # HIGH CONFIDENCE
            (r'\bdeepthroat(s|ed|ing)?\b', 0.40, False),
            (r'\bdeep\s*throat(s|ed|ing)?\b', 0.40, True),
            (r'\bdown\s+(my|her)\s+throat\b', 0.35, True),
            (r'\bthroat\s+(fuck|fucking|fucked)\b', 0.40, True),
            (r'\bgag(s|ged|ging)?\s+on\s+(his|the)\s+(cock|dick)\b', 0.35, True),
            (r'\btake(s)?\s+it\s+all\s+the\s+way\s+down\b', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bchoke(s|d)?\s+on\s+(his|the)\s+(cock|dick)\b', 0.30, True),
            (r'\ball\s+the\s+way\s+down\s+(my|her)\s+throat\b', 0.35, True),
        ],

        "blowjob": [
            # HIGH CONFIDENCE
            (r'\bblowjob\b', 0.40, False),
            (r'\bblow\s*job\b', 0.40, True),
            (r'\bbj\s+(vid|video|scene|clip)\b', 0.40, True),
            (r'\bsuck(s|ed|ing)?\s+(his|the)\s+(cock|dick)\b', 0.40, True),
            (r'\bcock\s+suck(ing|er)?\b', 0.35, True),
            (r'\bgive(s)?\s+(him\s+)?(a\s+)?head\b', 0.30, True),
            (r'\bgiving\s+head\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\b(his|the)\s+(cock|dick)\s+in\s+(my|her)\s+mouth\b', 0.35, True),
            (r'\bworship(ping)?\s+(his|the)\s+(cock|dick)\b', 0.30, True),
            (r'\bon\s+(my|her)\s+knees\b(?=.*(suck|cock|dick|mouth))', 0.25, True),
        ],

        "deepthroat_dildo": [
            # HIGH CONFIDENCE - dildo-specific deepthroat
            (r'\bdeepthroat(s|ed|ing)?\s+(my|the|a)?\s*dildo\b', 0.40, True),
            (r'\bdildo\s+deepthroat\b', 0.40, True),
            (r'\bthroat(s|ed|ing)?\s+(my|the|a)?\s*dildo\b', 0.35, True),
            (r'\bgag(s|ged|ging)?\s+on\s+(my|the|a)?\s*dildo\b', 0.40, True),
            (r'\bdildo\s+down\s+(my|her)\s+throat\b', 0.40, True),
            (r'\bsuck(ing)?\s+(my|the|a)?\s*dildo\s+deep\b', 0.35, True),
            # Pattern for when dildo and deepthroat appear in same text
            (r'\bdildo\b.*\bdeepthroat\b', 0.45, True),
            (r'\bdeepthroat\b.*\bdildo\b', 0.45, True),
            (r'\bgag(s|ged|ging)?\s+on\b.*\bdildo\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\btoy\s+deepthroat\b', 0.30, True),
            (r'\bdeep\s+in\s+(my|her)\s+throat\b(?=.*(toy|dildo))', 0.30, True),
        ],

        "blowjob_dildo": [
            # HIGH CONFIDENCE - dildo-specific oral
            (r'\bsuck(s|ed|ing)?\s+(my|the|a|my\s+favorite)?\s*dildo\b', 0.45, True),
            (r'\bsuck(s|ed|ing)?\s+my\s+\w+\s+dildo\b', 0.45, True),  # "sucking my favorite dildo"
            (r'\bdildo\s+(blow|bj|suck)\b', 0.40, True),
            (r'\b(blow|bj)\s+(my|the|a)?\s*dildo\b', 0.40, True),
            (r'\bdildo\s+in\s+(my|her)\s+mouth\b', 0.35, True),
            (r'\boral\s+(on|with)\s+(my|the|a)?\s*dildo\b', 0.35, True),
            (r'\blicking\s+(my|the|a)?\s*dildo\b', 0.30, True),
            # Pattern for any sucking + dildo in same text
            (r'\bsuck(s|ed|ing)?\b.*\bdildo\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\btoy\s+worship\b', 0.25, True),
            (r'\bmouth\s+(on|around)\s+(my|the|a)?\s*(toy|dildo)\b', 0.30, True),
        ],

        "boy_girl": [
            # HIGH CONFIDENCE
            (r'\bboy\s+girl\s+(vid|video|sex|scene|porn|content)\b', 0.40, True),
            (r'\bb/g\s+(vid|video|sex|action|scene|content)\b', 0.40, True),
            (r'\bsex\s+tape\b', 0.40, True),
            (r'\bhis\s+(cock|dick)\s+(in|inside)\b', 0.35, True),
            (r'\bhe\s+(fuck(s|ed|ing)?|pound(s|ed|ing)?|cum(s|med)?)\b', 0.30, True),
            (r'\bfuck(ed|ing)?\s+(by|with)\s+(a\s+)?(guy|man|boy|him|bf|boyfriend)\b', 0.35, True),
            (r'\briding\s+his\s+(cock|dick)\b', 0.40, True),
            (r'\b(guy|man|boy|bf|boyfriend)\s+(fuck|fucking|pounds|pounding)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bhis\s+(cock|dick)\b', 0.20, True),
            (r'\bwith\s+(my\s+)?(bf|boyfriend|hubby|husband)\b(?=.*(fuck|sex|cock|dick))', 0.30, True),
            (r'\bbent\s+over\s+and\s+fuck(ed|ing)\b', 0.30, True),
            (r'\btaking\s+him\s+(deep|hard)\b', 0.25, True),
        ],

        # ============================================================
        # SOLO EXPLICIT CONTENT TYPES (4 types)
        # ============================================================

        "pussy_play": [
            # HIGH CONFIDENCE
            (r'\bpussy\s+(play|rub|rubbing|finger|fingering|spread)\b', 0.40, True),
            (r'\bfinger(s|ed|ing)?\s+(my|her)\s+pussy\b', 0.40, True),
            (r'\brub(s|bed|bing)?\s+(my|her)\s+(pussy|clit)\b', 0.35, True),
            (r'\b(spread|spreading)\s+(my|her)\s+(pussy|lips)\b', 0.35, True),
            (r'\bplaying\s+with\s+(my|her)\s+pussy\b', 0.40, True),
            (r'\bpussy\s+close\s*up\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\btouching\s+(myself|my\s+pussy)\b', 0.30, True),
            (r'\bclit\s+(rub|play|massage)\b', 0.30, True),
            (r'\bwet\s+pussy\b(?=.*(play|touch|finger|show))', 0.25, True),
        ],

        "toy_play": [
            # HIGH CONFIDENCE
            (r'\btoy\s+(play|fun|time|insertion)\b', 0.40, True),
            (r'\busing\s+(my|a|the)\s+(toy|vibrator|dildo)\b', 0.40, True),
            (r'\bvibrator\s+(play|fun|time|vid|video)\b', 0.40, True),
            (r'\bdildo\s+(play|fun|fuck|fucking|ride|riding)\b', 0.40, True),
            (r'\b(fuck|ride|riding)\s+(my|a|the)\s+(toy|dildo|vibrator)\b', 0.40, True),
            (r'\btoy\s+in\s+(my|her)\s+(pussy|ass)\b', 0.40, True),
            (r'\binserting\s+(my|a|the)\s+(toy|dildo|vibrator)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bvibrat(or|e|es|ed|ing)\b(?=.*(pussy|clit|on\s+me))', 0.30, True),
            (r'\bmagic\s+wand\b', 0.30, True),
            (r'\bhitachi\b', 0.30, False),
            (r'\blush\b(?=.*(toy|play|control|vibrat))', 0.25, True),
        ],

        "tits_play": [
            # HIGH CONFIDENCE
            (r'\btits?\s+(play|bounce|bouncing|jiggle|squeeze|drop)\b', 0.40, True),
            (r'\bboobs?\s+(play|bounce|bouncing|jiggle|squeeze|drop)\b', 0.40, True),
            (r'\bbreasts?\s+(play|massage|fondl)\b', 0.35, True),
            (r'\bplaying\s+with\s+(my|her)\s+(tits|boobs|breasts)\b', 0.40, True),
            (r'\bnipple\s+(play|pinch|suck|clamps)\b', 0.35, True),
            (r'\btitty\s+(drop|fuck|play|bounce)\b', 0.40, True),
            (r'\boil(ed|ing)?\s+(my|her)\s+(tits|boobs)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bsqueez(e|ing)\s+(my|her)\s+(tits|boobs)\b', 0.30, True),
            (r'\bjiggl(e|ing|y)\s+(tits|boobs)\b', 0.30, True),
            (r'\btit(s)?\s+worshi?p\b', 0.30, True),
        ],

        "solo": [
            # HIGH CONFIDENCE
            (r'\bsolo\s+(vid|video|play|session|content|clip)\b', 0.40, True),
            (r'\bmasturbat(e|es|ed|ing|ion)\b', 0.40, False),
            (r'\btouch(ing)?\s+myself\b', 0.35, True),
            (r'\bpleasuring\s+myself\b', 0.40, True),
            (r'\bmaking\s+myself\s+cum\b', 0.40, True),
            (r'\bme\s+time\b(?=.*(play|touch|naughty|sexy))', 0.30, True),
            (r'\bself\s+(pleasure|love|play)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bjust\s+me\b(?=.*(play|touch|alone|naughty))', 0.25, True),
            (r'\ball\s+alone\b(?=.*(play|touch|fun|naughty))', 0.25, True),
            (r'\balone\s+time\b', 0.25, True),
        ],

        # ============================================================
        # INTERACTIVE CONTENT TYPES (2 types)
        # ============================================================

        "joi": [
            # HIGH CONFIDENCE
            (r'\bjoi\b', 0.40, False),
            (r'\bjerk\s*off\s+instruction(s)?\b', 0.40, True),
            (r'\bstroke\s+(with|for)\s+me\b', 0.35, True),
            (r'\bstroke\s+instruction(s)?\b', 0.40, True),
            (r'\bcum\s+(with|for)\s+me\b', 0.35, True),
            (r'\bfollow\s+my\s+instructions?\b', 0.30, True),
            (r'\bdo\s+(as|what)\s+i\s+say\b', 0.25, True),
            (r'\bedge\s+with\s+me\b', 0.35, True),
            (r'\bi\s+tell\s+you\s+(when|how)\s+to\s+(stroke|cum)\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\btell(ing)?\s+you\s+(when|how)\s+to\s+(stroke|touch|cum)\b', 0.30, True),
            (r'\bedging\s+(game|session|instruction)\b', 0.30, True),
        ],

        "dick_rating": [
            # HIGH CONFIDENCE
            (r'\bdick\s+rat(e|ing|ed)\b', 0.40, True),
            (r'\bcock\s+rat(e|ing|ed)\b', 0.40, True),
            (r'\brat(e|ing)\s+(your|his|the)\s+(dick|cock)\b', 0.40, True),
            (r'\bdick\s+review\b', 0.40, True),
            (r'\bsend\s+(me\s+)?(your\s+)?(dick|cock)\s+(pic|photo)\b', 0.35, True),
            (r'\blet\s+me\s+rate\s+(your|it)\b', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bhonest\s+(dick|cock)\s+rating\b', 0.35, True),
            (r'\bdr\s+service\b', 0.25, True),
            (r'\bspp\s+rating\b', 0.25, True),
        ],

        # ============================================================
        # FETISH CONTENT TYPES (2 types)
        # ============================================================

        "dom_sub": [
            # HIGH CONFIDENCE
            (r'\bdomm?(e|ination)?\b', 0.35, False),
            (r'\bsubmi(t|ssion|ssive)\b', 0.35, False),
            (r'\bmaster\b(?=.*(slave|obey|command|worship))', 0.35, True),
            (r'\bslave\b', 0.35, False),
            (r'\bmistress\b', 0.40, False),
            (r'\bgoddess\b(?=.*(worship|obey|serve|kneel))', 0.35, True),
            (r'\bobey\s+(me|your|my)\b', 0.35, True),
            (r'\bcommand(s|ed|ing)?\b(?=.*(you|obey|follow))', 0.30, True),
            (r'\bkneel\s+(for|before)\s+(me|your)\b', 0.40, True),
            (r'\bbeg(ging)?\s+(me|for)\b', 0.30, True),
            (r'\bpunish(ment|ed|ing)?\b', 0.30, False),
            # MEDIUM CONFIDENCE
            (r'\bcontrol(ling|led)?\b(?=.*(you|your|him))', 0.25, True),
            (r'\bworship\s+(me|my|her)\b', 0.30, True),
            (r'\bserve\s+(me|your|my)\b', 0.25, True),
            (r'\bowned\b', 0.25, False),
        ],

        "feet": [
            # HIGH CONFIDENCE
            (r'\bfeet\s+(pics|pic|photos?|vid|video|content|worship)\b', 0.40, True),
            (r'\bfoot\s+(fetish|worship|job|play)\b', 0.40, True),
            (r'\btoes?\s+(suck|lick|worship)\b', 0.40, True),
            (r'\bsoles?\b(?=.*(show|pic|worship|lick))', 0.35, True),
            (r'\bfootjob\b', 0.40, False),
            (r'\barch(es)?\b(?=.*(feet|foot|show))', 0.30, True),
            (r'\bpedicure\b(?=.*(feet|toes|show))', 0.25, True),
            # MEDIUM CONFIDENCE
            (r'\bfeet\b(?!.*(\d+\s*(feet|ft)|square\s*feet))', 0.20, False),  # Avoid measurements
            (r'\bpretty\s+(feet|toes)\b', 0.30, True),
            (r'\bheel(s)?\b(?=.*(feet|foot|worship|lick))', 0.25, True),
            (r'\bankle(s)?\b(?=.*(show|worship))', 0.20, True),
        ],

        # ============================================================
        # THEMED CONTENT TYPES (6 types)
        # ============================================================

        "shower_bath": [
            # HIGH CONFIDENCE
            (r'\bshower\s+(vid|video|scene|fun|time|content)\b', 0.40, True),
            (r'\bbath\s+(time|vid|video|scene|fun|content)\b', 0.40, True),
            (r'\bsoap(y|ed|ing)?\s+(up|body|fun)\b', 0.35, True),
            (r'\bwet\s+and\s+(wild|naked|sexy)\b', 0.35, True),
            (r'\bin\s+the\s+(shower|bath|tub)\b', 0.35, True),
            (r'\bsteamy\s+(shower|bath)\b', 0.35, True),
            (r'\bwashing\s+(my|her)\s+(body|self)\b', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bbathtub\b', 0.25, False),
            (r'\bdripping\s+wet\b', 0.25, True),
            (r'\bsoaking\s+wet\b', 0.25, True),
            (r'\bwater\s+running\s+down\b', 0.25, True),
        ],

        "pool_outdoor": [
            # HIGH CONFIDENCE
            (r'\bpool(side)?\s+(vid|video|fun|time|content|day)\b', 0.40, True),
            (r'\boutdoor(s)?\s+(vid|video|fun|content|shoot)\b', 0.40, True),
            (r'\bbeach\s+(vid|video|fun|content|day)\b', 0.40, True),
            (r'\boutside\s+(fun|content|shoot|vid|video)\b', 0.35, True),
            (r'\bby\s+the\s+pool\b', 0.35, True),
            (r'\bin\s+the\s+(sun|sunshine)\b', 0.30, True),
            (r'\bnature\s+(content|vid|video|shoot)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bsunbath(e|ing)\b', 0.30, False),
            (r'\bpublic\s+(flash|fun|dare)\b', 0.30, True),
            (r'\bswimming\s+pool\b', 0.25, True),
            (r'\bbackyard\s+(fun|content)\b', 0.25, True),
        ],

        "lingerie": [
            # HIGH CONFIDENCE
            (r'\blingerie\s+(set|vid|video|try|haul|content|shoot)\b', 0.40, True),
            (r'\b(sexy|lacy|new)\s+lingerie\b', 0.35, True),
            (r'\bstockings\s+(and|with|vid|video|content)\b', 0.35, True),
            (r'\bgarter\s+(belt|set)\b', 0.35, True),
            (r'\bcorset\b', 0.30, False),
            (r'\bbodystocking\b', 0.35, False),
            (r'\bteddy\b(?=.*(lingerie|lace|sexy))', 0.30, True),
            (r'\bnegligee\b', 0.35, False),
            # MEDIUM CONFIDENCE
            (r'\blace\s+(panties|bra|set)\b', 0.30, True),
            (r'\bthong\s+(try|haul|vid|video)\b', 0.30, True),
            (r'\bpanties\s+(try|haul|vid|video)\b', 0.30, True),
            (r'\bsexy\s+(bra|underwear)\b', 0.25, True),
        ],

        "story_roleplay": [
            # HIGH CONFIDENCE
            (r'\broleplay\b', 0.40, False),
            (r'\brole\s*play\b', 0.40, True),
            (r'\bpretend\s+(to\s+be|i\'m|we\'re)\b', 0.35, True),
            (r'\bscenario\b', 0.30, False),
            (r'\bfantasy\s+(roleplay|scenario|story)\b', 0.40, True),
            (r'\bimagine\s+(you\'re|we\'re|i\'m)\b', 0.30, True),
            (r'\bact(ing)?\s+out\b', 0.25, True),
            (r'\bcharacter\s+(play|costume)\b', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bcosplay\b', 0.30, False),
            (r'\bstorytime\b', 0.25, False),
            (r'\bplaying\s+(the\s+)?(role|part)\b', 0.25, True),
            (r'\bdress(ed)?\s+up\s+as\b', 0.25, True),
        ],

        "pov": [
            # HIGH CONFIDENCE
            (r'\bpov\b', 0.40, False),
            (r'\bpoint\s+of\s+view\b', 0.40, True),
            (r'\byour\s+(view|perspective|angle)\b', 0.35, True),
            (r'\blook(ing)?\s+down\s+at\s+(me|her)\b', 0.35, True),
            (r'\bfrom\s+your\s+(angle|view|perspective|eyes)\b', 0.35, True),
            (r'\byou\'re\s+(look|watch)ing\s+(down|at\s+me)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bas\s+if\s+you\s+were\s+(here|there)\b', 0.25, True),
            (r'\blooking\s+up\s+at\s+you\b', 0.30, True),
            (r'\byour\s+eyes\b(?=.*(see|view|look))', 0.25, True),
        ],

        "gfe": [
            # HIGH CONFIDENCE
            (r'\bgfe\b', 0.40, False),
            (r'\bgirlfriend\s+experience\b', 0.40, True),
            (r'\bvirtual\s+girlfriend\b', 0.40, True),
            (r'\b(be|i\'m)\s+your\s+girlfriend\b', 0.35, True),
            (r'\btreat\s+you\s+like\s+(my\s+)?(bf|boyfriend)\b', 0.35, True),
            (r'\bbf\s+treatment\b', 0.35, True),
            (r'\bdate\s+night\b(?=.*(virtual|online|content))', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bcuddle\s+(time|vid|video)\b', 0.25, True),
            (r'\bboyfriend\s+(material|vibes)\b', 0.25, True),
            (r'\bsweet\s+nothings\b', 0.25, True),
            (r'\bgood\s+morning\s+(baby|babe|handsome)\b', 0.25, True),
        ],

        # ============================================================
        # PROMOTIONAL CONTENT TYPES (5 types)
        # ============================================================

        "bundle_offer": [
            # HIGH CONFIDENCE
            (r'\bbundle\s+(deal|offer|sale|discount|special)\b', 0.40, True),
            (r'\b(buy|get)\s+\d+\s+(for|at)\s+\$?\d+\b', 0.35, True),
            (r'\bpack(age)?\s+(deal|offer|sale)\b', 0.35, True),
            (r'\bcollection\s+(sale|deal|offer)\b', 0.35, True),
            (r'\bbuy\s+more\s+save\s+more\b', 0.35, True),
            (r'\bvalue\s+(pack|bundle|deal)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\b\d+\s+(vids?|videos?)\s+for\s+\$?\d+\b', 0.30, True),
            (r'\bbulk\s+(deal|discount|purchase)\b', 0.30, True),
            (r'\bcombo\s+(deal|offer)\b', 0.25, True),
        ],

        "flash_sale": [
            # HIGH CONFIDENCE
            (r'\bflash\s+sale\b', 0.40, True),
            (r'\blimited\s+time\s+(only|offer|deal|sale)\b', 0.40, True),
            (r'\b(today|tonight)\s+only\b(?=.*(sale|deal|discount|\$|off))', 0.35, True),
            (r'\bhurry\b(?=.*(sale|deal|expires|ends))', 0.30, True),
            (r'\bends?\s+(soon|tonight|today)\b', 0.30, True),
            (r'\b(\d+|one|two|few)\s+hour(s)?\s+left\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bquick\s+(sale|deal)\b', 0.30, True),
            (r'\blast\s+chance\b(?=.*(sale|deal|buy|get))', 0.30, True),
            (r'\bdon\'t\s+miss\s+(out|this)\b(?=.*(sale|deal|offer))', 0.25, True),
            (r'\b\d+%\s+off\b(?=.*(today|tonight|limited|hurry))', 0.30, True),
        ],

        "exclusive_content": [
            # HIGH CONFIDENCE
            (r'\bexclusive\s+(content|vid|video|set|drop|release)\b', 0.40, True),
            (r'\bnever\s+(before\s+)?(seen|released)\b', 0.35, True),
            (r'\bonly\s+(on|at|for)\s+(my\s+)?(page|onlyfans|of)\b', 0.35, True),
            (r'\bvip\s+(only|exclusive|content)\b', 0.35, True),
            (r'\bpremium\s+(content|vid|video)\b', 0.35, True),
            (r'\bfirst\s+time\s+(ever|releasing)\b', 0.30, True),
            # MEDIUM CONFIDENCE
            (r'\bspecial\s+(release|drop|content)\b', 0.30, True),
            (r'\bunreleased\b', 0.30, False),
            (r'\bnewly\s+released\b', 0.25, True),
        ],

        "behind_scenes": [
            # HIGH CONFIDENCE
            (r'\bbehind\s+(the\s+)?scenes?\b', 0.40, True),
            (r'\bbts\b', 0.40, False),
            (r'\bmaking\s+of\b', 0.35, True),
            (r'\bhow\s+(i|we)\s+(film|shoot|make)\b', 0.35, True),
            (r'\bbloopers?\b', 0.35, False),
            (r'\bouttakes?\b', 0.35, False),
            (r'\bshoot\s+day\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bbehind\s+the\s+camera\b', 0.30, True),
            (r'\bset\s+life\b', 0.25, True),
            (r'\braw\s+footage\b', 0.25, True),
        ],

        "live_stream": [
            # HIGH CONFIDENCE
            (r'\blive\s+stream\b', 0.40, True),
            (r'\blive(streaming)?\s+(show|session|tonight|now|soon)\b', 0.40, True),
            (r'\bgoing\s+live\b', 0.40, True),
            (r'\bjoin\s+me\s+live\b', 0.40, True),
            (r'\blive\s+(at|@)\s+\d+\b', 0.35, True),
            (r'\bwatch\s+me\s+live\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\blive\s+(content|interaction)\b', 0.30, True),
            (r'\bcatch\s+me\s+live\b', 0.35, True),
            (r'\bon\s+cam\s+live\b', 0.30, True),
            (r'\blive\s+right\s+now\b', 0.35, True),
        ],

        # ============================================================
        # ENGAGEMENT CONTENT TYPES (3 types)
        # ============================================================

        "teasing": [
            # HIGH CONFIDENCE
            (r'\bteas(e|es|ed|ing)\s+(vid|video|content|you)\b', 0.40, True),
            (r'\bjust\s+a\s+(tease|taste|peek|preview)\b', 0.40, True),
            (r'\bsneak\s+(peek|preview)\b', 0.40, True),
            (r'\bpreview\s+(of|for)\b', 0.35, True),
            (r'\btaste\s+of\s+what\'s\s+(coming|to\s+come)\b', 0.35, True),
            (r'\blittle\s+tease\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bwanna\s+see\s+more\b', 0.30, True),
            (r'\bmore\s+where\s+this\s+came\b', 0.25, True),
            (r'\bfull\s+(vid|video)\s+(in|on|available)\b', 0.25, True),
            (r'\bunlock\s+(to\s+)?see\s+(more|the\s+rest)\b', 0.30, True),
        ],

        "tip_request": [
            # HIGH CONFIDENCE
            (r'\btip\s+me\b', 0.40, True),
            (r'\bsend\s+(a\s+)?tip\b', 0.40, True),
            (r'\btip\s+\$\d+\b', 0.40, True),
            (r'\$\d+.*\btip\b', 0.35, True),
            (r'\bshow\s+(me\s+)?love\b', 0.30, True),
            (r'\bspoil\s+me\b', 0.40, True),
            (r'\btip\s+\d+.*(?:get|receive|unlock)\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\btip.*(?:bundle|content|video)\b', 0.30, True),
            (r'\bsend.*gift\b', 0.25, True),
            (r'\bdonate\b', 0.25, False),
            (r'\bsupport\s+me\b', 0.25, True),
            (r'\btreat\s+me\b', 0.25, True),
        ],

        "renewal_retention": [
            # HIGH CONFIDENCE
            (r'\brenew(al)?\b', 0.40, False),
            (r'\brebill\b', 0.40, False),
            (r'\bauto[- ]?renew\b', 0.40, True),
            (r'\benable.*renew\b', 0.35, True),
            (r'\bturn.*renew\s+on\b', 0.35, True),
            (r'\bstay\s+subscribed\b', 0.40, True),
            (r'\bkeep.*subscri(be|ption)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bdon\'t\s+(leave|go|unsubscribe)\b', 0.30, True),
            (r'\bmiss\s+you\b.*(?:sub|back)', 0.25, True),
            (r'\bcome\s+back\b.*(?:sub|renew)', 0.25, True),
            (r'\bexpired\b.*(?:renew|sub)', 0.25, True),
            (r'\bwin.*back\b', 0.30, True),
        ],

        # ============================================================
        # IMPLIED CONTENT TYPES (4 types)
        # ============================================================

        "implied_pussy_play": [
            # HIGH CONFIDENCE - suggestive but not explicit
            (r'\bwish\s+you\s+could\s+(see|touch)\s+(my\s+)?pussy\b', 0.35, True),
            (r'\bthink(ing)?\s+(about|of)\s+(my\s+)?pussy\b', 0.35, True),
            (r'\bso\s+wet\s+(for\s+you|right\s+now)\b', 0.30, True),
            (r'\bdripping\s+for\s+you\b', 0.30, True),
            (r'\bimagine\s+(touching|tasting)\s+(my\s+)?pussy\b', 0.35, True),
            (r'\bwant\s+to\s+touch\s+(my\s+)?pussy\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bso\s+horny\b(?!.*(fuck|cock|dick|finger|play|toy))', 0.25, True),
            (r'\baching\s+for\s+you\b', 0.25, True),
            (r'\bneed\s+you\s+inside\b(?!.*(fuck|cock|dick))', 0.25, True),
        ],

        "implied_solo": [
            # HIGH CONFIDENCE - suggestive self-pleasure references
            (r'\bthinking\s+of\s+you\s+(while|as)\s+i\b', 0.35, True),
            (r'\bwish\s+you\s+were\s+(here|watching)\b', 0.30, True),
            (r'\bcan\'t\s+stop\s+thinking\s+about\s+you\b', 0.25, True),
            (r'\bmissing\s+you\s+(tonight|right\s+now)\b', 0.25, True),
            (r'\bgetting\s+(myself\s+)?ready\s+for\s+bed\b', 0.25, True),
            (r'\blonely\s+(tonight|in\s+bed)\b', 0.25, True),
            # MEDIUM CONFIDENCE
            (r'\bhaving\s+fun\s+alone\b', 0.25, True),
            (r'\blate\s+night\s+thoughts\b', 0.20, True),
            (r'\bkeep(s)?\s+me\s+company\b', 0.20, True),
        ],

        "implied_tits_play": [
            # HIGH CONFIDENCE - suggestive breast references
            (r'\bwish\s+you\s+could\s+(see|touch|feel)\s+(my\s+)?(tits|boobs|breasts)\b', 0.35, True),
            (r'\bthink(ing)?\s+(about|of)\s+(my\s+)?(tits|boobs)\b', 0.35, True),
            (r'\bwant\s+to\s+touch\s+(my\s+)?(tits|boobs)\b', 0.35, True),
            (r'\bimagine\s+(my\s+)?(tits|boobs)\s+(in|on)\b', 0.30, True),
            (r'\b(tits|boobs)\s+need\s+(attention|touching)\b', 0.30, True),
            # Pattern for "thinking about you touching my boobs"
            (r'\bthinking\s+about\s+you\s+touching\s+(my\s+)?(tits|boobs|breasts)\b', 0.40, True),
            (r'\b(you\s+)?touching\s+(my\s+)?(tits|boobs|breasts)\b', 0.35, True),
            # MEDIUM CONFIDENCE
            (r'\bnipples?\s+(hard|showing|poking)\b', 0.25, True),
            (r'\bno\s+bra\b', 0.20, True),
            (r'\bbraless\b', 0.20, False),
        ],

        "implied_toy_play": [
            # HIGH CONFIDENCE - suggestive toy references
            (r'\bthinking\s+(about|of)\s+using\s+(my\s+)?toy\b', 0.35, True),
            (r'\bwish\s+you\s+could\s+(see|watch)\s+me\s+with\s+(my\s+)?toy\b', 0.35, True),
            (r'\b(my\s+)?toy\s+is\s+(charged|ready|waiting)\b', 0.35, True),
            (r'\btime\s+for\s+(my\s+)?toy\b', 0.30, True),
            (r'\bimagine\s+me\s+with\s+(my\s+)?toy\b', 0.30, True),
            # Pattern for "toy is all charged up and ready"
            (r'\b(my\s+)?toy\s+is\s+all\s+charged\b', 0.40, True),
            (r'\btoy\s+(is\s+)?(all\s+)?(charged|ready)\s+(up\s+)?(and\s+ready)?\b', 0.40, True),
            # MEDIUM CONFIDENCE
            (r'\bgot\s+(a\s+)?new\s+toy\b', 0.25, True),
            (r'\bfavorite\s+toy\b', 0.25, True),
            (r'\bcharging\s+(my\s+)?vibrator\b', 0.25, True),
        ],
    }

    def __init__(self):
        """Initialize the classifier with compiled regex patterns."""
        self._compiled_patterns: dict[str, list[tuple[re.Pattern, float, bool]]] = {}

        for content_type, patterns in self.PATTERNS.items():
            self._compiled_patterns[content_type] = [
                (re.compile(pattern, re.IGNORECASE), weight, is_phrase)
                for pattern, weight, is_phrase in patterns
            ]

    def classify(self, text: str) -> tuple[int, float]:
        """
        Classify a single caption text into a content type.

        Args:
            text: The caption text to classify.

        Returns:
            Tuple of (content_type_id, confidence).
            Returns (0, 0.0) if no match found.
        """
        result = self._classify_detailed(text)
        if result is None:
            return (0, 0.0)
        return result.as_tuple()

    def classify_detailed(self, text: str) -> Optional[ClassificationResult]:
        """
        Classify a caption with full result details.

        Args:
            text: The caption text to classify.

        Returns:
            ClassificationResult with full details, or None if no match.
        """
        return self._classify_detailed(text)

    def _classify_detailed(self, text: str) -> Optional[ClassificationResult]:
        """
        Internal classification method with full details.

        Processes content types in priority order (most specific first)
        to ensure explicit content is matched before general patterns.
        """
        if not text or not text.strip():
            return None

        text_lower = text.lower()
        best_match: Optional[ClassificationResult] = None

        # Process in priority order
        for content_type in self.TYPE_PRIORITY_ORDER:
            patterns = self._compiled_patterns.get(content_type, [])
            if not patterns:
                continue

            total_weight = 0.0
            matched_patterns: list[str] = []
            phrase_bonus = 0.0

            for compiled_pattern, weight, is_phrase in patterns:
                if compiled_pattern.search(text_lower):
                    total_weight += weight
                    matched_patterns.append(compiled_pattern.pattern)
                    if is_phrase:
                        phrase_bonus = max(phrase_bonus, 0.05)  # Phrase matches get bonus

            if matched_patterns:
                # Calculate confidence score
                # Base: sum of weights, capped at 0.95
                # Bonus for phrase matches and multiple matches
                base_confidence = min(total_weight, 0.95)

                # Multi-match bonus: +0.05 for 2+ matches, +0.10 for 3+ matches
                match_count = len(matched_patterns)
                if match_count >= 3:
                    match_bonus = 0.10
                elif match_count >= 2:
                    match_bonus = 0.05
                else:
                    match_bonus = 0.0

                final_confidence = min(base_confidence + phrase_bonus + match_bonus, 1.0)

                # Ensure minimum confidence of 0.60 for any match
                final_confidence = max(final_confidence, 0.60)

                result = ClassificationResult(
                    content_type_id=self.CONTENT_TYPE_IDS[content_type],
                    content_type_name=content_type,
                    confidence=round(final_confidence, 4),
                    category=self.CONTENT_TYPE_CATEGORIES[content_type],
                    matched_patterns=matched_patterns,
                )

                # First match wins due to priority ordering
                # However, we consider higher confidence as better
                if best_match is None or result.confidence > best_match.confidence:
                    best_match = result

                    # If confidence is very high, stop early
                    if best_match.confidence >= 0.90:
                        return best_match

        return best_match

    def classify_batch(self, texts: list[str]) -> list[tuple[int, float]]:
        """
        Classify multiple captions efficiently.

        Args:
            texts: List of caption texts to classify.

        Returns:
            List of (content_type_id, confidence) tuples in same order as input.
        """
        return [self.classify(text) for text in texts]

    def classify_batch_detailed(self, texts: list[str]) -> list[Optional[ClassificationResult]]:
        """
        Classify multiple captions with full details.

        Args:
            texts: List of caption texts to classify.

        Returns:
            List of ClassificationResult objects (or None) in same order as input.
        """
        return [self._classify_detailed(text) for text in texts]

    def get_content_type_name(self, content_type_id: int) -> Optional[str]:
        """Get content type name from ID."""
        return self.CONTENT_TYPE_NAMES.get(content_type_id)

    def get_content_type_id(self, content_type_name: str) -> Optional[int]:
        """Get content type ID from name."""
        return self.CONTENT_TYPE_IDS.get(content_type_name)


def test_classifier():
    """Test the classifier with sample captions."""
    classifier = ContentTypeClassifier()

    # Test cases organized by expected content type
    test_cases: list[tuple[str, str]] = [
        # Explicit
        ("Watch me take his cock deep in my ass", "anal"),
        ("Creampie compilation - he filled me up so good", "creampie"),
        ("Watch me squirt everywhere", "squirt"),
        ("Threesome with my bestie and her bf", "boy_girl_girl"),
        ("Three girls having fun together", "girl_girl_girl"),
        ("Lesbian sex tape with my girlfriend", "girl_girl"),
        ("Deepthroat video - all the way down", "deepthroat"),
        ("Sloppy blowjob video just dropped", "blowjob"),
        ("Gagging on my dildo - deepthroat practice", "deepthroat_dildo"),
        ("Sucking my favorite dildo", "blowjob_dildo"),
        ("B/G sex tape with my bf", "boy_girl"),

        # Solo Explicit
        ("Playing with my pussy for you", "pussy_play"),
        ("New toy play video just dropped", "toy_play"),
        ("Tits play and nipple clamps", "tits_play"),
        ("Solo masturbation video", "solo"),

        # Interactive
        ("JOI - follow my instructions", "joi"),
        ("Dick rating service available", "dick_rating"),

        # Fetish
        ("Your goddess demands worship - obey me", "dom_sub"),
        ("Feet pics and toe worship content", "feet"),

        # Themed
        ("Steamy shower video", "shower_bath"),
        ("Pool day content just dropped", "pool_outdoor"),
        ("New lingerie try on haul", "lingerie"),
        ("Naughty roleplay scenario for you", "story_roleplay"),
        ("POV you're looking down at me", "pov"),
        ("GFE - let me be your virtual girlfriend", "gfe"),

        # Promotional
        ("Bundle deal - 5 videos for $25", "bundle_offer"),
        ("Flash sale - limited time only!", "flash_sale"),
        ("Exclusive content never before seen", "exclusive_content"),
        ("Behind the scenes from today's shoot", "behind_scenes"),
        ("Going live tonight at 9pm!", "live_stream"),

        # Engagement
        ("Just a little tease before the full video", "teasing"),
        ("Tip me $10 and get a surprise", "tip_request"),
        ("Don't forget to renew your subscription", "renewal_retention"),

        # Implied
        ("Thinking about my pussy while I fall asleep", "implied_pussy_play"),
        ("Wish you were here watching me tonight", "implied_solo"),
        ("Thinking about you touching my boobs", "implied_tits_play"),
        ("My toy is all charged up and ready", "implied_toy_play"),

        # Edge cases - should match most specific
        ("Anal sex tape with my boyfriend", "anal"),  # Should be anal, not boy_girl
        ("Creampie threesome with two girls", "creampie"),  # Should be creampie, not bgg
    ]

    print("=" * 80)
    print("CONTENT TYPE CLASSIFIER TEST RESULTS")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for caption, expected_type in test_cases:
        result = classifier.classify_detailed(caption)

        if result is None:
            actual_type = "NONE"
            confidence = 0.0
            category = "N/A"
            patterns = []
        else:
            actual_type = result.content_type_name
            confidence = result.confidence
            category = result.category
            patterns = result.matched_patterns[:3]  # Show first 3 patterns

        status = "PASS" if actual_type == expected_type else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"[{status}] Expected: {expected_type:25} | Got: {actual_type:25}")
        print(f"       Caption: {caption[:60]}...")
        print(f"       Confidence: {confidence:.2f} | Category: {category}")
        if patterns:
            print(f"       Patterns: {', '.join(p[:30] + '...' if len(p) > 30 else p for p in patterns)}")
        print()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(test_cases)} tests passed ({passed/len(test_cases)*100:.1f}%)")
    print(f"         {failed} tests failed")
    print("=" * 80)

    return passed, failed


def main():
    """Main entry point for testing."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        passed, failed = test_classifier()
        sys.exit(0 if failed == 0 else 1)

    # Interactive mode
    classifier = ContentTypeClassifier()

    print("Content Type Classifier - Interactive Mode")
    print("Enter caption text to classify (or 'quit' to exit)")
    print("-" * 50)

    while True:
        try:
            text = input("\nCaption: ").strip()
            if text.lower() in ("quit", "exit", "q"):
                break

            if not text:
                continue

            result = classifier.classify_detailed(text)

            if result is None:
                print("  No match found")
            else:
                print(f"  Content Type: {result.content_type_name} (ID: {result.content_type_id})")
                print(f"  Category: {result.category}")
                print(f"  Confidence: {result.confidence:.4f}")
                print(f"  Matched Patterns: {len(result.matched_patterns)}")
                for pattern in result.matched_patterns[:5]:
                    print(f"    - {pattern}")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
