# Caption Import Validation Checklist

**Version:** 1.0
**For:** Caption Pipeline Engineers
**Last Updated:** 2025-12-12

---

## Pre-Import Validation

### Step 1: Length Check
- [ ] All captions >= 20 characters (flag exceptions for manual review)
- [ ] No empty or whitespace-only captions
- [ ] Emoji-only captions flagged for approval
- [ ] Calculate length distribution before import

**SQL Check:**
```sql
-- Run against staging table before import
SELECT
  COUNT(*) as total_captions,
  COUNT(CASE WHEN LENGTH(caption_text) < 20 THEN 1 END) as short_count,
  COUNT(CASE WHEN LENGTH(caption_text) < 10 THEN 1 END) as emoji_count,
  ROUND(100.0 * COUNT(CASE WHEN LENGTH(caption_text) < 20 THEN 1 END) / COUNT(*), 2) as short_pct
FROM staging_captions;
```

**Acceptance Criteria:** < 15% short captions

---

### Step 2: Content Quality
- [ ] No incomplete sentences or fragments
- [ ] No test data or placeholder text (e.g., "test", "asdf", "caption here")
- [ ] Proper punctuation and capitalization
- [ ] No excessive whitespace or special characters
- [ ] Language detection for non-English content

**SQL Check:**
```sql
-- Detect test/placeholder content
SELECT caption_text
FROM staging_captions
WHERE LOWER(caption_text) IN ('test', 'asdf', 'xxx', 'caption', 'temp')
   OR caption_text LIKE '%[test]%'
   OR caption_text LIKE '%TODO%'
   OR LENGTH(TRIM(caption_text)) < LENGTH(caption_text) * 0.8; -- excessive whitespace
```

**Acceptance Criteria:** Zero test/placeholder captions

---

### Step 3: Duplicate Detection
- [ ] Check against `caption_hash` for exact duplicates
- [ ] Check against `caption_normalized` for near-duplicates
- [ ] Flag duplicates for review
- [ ] Verify uniqueness within import batch

**SQL Check:**
```sql
-- Check for duplicates against existing captions
SELECT
  s.caption_text as new_caption,
  c.caption_text as existing_caption,
  c.times_used,
  c.total_earnings
FROM staging_captions s
INNER JOIN caption_bank c
  ON LOWER(TRIM(s.caption_text)) = LOWER(TRIM(c.caption_text))
WHERE c.is_active = 1;

-- Check for internal duplicates in staging
SELECT
  caption_text,
  COUNT(*) as duplicate_count
FROM staging_captions
GROUP BY LOWER(TRIM(caption_text))
HAVING COUNT(*) > 1;
```

**Acceptance Criteria:** All duplicates reviewed and deduplicated

---

### Step 4: Schema Compliance
- [ ] Required fields populated (caption_text, schedulable_type)
- [ ] Valid content_type_id reference
- [ ] Valid page_name if specified
- [ ] Valid creator_id if creator-specific
- [ ] Dates in correct format (ISO 8601)

**SQL Check:**
```sql
-- Validate required fields and foreign keys
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN caption_text IS NULL OR caption_text = '' THEN 1 END) as missing_text,
  COUNT(CASE WHEN schedulable_type IS NULL THEN 1 END) as missing_type,
  COUNT(CASE WHEN content_type_id IS NOT NULL
             AND content_type_id NOT IN (SELECT content_type_id FROM content_types)
             THEN 1 END) as invalid_content_type,
  COUNT(CASE WHEN creator_id IS NOT NULL
             AND creator_id NOT IN (SELECT creator_id FROM creators)
             THEN 1 END) as invalid_creator
FROM staging_captions;
```

**Acceptance Criteria:** All required fields valid, zero schema violations

---

### Step 5: Performance Baseline
- [ ] Assign initial performance score based on length/quality
- [ ] Set freshness score to 100 for new captions
- [ ] Initialize usage counters to 0
- [ ] Set default persona_tone if detectable

**SQL Update:**
```sql
-- Initialize performance metrics
UPDATE staging_captions
SET
  performance_score = CASE
    WHEN LENGTH(caption_text) >= 50 THEN 55
    WHEN LENGTH(caption_text) >= 20 THEN 50
    ELSE 45
  END,
  freshness_score = 100,
  times_used = 0,
  total_earnings = 0,
  created_at = CURRENT_TIMESTAMP,
  is_active = 1;
```

---

## Post-Import Verification

### Immediate Checks (Within 1 Hour)

**Check 1: Import Success**
```sql
-- Verify import success
SELECT
  COUNT(*) as imported_count,
  COUNT(CASE WHEN LENGTH(caption_text) < 20 THEN 1 END) as short_count,
  COUNT(CASE WHEN LENGTH(caption_text) < 10 THEN 1 END) as emoji_count,
  MIN(created_at) as first_import,
  MAX(created_at) as last_import
FROM caption_bank
WHERE created_at >= DATE('now', '-1 day');
```

**Expected:** Import count matches staging count

---

**Check 2: Quality Distribution**
```sql
-- Check quality distribution
SELECT
  source,
  COUNT(*) as count,
  ROUND(AVG(LENGTH(caption_text)), 1) as avg_length,
  ROUND(AVG(performance_score), 2) as avg_perf,
  MIN(LENGTH(caption_text)) as min_length,
  MAX(LENGTH(caption_text)) as max_length
FROM caption_bank
WHERE created_at >= DATE('now', '-1 day')
GROUP BY source;
```

**Expected:** Avg length >= 60 chars, avg performance >= 50

---

**Check 3: Schedulable Type Distribution**
```sql
-- Verify schedulable types
SELECT
  schedulable_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank WHERE created_at >= DATE('now', '-1 day')), 2) as percentage
FROM caption_bank
WHERE created_at >= DATE('now', '-1 day')
GROUP BY schedulable_type;
```

**Expected:** Balanced distribution (PPV 40-60%, Bump 20-40%, Wall 10-30%)

---

### Daily Monitoring (First 7 Days)

**Monitor 1: Usage Tracking**
```sql
-- Track usage of new captions
SELECT
  DATE(created_at) as import_date,
  COUNT(*) as total_imported,
  COUNT(CASE WHEN times_used > 0 THEN 1 END) as used_count,
  ROUND(100.0 * COUNT(CASE WHEN times_used > 0 THEN 1 END) / COUNT(*), 2) as usage_pct
FROM caption_bank
WHERE created_at >= DATE('now', '-7 days')
GROUP BY DATE(created_at)
ORDER BY import_date DESC;
```

**Expected:** 5-15% usage rate within first week

---

**Monitor 2: Performance Validation**
```sql
-- Check early performance signals
SELECT
  LENGTH(caption_text) as length_category,
  COUNT(*) as used_count,
  ROUND(AVG(total_earnings), 2) as avg_earnings,
  ROUND(AVG(performance_score), 2) as avg_perf
FROM caption_bank
WHERE created_at >= DATE('now', '-7 days')
  AND times_used > 0
GROUP BY CASE
  WHEN LENGTH(caption_text) < 20 THEN '< 20'
  WHEN LENGTH(caption_text) < 50 THEN '20-49'
  WHEN LENGTH(caption_text) < 100 THEN '50-99'
  ELSE '100+'
END;
```

**Expected:** Positive correlation between length and earnings

---

## Exception Approval Process

### Emoji-Only Captions (< 10 chars)

**Approval Required From:** Content Manager
**Documentation Needed:**
1. Specific use case (wall post, attention grabber, etc.)
2. Creator context (if creator-specific)
3. Expected placement strategy

**Approval Criteria:**
- Must be wall-eligible
- Part of multi-message campaign
- Creator has existing high-performing emoji captions

---

### Very Short Captions (10-19 chars)

**Approval Required From:** Team Lead
**Documentation Needed:**
1. Creator assignment (must be creator-specific)
2. Performance justification (if migrated from another platform)

**Auto-Approval IF:**
- Creator-specific AND
- Wall-eligible AND
- Part of bulk creator import with track record

---

### Bulk Imports with >15% Short Captions

**Escalation:** Pause import pipeline
**Review Process:**
1. Sample 20 random short captions
2. Manual quality assessment
3. Decision: Accept, filter, or reject batch

**Criteria for Acceptance:**
- All short captions have valid use cases
- Source has historical quality track record
- Manual review shows context-appropriate content

---

## Quality Metrics Dashboard

### Weekly KPIs (Report Every Monday)

```sql
-- Weekly quality report
SELECT
  'Total Active Captions' as metric,
  COUNT(*) as value
FROM caption_bank
WHERE is_active = 1

UNION ALL

SELECT
  'Avg Caption Length',
  ROUND(AVG(LENGTH(caption_text)), 1)
FROM caption_bank
WHERE is_active = 1

UNION ALL

SELECT
  'Short Captions (<20 chars) %',
  ROUND(100.0 * COUNT(CASE WHEN LENGTH(caption_text) < 20 THEN 1 END) / COUNT(*), 2)
FROM caption_bank
WHERE is_active = 1

UNION ALL

SELECT
  'Emoji-Only Captions %',
  ROUND(100.0 * COUNT(CASE WHEN LENGTH(caption_text) < 10 THEN 1 END) / COUNT(*), 2)
FROM caption_bank
WHERE is_active = 1

UNION ALL

SELECT
  'Avg Performance Score',
  ROUND(AVG(performance_score), 2)
FROM caption_bank
WHERE is_active = 1

UNION ALL

SELECT
  'Unused Captions (30+ days) %',
  ROUND(100.0 * COUNT(CASE WHEN times_used = 0 AND created_at < DATE('now', '-30 days') THEN 1 END) / COUNT(*), 2)
FROM caption_bank
WHERE is_active = 1;
```

---

## Escalation Contacts

| Issue Type | Contact | Response Time |
|------------|---------|---------------|
| Schema violations | Database Admin | Immediate |
| Quality concerns | Content Manager | 24 hours |
| Duplicate detection | Pipeline Engineer | 4 hours |
| Exception approvals | Team Lead | Same day |
| Emergency import halt | Database Admin | Immediate |

---

## Import Checklist Summary

**Before Import:**
- [ ] Run all Pre-Import validation checks
- [ ] Review and approve any exceptions
- [ ] Verify staging table schema matches production
- [ ] Document import source and metadata

**During Import:**
- [ ] Monitor import progress for errors
- [ ] Log any warnings or skipped records
- [ ] Verify transaction completion

**After Import:**
- [ ] Run Post-Import verification queries
- [ ] Compare staging count vs. imported count
- [ ] Document any discrepancies
- [ ] Enable captions for scheduling (if auto-approve)

**First Week:**
- [ ] Daily usage monitoring
- [ ] Performance tracking
- [ ] Quality issue escalation
- [ ] Update import documentation with learnings

---

**Contact:** Database Quality Team
**Email:** database-quality@eros.internal
**Slack Channel:** #eros-database-quality
**Last Updated:** 2025-12-12
