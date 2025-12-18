"""
Tone Classification Prompts for OnlyFans Captions
================================================

This module provides optimized prompts for Claude Sonnet to classify
OnlyFans caption tones into one of six categories.

Tone Taxonomy:
- seductive: Alluring, tempting, focused on desire and intimacy
- aggressive: Explicit, commanding, high-intensity language with profanity
- playful: Fun, teasing, lighthearted with humor and excitement
- submissive: Yielding, eager to please, deferential tone
- dominant: Commanding, controlling, authoritative
- bratty: Demanding, entitled, princess/spoiled attitude

Usage:
    from tone_prompts import build_classification_prompt, parse_response

    messages = build_classification_prompt("Your caption text here")
    # Send to Claude API
    result = parse_response(response_text)
"""

import json
import re
from typing import Optional

# =============================================================================
# TONE DEFINITIONS
# =============================================================================

TONE_DEFINITIONS: dict[str, str] = {
    "seductive": "Alluring, tempting, focused on desire and intimacy. Uses suggestive language that draws the reader in with promises of pleasure or connection.",
    "aggressive": "Explicit, commanding, high-intensity language with profanity. Direct, raw, and unapologetically sexual with forceful energy.",
    "playful": "Fun, teasing, lighthearted with humor and excitement. Uses playful language, emojis, and creates a sense of mischief or flirtation.",
    "submissive": "Yielding, eager to please, deferential tone. Expresses desire to serve, obey, or satisfy. Often uses terms like 'daddy' and conveys vulnerability.",
    "dominant": "Commanding, controlling, authoritative. Issues orders, sets expectations, and maintains power in the dynamic.",
    "bratty": "Demanding, entitled, princess/spoiled attitude. Expects to be treated special, uses whiny or demanding language, self-focused."
}

VALID_TONES = list(TONE_DEFINITIONS.keys())

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are an expert content tone classifier for OnlyFans captions. Your task is to classify the emotional tone of captions into exactly ONE of six categories.

## Tone Categories

1. **seductive** - Alluring, tempting, focused on desire and intimacy. Draws the reader in with suggestive promises.
2. **aggressive** - Explicit, commanding, high-intensity with profanity. Raw, direct, forceful sexual energy.
3. **playful** - Fun, teasing, lighthearted with humor. Mischievous, flirty, uses "hehe", "oops", playful emojis.
4. **submissive** - Yielding, eager to please, deferential. Uses "daddy", expresses desire to serve/obey.
5. **dominant** - Commanding, controlling, authoritative. Issues orders, maintains power.
6. **bratty** - Demanding, entitled, princess attitude. Expects special treatment, whiny/demanding.

## Classification Rules

- Choose the SINGLE most dominant tone
- Consider the overall energy and intent, not just individual words
- Profanity alone does not make something "aggressive" - consider the power dynamic
- "Playful" requires lightheartedness; sexual content without humor is not playful
- When uncertain between two tones, consider which energy the creator is projecting

## Output Format

Respond with ONLY valid JSON in this exact format:
{"tone": "<tone>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}"""

# =============================================================================
# FEW-SHOT EXAMPLES
# =============================================================================

FEW_SHOT_EXAMPLES: list[dict] = [
    # Seductive examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"I\'ve been waiting for you all day... want to see what I\'ve been doing?"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "seductive", "confidence": 0.95, "reasoning": "Creates anticipation and desire through suggestive mystery, drawing the reader in with an intimate invitation."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"Come closer... I have a secret I want to whisper in your ear"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "seductive", "confidence": 0.92, "reasoning": "Uses intimacy and mystery to create allure, inviting closeness with tempting suggestion."}'
    },

    # Aggressive examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"Get your ass over here and watch me take this dick"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "aggressive", "confidence": 0.98, "reasoning": "Direct command with profanity, explicit content, and forceful high-intensity energy."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"Fuck being subtle. You know you want to see me ride it hard"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "aggressive", "confidence": 0.94, "reasoning": "Profanity combined with bold, unapologetic directness and raw sexual energy."}'
    },

    # Playful examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"Oops! I may have taken some pics that are too naughty to post hehe"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "playful", "confidence": 0.96, "reasoning": "Lighthearted mischief with \\"oops\\" and \\"hehe\\", creating fun teasing energy around naughty content."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"Guess what I\'m hiding under this towel? Wrong answers only!"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "playful", "confidence": 0.93, "reasoning": "Interactive humor with game-like engagement, lighthearted teasing rather than direct seduction."}'
    },

    # Submissive examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"I\'ll do whatever you want daddy... just tell me what you need"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "submissive", "confidence": 0.97, "reasoning": "Deferential language with \\"daddy\\", expressing eagerness to please and follow direction."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"Use me however you want... I just want to make you happy"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "submissive", "confidence": 0.95, "reasoning": "Yielding, service-oriented language prioritizing the other\'s desires over self."}'
    },

    # Dominant examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"You\'re going to do exactly what I say. No questions. Understood?"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "dominant", "confidence": 0.98, "reasoning": "Direct commands with authoritative tone, establishes clear power dynamic and control."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"On your knees. Now. Don\'t make me ask twice"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "dominant", "confidence": 0.96, "reasoning": "Commanding orders with implied consequences, maintains complete authority."}'
    },

    # Bratty examples
    {
        "role": "user",
        "content": 'Classify this caption:\n"I deserve to be spoiled today! Someone better treat me like the princess I am"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "bratty", "confidence": 0.97, "reasoning": "Entitled expectation of special treatment with princess attitude and demanding tone."}'
    },
    {
        "role": "user",
        "content": 'Classify this caption:\n"Why hasn\'t anyone bought this yet?? I worked SO hard on it! You guys are the worst"'
    },
    {
        "role": "assistant",
        "content": '{"tone": "bratty", "confidence": 0.94, "reasoning": "Whiny, demanding, guilt-tripping language expecting attention and purchases."}'
    }
]


# =============================================================================
# MODULE FUNCTIONS
# =============================================================================

def get_system_prompt() -> str:
    """
    Returns the classification system prompt.

    Returns:
        str: The system prompt for tone classification.
    """
    return SYSTEM_PROMPT


def get_few_shot_examples() -> list[dict]:
    """
    Returns the few-shot examples for tone classification.

    Returns:
        list[dict]: List of message dictionaries with role and content.
    """
    return FEW_SHOT_EXAMPLES.copy()


def build_classification_prompt(caption_text: str) -> list[dict]:
    """
    Builds the full message array for classification.

    Args:
        caption_text: The caption text to classify.

    Returns:
        list[dict]: Complete message array ready for Claude API.

    Example:
        messages = build_classification_prompt("Check out my new pics!")
        # Returns: [{"role": "system", ...}, {"role": "user", ...}, ...]
    """
    # Clean the caption text
    clean_caption = caption_text.strip()
    if not clean_caption:
        raise ValueError("Caption text cannot be empty")

    # Build message array
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Add few-shot examples
    messages.extend(FEW_SHOT_EXAMPLES)

    # Add the actual classification request
    messages.append({
        "role": "user",
        "content": f'Classify this caption:\n"{clean_caption}"'
    })

    return messages


def parse_response(response_text: str) -> dict:
    """
    Parses Claude's JSON response into a structured dictionary.

    Args:
        response_text: The raw text response from Claude.

    Returns:
        dict: Parsed response with 'tone', 'confidence', 'reasoning', and 'valid' keys.

    Example:
        result = parse_response('{"tone": "playful", "confidence": 0.9, "reasoning": "..."}')
        # Returns: {"tone": "playful", "confidence": 0.9, "reasoning": "...", "valid": True}
    """
    result = {
        "tone": None,
        "confidence": None,
        "reasoning": None,
        "valid": False,
        "error": None
    }

    try:
        # Try to extract JSON from the response
        # Handle cases where Claude might add extra text
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if not json_match:
            result["error"] = "No JSON object found in response"
            return result

        json_str = json_match.group()
        parsed = json.loads(json_str)

        # Validate required fields
        if "tone" not in parsed:
            result["error"] = "Missing 'tone' field"
            return result

        tone = parsed["tone"].lower().strip()
        if tone not in VALID_TONES:
            result["error"] = f"Invalid tone '{tone}'. Must be one of: {VALID_TONES}"
            return result

        # Extract confidence (default to 0.8 if missing)
        confidence = parsed.get("confidence", 0.8)
        if isinstance(confidence, str):
            confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        # Extract reasoning (default to empty string)
        reasoning = parsed.get("reasoning", "")

        result["tone"] = tone
        result["confidence"] = confidence
        result["reasoning"] = reasoning
        result["valid"] = True

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {str(e)}"
    except (ValueError, TypeError) as e:
        result["error"] = f"Value error: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result


def get_tone_definition(tone: str) -> Optional[str]:
    """
    Returns the definition for a specific tone.

    Args:
        tone: The tone name to look up.

    Returns:
        str or None: The tone definition, or None if not found.
    """
    return TONE_DEFINITIONS.get(tone.lower())


def estimate_prompt_tokens(caption_text: str) -> int:
    """
    Estimates the total token count for a classification prompt.

    This is a rough estimate using the ~4 chars per token rule.
    Actual token count may vary.

    Args:
        caption_text: The caption to be classified.

    Returns:
        int: Estimated token count.
    """
    messages = build_classification_prompt(caption_text)
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // 4  # Rough estimate


# =============================================================================
# TESTING / VALIDATION
# =============================================================================

def validate_prompt_module() -> dict:
    """
    Validates the prompt module configuration.

    Returns:
        dict: Validation results with 'valid' boolean and any 'errors'.
    """
    errors = []

    # Check tone definitions
    if len(TONE_DEFINITIONS) != 6:
        errors.append(f"Expected 6 tone definitions, found {len(TONE_DEFINITIONS)}")

    # Check few-shot examples (should have 2 per tone = 12 total pairs = 24 messages)
    if len(FEW_SHOT_EXAMPLES) != 24:
        errors.append(f"Expected 24 few-shot messages (2 per tone), found {len(FEW_SHOT_EXAMPLES)}")

    # Check system prompt exists
    if not SYSTEM_PROMPT or len(SYSTEM_PROMPT) < 100:
        errors.append("System prompt is missing or too short")

    # Test parse_response with valid input
    test_response = '{"tone": "playful", "confidence": 0.9, "reasoning": "test"}'
    parsed = parse_response(test_response)
    if not parsed["valid"]:
        errors.append(f"Failed to parse valid test response: {parsed['error']}")

    # Test parse_response with invalid tone
    invalid_response = '{"tone": "invalid_tone", "confidence": 0.9, "reasoning": "test"}'
    parsed_invalid = parse_response(invalid_response)
    if parsed_invalid["valid"]:
        errors.append("Should have rejected invalid tone")

    # Estimate token count
    sample_caption = "This is a test caption for token estimation."
    estimated_tokens = estimate_prompt_tokens(sample_caption)
    if estimated_tokens > 1500:
        errors.append(f"Prompt exceeds 1500 token target: ~{estimated_tokens} tokens")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "token_estimate": estimated_tokens,
        "tone_count": len(TONE_DEFINITIONS),
        "example_count": len(FEW_SHOT_EXAMPLES) // 2  # Pairs
    }


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("TONE CLASSIFICATION PROMPT MODULE")
    print("=" * 60)

    # Run validation
    print("\n[1] Running module validation...")
    validation = validate_prompt_module()

    if validation["valid"]:
        print("    Status: PASSED")
    else:
        print("    Status: FAILED")
        for error in validation["errors"]:
            print(f"    - {error}")

    print(f"    Tone definitions: {validation['tone_count']}")
    print(f"    Few-shot examples: {validation['example_count']} pairs")
    print(f"    Estimated tokens: ~{validation['token_estimate']}")

    # Show tone definitions
    print("\n[2] Tone Definitions:")
    for tone, definition in TONE_DEFINITIONS.items():
        print(f"    {tone}: {definition[:60]}...")

    # Test build_classification_prompt
    print("\n[3] Testing prompt builder...")
    test_caption = "Come see what I've been up to today, baby"
    try:
        messages = build_classification_prompt(test_caption)
        print(f"    Built {len(messages)} messages for caption")
        print(f"    System prompt: {len(messages[0]['content'])} chars")
        print(f"    Final user message: {messages[-1]['content'][:50]}...")
    except Exception as e:
        print(f"    ERROR: {e}")

    # Test parse_response
    print("\n[4] Testing response parser...")
    test_cases = [
        '{"tone": "seductive", "confidence": 0.95, "reasoning": "Intimate invitation"}',
        '{"tone": "PLAYFUL", "confidence": 0.8, "reasoning": "Fun energy"}',
        '{"tone": "invalid", "confidence": 0.5}',
        'Some text before {"tone": "dominant", "confidence": 0.9, "reasoning": "test"} after',
        'not json at all'
    ]

    for test in test_cases:
        result = parse_response(test)
        status = "VALID" if result["valid"] else f"INVALID ({result['error']})"
        print(f"    {test[:40]}... -> {status}")

    print("\n" + "=" * 60)
    print("Module ready for import by tone_classifier.py")
    print("=" * 60)

    sys.exit(0 if validation["valid"] else 1)
