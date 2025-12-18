# Caption Quality Standards - EROS Database

**Version:** 1.0
**Effective Date:** 2025-12-12
**Owner:** Database Quality Team

---

## Minimum Length Requirements

### By Schedulable Type

| Type | Minimum Length | Recommended Range | Rationale |
|------|----------------|-------------------|-----------|
| PPV (Pay-Per-View) | 20 characters | 50-150 characters | Needs value proposition and call-to-action |
| Bump (Follow-up) | 15 characters | 30-80 characters | Reminder + urgency |
| Wall Post | 10 characters | 20-100 characters | Teaser + engagement hook |
| Free Preview | 25 characters | 40-120 characters | Must entice without revealing |

### By Content Type

| Content Type | Min Length | Notes |
|--------------|-----------|-------|
| Solo | 30 chars | Describe action + mood |
| BG (Boy/Girl) | 40 chars | Context + participants |
| Sextape | 50 chars | Build anticipation |
| Bundle | 60 chars | List value proposition |
| Dick Rating | 25 chars | Personalization hook |

---

## Exception Cases (Short Captions Allowed)

### Emoji Teasers (< 10 chars)
- **Allowed IF:** High historical performance (earnings >= $50 OR uses >= 5)
- **Use Case:** Wall posts, attention grabbers
- **Examples:** `😈`, `🍆💦`, `💕`
- **Approval:** Must be manually reviewed before activation

### Very Short Captions (10-19 chars)
- **Allowed IF:**
  - Creator-specific (`creator_id` populated)
  - Wall-eligible content
  - Proven track record (performance_score >= 60)
- **Examples:** `Hey babes`, `Fuck me?`, `peekaboo`

---

## Preservation Rules

A short caption (<20 chars) is **preserved** if ANY of these conditions are met:

1. `total_earnings >= $50` - Proven revenue generator
2. `times_used >= 5 AND performance_score >= 60` - Frequent high performer
3. `earnings_per_use >= $30` - High conversion rate
4. `creator_id IS NOT NULL` - Creator-specific content

---

## Cleanup Triggers

A short caption (<20 chars) is **cleanup candidate** if ALL of these conditions are met:

1. `times_used = 0` OR (`times_used > 0` AND `total_earnings = 0`)
2. `creator_id IS NULL OR creator_id = ''` (not creator-specific)
3. Does not meet any preservation rule above
4. `created_at < DATE('now', '-30 days')` (had time to prove value)

---

## Import Validation Rules

### Pre-Import Checks

1. **Length validation:** Flag captions < 20 chars for manual review
2. **Emoji-only detection:** Flag captions with 0 alphanumeric characters
3. **Fragment detection:** Check for incomplete sentences
4. **Duplicate detection:** Prevent near-duplicate short captions

### Post-Import Quality Scan

Run weekly:
```sql
-- Flag low-quality imports within 7 days
SELECT
  caption_id,
  caption_text,
  LENGTH(caption_text) as len,
  'QUALITY_WARNING' as flag
FROM caption_bank
WHERE created_at >= DATE('now', '-7 days')
  AND is_active = 1
  AND LENGTH(caption_text) < 20
  AND times_used = 0;
```

---

## Ongoing Monitoring

### Weekly Quality Check
```sql
-- Run every Monday
SELECT
  CASE
    WHEN LENGTH(caption_text) < 20 THEN 'SHORT'
    WHEN LENGTH(caption_text) < 50 THEN 'MEDIUM'
    ELSE 'LONG'
  END as length_category,
  COUNT(*) as count,
  ROUND(AVG(performance_score), 2) as avg_perf,
  SUM(times_used) as total_uses
FROM caption_bank
WHERE is_active = 1
GROUP BY length_category;
```

### Monthly Cleanup Review
- Review captions < 20 chars with 0 uses after 90 days
- Audit emoji-only captions for performance trends
- Check for new low-performers

---

## Performance Targets

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Avg Caption Length | 75 chars | 60-120 chars |
| % Short Captions (< 50 chars) | < 25% | 20-30% |
| % Emoji-only | < 0.1% | 0-0.5% |
| Avg Performance (Short) | >= 48 | 45-55 |

---

## Data-Driven Insights from Audit 006

### Key Finding: Short Caption Performance

**Analysis Date:** 2025-12-12
**Sample Size:** 146 short captions cleaned up

| Length Category | Count | Avg Earnings | Zero Earnings | Usage Rate |
|----------------|-------|--------------|---------------|------------|
| < 10 chars (emoji-only) | 23 | $0.00 | 100% | 0% |
| 10-19 chars | 123 | $0.00 | 99.3% | 0.8% |
| 20+ chars (benchmark) | 19,444 | $47.32 | 34.2% | 65.8% |

**Conclusion:** Captions under 20 characters have a 99.3% failure rate unless they meet specific exception criteria.

### Protected Short Captions

**Preserved despite length:** 12 short captions with proven performance
- Average earnings: $127.50 per caption
- Average uses: 8.3 times
- Average performance score: 72.1

**Lesson:** Quality exceptions exist, but require data-backed validation.

---

## Automated Quality Scoring

Future imports should include automated quality score calculation:

```sql
-- Quality score algorithm (0-100 scale)
SELECT
  caption_id,
  caption_text,
  (
    -- Length component (40 points max)
    CASE
      WHEN LENGTH(caption_text) >= 50 THEN 40
      WHEN LENGTH(caption_text) >= 20 THEN 30
      WHEN LENGTH(caption_text) >= 10 THEN 15
      ELSE 0
    END +

    -- Alphanumeric ratio (20 points max)
    CASE
      WHEN LENGTH(REPLACE(REPLACE(caption_text, ' ', ''), char(10), '')) > 5 THEN 20
      ELSE 10
    END +

    -- Punctuation presence (10 points max)
    CASE
      WHEN caption_text LIKE '%?%' OR caption_text LIKE '%!%' THEN 10
      ELSE 5
    END +

    -- Call-to-action detection (30 points max)
    CASE
      WHEN LOWER(caption_text) LIKE '%unlock%' OR
           LOWER(caption_text) LIKE '%check%' OR
           LOWER(caption_text) LIKE '%get%' OR
           LOWER(caption_text) LIKE '%see%' THEN 30
      ELSE 0
    END
  ) as quality_score
FROM caption_bank;
```

---

## Review Schedule

- **Weekly:** Quality metrics review (Monday mornings)
- **Monthly:** Cleanup candidate review (First Friday)
- **Quarterly:** Standards review and update
- **Annual:** Comprehensive performance analysis

---

**Approved by:** Database Administrator
**Review Cycle:** Quarterly
**Next Review:** 2026-03-12
