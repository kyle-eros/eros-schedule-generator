# Send Type Reference Guide

> Comprehensive reference for all 22 send types supported by the EROS Schedule Generator, including requirements, constraints, and usage guidelines.

**Version:** 2.2.0 | **Updated:** 2025-12-16

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Send Types by Category](#send-types-by-category)
   - [Revenue Types (7)](#revenue-types-7)
   - [Engagement Types (9)](#engagement-types-9)
   - [Retention Types (5)](#retention-types-5)
3. [Detailed Send Type Profiles](#detailed-send-type-profiles)
4. [Caption Type Mappings Summary](#caption-type-mappings-summary)
5. [Usage Guidelines by Category](#usage-guidelines-by-category)
6. [Common Troubleshooting](#common-troubleshooting)
7. [References](#references)

---

## Quick Reference

This document provides a comprehensive reference for all 22 send types supported by the EROS Schedule Generator. Each send type represents a distinct content scheduling pattern with specific requirements, constraints, and use cases.

---

## Send Types by Category

### Revenue Types (9)

Send types focused on direct monetization through sales, tips, and campaigns.

| # | Key | Display Name | Requires Media | Requires Flyer | Can Have Followup | Page Type | Max/Day |
|---|-----|--------------|----------------|----------------|-------------------|-----------|---------|
| 1 | `ppv_unlock` | PPV Unlock | YES | YES (paid) | YES | both | 4 |
| 2 | `ppv_wall` | PPV Wall | YES | YES | NO | **free** | 3 |
| 3 | `tip_goal` | Tip Goal | YES | YES | NO | **paid** | 2 |
| 4 | `bundle` | Bundle Post | YES | YES | YES | both | 3 |
| 5 | `flash_bundle` | Flash Bundle | YES | YES | NO | both | 2 |
| 6 | `game_post` | Game Post | YES | YES | NO | both | 2 |
| 7 | `first_to_tip` | First To Tip | YES | YES | NO | both | 2 |
| 8 | `vip_program` | VIP Program | YES | YES | NO | both | 1 |
| 9 | `snapchat_bundle` | Snapchat Bundle | YES | YES | NO | both | 1 |

### Engagement Types (9)

Send types focused on fan interaction, visibility, and engagement metrics.

| # | Key | Display Name | Requires Media | Requires Flyer | Can Have Followup | Page Type | Max/Day |
|---|-----|--------------|----------------|----------------|-------------------|-----------|---------|
| 8 | `link_drop` | Link Drop | NO (auto) | NO | NO | both | 5 |
| 9 | `wall_link_drop` | Wall Link Drop | YES | YES | NO | both | 3 |
| 10 | `bump_normal` | Normal Bump | YES | NO | NO | both | 6 |
| 11 | `bump_descriptive` | Descriptive Bump | YES | NO | NO | both | 4 |
| 12 | `bump_text_only` | Text Only Bump | NO | NO | NO | both | 8 |
| 13 | `bump_flyer` | Flyer/GIF Bump | YES | YES | NO | both | 4 |
| 14 | `dm_farm` | DM Farm Post | YES | Optional | NO | both | 3 |
| 15 | `like_farm` | Like Farm Post | YES | Optional | NO | both | 2 |
| 16 | `live_promo` | Live Promo Post | YES | YES | NO | both | 2 |

### Retention Types (4)

Send types focused on subscriber retention, renewal, and re-engagement.

| # | Key | Display Name | Requires Media | Requires Flyer | Can Have Followup | Page Type | Max/Day |
|---|-----|--------------|----------------|----------------|-------------------|-----------|---------|
| 19 | `renew_on_post` | Renew On Post | YES | Optional | NO | **paid** | 2 |
| 20 | `renew_on_message` | Renew On Message | YES | Optional | NO | **paid** | 2 |
| 21 | `ppv_followup` | PPV Follow Up | Optional | NO | NO | both | 5 |
| 22 | `expired_winback` | Expired Sub Message | YES | YES | NO | **paid** | 1 |

---

## Detailed Send Type Profiles

### 1. PPV Unlock (`ppv_unlock`)

**Category**: Revenue
**Purpose**: Primary PPV for pictures and videos - main revenue driver for both paid and free pages
**Strategy**: Long-form descriptive caption with heavy emojis, compelling preview

**Requirements**:
- Media: YES
- Flyer: YES (paid pages must use campaigns), Optional (free pages can use unlocks)
- Price: YES
- Expiration: NO

**Caption Characteristics**:
- Length: Long (150-300 characters)
- Emoji Recommendation: Heavy (3-5 emojis)
- Caption Types: `ppv_unlock`, `descriptive_tease`

**Usage Guidelines**:
- Primary revenue generator - schedule 2-4 per day
- Peak hours: 7pm, 9pm, 10am, 2pm
- Auto-generate follow-ups 15-30 minutes after send
- Paid pages: Must use campaign format with GIF/picture flyer
- Free pages: Can use post unlocks
- Replaces legacy `ppv_video` and `ppv_message` types

**Common Use Cases**:
- High-production value content (B/G, anal, solo premium)
- Exclusive or limited content
- Scene-based storytelling content
- DM unlocks for free pages

---

### 2. PPV Wall (`ppv_wall`)

**Category**: Revenue
**Purpose**: Wall-based PPV for free pages only - public teaser with locked content
**Strategy**: Attractive wall post with locked preview to drive purchases from profile visitors
**Page Type**: FREE PAGES ONLY

**Requirements**:
- Media: YES
- Flyer: YES (preview image or GIF)
- Price: YES
- Expiration: NO

**Caption Characteristics**:
- Length: Medium (100-200 characters)
- Emoji Recommendation: Moderate (2-4 emojis)
- Caption Types: `ppv_unlock`, `descriptive_tease`

**Usage Guidelines**:
- Maximum 3 per day on free pages
- Best for high-quality preview content that entices purchases
- Use attractive flyer to grab attention from feed
- Not available for paid pages (use ppv_unlock instead)
- Great for driving traffic from OnlyFans search/discovery

**Common Use Cases**:
- Free page wall monetization
- High-quality teasers for premium content
- Discovery feed optimization
- Profile visitor conversion

---

### 3. Tip Goal (`tip_goal`)

**Category**: Revenue
**Purpose**: Tip campaign with configurable modes for paid pages
**Strategy**: Community-driven tipping with three distinct modes
**Page Type**: PAID PAGES ONLY

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO (uses tip amounts)
- Expiration: YES (configurable)
- Mode: Required (goal_based, individual, competitive)

**Tip Goal Modes**:

1. **Goal-Based Mode**: Community tips toward shared goal
   - Set total goal amount (e.g., $500)
   - All tips count toward single goal
   - Reward unlocks when goal reached
   - Best for: Community engagement, stretch goals

2. **Individual Mode**: Each tipper gets reward at threshold
   - Set tip amount threshold (e.g., $25)
   - Each person who tips threshold gets reward
   - No community goal tracking
   - Best for: Premium content, exclusive access

3. **Competitive Mode**: Race to be first/top tipper
   - Set goal amount as threshold
   - First person to reach threshold wins
   - Or highest tipper within time period wins
   - Best for: Exclusive 1-on-1 content, special prizes

**Caption Characteristics**:
- Length: Medium (100-200 characters)
- Emoji Recommendation: Heavy (3-5 emojis)
- Caption Types: `tip_request`, `exclusive_offer`

**Usage Guidelines**:
- Maximum 2 per day
- Not available for free pages
- Choose mode based on content exclusivity and audience size
- Set expiration based on goal amount (24-72 hours typical)
- Use compelling flyer showing reward preview

**Common Use Cases**:
- Community goal campaigns (goal_based)
- Premium content access (individual)
- Exclusive 1-on-1 prizes (competitive)
- Special event unlocks

**Configuration Examples**:
```json
{
  "send_type_key": "tip_goal",
  "tip_goal_mode": "goal_based",
  "goal_amount": 500.00,
  "expires_at": "2025-12-18T23:59:59"
}

{
  "send_type_key": "tip_goal",
  "tip_goal_mode": "individual",
  "goal_amount": 25.00
}

{
  "send_type_key": "tip_goal",
  "tip_goal_mode": "competitive",
  "goal_amount": 100.00,
  "expires_at": "2025-12-17T20:00:00"
}
```

---

### 4. VIP Program (`vip_program`)

**Category**: Revenue
**Purpose**: Promote VIP tier ($200 tip) for exclusive content access
**Strategy**: Create exclusivity, FOMO, and emphasize special access

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO (uses tip amount)
- Expiration: NO

**Caption Characteristics**:
- Length: Medium (75-150 characters)
- Emoji Recommendation: Moderate (1-3 emojis)
- Caption Types: `tip_request`, `exclusive_offer`

**Usage Guidelines**:
- Post once, never repost
- Set as campaign starting at $1,000 goal, expand in $1,000 increments to $10,000
- Maximum 1 per day (typically much less frequent)
- Use high-quality flyer design

**Common Use Cases**:
- Converting high-value fans
- Building exclusive tier access
- Special content bundle promotion

---

### 3. Game Post (`game_post`)

**Category**: Revenue
**Purpose**: Gamified buying opportunity (spin-the-wheel, contests)
**Strategy**: Fun, interactive, chance-based purchasing

**Requirements**:
- Media: YES (typically GIF)
- Flyer: YES
- Price: YES
- Expiration: YES (24 hours)

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Heavy
- Caption Types: `engagement_hook`

**Usage Guidelines**:
- Maximum 2 per day
- Campaign style with set price to play
- Almost always uses animated GIF
- Set 24-hour expiration

**Common Use Cases**:
- Spin-the-wheel games
- Prize contests
- Mystery box offerings

---

### 4. Bundle (`bundle`)

**Category**: Revenue
**Purpose**: Content bundle at set price
**Strategy**: Advertise deal value, sexy but not overly salesy

**Requirements**:
- Media: YES
- Flyer: YES
- Price: YES
- Expiration: NO

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Moderate
- Caption Types: `ppv_unlock`, `exclusive_offer`

**Usage Guidelines**:
- Maximum 3 per day
- Use GIF or picture flyer
- Can have follow-ups
- Emphasize value and savings

**Common Use Cases**:
- Multi-video packages
- Content type collections (all B/G videos)
- Monthly mega bundles

---

### 5. Flash Bundle (`flash_bundle`)

**Category**: Revenue
**Purpose**: Limited-quantity urgency bundle
**Strategy**: Create scarcity and FOMO

**Requirements**:
- Media: YES
- Flyer: YES
- Price: YES
- Expiration: YES (24 hours)

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Heavy
- Caption Types: `ppv_unlock`, `exclusive_offer`

**Usage Guidelines**:
- Maximum 2 per day
- Campaign style with generic graphic or model GIF/picture
- Emphasize limited quantity
- 24-hour expiration

**Common Use Cases**:
- First 10 buyers deals
- Limited time offers
- Clearance bundles

---

### 6. Snapchat Bundle (`snapchat_bundle`)

**Category**: Revenue
**Purpose**: Throwback Snapchat content bundle
**Strategy**: Nostalgia marketing, early content appeal

**Requirements**:
- Media: YES
- Flyer: YES
- Price: YES
- Expiration: NO

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Moderate
- Caption Types: `ppv_unlock`

**Usage Guidelines**:
- Maximum 1 per day
- Use throwback picture with Snapchat text bar as flyer
- High conversion rate historically
- Emphasize age (18-19) and authenticity

**Common Use Cases**:
- Snapchat archive content
- Early career throwbacks
- Nostalgia-driven sales

---

### 7. First To Tip (`first_to_tip`)

**Category**: Revenue
**Purpose**: Gamified tip race where goal = tip amount
**Strategy**: Competition, speed incentive, exclusivity

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO (uses tip amount)
- Expiration: YES (24 hours+)

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Heavy
- Caption Types: `tip_request`, `engagement_hook`

**Usage Guidelines**:
- Maximum 2 per day
- Visually enticing caption and flyer
- Set goal to match exact tip amount
- Expire after 24 hours (longer for higher goals)

**Common Use Cases**:
- Exclusive content races
- Special access competitions
- Limited edition rewards

---

### 8. Link Drop (`link_drop`)

**Category**: Engagement
**Purpose**: Repost campaign link (like a retweet)
**Strategy**: Short promotional push, auto-preview

**Requirements**:
- Media: NO (auto-generated preview)
- Flyer: NO
- Price: NO
- Expiration: YES (24 hours)

**Caption Characteristics**:
- Length: Short (30-75 characters)
- Emoji Recommendation: Light (0-2 emojis)
- Caption Types: `engagement_hook`, `flirty_opener`

**Usage Guidelines**:
- Maximum 5 per day
- Always expire after 24 hours
- Post preview generates automatically if done correctly
- Short caption promoting campaign or buying opportunity

**Common Use Cases**:
- Boosting active campaigns
- Re-promoting wall posts
- Driving traffic to recent content

---

### 9. Wall Link Drop (`wall_link_drop`)

**Category**: Engagement
**Purpose**: Promote specific wall campaign
**Strategy**: Manual media + link for wall tip promotion

**Requirements**:
- Media: YES (manual)
- Flyer: YES
- Price: NO
- Expiration: YES (24 hours)

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Light
- Caption Types: `engagement_hook`

**Usage Guidelines**:
- Maximum 3 per day
- Must manually add GIF/picture from same scene (no auto-preview)
- Great for pushing wall tips
- Include link to campaign

**Common Use Cases**:
- Wall tip campaigns
- Goal-based wall posts
- Special wall content promotion

---

### 10. Normal Bump (`bump_normal`)

**Category**: Engagement
**Purpose**: Entice fans to DM you
**Strategy**: Short, flirty, cute picture

**Requirements**:
- Media: YES
- Flyer: NO
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Short (30-75 characters)
- Emoji Recommendation: Moderate
- Caption Types: `flirty_opener`, `engagement_hook`

**Usage Guidelines**:
- Maximum 6 per day
- Cute/flirty picture paired with short caption
- Sound like a horny girl but keep it brief
- Most common engagement type

**Common Use Cases**:
- DM farming
- Engagement boosting
- Fan interaction
- Following up PPVs

---

### 11. Descriptive Bump (`bump_descriptive`)

**Category**: Engagement
**Purpose**: Drive DMs through storytelling
**Strategy**: Longer sexual narrative

**Requirements**:
- Media: YES
- Flyer: NO
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Long
- Emoji Recommendation: Moderate
- Caption Types: `descriptive_tease`, `sexting_response`

**Usage Guidelines**:
- Maximum 4 per day
- Uses longer, sexually descriptive caption
- Creates anticipation and intrigue
- More narrative-driven than normal bumps

**Common Use Cases**:
- Story-based engagement
- Sexual narrative hooks
- Building anticipation for content

---

### 12. Text Only Bump (`bump_text_only`)

**Category**: Engagement
**Purpose**: Quick engagement without media
**Strategy**: Minimal, fast, conversational

**Requirements**:
- Media: NO
- Flyer: NO
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Heavy
- Caption Types: `flirty_opener`

**Usage Guidelines**:
- Maximum 8 per day
- Short, flirty, cute text only
- Example: "wyd right now daddy 😈"
- Fastest engagement type

**Common Use Cases**:
- Quick check-ins
- High-frequency touchpoints
- Conversational engagement

---

### 13. Flyer/GIF Bump (`bump_flyer`)

**Category**: Engagement
**Purpose**: High-visibility bump with designed media
**Strategy**: Maximum attention with visual + text

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Long
- Emoji Recommendation: Heavy
- Caption Types: `descriptive_tease`, `ppv_unlock`

**Usage Guidelines**:
- Maximum 4 per day
- Longer sexual caption paired with designed flyer or GIF
- Maximum attention-grabbing format
- Higher production value than normal bumps

**Common Use Cases**:
- Premium engagement
- High-visibility touchpoints
- Designed promotional content

---

### 14. DM Farm (`dm_farm`)

**Category**: Engagement
**Purpose**: Drive immediate DMs
**Strategy**: Incentive-based immediate action

**Requirements**:
- Media: YES
- Flyer: Optional
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Heavy
- Caption Types: `engagement_hook`, `flirty_opener`

**Usage Guidelines**:
- Maximum 3 per day
- GIF, picture, or flyer
- "DM me for free surprise" or "I'm active now - DM me!"
- Emoji incentives work best

**Common Use Cases**:
- Free content giveaways via DM
- Active now notifications
- Direct engagement boosting

---

### 15. Like Farm (`like_farm`)

**Category**: Engagement
**Purpose**: Boost engagement metrics
**Strategy**: Incentivize post likes

**Requirements**:
- Media: YES
- Flyer: Optional
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Moderate
- Caption Types: `engagement_hook`

**Usage Guidelines**:
- Maximum 2 per day
- Encourage fans to "Like all posts" for free incentive
- Boosts algorithmic visibility
- Good for new pages

**Common Use Cases**:
- Algorithm boosting
- Engagement farming
- Free incentive giveaways

---

### 16. Live Promo (`live_promo`)

**Category**: Engagement
**Purpose**: Announce upcoming livestream
**Strategy**: Build anticipation for live event

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO
- Expiration: YES (until livestream)

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Moderate
- Caption Types: `engagement_hook`

**Usage Guidelines**:
- Maximum 2 per day
- Use livestream flyer with specific time and info in caption
- Post 2-6 hours before livestream
- Include timezone if necessary

**Common Use Cases**:
- Livestream announcements
- Special event promotion
- Interactive session invites

---

### 17. Renew On Post (`renew_on_post`)

**Category**: Retention
**Page Type**: PAID ONLY
**Purpose**: Convince fans to enable auto-renewal
**Strategy**: Enticing offer with renewal link on wall

**Requirements**:
- Media: YES
- Flyer: Optional
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Moderate
- Caption Types: `renewal_pitch`

**Usage Guidelines**:
- Maximum 2 per day
- Enticing caption with auto-renew link
- Can use GIFs, pictures, or videos
- Link format: `https://onlyfans.com/USERNAME?enable_renew=1`

**Common Use Cases**:
- Auto-renew campaigns
- Subscriber retention
- Renewal incentive offers

---

### 18. Renew On Message (`renew_on_message`)

**Category**: Retention
**Page Type**: PAID ONLY
**Purpose**: Targeted message to renew-off fans
**Strategy**: Free incentive for clicking renewal link

**Audience Target**: `renew_off` (fans with auto-renewal disabled)

**Requirements**:
- Media: YES
- Flyer: Optional
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Heavy
- Caption Types: `renewal_pitch`, `exclusive_offer`

**Usage Guidelines**:
- Maximum 2 per day
- Sent specifically to fans with auto-renewal OFF
- Offer free prize/incentive for clicking renewal link
- Highly targeted, high conversion

**Common Use Cases**:
- Renewal conversion campaigns
- Free content for renewers
- Retention incentives

---

### 19. PPV Message (`ppv_message`) - DEPRECATED

**Status**: DEPRECATED - Use `ppv_unlock` instead
**Transition Period**: Until 2025-01-16 (30 days)

**Category**: Retention
**Purpose**: Mass message with locked post (MERGED INTO ppv_unlock)
**Strategy**: This functionality is now handled by `ppv_unlock` send type

**Migration Path**:
- All new schedules should use `ppv_unlock` for both wall posts and DM unlocks
- Existing `ppv_message` schedules will continue to work during transition period
- After 2025-01-16, `ppv_message` will be removed from the system

**Replacement**:
```json
// Old (ppv_message)
{
  "send_type_key": "ppv_message",
  "channel": "mass_message"
}

// New (ppv_unlock)
{
  "send_type_key": "ppv_unlock",
  "channel_key": "mass_message"
}
```

---

### 20. PPV Follow Up (`ppv_followup`)

**Category**: Retention
**Purpose**: Close-the-sale follow-up 10-30 min after PPV
**Strategy**: Soft pressure, incentive, or excitement

**Parent Send Types**: `ppv_video`, `ppv_message`, `bundle`
**Audience Target**: `ppv_non_purchasers`

**Requirements**:
- Media: Optional
- Flyer: NO
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Short
- Emoji Recommendation: Moderate
- Caption Types: `ppv_followup`, `flirty_opener`

**Usage Guidelines**:
- Maximum 5 per day (auto-generated from parent PPVs)
- Sent 10-30 minutes after original PPV
- Targets only fans who saw but didn't buy
- Examples: "I can't believe I just sent this 😳" or "Free nude if you buy right now!"

**Common Use Cases**:
- Conversion boosting
- Last-chance offers
- Urgency creation

---

### 21. Expired Winback (`expired_winback`)

**Category**: Retention
**Page Type**: PAID ONLY
**Purpose**: Re-engage former subscribers
**Strategy**: Match current campaign/incentive

**Audience Target**: `expired_recent` or `expired_all`

**Requirements**:
- Media: YES
- Flyer: YES
- Price: NO
- Expiration: NO

**Caption Characteristics**:
- Length: Medium
- Emoji Recommendation: Moderate
- Caption Types: `renewal_pitch`, `exclusive_offer`

**Usage Guidelines**:
- Run daily
- Message must match current subscriber campaign/incentive
- Always send with picture/GIF flyers
- Maximum 1 per day

**Common Use Cases**:
- Winback campaigns
- Expired subscriber re-engagement
- Special return offers

---

## Caption Type Mappings Summary

### Revenue Send Types → Caption Types

| Send Type | Primary Caption Types | Alternative Caption Types |
|-----------|----------------------|---------------------------|
| ppv_unlock | `ppv_unlock` | `descriptive_tease` |
| ppv_wall | `ppv_unlock` | `descriptive_tease` |
| tip_goal | `tip_request`, `exclusive_offer` | `engagement_hook` |
| bundle | `ppv_unlock` | `exclusive_offer` |
| flash_bundle | `ppv_unlock`, `exclusive_offer` | - |
| game_post | `engagement_hook` | - |
| first_to_tip | `tip_request` | `engagement_hook` |
| vip_program | `tip_request` | `exclusive_offer` |
| snapchat_bundle | `ppv_unlock` | - |

### Engagement Send Types → Caption Types

| Send Type | Primary Caption Types | Alternative Caption Types |
|-----------|----------------------|---------------------------|
| link_drop | `engagement_hook` | `flirty_opener` |
| wall_link_drop | `engagement_hook` | - |
| bump_normal | `flirty_opener` | `engagement_hook` |
| bump_descriptive | `descriptive_tease` | `sexting_response` |
| bump_text_only | `flirty_opener` | - |
| bump_flyer | `descriptive_tease` | `ppv_unlock` |
| dm_farm | `engagement_hook`, `flirty_opener` | - |
| like_farm | `engagement_hook` | - |
| live_promo | `engagement_hook` | - |

### Retention Send Types → Caption Types

| Send Type | Primary Caption Types | Alternative Caption Types |
|-----------|----------------------|---------------------------|
| renew_on_post | `renewal_pitch` | - |
| renew_on_message | `renewal_pitch` | `exclusive_offer` |
| ppv_followup | `ppv_followup` | `flirty_opener` |
| expired_winback | `renewal_pitch`, `exclusive_offer` | - |
| ~~ppv_message~~ | DEPRECATED - Use ppv_unlock | - |

---

## Usage Guidelines by Category

### Revenue Category Strategy

**Goal**: Maximize direct monetization
**Volume**: 2-4 items per day (varies by tier)
**Timing**: Peak hours (7pm, 9pm, 10am, 2pm)
**Follow-ups**: Always enable for PPVs and bundles

**Distribution**:
- 60-70%: `ppv_unlock` (primary revenue driver)
- 15-20%: Wall PPV for free pages (`ppv_wall`) or Tip Goals for paid pages (`tip_goal`)
- 15-20%: Bundles (`bundle`, `flash_bundle`, `snapchat_bundle`)
- 5-10%: Games and special offers (`game_post`, `vip_program`, `first_to_tip`)

**Best Practices**:
- Always use high-quality flyers for paid pages
- Price based on content type performance tiers
- Stagger revenue sends minimum 2 hours apart
- Enable auto-follow-ups for conversion boosting

---

### Engagement Category Strategy

**Goal**: Maximize visibility and fan interaction
**Volume**: 3-6 items per day (varies by tier)
**Timing**: Distributed between revenue sends (45-90 min after)
**Follow-ups**: Not applicable

**Distribution**:
- 40-50%: Bumps (`bump_normal`, `bump_descriptive`, `bump_text_only`, `bump_flyer`)
- 30-40%: Link drops (`link_drop`, `wall_link_drop`)
- 10-20%: Farms and special (`dm_farm`, `like_farm`, `live_promo`)

**Best Practices**:
- Use bumps to keep feed active between PPVs
- Link drops to boost campaign visibility
- DM farms when actively monitoring messages
- Vary bump types to avoid repetition

---

### Retention Category Strategy

**Goal**: Maximize subscriber lifetime value
**Volume**: 1-3 items per day (paid pages only, except PPV messages)
**Timing**: Off-peak hours to avoid competing with revenue sends
**Follow-ups**: Yes for PPV messages

**Distribution** (Paid Pages):
- Daily: `expired_winback` (1 per day)
- 2-3x per week: `renew_on_message` (to renew_off segment)
- As needed: `renew_on_post`
- Auto-generated: `ppv_followup` (from parent PPVs)

**Best Practices**:
- Run expired winback daily with current incentive
- Target renew_off segment with renewal messages
- Use `ppv_unlock` for mass DM campaigns (not deprecated `ppv_message`)
- Auto-generate follow-ups for all PPV types

---

## Common Troubleshooting

### "No captions available for send type X"

**Cause**: No captions in caption_bank match the required caption types for this send type.

**Solution**:
1. Check send type caption requirements in `send_type_caption_requirements` table
2. Verify caption_bank has captions with matching `caption_type`
3. Lower `min_performance` or `min_freshness` thresholds
4. Add new captions of required types

---

### "Send type not available for page type"

**Cause**: Attempting to use a paid-only send type (e.g., `renew_on_message`) on a free page.

**Solution**:
1. Check `page_type_restriction` column in `send_types` table
2. Use only send types with `page_type_restriction = 'both'` for free pages
3. Filter send types by page type using `get_send_types(page_type='free')`

---

### "Volume constraints exceeded"

**Cause**: Schedule exceeds `max_per_day` or `max_per_week` for a send type.

**Solution**:
1. Check `max_per_day` column in `send_types` table
2. Reduce quantity of that send type in schedule
3. Distribute across more days
4. Adjust volume configuration in `volume_assignments` table

---

## References

- Database Schema: `/database/migrations/008_send_types_foundation.sql`
- Seed Data: `/database/migrations/008_send_types_seed_data.sql`
- Caption Type Mappings: `/database/migrations/008_mapping_tables.sql`
- Architecture Documentation: [ENHANCED_SEND_TYPE_ARCHITECTURE.md](ENHANCED_SEND_TYPE_ARCHITECTURE.md)
- User Guide: [USER_GUIDE.md](USER_GUIDE.md)
- Glossary: [GLOSSARY.md](GLOSSARY.md)
- MCP Server Tools: `/mcp/eros_db_server.py`

---

*Version 2.1.0 | Last Updated: 2025-12-16*
*Total Send Types: 22 (21 active + 1 deprecated) | Categories: 3 | Channels: 5 | Audience Targets: 10*
