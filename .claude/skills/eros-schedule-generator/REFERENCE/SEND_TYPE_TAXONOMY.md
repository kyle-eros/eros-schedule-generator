# Send Type Taxonomy

**Version**: 2.4.0 | **Status**: Canonical Reference | **Last Updated**: 2025-12-19

Complete reference for the 22 send types in the EROS Schedule Generator. This is the single source of truth for send type categorization, constraints, and usage rules.

---

## Revenue Types (9)

Send types focused on direct monetization through sales, tips, and campaigns.

| Key | Display Name | Max/Day | Max/Week | Page Type | Requires Media | Requires Flyer | Can Followup |
|-----|--------------|---------|----------|-----------|----------------|----------------|--------------|
| `ppv_unlock` | PPV Unlock | 4 | - | both | YES | YES (paid) | YES |
| `ppv_wall` | PPV Wall | 3 | - | **free only** | YES | YES | NO |
| `tip_goal` | Tip Goal | 2 | - | **paid only** | YES | YES | NO |
| `bundle` | Bundle Post | 3 | - | both | YES | YES | YES |
| `flash_bundle` | Flash Bundle | 2 | - | both | YES | YES | NO |
| `game_post` | Game Post | 2 | - | both | YES | YES | NO |
| `first_to_tip` | First To Tip | 2 | - | both | YES | YES | NO |
| `vip_program` | VIP Program | 1 | 1 | both | YES | YES | NO |
| `snapchat_bundle` | Snapchat Bundle | 1 | 1 | both | YES | YES | NO |

### Revenue Notes

- **`ppv_unlock`**: Primary PPV for pictures/videos - main revenue driver for both page types
  - Paid pages: Must use campaign format with flyer
  - Free pages: Can use post unlocks or DM unlocks
  - Replaces deprecated `ppv_message` and `ppv_video`
- **`ppv_wall`**: Wall-based PPV for FREE pages only - public teaser with locked content
- **`tip_goal`**: Tip campaign with 3 modes (goal_based, individual, competitive) - PAID pages only
- **`vip_program`**: VIP tier promotion ($200 tip) - maximum 1 per week
- **`snapchat_bundle`**: Throwback Snapchat content - maximum 1 per week

---

## Engagement Types (9)

Send types focused on fan interaction, visibility, and engagement metrics.

| Key | Display Name | Max/Day | Max/Week | Page Type | Requires Media | Requires Flyer | Can Followup |
|-----|--------------|---------|----------|-----------|----------------|----------------|--------------|
| `link_drop` | Link Drop | 5 | - | both | NO (auto) | NO | NO |
| `wall_link_drop` | Wall Link Drop | 3 | - | both | YES | YES | NO |
| `bump_normal` | Normal Bump | 6 | - | both | YES | NO | NO |
| `bump_descriptive` | Descriptive Bump | 4 | - | both | YES | NO | NO |
| `bump_text_only` | Text Only Bump | 8 | - | both | NO | NO | NO |
| `bump_flyer` | Flyer/GIF Bump | 4 | - | both | YES | YES | NO |
| `dm_farm` | DM Farm Post | 3 | - | both | YES | Optional | NO |
| `like_farm` | Like Farm Post | 2 | - | both | YES | Optional | NO |
| `live_promo` | Live Promo | 2 | - | both | YES | YES | NO |

### Engagement Notes

- **Bump types**: Short, flirty messages to drive DM engagement
  - `bump_normal`: Most common, cute picture + short caption
  - `bump_descriptive`: Longer sexual narrative
  - `bump_text_only`: No media, fastest engagement
  - `bump_flyer`: High-visibility with designed media
- **Link drops**: Repost campaign links for visibility boost
  - `link_drop`: Auto-preview, no manual media
  - `wall_link_drop`: Manual media + link for wall campaigns
- **Farm types**: Incentivize specific engagement actions
  - `dm_farm`: "DM me for free surprise" style posts
  - `like_farm`: Encourage fans to like posts for free incentive

---

## Retention Types (4)

Send types focused on subscriber retention, renewal, and re-engagement.

| Key | Display Name | Max/Day | Max/Week | Page Type | Requires Media | Requires Flyer | Can Followup |
|-----|--------------|---------|----------|-----------|----------------|----------------|--------------|
| `renew_on_post` | Renew On Post | 2 | - | **paid only** | YES | Optional | NO |
| `renew_on_message` | Renew On Message | 2 | - | **paid only** | YES | Optional | NO |
| `ppv_followup` | PPV Follow Up | 5 | - | both | Optional | NO | NO |
| `expired_winback` | Expired Sub Message | 1 | - | **paid only** | YES | YES | NO |

### Retention Notes

- **Renewal types**: Only for PAID pages
  - `renew_on_post`: Wall post with auto-renew link
  - `renew_on_message`: Targeted message to `renew_off` segment with free incentive
- **`ppv_followup`**: Auto-generated 20-60 min after parent PPV (separate from PPV unlock limit)
  - Targets `ppv_non_purchasers` audience
  - Maximum 5 per day (scales at 80% of PPV count)
- **`expired_winback`**: Re-engage former subscribers - run daily

---

## Critical Constraints

### Page Type Restrictions

| Page Type | Allowed Send Types | Excluded Send Types |
|-----------|-------------------|---------------------|
| **FREE** | All except retention types | `tip_goal`, `renew_on_post`, `renew_on_message`, `expired_winback` |
| **PAID** | All 22 types | `ppv_wall` |

### Daily Limits

- **PPV Unlocks**: Maximum 4/day (primary revenue sends)
- **PPV Followups**: Maximum 5/day (auto-generated, scales at 80% of PPV count)
- **Bumps**: Total bump count varies by content category (see Volume Optimization)

### Weekly Limits

- **VIP Program**: 1/week maximum
- **Snapchat Bundle**: 1/week maximum

### Caption Freshness

- **Minimum reuse threshold**: 30 days since last use
- **Never-used captions**: Priority score = 100
- **Freshness formula**: `100 - (days_since_last_use * 2)`

---

## Weekly Distribution Minimums

Required minimum counts across 7-day schedule for type variety.

### Revenue Types

| Send Type | Min Weekly | Notes |
|-----------|-----------|-------|
| `ppv_unlock` | 7 | Daily presence required |
| `ppv_wall` | 3 | FREE pages only |
| `tip_goal` | 3 | PAID pages only |
| `bundle` | 3 | Standard bundles |
| `flash_bundle` | 2 | Urgency bundles |
| `game_post` | 2 | Interactive games |
| `first_to_tip` | 2 | Competition posts |
| `vip_program` | 1 | Once per week max |
| `snapchat_bundle` | 1 | Once per week max |

### Engagement Types

| Send Type | Min Weekly | Notes |
|-----------|-----------|-------|
| `bump_normal` | 5 | Most common bump type |
| `bump_descriptive` | 4 | Story-based bumps |
| `bump_text_only` | 3 | Fast touchpoints |
| `bump_flyer` | 2 | High-visibility bumps |
| `link_drop` | 5 | Campaign boosting |
| `wall_link_drop` | 3 | Wall campaign links |
| `dm_farm` | 4 | DM engagement |
| `like_farm` | 1 | Algorithmic boost |

### Retention Types

| Send Type | Min Weekly | Notes |
|-----------|-----------|-------|
| `renew_on_message` | 4 | To renew_off segment |
| `renew_on_post` | 3 | Wall renewal posts |
| `expired_winback` | 5 | Daily winback recommended |
| `ppv_followup` | N/A | Auto-generated from PPVs |

---

## Deprecation Notice

**`ppv_message`** - DEPRECATED as of 2025-12-16
- **Status**: Merged into `ppv_unlock`
- **Transition**: Complete
- **Replacement**: Use `ppv_unlock` with `channel_key: "mass_message"`
- **Reason**: Redundant functionality, simplified taxonomy

---

## Version History

- **v2.4.0** (2025-12-19): Added bump multiplier and followup scaling
- **v2.3.0** (2025-12-16): Deprecated `ppv_message`, merged into `ppv_unlock`
- **v2.2.0** (2025-12-15): Added tip_goal modes, updated constraints
- **v2.1.0** (2025-12-14): Expanded to 22 types, added page type restrictions
- **v2.0.0** (2025-12-10): Complete taxonomy overhaul

---

*For detailed send type profiles, caption mappings, and usage examples, see `/docs/SEND_TYPE_REFERENCE.md`*
