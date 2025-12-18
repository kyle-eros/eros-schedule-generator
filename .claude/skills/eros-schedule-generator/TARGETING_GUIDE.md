# Targeting Guide

Audience targeting reference for EROS schedule generation.

## All Audience Targets

| Target Key | Display Name | Description | Typical Reach | Page Types | Channels |
|------------|--------------|-------------|---------------|------------|----------|
| all_active | All Active Fans | All current subscribers | 100% | paid, free | mass_message, wall_post, story |
| renew_off | Renew Off | Auto-renewal disabled | 40% | paid only | targeted_message, mass_message |
| renew_on | Renew On | Auto-renewal enabled | 60% | paid only | targeted_message, mass_message |
| expired_recent | Recently Expired | Expired within 30 days | varies | paid only | targeted_message |
| expired_all | All Expired | All former subscribers | varies | paid only | targeted_message |
| never_purchased | Never Purchased | No PPV purchases ever | 70% | paid, free | targeted_message, mass_message |
| recent_purchasers | Recent Purchasers | Purchased in last 7 days | 20% | paid, free | targeted_message, mass_message |
| high_spenders | High Spenders | Top 10% by spend | 10% | paid, free | targeted_message, mass_message |
| inactive_7d | Inactive 7 Days | No engagement 7+ days | 30% | paid, free | targeted_message, mass_message |
| ppv_non_purchasers | PPV Non-Purchasers | Viewed but didn't buy | varies | paid, free | targeted_message |

---

## Target Definitions

### all_active

**All current active subscribers.**

- **Reach**: 100% of subscriber base
- **Use Case**: Broad announcements, general content, mass promotions
- **Best For**: PPV launches, general bumps, link drops
- **Frequency**: Can be used multiple times daily

### renew_off

**Subscribers with auto-renewal disabled.**

- **Reach**: ~40% of paid subscribers
- **Use Case**: Re-engagement, renewal incentives
- **Best For**: renew_on_message, special offers
- **Page Type**: Paid only
- **Strategy**: Remind them of value before expiration

### renew_on

**Subscribers with auto-renewal enabled.**

- **Reach**: ~60% of paid subscribers
- **Use Case**: Loyalty rewards, exclusive content
- **Best For**: VIP offers, appreciation messages
- **Page Type**: Paid only
- **Strategy**: Reward loyalty, maintain satisfaction

### expired_recent

**Subscribers who expired within last 30 days.**

- **Reach**: Varies by churn rate
- **Use Case**: Win-back campaigns
- **Best For**: expired_winback, special return offers
- **Page Type**: Paid only
- **Strategy**: Fresh enough to remember, act quickly

### expired_all

**All former subscribers regardless of time.**

- **Reach**: Varies widely
- **Use Case**: Major announcements, comeback campaigns
- **Best For**: Big promotions, milestone celebrations
- **Page Type**: Paid only
- **Strategy**: Cast wide net for re-subscriptions

### never_purchased

**Subscribers who have never bought PPV content.**

- **Reach**: ~70% of subscriber base
- **Use Case**: First purchase conversion
- **Best For**: Introductory offers, sample content
- **Strategy**: Lower barrier to first purchase

### recent_purchasers

**Subscribers who purchased PPV in last 7 days.**

- **Reach**: ~20% of subscriber base
- **Use Case**: Upsells, related content
- **Best For**: Bundle offers, similar content
- **Strategy**: Capitalize on buying momentum

### high_spenders

**Top 10% of subscribers by total spend.**

- **Reach**: 10% of subscriber base
- **Use Case**: Premium offerings, VIP treatment
- **Best For**: vip_program, exclusive bundles
- **Strategy**: Nurture highest-value relationships

### inactive_7d

**Subscribers with no engagement in 7+ days.**

- **Reach**: ~30% of subscriber base
- **Use Case**: Re-engagement campaigns
- **Best For**: dm_farm, engaging content
- **Strategy**: Bring back before they expire

### ppv_non_purchasers

**Subscribers who viewed PPV but didn't buy.**

- **Reach**: Varies by PPV send
- **Use Case**: Follow-up sales, urgency creation
- **Best For**: ppv_followup exclusively
- **Strategy**: Close the sale with urgency/FOMO

---

## Send Type to Target Default Mapping

| Send Type | Default Target | Alternate Targets | Notes |
|-----------|----------------|-------------------|-------|
| ppv_unlock | all_active | recent_purchasers, high_spenders | Broad reach for max revenue |
| ppv_wall | all_active | never_purchased | FREE pages only |
| tip_goal | all_active | high_spenders | PAID pages only |
| vip_program | high_spenders | all_active | Premium targeting preferred |
| game_post | all_active | - | Broad participation needed |
| bundle | all_active | recent_purchasers | General or targeted |
| flash_bundle | all_active | high_spenders | Urgency works broadly |
| snapchat_bundle | all_active | - | Nostalgia appeal |
| first_to_tip | all_active | - | Competition needs volume |
| link_drop | all_active | - | Maximum reach for links |
| wall_link_drop | all_active | - | Wall post, no targeting |
| bump_normal | all_active | - | General engagement |
| bump_descriptive | all_active | - | Story content |
| bump_text_only | all_active | - | Light touch |
| bump_flyer | all_active | - | Visual impact |
| dm_farm | all_active | inactive_7d | Re-engagement option |
| like_farm | all_active | - | Broad participation |
| live_promo | all_active | - | Maximum attendance |
| renew_on_post | all_active | - | Wall post, no targeting |
| renew_on_message | renew_off | - | **Must target renew_off** |
| ppv_followup | ppv_non_purchasers | - | **Must target non-purchasers** |
| expired_winback | expired_recent | expired_all | Win-back targeting |

---

## Channel Capabilities

### wall_post

**Public wall content visible to all subscribers.**

- **Targeting**: None (visible to all)
- **Use Case**: Announcements, teasers, promos
- **Send Types**: wall_link_drop, renew_on_post

### mass_message

**Direct message to subscriber segments.**

- **Targeting**: all_active or any segment
- **Use Case**: PPV, offers, engagement
- **Send Types**: Most revenue and engagement types

### targeted_message

**Direct message to specific audience segments.**

- **Targeting**: Full targeting support
- **Use Case**: Personalized outreach
- **Send Types**: renew_on_message, ppv_followup, expired_winback

### story

**Temporary content (24hr).**

- **Targeting**: None (visible to all)
- **Use Case**: Casual updates, behind-scenes
- **Send Types**: Generally not scheduled

### live

**Livestream sessions.**

- **Targeting**: None (all can join)
- **Use Case**: Real-time engagement
- **Send Types**: live_promo promotes these

---

## Targeting Strategy Matrix

### By Subscriber Value

| Value Tier | Targets | Strategy |
|------------|---------|----------|
| High (top 10%) | high_spenders | VIP treatment, exclusive offers |
| Medium (middle 60%) | all_active, renew_on | Standard content mix |
| Low (bottom 30%) | never_purchased, inactive_7d | Conversion focus |

### By Engagement Level

| Engagement | Targets | Strategy |
|------------|---------|----------|
| Active | recent_purchasers, renew_on | Maintain, upsell |
| Moderate | all_active | Consistent content |
| Declining | inactive_7d, renew_off | Re-engage |
| Lapsed | expired_recent, expired_all | Win-back |

### By Purchase History

| Purchase Status | Targets | Strategy |
|-----------------|---------|----------|
| Never bought | never_purchased | Low-barrier first offer |
| Occasional | all_active | Regular PPV mix |
| Frequent | recent_purchasers | Premium content |
| Whales | high_spenders | VIP exclusive |

---

## Page Type Restrictions

### Targets Available for Both Page Types

- all_active
- never_purchased
- recent_purchasers
- high_spenders
- inactive_7d
- ppv_non_purchasers

### Targets Available for Paid Pages Only

- renew_off
- renew_on
- expired_recent
- expired_all

**Note**: Free pages do not have subscription expiration or renewal concepts, so these targets are not applicable.

---

## Targeting Best Practices

### Do

- Use ppv_non_purchasers for all follow-ups
- Target renew_off for renewal messaging
- Use high_spenders for premium offers
- Target inactive_7d before they expire
- Use recent_purchasers for upsells

### Don't

- Target expired subscribers with non-winback content
- Use narrow segments for broad promotions
- Over-message high_spenders (they're valuable)
- Ignore never_purchased segment
- Use paid-only targets on free pages

### Frequency Guidelines by Target

| Target | Max Messages/Day | Max Messages/Week |
|--------|------------------|-------------------|
| all_active | Unlimited | Follow tier limits |
| high_spenders | 2 | 7 |
| inactive_7d | 2 | 5 |
| renew_off | 1 | 3 |
| expired_recent | 1 | 2 |
| ppv_non_purchasers | Per PPV sent | N/A |
