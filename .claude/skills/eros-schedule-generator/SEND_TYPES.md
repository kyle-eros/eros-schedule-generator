# Send Types Reference

Complete reference for all 22 send types in the EROS scheduling system.

## Quick Reference Table

| Key | Category | Display Name | Media | Flyer | Price | Link | Expiration | Followup | Page Type |
|-----|----------|--------------|-------|-------|-------|------|------------|----------|-----------|
| ppv_unlock | revenue | PPV Unlock | Yes | Yes | Yes | No | No | Yes | both |
| ppv_wall | revenue | PPV Wall | Yes | Yes | Yes | No | No | Yes | FREE only |
| tip_goal | revenue | Tip Goal | Yes | No | Yes | No | No | No | PAID only |
| vip_program | revenue | VIP Program | Yes | Yes | No | No | No | No | both |
| game_post | revenue | Game Post | Yes | No | Yes | No | 24hr | No | both |
| bundle | revenue | Bundle | Yes | Yes | Yes | No | No | No | both |
| flash_bundle | revenue | Flash Bundle | Yes | Yes | Yes | No | 24hr | No | both |
| snapchat_bundle | revenue | Snapchat Bundle | Yes | Yes | Yes | No | No | No | both |
| first_to_tip | revenue | First to Tip | Yes | Yes | No | No | 24hr | No | both |
| link_drop | engagement | Link Drop | No | No | No | Yes | 24hr | No | both |
| wall_link_drop | engagement | Wall Link Drop | Yes | No | No | Yes | No | No | both |
| bump_normal | engagement | Bump (Normal) | Yes | No | No | No | No | No | both |
| bump_descriptive | engagement | Bump (Descriptive) | Yes | No | No | No | No | No | both |
| bump_text_only | engagement | Bump (Text Only) | No | No | No | No | No | No | both |
| bump_flyer | engagement | Bump (Flyer) | Yes | Yes | No | No | No | No | both |
| dm_farm | engagement | DM Farm | Yes | No | No | No | No | No | both |
| like_farm | engagement | Like Farm | Yes | No | No | No | No | No | both |
| live_promo | engagement | Live Promo | Yes | Yes | No | No | No | No | both |
| renew_on_post | retention | Renew On (Post) | Yes | No | No | Yes | No | No | paid |
| renew_on_message | retention | Renew On (Message) | Yes | No | No | No | No | No | paid |
| ppv_followup | retention | PPV Followup | No | No | No | No | No | No | both |
| expired_winback | retention | Expired Winback | Yes | No | No | No | No | No | paid |

---

## Revenue Category (9 Types)

Revenue-generating send types are the primary monetization drivers. These should comprise 50-60% of daily sends.

### 1. ppv_unlock

**Primary revenue driver for the platform (pics + videos).**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | long |
| Emoji Style | heavy |
| Requirements | media + flyer + price |
| Can Have Followup | Yes (20 min delay) |
| Max Per Day | 4 |
| Min Time Between | 2 hours |
| Page Type | both |

**Usage Notes:**
- Core monetization mechanism for both pics and videos
- Always pair with high-quality preview content
- Flyer should highlight value proposition
- Follow-ups target non-purchasers to close sales
- Renamed from ppv_video to reflect broader content types

---

### 2. ppv_wall

**Wall-posted PPV content (FREE pages only).**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | long |
| Emoji Style | heavy |
| Requirements | media + flyer + price |
| Can Have Followup | Yes (20 min delay) |
| Max Per Day | 3 |
| Min Time Between | 3 hours |
| Page Type | FREE only |

**Usage Notes:**
- FREE page exclusive - drives PPV sales on free accounts
- Posted on creator's wall for public visibility
- Requires promotional flyer to attract attention
- Follow-ups can target non-purchasers
- Use for fan-gating exclusive content

---

### 3. tip_goal

**Goal-based tipping system (PAID pages only).**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | heavy |
| Requirements | media + price + tip_goal_mode |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 4 hours |
| Page Type | PAID only |

**Tip Goal Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| goal_based | Collective goal, unlocks for all tippers | Community content unlock |
| individual | Each fan tips to unlock for themselves | Personal access model |
| competitive | First N tippers get exclusive access | Scarcity/competition driver |

**Usage Notes:**
- PAID pages only - leverages subscription relationship
- Creates urgency through goal mechanics
- goal_based mode builds community participation
- individual mode maximizes per-fan revenue
- competitive mode drives FOMO and early action
- Heavy emoji use matches gamification energy

---

### 4. vip_program

**VIP tier promotion targeting $200 tip goal.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media + flyer |
| Can Have Followup | No |
| Max Per Day | 1 |
| Max Per Week | 1 |
| Min Time Between | 24 hours |
| Page Type | both |

**Usage Notes:**
- Premium offering, use sparingly
- Weekly limit prevents audience fatigue
- Flyer should emphasize exclusive benefits
- Best scheduled mid-week when engagement peaks

---

### 5. game_post

**Spin-the-wheel and contest promotions.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | heavy |
| Requirements | media + price |
| Expiration | 24 hours |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 4 hours |
| Page Type | both |

**Usage Notes:**
- Creates excitement and urgency
- 24hr expiration drives immediate action
- Heavy emoji use matches playful tone
- Effective on weekends when fans are active

---

### 6. bundle

**Content bundle at set price point.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media + flyer + price |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 3 hours |
| Page Type | both |

**Usage Notes:**
- Standard bundled content offering
- Flyer should display bundle contents/value
- Price should reflect perceived value
- Can run multiple per day with variety

---

### 7. flash_bundle

**Limited-quantity urgency bundle.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | heavy |
| Requirements | media + flyer + price |
| Expiration | 24 hours |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 6 hours |
| Page Type | both |

**Usage Notes:**
- Creates scarcity and FOMO
- Heavy emoji emphasizes urgency
- 24hr expiration enforces limited availability
- Best used during high-traffic periods

---

### 8. snapchat_bundle

**Throwback/archive content from Snapchat.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media + flyer + price |
| Can Have Followup | No |
| Max Per Day | 1 |
| Max Per Week | 1 |
| Min Time Between | 24 hours |
| Page Type | both |

**Usage Notes:**
- Nostalgia-driven content offering
- Weekly limit preserves exclusivity
- Appeals to long-term fans
- Flyer should highlight "throwback" nature

---

### 9. first_to_tip

**Gamified tip race competition.**

| Attribute | Value |
|-----------|-------|
| Category | revenue |
| Caption Length | medium |
| Emoji Style | heavy |
| Requirements | media + flyer |
| Expiration | 24 hours |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 6 hours |
| Page Type | both |

**Usage Notes:**
- Competitive element drives engagement
- Heavy emoji matches game energy
- 24hr window creates urgency
- Best when audience is most active

---

## Engagement Category (9 Types)

Engagement types maintain audience connection and drive interaction. These should comprise 30-35% of daily sends.

### 10. link_drop

**Repost campaign link promotion.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | light |
| Requirements | link (no media - auto-preview) |
| Expiration | 24 hours |
| Can Have Followup | No |
| Max Per Day | 3 |
| Min Time Between | 2 hours |
| Page Type | both |

**Usage Notes:**
- No media needed - link generates preview
- Short caption keeps focus on link
- 24hr expiration for campaign freshness
- Can run multiple daily for different campaigns

---

### 11. wall_link_drop

**Wall post campaign promotion.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | light |
| Requirements | media + link |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 3 hours |
| Page Type | both |

**Usage Notes:**
- Combines visual with link call-to-action
- Wall placement increases visibility
- Short caption directs to link action
- Good for cross-promotion

---

### 12. bump_normal

**Short flirty engagement bump.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | light |
| Requirements | media |
| Can Have Followup | No |
| Max Per Day | 5 |
| Min Time Between | 1 hour |
| Page Type | both |

**Usage Notes:**
- Quick touchpoint with audience
- Maintains presence without heavy ask
- High frequency allowed (5/day)
- Good filler between revenue sends

---

### 13. bump_descriptive

**Story-driven engagement bump.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | long |
| Emoji Style | moderate |
| Requirements | media |
| Can Have Followup | No |
| Max Per Day | 3 |
| Min Time Between | 2 hours |
| Page Type | both |

**Usage Notes:**
- Narrative content builds connection
- Long caption allows storytelling
- More impactful than normal bump
- Use when sharing personal content

---

### 14. bump_text_only

**Text-only engagement bump.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | light |
| Requirements | none |
| Can Have Followup | No |
| Max Per Day | 4 |
| Min Time Between | 2 hours |
| Page Type | both |

**Usage Notes:**
- No media required
- Quick conversational touchpoint
- Good when vault content limited
- Maintains presence with minimal effort

---

### 15. bump_flyer

**High-impact flyer-based bump.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | long |
| Emoji Style | moderate |
| Requirements | media + flyer |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 4 hours |
| Page Type | both |

**Usage Notes:**
- Professional designed visual
- Long caption complements flyer message
- Lower frequency due to production effort
- Use for announcements or special content

---

### 16. dm_farm

**DM engagement driver.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | heavy |
| Requirements | media |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 4 hours |
| Page Type | both |

**Usage Notes:**
- Encourages direct message responses
- Heavy emoji creates approachable tone
- Builds 1:1 connection opportunities
- Good for converting casual viewers

---

### 17. like_farm

**Like-all-posts incentive.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | short |
| Emoji Style | light |
| Requirements | media |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 24 hours |
| Page Type | both |

**Usage Notes:**
- Drives engagement metrics
- Once daily maximum to avoid spam feel
- Simple ask with clear action
- Boosts algorithmic visibility

---

### 18. live_promo

**Livestream announcement.**

| Attribute | Value |
|-----------|-------|
| Category | engagement |
| Caption Length | medium |
| Emoji Style | heavy |
| Requirements | media + flyer |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 2 hours |
| Page Type | both |

**Usage Notes:**
- Promotes upcoming live sessions
- Heavy emoji creates excitement
- Flyer should include time/date
- Schedule before actual live time

---

## Retention Category (4 Types)

Retention types focus on subscriber maintenance and win-back. These should comprise 10-15% of daily sends. **Note: Several retention types are restricted to paid pages only.**

### 19. renew_on_post

**Auto-renewal promotion (wall post).**

| Attribute | Value |
|-----------|-------|
| Category | retention |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media + link |
| Can Have Followup | No |
| Max Per Day | 2 |
| Min Time Between | 12 hours |
| Page Type | **paid only** |

**Usage Notes:**
- Promotes auto-renewal feature
- Wall placement for broad visibility
- Link directs to renewal settings
- PAID PAGES ONLY - not applicable to free pages

---

### 20. renew_on_message

**Auto-renewal targeted message.**

| Attribute | Value |
|-----------|-------|
| Category | retention |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media |
| Target Audience | renew_off |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 24 hours |
| Page Type | **paid only** |

**Usage Notes:**
- Targets subscribers with auto-renew disabled
- Personal message approach
- Once daily to avoid annoyance
- PAID PAGES ONLY - not applicable to free pages

---

### 21. ppv_followup

**Close-the-sale followup message.**

| Attribute | Value |
|-----------|-------|
| Category | retention |
| Caption Length | short |
| Emoji Style | moderate |
| Requirements | none |
| Target Audience | ppv_non_purchasers |
| Can Have Followup | No |
| Max Per Day | 4 |
| Min Time Between | 1 hour |
| Page Type | both |

**Usage Notes:**
- Automatically generated after PPV sends
- Targets those who viewed but didn't purchase
- Short, urgent messaging
- Creates FOMO to close sales

---

## DEPRECATED Send Types

### ppv_message (DEPRECATED)

**⚠️ DEPRECATED - Merged into ppv_unlock**

| Attribute | Value |
|-----------|-------|
| Status | DEPRECATED |
| Replacement | ppv_unlock |
| Removal Date | 30 days from 2025-12-16 |

**Migration Notes:**
- ppv_message functionality merged into ppv_unlock
- Existing schedules will continue to work during transition period
- New schedules should use ppv_unlock instead
- After 30-day transition, ppv_message will be removed from system

---

### 22. expired_winback

**Former subscriber outreach.**

| Attribute | Value |
|-----------|-------|
| Category | retention |
| Caption Length | medium |
| Emoji Style | moderate |
| Requirements | media |
| Can Have Followup | No |
| Max Per Day | 1 |
| Min Time Between | 24 hours |
| Page Type | **paid only** |

**Usage Notes:**
- Re-engages lapsed subscribers
- Once daily to respect boundaries
- Media showcases what they're missing
- PAID PAGES ONLY - not applicable to free pages

---

## Category Summary

| Category | Count | Purpose | Daily Share |
|----------|-------|---------|-------------|
| Revenue | 9 | Direct monetization | 50-60% |
| Engagement | 9 | Audience connection | 30-35% |
| Retention | 4 | Subscriber maintenance | 10-15% |
| **Total** | **22** | | **100%** |

---

## Page Type Restrictions

### Both (Paid and Free)
All send types except those listed below.

### Free Pages Only
- ppv_wall

Wall-posted PPV content designed for free page monetization.

### Paid Pages Only
- tip_goal
- renew_on_post
- renew_on_message
- expired_winback

These types require subscription-based pages and are automatically excluded from free page schedules.
