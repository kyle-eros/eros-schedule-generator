# Getting Started with EROS Schedule Generator

Welcome to the EROS Schedule Generator! This guide will walk you through your first schedule generation in just a few minutes.

## Prerequisites Checklist

Before you begin, ensure you have:

- [ ] **Claude Code MAX Subscription** - Required for multi-agent orchestration
- [ ] **Python 3.11+** - Check with `python --version` or `python3 --version`
- [ ] **Project Cloned** - You should be in `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT`
- [ ] **Database Available** - Verify `database/eros_sd_main.db` exists (250MB)

## Step 1: Verify Installation

Let's confirm everything is working by listing active creators.

### Command

```bash
/eros:creators
```

Or ask Claude directly:

```
Show me all active creators
```

### What to Look For

You should see a table of 37 active creators with:
- Creator ID and page name
- Display name
- Page type (paid/free)
- Performance tier (1-5)
- Volume level (Low/Mid/High/Ultra)
- Current earnings and fan count

### Example Output

```
ACTIVE CREATORS (37 total)

Tier 1 Creators (Top Performers)
================================
alexia (paid) - $127,450 | 2,847 fans | Volume: High
miss_alexa (paid) - $98,320 | 1,923 fans | Volume: Mid
...
```

### Troubleshooting

If you see errors:
- **"Database not found"**: Check that `database/eros_sd_main.db` exists
- **"MCP server not available"**: Verify `mcp/eros_db_server.py` is present
- **"Permission denied"**: Ensure database file has read permissions

## Step 2: Analyze a Creator

Before generating a schedule, let's analyze a creator's performance trends to understand their current state.

### Command

```bash
/eros:analyze alexia
```

Or:

```
Analyze performance trends for alexia
```

### What to Review

The analysis will show:

1. **Saturation Score (0-100)**
   - High (70+): Creator may be oversending, engagement declining
   - Medium (40-70): Healthy balance
   - Low (0-40): Opportunity to increase volume

2. **Opportunity Score (0-100)**
   - High (70+): Underutilized time slots with potential
   - Medium (40-70): Some opportunities available
   - Low (0-40): Market saturated

3. **Content Type Rankings**
   - **TOP**: Prioritize these (high engagement, high revenue)
   - **MID**: Use regularly (decent performance)
   - **LOW**: Use sparingly (underperforming)
   - **AVOID**: Exclude from schedules (poor performance)

4. **Best Timing Windows**
   - Optimal hours for posting (based on historical data)
   - Best days of week
   - Average earnings per time slot

### Example Output

```
PERFORMANCE ANALYSIS: alexia
Period: Last 14 days

Saturation Score: 42/100 (Healthy)
Opportunity Score: 68/100 (High potential)
Recommended Volume Delta: +1 (increase slightly)

Content Type Rankings:
TOP: B/G, Solo, Toys (use frequently)
MID: Teasing, Shower (moderate use)
LOW: Outdoor (use sparingly)
AVOID: None

Best Hours: 10 AM, 2 PM, 8 PM (PST)
Best Days: Tuesday, Friday, Saturday
```

### Interpretation

- **Saturation < 50 & Opportunity > 60**: Excellent conditions, can increase volume
- **Saturation > 70**: Reduce send frequency, audience is fatigued
- **TOP content types**: These should dominate your schedule (60%+ of sends)
- **Best timing**: Schedule high-value PPVs during these windows

## Step 3: Generate Your First Schedule

Now let's generate an optimized weekly schedule.

### Command

```bash
/eros:generate alexia
```

Or specify details:

```
Generate a weekly schedule for alexia starting December 16, 2025
```

### What Happens (7-Phase Pipeline)

The system executes these phases automatically:

1. **Phase 1: Performance Analysis** (5-10 seconds)
   - Retrieves saturation/opportunity scores
   - Analyzes volume performance trends
   - Determines optimal volume level

2. **Phase 2: Send Type Allocation** (10-15 seconds)
   - Distributes 21 send types across 7 days
   - Validates category balance (Revenue/Engagement/Retention)
   - Applies max_per_day and max_per_week constraints

3. **Phase 3: Content Curation** (15-20 seconds)
   - Selects captions from 58,763 caption bank
   - Applies freshness scoring (prioritizes unused captions)
   - Matches caption types to send type requirements
   - Filters by TOP/MID content type rankings

4. **Phase 4: Audience Targeting** (5-10 seconds)
   - Assigns audience segments to each send
   - Validates targeting compatibility with page type
   - Configures filter criteria

5. **Phase 5: Timing Optimization** (10-15 seconds)
   - Analyzes historical performance by hour/day
   - Assigns optimal posting times
   - Distributes sends across peak windows

6. **Phase 6: Followup Generation** (5-10 seconds)
   - Auto-generates PPV followups (max 4/day)
   - Applies 20-minute minimum delays
   - Links followups to parent PPV messages

7. **Phase 7: Quality Validation** (5-10 seconds)
   - Validates volume constraints
   - Checks caption freshness thresholds
   - Verifies page type compatibility
   - Ensures category balance

**Total Time**: 60-90 seconds

### Example Output

```
SCHEDULE GENERATED: alexia
Week: December 16-22, 2025
Volume Level: High (5-6 PPV/day, 4-5 bumps/day)

═══════════════════════════════════════════════════════════════════════

MONDAY, December 16, 2025
────────────────────────────────────────────────────────────────────────

10:00 AM | PPV Video | Mass Message → All Paid Fans
Caption: "Good morning babes! Just filmed the HOTTEST solo vid... who wants to see? 🔥😈"
Content Type: Solo | Price: $15.00
Performance Score: 87 | Freshness: 92

10:20 AM | PPV Followup | Mass Message → Non-Openers
Caption: "Don't miss this one babe, it's 🔥🔥🔥"
Parent: 10:00 AM PPV | Auto-generated followup

2:00 PM | Bump (Normal) | Wall Post → Public
Caption: "New content in DMs 💕 Check your messages!"
No media required

8:00 PM | PPV Video | Mass Message → High Spenders
Caption: "Exclusive B/G content just for you... this one is WILD 😏💦"
Content Type: B/G | Price: $25.00
Performance Score: 92 | Freshness: 88

...
```

## Step 4: Review and Save

### Quality Checklist

Before saving, verify:

- [ ] **Volume is appropriate**: Not too many sends for saturation score
- [ ] **Content variety**: Multiple content types (avoid repetition)
- [ ] **Caption freshness**: Most captions have freshness > 60
- [ ] **Timing is optimal**: High-value PPVs during best hours
- [ ] **Price points**: Align with content type value ($10-30 range)
- [ ] **Followups are limited**: Max 4 per day with 20+ min delays
- [ ] **Page type compatibility**: No retention types on free pages

### Save to Database

If satisfied, the schedule is automatically saved via:

```
save_schedule(
  creator_id="alexia",
  week_start="2025-12-16",
  items=[...]
)
```

You'll receive a confirmation:

```
✓ Schedule saved successfully
  Template ID: 1547
  Items created: 49
  Week: 2025-12-16 to 2025-12-22
```

### Export Options

Request specific formats:

**CSV Export** (for spreadsheets):
```
Export the schedule to CSV
```

**JSON Export** (for automation):
```
Export the schedule to JSON
```

**Markdown** (for review):
```
Show the schedule in markdown format
```

## Next Steps

Now that you've generated your first schedule, explore advanced features:

### Learn About Send Types

Read the [Send Type Reference Guide](SEND_TYPE_REFERENCE.md) to understand:
- All 21 send types
- Category breakdown (Revenue/Engagement/Retention)
- Configuration options (max_per_day, page_type_restriction)
- Caption type requirements
- Pricing and timing recommendations

### Customize Schedules

Experiment with customization options:

```
# Focus on specific categories
Generate revenue-focused schedule for alexia

# Volume override
Generate schedule for alexia with volume level 4

# Exclude content types
Generate schedule for alexia excluding Solo content

# Time window preferences
Generate schedule with evening focus for alexia
```

### Batch Generation

Generate for multiple creators:

```
Generate schedules for all tier 1 creators
```

### Advanced Features

Explore advanced capabilities in the [User Guide](USER_GUIDE.md):
- Performance trend analysis
- Caption freshness management
- Volume calibration strategies
- Timing optimization techniques
- Multi-creator batch processing

## Common First-Time Questions

### How accurate is the performance analysis?

Analysis is based on real historical data:
- 71,998+ mass messages analyzed
- 30-day rolling window (configurable to 7/14/90 days)
- Statistical significance requires 100+ sends minimum

### Can I edit the schedule after generation?

Yes! Schedules are saved in `schedule_templates` and `schedule_items` tables. You can:
- Manually edit via SQL
- Regenerate with different parameters
- Export to CSV for spreadsheet editing

### What if a creator has no performance data?

For new creators:
- System uses default timing windows
- Content types default to general recommendations
- Volume starts at Level 2 (Mid)
- After 30 days, personalized optimization kicks in

### How often should I regenerate schedules?

Recommended frequency:
- **Weekly**: Standard practice for most creators
- **Bi-weekly**: For low-volume creators
- **Daily adjustments**: For high-tier creators during promotions

### What happens if vault content is unavailable?

The system:
1. Checks `vault_matrix` for content availability
2. Excludes content types with `has_content = 0`
3. Suggests alternative content types
4. Warns if insufficient variety available

## Getting Help

If you encounter issues:

1. **Check Troubleshooting** in [User Guide](USER_GUIDE.md#troubleshooting)
2. **Review Error Messages** - Most are self-explanatory with solutions
3. **Verify Data** - Use `/eros:analyze` to check creator data completeness
4. **Consult API Reference** - [API_REFERENCE.md](API_REFERENCE.md) for tool details

## Quick Reference Commands

| Command | Purpose |
|---------|---------|
| `/eros:creators` | List all active creators |
| `/eros:analyze <creator>` | Analyze performance trends |
| `/eros:generate <creator>` | Generate weekly schedule |
| `Show vault for <creator>` | Check content availability |
| `Show send types` | List all 21 send types |
| `Export schedule to CSV` | Export in CSV format |

---

**You're now ready to start generating optimized schedules!**

For comprehensive documentation, see the [User Guide](USER_GUIDE.md) and [API Reference](API_REFERENCE.md).

---

*EROS Schedule Generator v2.2.0*
*Last Updated: December 16, 2025*
