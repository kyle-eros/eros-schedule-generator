# EROS Scheduling Pipeline - Rollback Test Plan

**Created**: 2025-12-16
**Version**: 1.0
**Status**: Wave 0 Baseline

---

## Overview

This document defines the rollback test procedures for each wave of the EROS scheduling pipeline enhancement. Each wave has specific rollback triggers, procedures, and validation tests.

---

## Wave 1: Foundation & Critical Scoring

### Feature Flags
```yaml
ENABLE_CHAR_LENGTH_MULTIPLIER: true
ENABLE_CONFIDENCE_DAMPENING: true
```

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Character length distribution off-target | <40% in 250-449 range after 100 schedules | Disable multiplier |
| EROS scoring errors | Any NaN values | Immediate rollback |
| Performance regression | >20% slower generation | Investigate |

### Rollback Procedure
```bash
# Step 1: Disable feature flags
sed -i 's/ENABLE_CHAR_LENGTH_MULTIPLIER: true/ENABLE_CHAR_LENGTH_MULTIPLIER: false/' config/system_config.yaml
sed -i 's/ENABLE_CONFIDENCE_DAMPENING: true/ENABLE_CONFIDENCE_DAMPENING: false/' config/system_config.yaml

# Step 2: Restart MCP server
systemctl restart eros-mcp

# Step 3: Verify rollback
pytest tests/test_eros_scoring.py -v

# Step 4: Git revert if needed
git revert [WAVE_1_SCORING_COMMIT_HASH]
```

### Validation Tests After Rollback
```python
def test_rollback_wave_1():
    """Verify Wave 1 rollback successful."""
    # Generate test schedule
    schedule = generate_schedule("test_creator")

    # Verify no character length multiplier applied
    assert "char_length_multiplier" not in schedule["metadata"]

    # Verify baseline metrics restored
    caption_lengths = [item["caption_length"] for item in schedule["items"]]
    avg_length = sum(caption_lengths) / len(caption_lengths)
    assert 100 < avg_length < 150  # Baseline range

    # Verify no EROS scoring errors
    assert all(item["eros_score"] is not None for item in schedule["items"])
```

**Recovery Time**: <5 minutes

---

## Wave 2: Timing & Scheduling Precision

### Feature Flags
```yaml
ENABLE_ROTATION_PATTERNS: true
ENABLE_TIMING_RULES: true
```

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Rotation patterns stuck | Same structure >5 consecutive days | Disable rotation |
| Timing violations | >5% of sends fail validation | Disable timing rules |
| Followup window errors | Any followup outside 15-45 min | Investigate |

### Rollback Procedure
```bash
# Step 1: Disable feature flags
sed -i 's/ENABLE_ROTATION_PATTERNS: true/ENABLE_ROTATION_PATTERNS: false/' config/system_config.yaml
sed -i 's/ENABLE_TIMING_RULES: true/ENABLE_TIMING_RULES: false/' config/system_config.yaml

# Step 2: Clear creator state cache
redis-cli FLUSHDB

# Step 3: Restart services
systemctl restart eros-mcp

# Step 4: Verify rollback
pytest tests/test_timing.py -v

# Step 5: Git revert if needed
git revert [WAVE_2_TIMING_COMMIT_HASH]
```

### Validation Tests After Rollback
```python
def test_rollback_wave_2():
    """Verify Wave 2 rollback successful."""
    # Generate test schedules
    schedules = [generate_schedule("test_creator") for _ in range(3)]

    # Verify no rotation tracking
    for schedule in schedules:
        assert "rotation_state" not in schedule["metadata"]

    # Verify timing rules disabled
    for schedule in schedules:
        for item in schedule["items"]:
            # Round minute times should be allowed again
            assert "timing_jitter" not in item

    # Verify no database errors
    assert get_creator_state("test_creator") is None
```

**Recovery Time**: <10 minutes

---

## Wave 3: Content Mix & Volume Optimization

### Feature Flags
```yaml
ENABLE_PAGE_TYPE_VOLUMES: true
ENABLE_VOLUME_TRIGGERS: true
```

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Volume calculation incorrect | Bumps not matching page type formula | Disable page type volumes |
| Campaign frequency wrong | Outside 14-20/month after 30 days | Investigate triggers |
| Followup limit exceeded | Any day >4 followups | Immediate fix |

### Rollback Procedure
```bash
# Step 1: Disable feature flags
sed -i 's/ENABLE_PAGE_TYPE_VOLUMES: true/ENABLE_PAGE_TYPE_VOLUMES: false/' config/system_config.yaml
sed -i 's/ENABLE_VOLUME_TRIGGERS: true/ENABLE_VOLUME_TRIGGERS: false/' config/system_config.yaml

# Step 2: Revert volume calculation
git checkout [BASELINE_COMMIT] python/analytics/volume_calculator.py

# Step 3: Restart services
systemctl restart eros-mcp

# Step 4: Verify rollback
pytest tests/test_volume.py -v
```

### Validation Tests After Rollback
```python
def test_rollback_wave_3():
    """Verify Wave 3 rollback successful."""
    # Generate schedules for different page types
    paid_schedule = generate_schedule("paid_creator")
    free_schedule = generate_schedule("free_creator")

    # Verify generic volumes (no page type differentiation)
    paid_bumps = count_bumps(paid_schedule)
    free_bumps = count_bumps(free_schedule)

    # Should be similar without page type multipliers
    assert abs(paid_bumps - free_bumps) < 5

    # Verify followup limits still work (baseline feature)
    for schedule in [paid_schedule, free_schedule]:
        daily_followups = count_daily_followups(schedule)
        assert all(count <= 4 for count in daily_followups.values())
```

**Recovery Time**: <10 minutes

---

## Wave 4: Authenticity & Quality Controls

### Feature Flags
```yaml
ENABLE_QUALITY_VALIDATORS: true
ENABLE_SCAM_DETECTION: true
```

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| False positives | >10% valid captions blocked | Disable validators |
| Structure scoring errors | Any scoring exceptions | Disable structure scoring |
| Scam detection false alarms | >5% legitimate content flagged | Tune or disable |

### Rollback Procedure
```bash
# Step 1: Disable feature flags
sed -i 's/ENABLE_QUALITY_VALIDATORS: true/ENABLE_QUALITY_VALIDATORS: false/' config/system_config.yaml
sed -i 's/ENABLE_SCAM_DETECTION: true/ENABLE_SCAM_DETECTION: false/' config/system_config.yaml

# Step 2: Remove structure scoring from selection
# Edit caption_selector.py to bypass quality checks

# Step 3: Restart services
systemctl restart eros-mcp

# Step 4: Verify rollback
pytest tests/test_quality.py -v
```

### Validation Tests After Rollback
```python
def test_rollback_wave_4():
    """Verify Wave 4 rollback successful."""
    # Generate test schedule
    schedule = generate_schedule("test_creator")

    # Verify no quality validators running
    for item in schedule["items"]:
        assert "quality_score" not in item
        assert "scam_warning" not in item
        assert "structure_score" not in item

    # Verify caption selection works without validators
    assert len(schedule["items"]) > 0
    assert all(item["caption_text"] for item in schedule["items"])
```

**Recovery Time**: <5 minutes

---

## Wave 5: Advanced Features & Polish

### Feature Flags
```yaml
ENABLE_PRICING_OPTIMIZATION: true
ENABLE_DAILY_AUTOMATION: true
```

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Invalid pricing | Any price outside allowed range | Disable pricing optimization |
| Automation failures | 3 consecutive daily digest failures | Stop cron jobs |
| Flavor rotation errors | Same flavor >3 consecutive days | Disable flavor rotation |

### Rollback Procedure
```bash
# Step 1: Disable feature flags
sed -i 's/ENABLE_PRICING_OPTIMIZATION: true/ENABLE_PRICING_OPTIMIZATION: false/' config/system_config.yaml
sed -i 's/ENABLE_DAILY_AUTOMATION: true/ENABLE_DAILY_AUTOMATION: false/' config/system_config.yaml

# Step 2: Stop cron jobs
crontab -r

# Step 3: Revert pricing logic
git checkout [PRE_WAVE_5] python/analytics/pricing_calculator.py

# Step 4: Restart services
systemctl restart eros-mcp

# Step 5: Verify rollback
pytest tests/test_polish.py -v
```

### Validation Tests After Rollback
```python
def test_rollback_wave_5():
    """Verify Wave 5 rollback successful."""
    # Generate test schedule
    schedule = generate_schedule("test_creator")

    # Verify default pricing
    for item in schedule["items"]:
        if item["send_type_key"] == "ppv_unlock":
            # Should use default tier-based pricing
            assert 10 <= item["suggested_price"] <= 25

    # Verify no daily automation
    assert not os.path.exists("/var/log/eros/daily_digest.log")

    # Verify schedules generate normally
    assert schedule["status"] == "success"
```

**Recovery Time**: <10 minutes

---

## Wave 6: Claude Code Integration

### Rollback Triggers
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Slash command failures | Any command exception | Remove command files |
| MCP integration errors | Connection failures | Revert MCP server |
| Skill activation issues | Skills not triggering | Disable skills |

### Rollback Procedure
```bash
# Step 1: Remove slash commands
rm .claude/commands/eros-*.md

# Step 2: Disable skills
mv .claude/skills/eros-* .claude/skills/disabled/

# Step 3: Revert MCP server
git checkout [PRE_WAVE_6] mcp/eros_db_server.py

# Step 4: Restart Claude Code
# User must restart their Claude Code session
```

### Validation Tests After Rollback
```python
def test_rollback_wave_6():
    """Verify Wave 6 rollback successful."""
    # Verify core scheduling pipeline unaffected
    schedule = generate_schedule("test_creator")
    assert schedule["status"] == "success"

    # Verify all Wave 1-5 features still work
    assert schedule["metadata"]["char_length_optimized"] == True
    assert schedule["metadata"]["timing_rules_applied"] == True
    assert schedule["metadata"]["quality_validated"] == True
```

**Recovery Time**: <5 minutes

**Note**: Wave 6 is purely additive and doesn't affect core scheduling pipeline.

---

## Emergency Full Rollback

If all waves need to be rolled back:

```bash
# Full emergency rollback
git checkout main
git reset --hard [PRE_WAVE_1_COMMIT]
systemctl restart eros-mcp
redis-cli FLUSHALL
crontab -r

# Verify baseline
pytest tests/test_baseline.py -v
```

**Recovery Time**: <15 minutes

---

## Rollback Decision Matrix

| Issue Severity | Wave Affected | Action | Escalation |
|---------------|---------------|--------|------------|
| Minor (<3 failures) | Single wave | Fix within 2 days | Technical lead |
| Major (3-5 failures) | Single wave | 1-week remediation | Engineering manager |
| Critical (>5 failures) | Multiple waves | Full rollback | Executive decision |

---

**Document Control**
- Version: 1.0
- Created: 2025-12-16
- Author: Wave 0 Baseline Team
- Next Review: Post-Wave 1 completion
