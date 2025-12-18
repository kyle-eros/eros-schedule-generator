# Caption Matching Heuristics

**Document Version:** 1.0
**Last Updated:** 2025-12-15
**Status:** Production Reference

## Overview

This document defines the complete caption selection algorithm used by the EROS Schedule Generator. Caption matching is critical for schedule quality - the right caption at the right time can double conversion rates, while poor caption selection destroys engagement and revenue.

**Core Principle:** Match high-performing, fresh captions to send type requirements while maintaining diversity and alignment with creator persona.

---

## Selection Algorithm

### Primary Selection Flow

```python
def select_caption(creator_id, send_type_key, used_caption_ids, recent_content_types):
    """
    Select optimal caption for a specific send type.

    Args:
        creator_id: Creator identifier
        send_type_key: Send type key (e.g., 'ppv_unlock', 'bump_normal')
        used_caption_ids: Set of caption_ids already used in current schedule
        recent_content_types: List of content_type_ids used in last 4 hours

    Returns:
        dict: Selected caption with caption_id, caption_text, caption_type, etc.
        None: If no suitable caption found (requires manual creation)
    """

    # STEP 1: Fetch type-appropriate captions from database
    # These are pre-filtered by send_type_caption_requirements table
    # and ordered by priority, then performance
    captions = get_send_type_captions(
        creator_id=creator_id,
        send_type_key=send_type_key,
        min_freshness=30,      # Default: Not used heavily in last 30 days
        min_performance=40,    # Default: Above-average performance
        limit=20               # Get top 20 candidates for scoring
    )

    # STEP 2: Filter out already used captions
    # Prevents repetition within same schedule
    available = [c for c in captions if c.caption_id not in used_caption_ids]

    if not available:
        # FALLBACK: Try with relaxed constraints
        return fallback_selection(creator_id, send_type_key, used_caption_ids, recent_content_types)

    # STEP 3: Score each available caption
    for caption in available:
        caption.composite_score = calculate_composite_score(
            caption=caption,
            send_type_key=send_type_key,
            recent_content_types=recent_content_types
        )

    # STEP 4: Sort by composite score (highest first)
    available.sort(key=lambda c: c.composite_score, reverse=True)

    # STEP 5: Return top-scoring caption
    return available[0]
```

---

## Scoring Formula

### Composite Score Calculation

```python
def calculate_composite_score(caption, send_type_key, recent_content_types):
    """
    Calculate weighted composite score for caption selection.

    Score Range: 0-100
    Higher score = Better match
    """

    # Base scores from database (0-100 scale)
    performance_score = caption.performance_score  # Historical conversion/engagement
    freshness_score = caption.freshness_score      # Days since last use, inverted

    # Calculate bonus components
    type_priority_bonus = calculate_type_priority_bonus(caption, send_type_key)
    persona_match_bonus = calculate_persona_match_bonus(caption, send_type_key)
    diversity_bonus = calculate_diversity_bonus(caption, recent_content_types)

    # Weighted composite score
    composite_score = (
        freshness_score * 0.40 +        # 40% weight: Prioritize unused captions
        performance_score * 0.35 +      # 35% weight: Prefer high-earning captions
        type_priority_bonus * 0.15 +    # 15% weight: Send type compatibility
        diversity_bonus * 0.05 +        # 5% weight: Prevent repetition
        persona_match_bonus * 0.05      # 5% weight: Minor tone alignment
    )

    return composite_score
```

### Scoring Component Details

#### 1. Freshness Score (40% weight)

**What It Measures:** How recently this caption was used. Fresher = less audience fatigue.

**Why It Matters:** Even top-performing captions lose effectiveness if overused. Subscribers notice repetition and engagement drops 30-50% after 3rd use in 30 days.

**How It's Calculated:**
```python
days_since_last_use = (today - caption.last_used_date).days

if days_since_last_use >= 30:
    freshness_score = 100
elif days_since_last_use >= 20:
    freshness_score = 70
elif days_since_last_use >= 10:
    freshness_score = 40
else:
    freshness_score = 10
```

**Usage Guidelines:**
- Ideal: freshness >= 30 days (score 100)
- Acceptable: freshness 20-29 days (score 70)
- Risky: freshness 10-19 days (score 40)
- Avoid: freshness < 10 days (score 10) unless emergency

---

#### 2. Performance Score (35% weight)

**What It Measures:** Historical effectiveness of this caption based on revenue/engagement metrics.

**Why It Matters:** Past performance is the strongest predictor of future results. A caption with 80+ performance consistently outperforms one with 40 performance.

**How It's Calculated:**
- Database tracks per-caption metrics: unlock_rate, revenue_per_send, engagement_rate
- Normalized to 0-100 scale
- Higher = Better historical performance

**Usage Guidelines:**
- Never go below min_performance=30 except in emergency fallback
- Performance 70+ = Proven winner, prioritize heavily
- Performance 40-69 = Solid performer, safe choice
- Performance 30-39 = Risky, only use if no better options

---

#### 3. Type Priority Bonus (15% weight)

**What It Measures:** How well caption_type aligns with send_type requirements based on send_type_caption_requirements table.

**Why It Matters:** Each send type has specific caption needs. Using ppv_unlock caption for ppv_unlock gets priority=1, using generic flirty gets priority=3 or lower.

**How It's Calculated:**
```python
# Priority from send_type_caption_requirements.priority_order
if caption.priority_order == 1:
    type_priority_bonus = 20  # Perfect match
elif caption.priority_order in [2, 3]:
    type_priority_bonus = 10  # Good match
else:
    type_priority_bonus = 0   # Weak match
```

**Priority Tiers:**
- Priority 1: Designed specifically for this send type (e.g., ppv_unlock for ppv_unlock)
- Priority 2: Compatible and effective (e.g., ppv_tease for ppv_unlock)
- Priority 3: Generic but usable (e.g., flirty_generic for bump_normal)
- Priority 4+: Poor fit, only use in fallback

---

#### 4. Diversity Bonus (5% weight)

**What It Measures:** Content variety within the schedule to avoid repetitive messaging.

**Why It Matters:** Sending 3 "anal" PPVs in 4 hours tanks conversion on 2nd and 3rd. Diverse content types keep audience engaged.

**How It's Calculated:**
```python
def calculate_diversity_bonus(caption, recent_content_types):
    """
    recent_content_types: List of content_type_ids used in last 4 hours
    """

    # Check if this caption's content_type already used recently
    if caption.content_type_id not in recent_content_types:
        diversity_bonus = 10  # Fresh content type, full bonus
    else:
        # Count how many times this type used recently
        usage_count = recent_content_types.count(caption.content_type_id)

        if usage_count == 1:
            diversity_bonus = 5   # Used once, half penalty
        elif usage_count == 2:
            diversity_bonus = 2   # Used twice, heavy penalty
        else:
            diversity_bonus = 0   # Used 3+ times, no bonus

    return diversity_bonus
```

**Diversity Rules:**
- Track content_types in rolling 4-hour window
- Bonus for introducing new content types
- Penalty for repeating same type within window
- Reset window every 4 hours for fresh start

---

#### 5. Persona Match Bonus (5% weight)

**What It Measures:** Alignment between caption style and creator's persona profile.

**Why It Matters:** Brand consistency builds trust. If creator persona is "girlfriend_next_door" with "low" emoji usage, a heavy-emoji caption feels off-brand.

**How It's Calculated:**
```python
def calculate_persona_match_bonus(caption, creator_persona):
    bonus = 0

    # Tone alignment (0-5 points)
    if caption.tone == creator_persona.preferred_tone:
        bonus += 5
    elif caption.tone in creator_persona.acceptable_tones:
        bonus += 2

    # Emoji style alignment (0-3 points)
    caption_emoji_level = count_emojis(caption.caption_text)
    if matches_emoji_preference(caption_emoji_level, creator_persona.emoji_style):
        bonus += 3

    # Slang/language level (0-2 points)
    if caption.slang_level == creator_persona.slang_level:
        bonus += 2

    return bonus  # Max 10 points
```

**Persona Alignment Importance:**
- High priority for free pages (brand building)
- Medium priority for paid pages (revenue focus)
- Always important for retention sends (consistency matters)

---

## Fallback Strategy

When primary selection returns no results, use progressive relaxation of constraints.

### Fallback Hierarchy

```python
def fallback_selection(creator_id, send_type_key, used_caption_ids, recent_content_types):
    """
    Progressive fallback when no captions meet primary criteria.
    """

    # FALLBACK LEVEL 1: Relax freshness requirement
    # Try freshness >= 20 instead of >= 30
    captions = get_send_type_captions(
        creator_id=creator_id,
        send_type_key=send_type_key,
        min_freshness=20,      # Relaxed from 30
        min_performance=40,
        limit=20
    )
    available = [c for c in captions if c.caption_id not in used_caption_ids]
    if available:
        return select_best_from_pool(available, send_type_key, recent_content_types)

    # FALLBACK LEVEL 2: Relax performance requirement
    # Try performance >= 30 instead of >= 40
    captions = get_send_type_captions(
        creator_id=creator_id,
        send_type_key=send_type_key,
        min_freshness=20,
        min_performance=30,    # Relaxed from 40
        limit=20
    )
    available = [c for c in captions if c.caption_id not in used_caption_ids]
    if available:
        return select_best_from_pool(available, send_type_key, recent_content_types)

    # FALLBACK LEVEL 3: Relax both constraints
    # Try freshness >= 10, performance >= 30
    captions = get_send_type_captions(
        creator_id=creator_id,
        send_type_key=send_type_key,
        min_freshness=10,      # Heavily relaxed
        min_performance=30,
        limit=20
    )
    available = [c for c in captions if c.caption_id not in used_caption_ids]
    if available:
        return select_best_from_pool(available, send_type_key, recent_content_types)

    # FALLBACK LEVEL 4: Use generic high-performers
    # Ignore send_type_key, get creator's best captions regardless of type
    captions = execute_query("""
        SELECT caption_id, caption_text, caption_type, performance_score, freshness_score
        FROM captions
        WHERE creator_id = ?
          AND performance_score >= 50
          AND freshness_score >= 20
        ORDER BY performance_score DESC
        LIMIT 10
    """, [creator_id])
    available = [c for c in captions if c.caption_id not in used_caption_ids]
    if available:
        return available[0]  # Take best performer

    # FALLBACK LEVEL 5: Flag for manual creation
    # No suitable captions exist in database
    return {
        'status': 'MANUAL_REQUIRED',
        'reason': 'No captions available for send_type_key',
        'send_type_key': send_type_key,
        'action': 'Create new caption or expand caption bank'
    }
```

### Fallback Decision Tree

```
No captions with freshness>=30, performance>=40?
  ├─> Try freshness>=20, performance>=40
  │   └─> Found? Use it (Level 1 fallback)
  │
  ├─> Try freshness>=20, performance>=30
  │   └─> Found? Use it (Level 2 fallback)
  │
  ├─> Try freshness>=10, performance>=30
  │   └─> Found? Use it (Level 3 fallback)
  │
  ├─> Ignore type matching, use best generic captions
  │   └─> Found? Use it (Level 4 fallback)
  │
  └─> Flag for manual caption creation (Level 5 fallback)
```

---

## Send Type Specific Rules

Each send type has unique caption requirements. These rules MUST be followed for effective messaging.

### Revenue Category

#### 1. ppv_unlock

**Send Type Key:** `ppv_unlock`
**Purpose:** Sell PPV content (videos and pictures) to audience
**Channel:** DMs (mass or targeted message)
**Note:** Replaces deprecated ppv_video and ppv_message types
**Caption Requirements:**

- **Caption Type Priority:**
  1. `ppv_unlock` (priority 1) - Designed for video PPV unlock
  2. `ppv_tease` (priority 2) - Teases content to build desire
  3. `flirty_explicit` (priority 3) - Explicit language to drive urgency

- **Length:** 250-400 characters
  - Too short (<200 chars): Underperforms, lacks context
  - Too long (>500 chars): Truncated in DM preview, hurts unlock rate

- **Emoji Usage:** Heavy (8-15 emojis)
  - Visual impact in DM list drives higher open rates
  - Emojis convey excitement and urgency

- **Tone:** Explicit, direct, value-focused
  - Clearly state what's in the video
  - Create FOMO (scarcity/urgency)
  - Include call-to-action

- **Content Requirements:**
  - Must mention video content type (solo, b/g, fetish, etc.)
  - Include duration if long-form (10+ min)
  - Highlight unique selling point

**Example High-Performer:**
```
OMG babe 😍🔥 just filmed the HOTTEST solo video for you 💦💦
20 minutes of me playing with my new toy 🍆💕
You're gonna LOVE what I do at the 12 min mark 😈😏
Unlock now before I delete it!! ⏰🔒 $15
```

**Selection Logic:**
```python
if send_type_key == 'ppv_unlock':
    # Require specific caption types
    assert caption.caption_type in ['ppv_unlock', 'ppv_tease', 'flirty_explicit']

    # Length check
    assert 250 <= len(caption.caption_text) <= 400

    # Emoji count check (heavy usage)
    emoji_count = count_emojis(caption.caption_text)
    assert emoji_count >= 8

    # Content type alignment
    # Caption should reference content type (video/picture)
    assert caption.content_type_id is not None
```

---

#### 2. ppv_wall

**Send Type Key:** `ppv_wall`
**Purpose:** Wall-posted PPV for discovery and profile visitor conversion
**Channel:** Wall post
**Page Type:** FREE pages only
**Caption Requirements:**

- **Caption Type Priority:**
  1. `ppv_offer` (priority 1) - Designed for wall PPV
  2. `teaser` (priority 2) - Visual tease to drive unlock
  3. `flirty_playful` (priority 3) - Playful engagement

- **Length:** 100-200 characters
  - Shorter than DM PPVs (wall context)
  - Must grab attention quickly

- **Emoji Usage:** Moderate (4-8 emojis)
  - Visual appeal in feed
  - Not overwhelming

- **Tone:** Teasing, curiosity-driven, FOMO
  - "Unlock to see..."
  - "You don't want to miss this"
  - Create desire without revealing too much

- **Content Requirements:**
  - Clear unlock value proposition
  - Price visible upfront
  - Works for both videos and pictures

**Example High-Performer:**
```
Can't post this publicly 🙈🔥
Unlock to see what I'm hiding 😈
Too hot for the timeline 💦
$12 to unlock 🔒✨
```

---

#### 3. tip_goal

**Send Type Key:** `tip_goal`
**Purpose:** Community tipping campaign with flexible modes
**Channel:** DMs or wall post
**Page Type:** PAID pages only
**Caption Requirements:**

- **Caption Type Priority:**
  1. `tip_goal_promo` (priority 1) - Designed for tip campaigns
  2. `game_invite` (priority 2) - Gamified engagement
  3. `community_ask` (priority 3) - Community participation

- **Length:** 200-350 characters
  - Need space to explain goal and reward
  - Mode-specific messaging

- **Emoji Usage:** Heavy (10-15 emojis)
  - Celebratory tone
  - Progress indicators

- **Tone:** Community-driven, exciting, collective
  - "Let's hit this goal together"
  - "Help me reach..."
  - Clear reward structure

- **Content Requirements:**
  - State tip goal amount clearly
  - Explain reward (what unlocks at goal)
  - Mode indication (goal_based/individual/competitive)
  - Progress updates if ongoing

**Example High-Performer (goal_based mode):**
```
TIP GOAL!! 🎯💕
Help me reach $500 and I'll unlock a FULL b/g video for EVERYONE 🔥💦
Currently at $240! Who wants to help? 😘✨
Any amount helps babe 💖🙏
Let's do this together!! 🎉
```

**Example High-Performer (competitive mode):**
```
RACE IS ON!! 🏁💕
First to tip $100 gets a FREE custom video 🎥😈
Second place: 50% off discount
Third place: Exclusive pic set 📸
Ready... set... TIP!! 💸🔥
```

---

#### 4. ppv_picture_set (DEPRECATED - Use ppv_unlock)

**Send Type Key:** `ppv_picture_set`
**Purpose:** Sell photo set PPV content
**Channel:** DMs
**Note:** This type is deprecated. Use `ppv_unlock` for both videos and pictures
**Caption Requirements:**

- **Caption Type Priority:**
  1. `ppv_unlock` (priority 1)
  2. `ppv_tease` (priority 2)
  3. `flirty_playful` (priority 3)

- **Length:** 150-300 characters
  - Shorter than video PPVs (visual content speaks for itself)

- **Emoji Usage:** Moderate-Heavy (6-12 emojis)
  - Visual appeal but not overwhelming

- **Tone:** Playful, teasing, visually descriptive
  - Describe what's in photos (outfit, setting, poses)
  - Create visual curiosity

- **Content Requirements:**
  - Photo count (e.g., "25 pics")
  - Theme/setting (e.g., "lingerie," "bathtub")
  - Tease best shots without revealing everything

**Example High-Performer:**
```
New photoshoot just for you 📸💋
40 pics of me in red lingerie 🔴👙
Wait til you see pic #17... 😈💦
$10 to unlock the full set 🔒✨
```

---

#### 5. ppv_followup

**Send Type Key:** `ppv_followup`
**Purpose:** Re-engage users who didn't unlock initial PPV
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `ppv_followup` (priority 1) - REQUIRED, no exceptions
  2. No other types acceptable

- **Length:** 80-150 characters
  - Short and punchy
  - Creates urgency without feeling spammy

- **Emoji Usage:** Light-Moderate (3-6 emojis)
  - Subtle reminder, not aggressive

- **Tone:** Urgency, FOMO, scarcity
  - "Last chance," "expiring soon," "only X left"
  - Gentle pressure without desperation

- **Timing:** 2-6 hours after initial PPV

- **Content Requirements:**
  - Reference original PPV
  - Add urgency element (time limit, deletion warning)
  - Shorter price or "last chance" positioning

**Example High-Performer:**
```
Still haven't unlocked? 😢
Deleting in 2 hours babe ⏰💔
Last chance!! 🔒
```

**Selection Logic:**
```python
if send_type_key == 'ppv_followup':
    # STRICT: Must be ppv_followup caption type
    assert caption.caption_type == 'ppv_followup', "PPV followups require specific caption type"

    # Must be short and urgent
    assert 80 <= len(caption.caption_text) <= 150

    # Timing validation (handled in schedule_architect)
    # Followup must be 2-6 hours after parent PPV
```

---

#### 6. expired_winback

**Send Type Key:** `expired_winback`
**Purpose:** Re-engage expired subscribers with renewal offer
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `renewal_pitch` (priority 1) - REQUIRED
  2. `expired_followup` (priority 2)

- **Length:** 200-350 characters
  - Need space to pitch value + offer

- **Emoji Usage:** Moderate (5-8 emojis)
  - Friendly reminder, not desperate

- **Tone:** Welcoming, value-focused, incentive-driven
  - "Miss you," "special offer," "exclusive deal"
  - Highlight what they're missing
  - Clear renewal incentive

- **Content Requirements:**
  - Acknowledge they expired
  - Present compelling reason to renew
  - Include special offer/discount if available
  - Reference recent/upcoming content they'd enjoy

**Example High-Performer:**
```
I miss you babe 😢💔
Haven't seen you in my DMs lately...
Special offer just for you: 30% off renewal 🎁✨
Plus instant access to my 3 new videos 🔥💦
Come back? 🥺👉👈
```

---

#### 7. trial_upsell (NOT in 22-type system)

**Send Type Key:** `trial_upsell`
**Purpose:** Convert trial subscribers to paid
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `upsell_pitch` (priority 1)
  2. `value_proposition` (priority 2)

- **Length:** 180-300 characters

- **Emoji Usage:** Moderate (6-10 emojis)

- **Tone:** Value-focused, benefit-driven
  - Show what they get with paid vs trial
  - Exclusive content access
  - Pricing justification

**Example High-Performer:**
```
Loving the free trial babe? 💕
Upgrade to VIP and get:
✅ 200+ exclusive pics/vids
✅ Daily DM chats
✅ Custom content discounts
Only $9.99/month 🎁💖
```

---

### Engagement Category

#### 6. bump_normal

**Send Type Key:** `bump_normal`
**Purpose:** Re-engage audience, drive DM conversation
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `flirty_opener` (priority 1)
  2. `check_in` (priority 2)
  3. `question_prompt` (priority 3)

- **Length:** 60-120 characters
  - Short, conversational
  - Easy to respond to

- **Emoji Usage:** Light-Moderate (3-6 emojis)

- **Tone:** Casual, flirty, question-based
  - Open-ended questions
  - Personal connection
  - Low-pressure engagement

- **Content Requirements:**
  - Should prompt response
  - Feels personal, not mass-sent
  - Can reference creator's activity (gym, cooking, etc.)

**Example High-Performer:**
```
Bored at the gym 🏋️😩
What are you up to today? 💬✨
```

**Selection Logic:**
```python
if send_type_key == 'bump_normal':
    # Must be conversational/question-based
    assert caption.caption_type in ['flirty_opener', 'check_in', 'question_prompt']

    # Keep it short
    assert 60 <= len(caption.caption_text) <= 120

    # Should feel personal
    # Bonus for question marks (engagement driver)
    if '?' in caption.caption_text:
        engagement_bonus = 5
```

---

#### 7. bump_text_only

**Send Type Key:** `bump_text_only`
**Purpose:** Quick engagement bump without media
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `flirty_opener` (priority 1) - REQUIRED
  2. No media captions acceptable

- **Length:** 40-80 characters
  - Very short, quick read

- **Emoji Usage:** Light (2-4 emojis)
  - Minimal, conversational

- **Tone:** Ultra-casual, spontaneous
  - Feels like real text message
  - "Thinking of you" vibes

- **Content Requirements:**
  - NO media required or expected
  - Pure text engagement
  - Should feel spontaneous, not sales-y

**Example High-Performer:**
```
Thinking about you 💭💕
How's your day going? 😊
```

---

#### 8. poll_question

**Send Type Key:** `poll_question`
**Purpose:** Drive engagement via interactive polls
**Channel:** Stories or DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `poll_prompt` (priority 1) - REQUIRED
  2. `question_prompt` (priority 2)

- **Length:** 50-100 characters
  - Question must be clear and concise

- **Emoji Usage:** Light (2-5 emojis)

- **Tone:** Fun, curious, opinion-seeking
  - Binary questions work best
  - Relatable topics

- **Content Requirements:**
  - Clear A vs B choice
  - Relevant to audience interests
  - Not overly sexual (save for PPVs)

**Example High-Performer:**
```
Which do you prefer on me? 👀
Red lingerie or black? 🔴⚫
```

---

#### 9. interactive_game

**Send Type Key:** `interactive_game`
**Purpose:** Fun engagement through games/challenges
**Channel:** DMs or Stories
**Caption Requirements:**

- **Caption Type Priority:**
  1. `game_prompt` (priority 1)
  2. `challenge_prompt` (priority 2)

- **Length:** 100-180 characters
  - Need space to explain game rules

- **Emoji Usage:** Heavy (8-12 emojis)
  - Visual, playful, fun

- **Tone:** Playful, exciting, interactive
  - Game mechanics clearly explained
  - Reward for participation

**Example High-Performer:**
```
Let's play a game! 🎮💕
Send me a number 1-10
I'll tell you which outfit I'm wearing today 👗✨
Spicy numbers get spicy pics 😈🔥
```

---

### Retention Category

#### 10. welcome_new_sub

**Send Type Key:** `welcome_new_sub`
**Purpose:** Onboard new subscribers, set expectations
**Channel:** DMs (automated on subscription)
**Caption Requirements:**

- **Caption Type Priority:**
  1. `welcome_message` (priority 1) - REQUIRED
  2. `intro_message` (priority 2)

- **Length:** 250-400 characters
  - Need space to introduce brand and set expectations

- **Emoji Usage:** Moderate (6-10 emojis)
  - Warm, welcoming, friendly

- **Tone:** Grateful, welcoming, informative
  - Thank them for subscribing
  - Explain what to expect (content schedule, DM responsiveness)
  - Invite engagement

- **Content Requirements:**
  - Personal greeting
  - What they can expect (content types, frequency)
  - Encouragement to DM/engage
  - Optional: Welcome discount or free content

**Example High-Performer:**
```
Welcome babe! 💕✨
So happy you subscribed!! 🥰
Here's what you get:
📸 Daily exclusive pics
🎥 2-3 videos per week
💬 I respond to all DMs personally!
Check your messages for a welcome surprise 🎁😘
```

---

#### 11. loyalty_reward

**Send Type Key:** `loyalty_reward`
**Purpose:** Reward long-term subscribers to boost retention
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `reward_message` (priority 1)
  2. `appreciation_message` (priority 2)

- **Length:** 150-250 characters

- **Emoji Usage:** Heavy (8-12 emojis)
  - Celebratory, appreciative

- **Tone:** Grateful, exclusive, rewarding
  - Acknowledge loyalty
  - Make subscriber feel special
  - Provide genuine value

- **Content Requirements:**
  - Reference subscription length (30 days, 90 days, etc.)
  - Include reward (free content, discount, exclusive access)
  - Feels personal and exclusive

**Example High-Performer:**
```
You've been here 3 months!! 🎉💖
Thank you so much for your loyalty babe 🥰
Here's a FREE video as a thank you gift 🎁🔥
Plus 20% off your next PPV 💕
You're the best!! 😘✨
```

---

#### 12. re_engagement_dormant

**Send Type Key:** `re_engagement_dormant`
**Purpose:** Re-activate subscribers who haven't engaged in 7+ days
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `check_in` (priority 1)
  2. `miss_you_message` (priority 2)

- **Length:** 120-200 characters

- **Emoji Usage:** Light-Moderate (4-7 emojis)

- **Tone:** Curious, caring, non-pushy
  - "Haven't heard from you"
  - Check if everything's ok
  - Invite re-engagement without pressure

**Example High-Performer:**
```
Haven't seen you in my DMs lately 😢
Everything ok babe? 💕
Miss chatting with you! 💬
Let me know you're still around 🥺👋
```

---

#### 13. content_teaser_feed

**Send Type Key:** `content_teaser_feed`
**Purpose:** Tease upcoming content on main feed to drive anticipation
**Channel:** Main Feed
**Caption Requirements:**

- **Caption Type Priority:**
  1. `teaser_caption` (priority 1)
  2. `announcement` (priority 2)

- **Length:** 100-200 characters
  - Feed captions can be longer than DMs

- **Emoji Usage:** Moderate-Heavy (6-10 emojis)

- **Tone:** Excited, anticipatory, hype-building
  - "Coming soon"
  - "Dropping tomorrow"
  - Build curiosity without revealing too much

**Example High-Performer:**
```
Something SPECIAL dropping tomorrow 🔥💦
You're not ready for this one 😈
Set your notifications babe!! 🔔✨
Trust me, you don't wanna miss it 💕👀
```

---

#### 14. behind_scenes

**Send Type Key:** `behind_scenes`
**Purpose:** Build connection through personal/BTS content
**Channel:** Feed or DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `personal_share` (priority 1)
  2. `bts_caption` (priority 2)

- **Length:** 150-300 characters

- **Emoji Usage:** Light-Moderate (4-8 emojis)

- **Tone:** Personal, authentic, relatable
  - Share something real
  - Build personal connection
  - Humanize the creator

**Example High-Performer:**
```
Quick BTS from today's photoshoot 📸✨
Took me 3 outfit changes to get the perfect shot 😅
My photographer was laughing at me the whole time 😂
But I think it turned out amazing! 💕
Coming to your DMs soon 😘
```

---

### Additional Send Types

#### 15. mass_free_content

**Send Type Key:** `mass_free_content`
**Purpose:** Mass send free content to boost goodwill
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `gift_message` (priority 1)
  2. `appreciation_message` (priority 2)

- **Length:** 100-180 characters

- **Emoji Usage:** Moderate-Heavy (6-10 emojis)

- **Tone:** Generous, grateful, no-strings-attached
  - Pure gift, no ask
  - Build goodwill
  - Appreciate subscribers

**Example High-Performer:**
```
Free gift for being an amazing subscriber 🎁💕
No unlock needed, just enjoy babe! 😘✨
You deserve it 💖🔥
```

---

#### 16. campaign_promo

**Send Type Key:** `campaign_promo`
**Purpose:** Promote limited-time campaigns (holidays, sales, themes)
**Channel:** DMs or Feed
**Caption Requirements:**

- **Caption Type Priority:**
  1. `promo_announcement` (priority 1)
  2. `limited_offer` (priority 2)

- **Length:** 200-350 characters

- **Emoji Usage:** Heavy (10-15 emojis)
  - Theme-appropriate (hearts for Valentine's, pumpkins for Halloween)

- **Tone:** Urgent, exciting, event-driven
  - Campaign theme clearly stated
  - Time-limited offer
  - Strong call-to-action

**Example High-Performer:**
```
VALENTINE'S DAY SPECIAL 💕💘
50% off ALL my PPVs today only!! 🎁✨
Plus send me a ❤️ and I'll send you a FREE pic 📸
Offer ends midnight!! ⏰🔥
Show me some love babe 😘💖
```

---

#### 17. price_drop

**Send Type Key:** `price_drop`
**Purpose:** Re-engage with reduced price on existing PPV
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `discount_offer` (priority 1)
  2. `ppv_followup` (priority 2)

- **Length:** 120-200 characters

- **Emoji Usage:** Moderate (6-9 emojis)

- **Tone:** Urgent, deal-focused, FOMO
  - Original price vs new price
  - Limited time
  - "Last chance to save"

**Example High-Performer:**
```
PRICE DROP!! 💰🔥
That video from yesterday?
Was $20, now only $10!! 😱
Grab it before price goes back up ⏰✨
Limited time babe! 💕
```

---

#### 18. bundle_offer

**Send Type Key:** `bundle_offer`
**Purpose:** Sell multiple pieces of content as discounted bundle
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `bundle_pitch` (priority 1)
  2. `value_proposition` (priority 2)

- **Length:** 250-400 characters
  - Need space to explain bundle contents and savings

- **Emoji Usage:** Heavy (10-15 emojis)

- **Tone:** Value-driven, savings-focused
  - List what's included
  - Show savings calculation
  - Create urgency

**Example High-Performer:**
```
MEGA BUNDLE DEAL 🎁💰
Get ALL 3 of my latest videos:
🔥 Solo shower video (15 min)
🔥 BG scene (20 min)
🔥 Toy play video (12 min)
Normally $45, bundle price $25!! 😱
Save $20 babe!! 💕✨
Limited time offer 🔒⏰
```

---

#### 19. custom_request_promo

**Send Type Key:** `custom_request_promo`
**Purpose:** Promote custom content services
**Channel:** DMs or Feed
**Caption Requirements:**

- **Caption Type Priority:**
  1. `service_promo` (priority 1)
  2. `custom_offer` (priority 2)

- **Length:** 200-350 characters

- **Emoji Usage:** Moderate (6-10 emojis)

- **Tone:** Professional, service-oriented, clear
  - Explain what customs are
  - Pricing structure
  - How to order
  - Turnaround time

**Example High-Performer:**
```
Taking custom video requests!! 📹💕
Want me to make something JUST for you? 😈
$10/min, any theme/outfit/scenario 🎬✨
DM me with your fantasy babe 💬🔥
48hr delivery ⏰
Let's make it happen! 😘💖
```

---

#### 20. sexting_session_promo

**Send Type Key:** `sexting_session_promo`
**Purpose:** Sell live sexting sessions
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `service_promo` (priority 1)
  2. `live_offer` (priority 2)

- **Length:** 180-300 characters

- **Emoji Usage:** Heavy (8-12 emojis)

- **Tone:** Exciting, interactive, intimate
  - Real-time interaction
  - What's included (pics, vids, chat)
  - Duration and pricing

**Example High-Performer:**
```
Live sexting sessions available!! 💬🔥
30 mins of just you and me 😈💕
Includes:
📸 Live pics
🎥 Live videos
💬 Dirty chat
$50 for 30 min session ⏰✨
DM "SEXT" to book! 😘💦
```

---

#### 21. voice_note_dm

**Send Type Key:** `voice_note_dm`
**Purpose:** Send voice messages for personal connection
**Channel:** DMs
**Caption Requirements:**

- **Caption Type Priority:**
  1. `voice_intro` (priority 1)
  2. `personal_share` (priority 2)

- **Length:** 60-120 characters
  - Brief text accompanying voice note

- **Emoji Usage:** Light (3-5 emojis)

- **Tone:** Personal, intimate, authentic
  - Voice does the heavy lifting
  - Text just introduces the voice note

**Example High-Performer:**
```
Sent you a voice message babe 🎤💕
Listen to it!! 😘
(So much easier than typing 😂)
```

---

## Diversity Tracking

### Content Type Repetition Rules

**Problem:** Sending multiple PPVs of same content type (e.g., 3 "anal" videos in 4 hours) destroys conversion on 2nd and 3rd sends.

**Solution:** Track content_type usage in rolling windows and penalize repetition.

### Rolling Window Tracking

```python
class DiversityTracker:
    """
    Track content type usage to maintain schedule diversity.
    """

    def __init__(self):
        self.window_hours = 4  # Track 4-hour windows
        self.schedule_items = []  # All scheduled items with timestamps

    def get_recent_content_types(self, current_time):
        """
        Get content_type_ids used in last 4 hours from current_time.
        """
        cutoff_time = current_time - timedelta(hours=self.window_hours)

        recent = [
            item.content_type_id
            for item in self.schedule_items
            if item.scheduled_datetime >= cutoff_time
            and item.scheduled_datetime < current_time
            and item.content_type_id is not None
        ]

        return recent

    def calculate_diversity_penalty(self, content_type_id, recent_content_types):
        """
        Calculate penalty for content type repetition.

        Returns: 0-10 (10 = fresh type, 0 = heavily repeated)
        """
        if content_type_id not in recent_content_types:
            return 10  # Fresh content type, full bonus

        usage_count = recent_content_types.count(content_type_id)

        if usage_count == 1:
            return 5   # Used once, mild penalty
        elif usage_count == 2:
            return 2   # Used twice, heavy penalty
        else:
            return 0   # Used 3+ times, maximum penalty
```

### Diversity Rules by Category

#### Revenue Items (PPVs, Upsells, Bundles)

**Critical:** Content diversity most important here.

- **4-Hour Window:** No same content_type more than twice
- **8-Hour Window:** No same content_type more than 3 times
- **Daily:** Aim for at least 4 different content types across all PPVs

**Enforcement:**
```python
if send_type.category == 'revenue':
    recent_4h = get_recent_content_types(current_time, hours=4)

    if recent_4h.count(caption.content_type_id) >= 2:
        # Already used twice in last 4 hours, heavy penalty
        diversity_penalty = -15  # Severe penalty to composite score
```

#### Engagement Items (Bumps, Polls, Games)

**Moderate:** Diversity helpful but not critical.

- **4-Hour Window:** No same message type more than once
- Can repeat general "check-in" vibes, but vary specific questions

#### Retention Items (Welcome, Loyalty, Re-engagement)

**Low:** Diversity less important, these are triggered/targeted.

- Focus on timing appropriateness over diversity
- Content type not typically relevant

### Diversity Scoring Matrix

| Usage in Last 4h | Diversity Bonus | Composite Impact |
|------------------|-----------------|------------------|
| 0 times (fresh)  | +10 points      | Higher selection probability |
| 1 time           | +5 points       | Neutral |
| 2 times          | +2 points       | Discouraged |
| 3+ times         | 0 points        | Heavily discouraged |

### Content Type Variety Targets

**Daily Schedule Goals:**

- **Minimum:** 3 different content types across revenue items
- **Optimal:** 5+ different content types
- **Exceptional:** 7+ different content types with balanced distribution

**Example Good Distribution (8 PPVs in day):**
- 2x Solo videos (morning, evening)
- 2x B/G videos (afternoon, night)
- 1x Toy play video (midday)
- 1x Picture set - lingerie (morning)
- 1x Picture set - shower (evening)
- 1x Custom promo (afternoon)

**Example Poor Distribution (8 PPVs in day):**
- 8x Solo videos (all day)
- Result: Conversion rate drops 40% after 3rd send

---

## Quality Assurance Checks

### Pre-Selection Validation

Before selecting any caption, validate:

```python
def validate_caption_eligibility(caption, send_type_key, used_caption_ids):
    """
    Validate caption meets minimum requirements for selection.

    Returns: (is_valid, error_message)
    """

    # Check 1: Not already used in current schedule
    if caption.caption_id in used_caption_ids:
        return False, "Caption already used in schedule"

    # Check 2: Caption type compatible with send type
    compatible_types = get_compatible_caption_types(send_type_key)
    if caption.caption_type not in compatible_types:
        return False, f"Caption type {caption.caption_type} not compatible with {send_type_key}"

    # Check 3: Meets minimum performance threshold
    if caption.performance_score < 30:
        return False, "Performance score below minimum threshold (30)"

    # Check 4: Not overused (freshness check)
    if caption.freshness_score < 10:
        return False, "Caption overused (freshness < 10)"

    # Check 5: Character length within acceptable range
    min_length, max_length = get_length_requirements(send_type_key)
    if not (min_length <= len(caption.caption_text) <= max_length):
        return False, f"Caption length {len(caption.caption_text)} outside range {min_length}-{max_length}"

    # All checks passed
    return True, None
```

### Post-Selection Validation

After selecting caption, validate schedule context:

```python
def validate_schedule_context(caption, scheduled_time, recent_schedule):
    """
    Validate caption fits within schedule context.

    Returns: (is_valid, warnings)
    """
    warnings = []

    # Check 1: Time spacing from similar sends
    similar_sends = [
        item for item in recent_schedule
        if item.send_type_key == caption.send_type_key
    ]

    for item in similar_sends:
        hours_apart = abs((scheduled_time - item.scheduled_datetime).total_seconds() / 3600)
        if hours_apart < 2:
            warnings.append(f"Similar send within 2 hours: {item.send_type_key} at {item.scheduled_datetime}")

    # Check 2: Content type diversity
    recent_content_types = [
        item.content_type_id
        for item in recent_schedule
        if abs((scheduled_time - item.scheduled_datetime).total_seconds() / 3600) <= 4
    ]

    if recent_content_types.count(caption.content_type_id) >= 2:
        warnings.append(f"Content type {caption.content_type_id} already used 2+ times in last 4 hours")

    # Check 3: Tone/persona alignment
    if caption.tone != get_creator_persona().preferred_tone:
        if caption.tone not in get_creator_persona().acceptable_tones:
            warnings.append(f"Caption tone {caption.tone} may not align with creator persona")

    # Valid even with warnings, but surface them
    return True, warnings
```

---

## Performance Optimization Tips

### Caption Bank Quality

**High-Quality Caption Bank = Easy Selection**

Ensure caption bank has:
- At least 15 captions per send type category
- Performance scores distributed: 30% at 70+, 50% at 50-69, 20% at 40-49
- Fresh captions rotated in monthly
- Regular pruning of under-performers (<30 performance)

### Selection Speed

**Fast Selection Algorithm:**

```python
def optimize_selection_performance():
    """
    Tips for fast caption selection in production.
    """

    # 1. Pre-filter at database level
    # get_send_type_captions already filters by compatibility
    # Don't re-fetch full caption bank

    # 2. Limit candidate pool
    # 20 candidates sufficient for good selection
    # Don't fetch 100+ captions

    # 3. Cache persona profiles
    # Creator persona doesn't change often
    # Cache for session duration

    # 4. Batch diversity tracking
    # Update diversity tracker once per schedule build
    # Don't recalculate for each caption

    # 5. Early termination
    # If top-scoring caption is 95+, select immediately
    # Don't waste time scoring remaining captions
```

### A/B Testing Heuristics

**Test Scoring Weights:**

Current formula:
```
score = performance*0.35 + freshness*0.25 + priority*0.20 + persona*0.10 + diversity*0.10
```

Consider testing:
- Performance-heavy: 0.50, 0.20, 0.15, 0.10, 0.05
- Freshness-heavy: 0.25, 0.40, 0.20, 0.10, 0.05
- Diversity-heavy: 0.30, 0.20, 0.15, 0.10, 0.25

Measure impact on:
- Schedule conversion rate
- Revenue per schedule
- Audience engagement metrics

---

## Error Handling

### Common Error Scenarios

#### 1. No Captions Available

**Scenario:** No captions meet selection criteria even after fallback.

**Response:**
```python
{
    'status': 'MANUAL_REQUIRED',
    'send_type_key': 'ppv_unlock',
    'reason': 'No captions available after all fallback attempts',
    'action': 'Add captions to caption bank for this send type',
    'suggestion': 'Create 3-5 ppv_unlock captions with performance_score >= 40'
}
```

#### 2. All Captions Already Used

**Scenario:** Caption bank exhausted within single schedule.

**Response:**
```python
{
    'status': 'REUSE_REQUIRED',
    'send_type_key': 'bump_normal',
    'reason': 'All available captions already used in current schedule',
    'action': 'Reuse best-performing caption with lowest repeat count',
    'selected_caption': caption_with_min_reuse
}
```

#### 3. Type Mismatch

**Scenario:** Requested send type has no compatible captions.

**Response:**
```python
{
    'status': 'CONFIG_ERROR',
    'send_type_key': 'new_send_type',
    'reason': 'No caption types mapped to this send type',
    'action': 'Configure send_type_caption_requirements for this send type'
}
```

---

## Summary

Caption matching is a multi-factor optimization problem balancing:

1. **Freshness** (40%): Prioritize unused captions
2. **Historical Performance** (35%): Prefer high-earning captions
3. **Type Fit** (15%): Send type compatibility
4. **Diversity** (5%): Prevent repetition
5. **Persona Alignment** (5%): Minor tone alignment

**Selection Process:**
1. Fetch type-appropriate candidates from database
2. Filter out already-used captions
3. Score each candidate with weighted formula
4. Select highest-scoring caption
5. Validate against schedule context
6. Use fallback hierarchy if needed

**Success Metrics:**
- 90%+ selections from primary criteria (no fallback needed)
- <5% manual caption creation required
- Diversity score 7+ (out of 10) per schedule
- Persona alignment 90%+ across all selections

Follow these heuristics to ensure every schedule uses optimal captions that drive maximum engagement and revenue while maintaining brand consistency and content variety.

---

**Document Status:** Production Ready
**Review Cycle:** Quarterly (next review: 2026-03-15)
**Owner:** Schedule Generation System
**Dependencies:** send_type_caption_requirements table, captions table, creator_persona table
