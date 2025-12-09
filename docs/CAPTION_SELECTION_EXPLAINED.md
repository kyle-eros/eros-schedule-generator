# Caption Selection Process Explained

> A friendly guide to how EROS picks the perfect captions for your creators

---

## The Big Picture

Think of caption selection like a talent show with judges. Each caption "auditions" and gets scored on multiple factors. The highest-scoring captions get selected - but there's also a bit of randomness to keep things fresh!

```
                    +------------------+
                    |   Caption Pool   |
                    |  (19,590 total)  |
                    +--------+---------+
                             |
                             v
              +-----------------------------+
              |    FILTER: Fresh Enough?    |
              |    (freshness >= 30)        |
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              |   LOAD: Creator & Persona   |
              |   Profile from Database     |
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              |   SCORE: Each Caption       |
              |   (Earnings + Fresh + Boost)|
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              |  SELECT: Weighted Random    |
              |  (Vose Alias Method)        |
              +-------------+---------------+
                            |
                            v
                    +-------+-------+
                    | Final Schedule |
                    +---------------+
```

---

## Step 1: The Initial Filter

Before any scoring happens, captions must pass the **freshness test**.

| Criteria | Threshold | What It Means |
|----------|-----------|---------------|
| Freshness Score | >= 30 | Caption hasn't been overused recently |
| Is Active | = true | Caption isn't disabled/archived |
| Creator Match | = yes | Caption belongs to this creator OR is universal |

**Why freshness matters:** If a fan sees the same caption 3x in a week, it loses impact. The freshness score automatically decays when a caption is used and recovers over time.

---

## Step 2: Loading the Creator Profile

For each caption to be scored properly, we need to know **who the creator is** and **what their voice sounds like**.

### Creator Context Loaded:

```
+------------------------+
|   Creator Profile      |
+------------------------+
| - Page name           |
| - Fan count           |
| - Page type (paid/free)|
| - Best performing hours|
| - Vault content types |
+------------------------+
         +
+------------------------+
|   Persona Profile      |
+------------------------+
| - Primary tone        |   e.g., "playful", "bratty"
| - Secondary tone      |   e.g., "seductive"
| - Emoji frequency     |   "heavy", "moderate", "light"
| - Slang level         |   "heavy", "light", "none"
| - Avg sentiment       |   0.0 - 1.0 score
+------------------------+
```

---

## Step 3: The Scoring Formula

This is where the magic happens! Each caption gets a **final weight** calculated using:

### The Earnings-First Formula

```
Weight = (Earnings x 0.70) + (Freshness x 0.20) + (Persona Boost x 0.10)
          ^^^^^^^^^^^^^       ^^^^^^^^^^^^^^^       ^^^^^^^^^^^^^^^^^^
          70% of weight       20% of weight         10% tiebreaker
```

### 3A: Earnings Score (70% Weight)

This is the **primary factor**. Why? Because we want to prioritize captions that have **proven they make money**.

```
Earnings Priority (Fallback Chain):
+-------------------------------------------+
| 1. Creator-Specific Earnings              |  <- Best: How did this caption
|    (from caption_creator_performance)     |     perform for THIS creator?
+-------------------------------------------+
                  |
                  | if none...
                  v
+-------------------------------------------+
| 2. Global Average Earnings                |  <- Good: How did it perform
|    (from caption_bank.avg_earnings)       |     across ALL creators?
+-------------------------------------------+
                  |
                  | if none...
                  v
+-------------------------------------------+
| 3. Performance Score x 0.5                |  <- Fallback: Use engagement
|    (scaled to 0-50 range)                 |     metrics as a proxy
+-------------------------------------------+
```

**Log-scale normalization** is used to handle outliers. If one caption earned $20,733 and most earn ~$38, the high earner won't completely dominate the selection.

### 3B: Freshness Score (20% Weight)

Simple: how recently was this caption used?

| Freshness | Meaning |
|-----------|---------|
| 100 | Brand new / not used recently |
| 70-99 | Used a few times, recovering |
| 30-69 | Used moderately, still eligible |
| <30 | **Filtered out** - needs rest |

### 3C: Persona Boost (10% Weight)

This is where **voice matching** happens. The goal: match the caption's style to the creator's personality.

---

## Step 4: Persona Matching in Detail

### The Boost Factors

Each matching attribute adds a multiplicative boost:

| Match Type | Boost | Example |
|------------|-------|---------|
| **Primary Tone** | 1.20x | Caption is "playful", creator's primary is "playful" |
| **Secondary Tone** | 1.10x | Caption is "seductive", creator's secondary is "seductive" |
| **Emoji Frequency** | 1.05x | Caption uses heavy emojis, creator uses heavy emojis |
| **Slang Level** | 1.05x | Both use light slang (gonna, wanna, lol) |
| **Sentiment Aligned** | 1.05x | Caption sentiment matches creator's average |

**Maximum Combined Boost: 1.40x** (capped to prevent any caption from dominating)

### How Tone is Detected

**Option A: Database Lookup**
If the caption already has tone/slang stored in the database, use it directly.

**Option B: Text Detection (Automatic Fallback)**
If attributes are missing, the system analyzes the caption text using keyword patterns:

```
Tone Keywords:
+------------+------------------------------------------+
| Tone       | Keywords                                 |
+------------+------------------------------------------+
| playful    | hehe, lol, tease, surprise, wink, silly  |
| aggressive | now, demand, obey, worship, must         |
| sweet      | baby, honey, love, miss you, xoxo        |
| dominant   | control, power, dominate, permission     |
| bratty     | whatever, ugh, deserve, spoil, gimme     |
| seductive  | tempt, desire, crave, fantasy, whisper   |
| direct     | exclusive, deal, unlock, sale, limited   |
+------------+------------------------------------------+
```

### Confidence Scoring

Not all text detections are equal! The system calculates **confidence**:

| Confidence | Signal Strength | What Happens |
|------------|-----------------|--------------|
| 0.9 | Strong (3+ keyword matches) | Trusted without LLM |
| 0.7 | Moderate (1-2 matches) | Trusted with slight uncertainty |
| 0.5 | Weak signal | May need LLM analysis |
| 0.3 | Competing tones | Flagged for LLM review |

---

## Step 5: LLM Full Mode (The Secret Sauce)

When you run in **full mode**, Claude's intelligence enhances the selection process.

### What Gets Flagged for LLM Analysis?

```
+----------------------------------------+
| Caption flagged for Claude review if:  |
+----------------------------------------+
| - No stored tone AND confidence < 60%  |
| - Very low confidence (< 40%)          |
| - Multiple competing tone signals      |
| - High performer (70+ score) but low   |
|   persona match (< 1.10x boost)        |
+----------------------------------------+
```

### What Claude Analyzes

For each flagged caption, Claude evaluates:

```
+-----------------------------------+
| 1. TRUE TONE                       |
|    What's the REAL tone beyond     |
|    keyword matching?               |
|                                    |
|    "Oh sure, I'll just give        |
|    this away for free..."          |
|    Keywords say: "sweet"           |
|    Claude says: "bratty/sarcastic" |
+-----------------------------------+

+-----------------------------------+
| 2. PERSONA MATCH SCORE (0-1.0)    |
|    How well does this fit the     |
|    creator's voice?                |
+-----------------------------------+

+-----------------------------------+
| 3. CONTENT QUALITY SCORE (0-1.0)  |
|    - Hook strength (30%)          |
|    - Urgency/scarcity (20%)       |
|    - Call-to-action (30%)         |
|    - Emotional resonance (20%)    |
+-----------------------------------+

+-----------------------------------+
| 4. AUTHENTICITY CHECK             |
|    Does it sound human?           |
|    Or robotic/AI-generated?       |
+-----------------------------------+
```

### Anti-AI Detection Tips Claude Uses

| Red Flag | Why It's Bad |
|----------|--------------|
| "I would like to offer you..." | Too formal |
| Perfect grammar, no quirks | Feels robotic |
| Generic phrases | Could be anyone |
| "do not" instead of "don't" | Missing contractions |

| Good Sign | Why It Works |
|-----------|--------------|
| Personality-specific phrases | Unique voice |
| Natural emoji usage | Authentic |
| Casual contractions | Real texting |
| Imperfect punctuation | Human touch |

---

## Step 6: The Vose Alias Selection

Once all captions have weights, we need to **select** the right number for the schedule.

### Why Not Just Pick the Top N?

If we always picked the highest-weighted captions:
- Same captions would appear every week
- No variety for fans
- Fresh content never gets tested

### The Solution: Weighted Random Selection

**Vose Alias Method** gives us O(1) selection time with weighted probabilities.

```
How It Works (Simplified):
+---------------------------------------------------+
| Caption A: weight 85  --> ~40% chance selected    |
| Caption B: weight 65  --> ~30% chance selected    |
| Caption C: weight 45  --> ~20% chance selected    |
| Caption D: weight 20  --> ~10% chance selected    |
+---------------------------------------------------+
```

Higher weights = higher probability of selection, but not guaranteed!

### No Duplicates Mode

When selecting for a 7-day schedule, we use `allow_duplicates=False`:
- Each caption can only be selected once
- System tries up to 20x the requested count to find unique captions
- Prevents the same caption appearing multiple times in a week

---

## The Complete Flow Diagram

```
                     START
                       |
                       v
        +-----------------------------+
        |  Load Creator from Database |
        +-----------------------------+
                       |
                       v
        +-----------------------------+
        |  Load Persona Profile       |
        |  (tone, emoji, slang, etc.) |
        +-----------------------------+
                       |
                       v
        +-----------------------------+
        |  Query Eligible Captions    |
        |  - is_active = true         |
        |  - freshness >= 30          |
        |  - creator match OR universal|
        +-----------------------------+
                       |
                       v
        +-----------------------------+
        |  For Each Caption:          |
        |                             |
        |  1. Get effective earnings  |
        |     (creator > global > perf)|
        |                             |
        |  2. Normalize to 0-100      |
        |     (log scale)             |
        |                             |
        |  3. Calculate persona boost |
        |     - Tone match?           |
        |     - Emoji match?          |
        |     - Slang match?          |
        |     - Sentiment aligned?    |
        |                             |
        |  4. Compute final weight    |
        |     earn*0.70 + fresh*0.20  |
        |     + persona*0.10          |
        +-----------------------------+
                       |
          +------------+------------+
          |                         |
     QUICK MODE               FULL MODE
          |                         |
          v                         v
    Pattern-based           +-----------------+
    scores only             | Identify low    |
          |                 | confidence      |
          |                 | captions        |
          |                 +-----------------+
          |                         |
          |                         v
          |                 +-----------------+
          |                 | Claude analyzes |
          |                 | flagged captions|
          |                 | - True tone     |
          |                 | - Quality score |
          |                 | - Authenticity  |
          |                 +-----------------+
          |                         |
          |                         v
          |                 +-----------------+
          |                 | Update weights  |
          |                 | with LLM        |
          |                 | insights        |
          |                 +-----------------+
          |                         |
          +------------+------------+
                       |
                       v
        +-----------------------------+
        |  Build Vose Alias Table     |
        |  (O(n) preprocessing)       |
        +-----------------------------+
                       |
                       v
        +-----------------------------+
        |  Select Required Captions   |
        |  - O(1) per selection       |
        |  - No duplicates            |
        +-----------------------------+
                       |
                       v
        +-----------------------------+
        |  Assign to Schedule Slots   |
        |  - Match content types      |
        |  - Apply timing rules       |
        +-----------------------------+
                       |
                       v
                     END
```

---

## Quick Reference: Weight Components

| Component | Weight | Source | Purpose |
|-----------|--------|--------|---------|
| **Earnings** | 70% | Database (3-tier fallback) | Prioritize proven performers |
| **Freshness** | 20% | Database (auto-calculated) | Prevent overuse |
| **Persona Boost** | 10% | Calculated (pattern + LLM) | Match creator voice |

---

## Quick Mode vs Full Mode

| Aspect | Quick Mode | Full Mode |
|--------|------------|-----------|
| **Speed** | Fast (~5 sec) | Slower (~30 sec) |
| **Tone Detection** | Pattern-only | Pattern + LLM |
| **Confidence** | Uses patterns as-is | Flags low-confidence for review |
| **Quality** | Good | Best |
| **Best For** | Quick drafts, testing | Production schedules |

---

## Why This System Works

1. **Money talks first** - 70% weight on earnings ensures top performers get selected
2. **Freshness prevents fatigue** - Captions rotate naturally
3. **Voice matching builds brand** - Persona boost ensures consistency
4. **Randomness adds variety** - Weighted selection keeps things interesting
5. **LLM catches edge cases** - Claude handles nuanced tone detection
6. **O(1) selection scales** - Vose Alias handles large caption pools efficiently

---

*Generated for EROS Schedule Generator v2.0*
