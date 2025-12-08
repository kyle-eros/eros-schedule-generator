# Content Classification Quick Reference

## Decision Tree

```
START
  |
  v
Contains direct anatomy terms + action verbs?
  |-- YES --> EXPLICIT
  |-- NO --> continue
  v
Contains fluid descriptors (dripping, wet, creamy)?
  |-- YES --> EXPLICIT
  |-- NO --> continue
  v
POV or close-up language?
  |-- YES --> EXPLICIT
  |-- NO --> continue
  v
Question framing ("wanna see?", "should I?")?
  |-- YES --> continue to implied check
  |-- NO --> continue
  v
Future tense promise ("I'll show you")?
  |-- YES --> IMPLIED
  |-- NO --> continue
  v
Euphemisms only (kitty, cherry, flower)?
  |-- YES --> IMPLIED
  |-- NO --> continue
  v
Hidden/covered language (underneath, peek)?
  |-- YES --> IMPLIED
  |-- NO --> continue
  v
UNCERTAIN? --> EXPLICIT (safety default)
```

## Quick Indicators Table

| Indicator | Classification | Example |
|-----------|----------------|---------|
| "look at my [body part]" | EXPLICIT | "look at my pussy" |
| "spreading/fucking/cumming" | EXPLICIT | "spreading for you" |
| "dripping/creamy/wet" + body | EXPLICIT | "my wet pussy" |
| "POV/close up" | EXPLICIT | "POV of me touching" |
| "freshly shaved/smooth" | EXPLICIT | "just shaved smooth" |
| "wanna see?" (question only) | IMPLIED | "wanna see what's under?" |
| "kitty/cherry/flower" (euphemism) | IMPLIED | "my little kitty" |
| "underneath/hidden/peek" | IMPLIED | "peek under my dress" |
| "I'll show you..." (future) | IMPLIED | "I'll show you later" |
| "slowly slide off" (pre-reveal) | IMPLIED | "watch me undress" |

## Content Type ID Mapping

| Original Type | ID | Implied Type | ID |
|---------------|----|--------------|----|
| pussy_play | 16 | implied_pussy_play | 34 |
| toy_play | 17 | implied_toy_play | 37 |
| tits_play | 18 | implied_tits_play | 36 |
| solo | 19 | implied_solo | 35 |

## Confidence Thresholds

| Score | Action |
|-------|--------|
| 0.95+ | Auto-apply classification |
| 0.80-0.94 | Apply with logging |
| 0.65-0.79 | Apply with review flag |
| 0.50-0.64 | Default to EXPLICIT, flag |
| <0.50 | Human review required |

## Edge Case Rules

1. **Mixed signals** (explicit + implied indicators) --> EXPLICIT
2. **Very short** (<10 words, unclear) --> EXPLICIT
3. **Emoji-heavy** (minimal text) --> EXPLICIT
4. **Non-English** --> EXPLICIT
5. **Unrecognized slang** --> EXPLICIT
6. **Question that delivers** ("Wanna see? Here it is") --> EXPLICIT
