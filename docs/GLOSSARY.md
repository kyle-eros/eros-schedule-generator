# EROS Schedule Generator Glossary

> Comprehensive glossary of all domain terms and technical concepts used in the EROS Schedule Generator system.

**Version:** 2.2.0 | **Updated:** 2025-12-16

---

## A

**Active Creator**
A creator with `is_active = 1` in the database who is currently scheduling content and has at least one active subscription page.

**Agent**
A specialized AI component with a specific role in the schedule generation pipeline. The system uses 8 agents: performance-analyst, send-type-allocator, content-curator, audience-targeter, timing-optimizer, followup-generator, schedule-assembler, and quality-validator.

**Algorithm Version**
The version identifier of the scheduling algorithm used to generate a template, stored in `schedule_templates.algorithm_version` (e.g., `multi_agent_v1`).

**Analytics Summary**
Aggregated performance metrics for a creator over a specified period, stored in `creator_analytics_summary` table.

**Audience Target**
A segment of subscribers defined by engagement level, purchase history, or subscription status. Examples include `all_active`, `renew_off`, `high_spenders`, and `ppv_non_purchasers`. See table `audience_targets`.

**Auto-Renewal**
OnlyFans feature where fans' subscriptions automatically renew at expiration. Tracked via `renewal_status` filter for targeted messaging.

**AVOID Tier**
Content types with poor performance (< 30 performance score) that should be excluded from schedules. See `top_content_types.performance_tier`.

---

## B

**Baseline**
Historical average performance metric used as comparison point for trend analysis. Typically calculated as 30-day rolling average.

**Batch Generation**
Creating schedules for multiple creators simultaneously, typically filtered by tier or page type.

**Best Hours**
Optimal posting times for a creator based on historical engagement patterns. Retrieved via `get_best_timing` MCP tool.

**Blueprint**
The comprehensive design document (`SCHEDULE_GENERATOR_BLUEPRINT.md`) defining the multi-agent architecture.

**Bump**
A follow-up message or engagement post designed to re-engage subscribers. Types include `bump_normal`, `bump_descriptive`, `bump_text_only`, and `bump_flyer`.

**Bundle**
A discounted collection of multiple content pieces sold together. Send types include `bundle`, `flash_bundle`, and `snapchat_bundle`.

---

## C

**Campaign**
OnlyFans post format with tip goal functionality, used for revenue-generating content with flyers.

**Caption**
Pre-written text used in messages, optimized for engagement and revenue. Stored in `caption_bank` table with performance and freshness scores.

**Caption Bank**
The collection of all available captions for a creator, including global (creator-agnostic) captions.

**Caption Type**
Category of caption based on purpose and tone. Examples: `ppv_unlock`, `flirty_opener`, `descriptive_tease`, `tip_request`, `renewal_pitch`, `engagement_hook`, `ppv_followup`, `sexting_response`, `exclusive_offer`.

**Category**
Top-level classification of send types: `revenue`, `engagement`, or `retention`.

**Channel**
The distribution method for content. Five types: `wall_post`, `mass_message`, `targeted_message`, `story`, `live`. Stored in `channels` table.

**Content Type**
Category of media content based on performers and acts. Examples: `solo`, `boy_girl`, `anal`, `girl_girl`, `themed`, `feet`, `joi`. Stored in `content_types` table.

**Creator**
An OnlyFans content creator managed by the system. Core entity in `creators` table.

**Creator ID**
Unique identifier for a creator, formatted as `creator_###` (e.g., `creator_001`).

---

## D

**Day of Week**
Integer representing weekday: 0=Sunday, 1=Monday, ..., 6=Saturday. Used in timing optimization.

**Descriptive Tease**
Caption type featuring longer, sexually descriptive narrative to build anticipation.

**Display Name**
Human-readable name for entities (creators, send types, channels, etc.).

**Distribution**
The spread of send types or content types across a schedule to maintain variety.

**DM Farm**
Direct message campaign designed to increase engagement metrics by prompting fans to send messages. Send type: `dm_farm`.

**Diversity Score**
Metric (0-1.0) measuring variety of content types used in a schedule. Target: > 0.8.

---

## E

**Emoji Frequency**
Creator persona attribute defining emoji usage pattern: `none`, `light`, `moderate`, or `heavy`.

**Emoji Recommendation**
Suggested emoji density for a send type's caption, stored in `send_types.emoji_recommendation`.

**Engagement**
Fan interaction metrics including views, likes, messages, and response rates.

**Engagement Score**
Composite metric (0-100) measuring subscriber interaction levels across multiple dimensions.

**Engagement Types**
Category of 9 send types focused on fan interaction: `link_drop`, `wall_link_drop`, `bump_normal`, `bump_descriptive`, `bump_text_only`, `bump_flyer`, `dm_farm`, `like_farm`, `live_promo`.

**Expiration**
Automatic removal/ending time for time-limited content. Stored in `schedule_items.expires_at`.

**Expired Subscriber**
Former subscriber whose subscription has ended. Targets: `expired_recent` (< 30 days), `expired_all`.

---

## F

**Fan**
A subscriber to a creator's OnlyFans page. Also called "subscriber".

**Filter Type**
Classification of audience targeting filter: `subscription_status`, `engagement`, `purchase_history`, `renewal_status`.

**Flash Bundle**
Time-limited bundle offer with urgency messaging and limited quantity. Send type: `flash_bundle`.

**Flyer**
Designed graphic (GIF or static image) used as media for campaigns and promotional posts.

**Followup**
Automated message sent after initial content to encourage action. Primary type: `ppv_followup`.

**Followup Delay**
Time interval (in minutes) between parent send and followup. Typical: 15-30 minutes.

**Free Page**
OnlyFans page with no subscription cost. Revenue generated through PPV and tips only.

**Freshness Score**
A 0-100 metric indicating how recently a caption was used. Formula: `100 - (days_since_last_use * 2)`, minimum 0. Threshold: 30+ recommended.

---

## G

**Game Post**
Gamified buying opportunity (spin-the-wheel, contests, mystery boxes). Send type: `game_post`.

**Generated At**
Timestamp when a schedule template was created. Stored in `schedule_templates.generated_at`.

**Global Caption**
Caption with `creator_id = NULL`, available for use by any creator.

---

## H

**High Spenders**
Audience segment of top 20% fans by total spend. Target: `high_spenders`.

---

## I

**Inactive**
Subscriber with no activity (views, purchases, messages) within specified timeframe. Target: `inactive_7d`.

**Item Type**
Legacy classification of schedule items: `ppv` or `bump`. Replaced by `send_type_id` in enhanced system.

---

## L

**Like Farm**
Campaign to generate likes on wall posts by offering incentives. Send type: `like_farm`.

**Link Drop**
Message containing link to previous campaign, creating auto-preview. Send type: `link_drop` or `wall_link_drop`.

**Linked Post URL**
URL to parent campaign for link drop posts. Stored in `schedule_items.linked_post_url`.

**Livestream**
Real-time broadcast to subscribers. Promoted via send type: `live_promo`.

---

## M

**Mass Message**
Message sent to all active subscribers or targeted segment. Channel: `mass_message`.

**MAX 20X**
Claude Code subscription tier enabling advanced multi-agent orchestration.

**MCP (Model Context Protocol)**
Interface protocol for database tools. Server: `eros-db`, Tools: 17 functions.

**Media Type**
Format of content attachment: `none`, `picture`, `gif`, `video`, `flyer`.

**MID Tier**
Content types with moderate performance (40-69 score). Use for diversity.

**Multi-Agent**
Architecture pattern using specialized agents working in parallel or sequence.

---

## N

**Never Purchased**
Subscribers who have never bought PPV content. Target: `never_purchased`.

---

## O

**OnlyFans (OF)**
Platform for creator content and fan subscriptions.

**Opportunity Score**
Metric (0-100) indicating growth potential and underutilized periods. Score > 70 suggests volume increase.

**Orchestrator**
Master agent coordinating the multi-agent pipeline. Uses Claude Opus 4.5.

---

## P

**Page Name**
Creator's OnlyFans username/URL slug. Stored in `creators.page_name`.

**Page Type**
Classification as `paid` (subscription required) or `free` (no subscription cost).

**Paid Page**
OnlyFans page requiring monthly subscription fee for access.

**Parent Send**
Original content item that triggers followups. Referenced via `schedule_items.parent_send_id`.

**Performance Analyst**
Agent responsible for analyzing trends, saturation, and optimization opportunities.

**Performance Score**
Metric (0-100) measuring content effectiveness based on engagement, revenue, and conversion rates.

**Performance Tier**
Creator ranking (1-5) based on total revenue and fan metrics. Tier 1 = highest.

**Persona**
Creator's communication style and brand identity. Stored in `creator_personas` table.

**Persona Profile**
Complete persona configuration including tone, archetype, emoji usage, slang level, and voice samples.

**PPV (Pay-Per-View)**
Content requiring additional purchase beyond subscription. Primary revenue driver.

**PPV Followup**
Message sent 10-30 minutes after PPV to non-purchasers encouraging sale. Send type: `ppv_followup`.

**PPV Message**
DEPRECATED - Mass message with locked content requiring payment. Merged into `ppv_unlock`. Send type: `ppv_message`.

**PPV Unlock**
Primary PPV for pictures and videos. Main revenue driver for both paid and free pages. Send type: `ppv_unlock`. Replaces legacy `ppv_video` and `ppv_message` types.

**PPV Wall**
Wall-based PPV for free pages only. Public teaser with locked content to drive purchases from profile visitors. Send type: `ppv_wall`.

**Tip Goal**
Tip campaign with configurable modes for paid pages. Three modes: goal_based (community goal), individual (each tipper gets reward), competitive (race to win). Send type: `tip_goal`.

**Tip Goal Mode**
Configuration for tip_goal send type. Options: `goal_based`, `individual`, `competitive`. Determines how tips are tracked and rewards distributed.

**Priority**
Ranking value (1-10) indicating importance. Lower = higher priority.

---

## Q

**Quality Score**
Overall schedule quality metric combining authenticity, diversity, and completeness.

**Quality Validator**
Agent providing final approval gate for generated schedules before output.

---

## R

**Recent Purchasers**
Fans who bought content in last 7 days. Target: `recent_purchasers`.

**Renew Off**
Fans with auto-renewal disabled. Paid page target: `renew_off`.

**Renew On**
Fans with auto-renewal enabled. Paid page target: `renew_on`.

**Renewal**
Automatic or manual subscription extension at expiration.

**Renewal Pitch**
Caption type designed to encourage auto-renewal activation or re-subscription.

**Retention**
Category of 5 send types focused on keeping subscribers: `renew_on_post`, `renew_on_message`, `ppv_message`, `ppv_followup`, `expired_winback`.

**Revenue**
Category of 7 send types focused on direct monetization: `ppv_video`, `vip_program`, `game_post`, `bundle`, `flash_bundle`, `snapchat_bundle`, `first_to_tip`.

---

## S

**Saturation Score**
Metric (0-100) indicating audience fatigue from high send frequency. Score > 70 suggests volume reduction.

**Schedule**
Weekly plan of content items with timing, captions, and targeting.

**Schedule Assembler**
Agent responsible for combining all inputs into final schedule with validation.

**Schedule Item**
Single scheduled message with timing, caption, send type, channel, and targeting. Stored in `schedule_items` table.

**Schedule Template**
Weekly collection of schedule items for a creator. Stored in `schedule_templates` table.

**Send Type**
One of 21 categorized message types with specific requirements and constraints. Stored in `send_types` table with unique `send_type_key`.

**Send Type Allocator**
Agent responsible for distributing send types across daily time slots.

**Send Type Key**
Unique identifier for send type (e.g., `ppv_video`, `bump_normal`). Primary reference in code.

**Skill**
Reusable Claude Code capability package. Main skill: `eros-schedule-generator`.

**Snapchat Bundle**
Throwback Snapchat content bundle with nostalgia appeal. Send type: `snapchat_bundle`.

**Story**
Temporary 24-hour content post. Channel: `story`.

**Subscriber**
Fan with active or expired subscription to creator's page.

---

## T

**Target**
See "Audience Target".

**Targeted Message**
Message sent to specific audience segment. Channel: `targeted_message`.

**Template**
See "Schedule Template".

**Template ID**
Unique identifier for schedule template. Primary key: `schedule_templates.template_id`.

**Tier**
See "Performance Tier" or content tier classifications (TOP/MID/LOW/AVOID).

**Timing Optimizer**
Agent calculating optimal posting times based on historical patterns.

**Timezone**
Creator's local timezone for scheduling. Stored in `creators.timezone`.

**TOP Tier**
Highest-performing content types (70+ score). Prioritize in schedules.

**Trend**
Direction and rate of change in performance metrics over time.

---

## V

**Vault**
Creator's available content inventory by content type. Tracked in `vault_matrix` table.

**Vault Availability**
Boolean and quantity metrics indicating available content types for scheduling.

**VIP Program**
Premium subscription tier promoted via tip campaigns ($200+). Send type: `vip_program`.

**Volume**
Frequency of sends per day/week.

**Volume Assignment**
Creator-specific send frequency configuration. Stored in `volume_assignments` table.

**Volume Config**
Settings controlling daily message frequency by category (revenue/engagement/retention).

**Volume Level**
Intensity classification: LOW (0-999 fans), MID (1K-4.9K), HIGH (5K-14.9K), ULTRA (15K+).

**Volume Performance**
Tracking table measuring volume effectiveness over time. Table: `volume_performance_tracking`.

---

## W

**Wall**
Creator's public feed visible to all subscribers. Channel: `wall_post`.

**Wall Link Drop**
Promotional message with manual media linking to wall campaign. Send type: `wall_link_drop`.

**Wave**
Implementation phase in multi-stage deployment. Blueprint uses 5 waves.

**Week End**
Last day of schedule period (typically Sunday). Stored in `schedule_templates.week_end`.

**Week Start**
First day of schedule period (typically Monday). Stored in `schedule_templates.week_start`.

**Winback**
Campaign targeting expired subscribers for re-engagement. Send type: `expired_winback`.

---

## Cross-References

### Send Type Categories
- **Revenue (9 types)**: ppv_unlock, ppv_wall, tip_goal, bundle, flash_bundle, game_post, first_to_tip, vip_program, snapchat_bundle
- **Engagement (9 types)**: link_drop, wall_link_drop, bump_normal, bump_descriptive, bump_text_only, bump_flyer, dm_farm, like_farm, live_promo
- **Retention (4 types)**: renew_on_post, renew_on_message, ppv_followup, expired_winback
- **Deprecated (1 type)**: ppv_message (merged into ppv_unlock)

### Caption Types
ppv_unlock, flirty_opener, descriptive_tease, tip_request, renewal_pitch, engagement_hook, ppv_followup, sexting_response, exclusive_offer

### Channels
wall_post, mass_message, targeted_message, story, live

### Audience Targets
all_active, renew_off, renew_on, expired_recent, expired_all, never_purchased, recent_purchasers, high_spenders, inactive_7d, ppv_non_purchasers

### Performance Tiers
TOP (70-100), MID (40-69), LOW (30-39), AVOID (< 30)

### Volume Levels
LOW (0-999 fans), MID (1K-4.9K), HIGH (5K-14.9K), ULTRA (15K+)

---

*Version 2.2.0 | Last Updated: 2025-12-16*
