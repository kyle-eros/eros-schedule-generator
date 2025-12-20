# Validation Rules Reference

**Version**: 2.0.0
**Last Updated**: 2025-12-19
**Purpose**: Canonical reference for the Four-Layer Defense validation architecture with v3.0 Pipeline Supercharge enhancements

---

## Four-Layer Defense Architecture

Caption selection and schedule validation are protected by four independent validation layers:

| Layer | Component | Responsibility | Status | Failure Action |
|-------|-----------|----------------|--------|----------------|
| **1** | **MCP Tools** | Database-level `vault_matrix` INNER JOIN + AVOID tier exclusion | Automatic | Returns only vault-compliant, non-AVOID captions |
| **2** | **caption-selection-pro** | Post-selection validation + ValidationProof generation | Upstream | Rejects non-compliant, selects next best |
| **3** | **Quality-Validator Agent** | Upstream proof verification + HARD REJECTION | Final Gate | Rejects entire schedule if ANY violation |
| **4** | **save_schedule Gatekeeper** | ValidationCertificate requirement (Phase 1: optional) | Database | Warns/rejects schedules without valid certificate |

### Layer 1: MCP Tools (Database-Level Filtering)

**Automatic filtering at database query level:**
- `get_send_type_captions()`: INNER JOIN on `vault_matrix` + AVOID tier exclusion
- `get_top_captions()`: INNER JOIN on `vault_matrix` + AVOID tier exclusion
- Returns ONLY vault-compliant, non-AVOID captions
- No configuration required - always active

### Layer 2: caption-selection-pro (Post-Selection Validation)

**Mandatory validation after caption selection:**
- Verifies vault compliance via `get_vault_availability()`
- Verifies AVOID exclusion via `get_content_type_rankings()`
- Generates **ValidationProof** with:
  - `vault_types_fetched`: Allowed content types
  - `avoid_types_fetched`: AVOID tier content types
  - `mcp_calls_executed`: Proof of MCP tool invocation
  - `earnings_ranking_used`: PPV-first content type rotation
- Rejects non-compliant captions, selects next-best alternative

### Layer 3: Quality-Validator Agent (Upstream Proof Verification)

**Independent re-validation of entire schedule:**
- Verifies `validation_proof` exists from caption-selection-pro
- Re-fetches AVOID types independently for data integrity
- HARD REJECTION on ANY vault or AVOID violation
- Generates **ValidationCertificate** for save_schedule gatekeeper
- **ZERO TOLERANCE** policy - no exceptions

### Layer 4: save_schedule Gatekeeper (Database Persistence)

**Final gate before database persistence:**
- Validates `ValidationCertificate` presence and freshness (<5 min)
- Confirms zero vault/AVOID violations in certificate
- **Phase 1** (current): Warns if certificate missing, allows save
- **Phase 2** (future): Rejects if certificate missing/invalid

---

## Hard Gates (NEVER Bypass)

These validation rules have **ZERO TOLERANCE** - any violation = schedule REJECTED.

### 1. Vault Matrix Compliance

**Rule**: Only captions matching creator's `vault_matrix` content types are allowed.

**Detection**:
```python
vault = get_vault_availability(creator_id)
allowed_types = {ct['type_name'] for ct in vault['available_content']}

for item in schedule.items:
    content_type = item.get('content_type')
    if content_type not in allowed_types:
        REJECT("Vault violation")
```

**Failure Code**: `VAULT_VIOLATION`
**Action**: REJECT schedule, return to caption-selection-pro

### 2. AVOID Tier Exclusion

**Rule**: Content types in AVOID tier are NEVER scheduled.

**Detection**:
```python
rankings = get_content_type_rankings(creator_id)
avoid_types = set(rankings.get('avoid_types', []))

for item in schedule.items:
    content_type = item.get('content_type')
    if content_type in avoid_types:
        REJECT("AVOID tier violation")
```

**Failure Code**: `AVOID_TIER_VIOLATION`
**Action**: REJECT schedule, return to caption-selection-pro

### 3. Page Type Restrictions

**Rule**: Retention types only for `paid` pages, type-specific exclusions enforced.

**Violations**:
- FREE page contains `tip_goal` → REJECTED (tip_goal is PAID only)
- PAID page contains `ppv_wall` → REJECTED (ppv_wall is FREE only)
- FREE page contains retention types → REJECTED

**Failure Code**: `PAGE_TYPE_VIOLATION`
**Action**: REJECT schedule, return to send-type-allocator

### 4. Send Type Diversity

**Rule**: Minimum 10 unique send_type_keys required.

**Thresholds**:
- Total unique types: >= 10
- Revenue types: >= 4 (of 9)
- Engagement types: >= 4 (of 9)
- Retention types (paid only): >= 2 (of 4)

**Failure Code**: `INSUFFICIENT_DIVERSITY`
**Action**: REJECT schedule, return to send-type-allocator

---

## Soft Gates (Warnings Only)

These rules produce warnings but allow schedule to proceed.

### 1. Freshness Thresholds

**Rule**: Captions should have `days_since_last_use >= 30`.

**Relaxation**: Can relax to >= 20 if caption pool limited
**Failure Code**: `LOW_FRESHNESS`
**Action**: WARN, proceed with schedule

### 2. Performance Minimums

**Rule**: Captions should have `performance_score >= 40`.

**Relaxation**: Can relax to >= 30 if high-performers limited
**Failure Code**: `LOW_PERFORMANCE`
**Action**: WARN, proceed with schedule

### 3. Volume Confidence

**Rule**: `confidence_score >= 0.6` (MODERATE or higher).

**Thresholds**:
- >= 0.8: HIGH confidence
- 0.6 - 0.79: MODERATE confidence (warning)
- 0.4 - 0.59: LOW confidence (apply conservative adjustments)
- < 0.4: VERY LOW confidence (flag for manual review)

**Failure Code**: `LOW_CONFIDENCE`
**Action**: WARN or NEEDS_REVIEW, adjust validation thresholds

---

## Rejection Criteria Table

| Condition | Severity | Status | Action |
|-----------|----------|--------|--------|
| ANY vault violation | CRITICAL | REJECTED | Return to caption-selection-pro |
| ANY AVOID tier violation | CRITICAL | REJECTED | Return to caption-selection-pro |
| < 12 unique send types | HIGH | REJECTED | Return to variety-enforcer |
| < 4 revenue types | HIGH | REJECTED | Return to send-type-allocator |
| < 4 engagement types | HIGH | REJECTED | Return to send-type-allocator |
| FREE page with tip_goal | HIGH | REJECTED | Return to send-type-allocator |
| PAID page with ppv_wall | HIGH | REJECTED | Return to send-type-allocator |
| Missing strategy_metadata | HIGH | REJECTED | Return to send-type-allocator |
| < 3 unique strategies | HIGH | REJECTED | Return to send-type-allocator |
| Quality score < 70 | MODERATE | REJECTED | Return to previous phase |
| Quality score 70-84 | LOW | NEEDS_REVIEW | Flag for human review |
| Quality score 85-100 | NONE | APPROVED | Save and deploy |
| Freshness < 30 days | LOW | WARNING | Log, proceed |
| Performance < 40 | LOW | WARNING | Log, proceed |
| Confidence < 0.6 | LOW | WARNING | Adjust thresholds, proceed |

---

## ValidationProof Structure (Layer 2 Output)

Generated by **caption-selection-pro** agent, verified by **quality-validator** agent.

**Required Fields**:
```json
{
  "validation_proof": {
    "vault_types_fetched": ["solo", "lingerie", "tease"],
    "avoid_types_fetched": ["feet", "deepthroat"],
    "mcp_calls_executed": {
      "get_vault_availability": {"called": true, "timestamp": "..."},
      "get_content_type_rankings": {"called": true, "timestamp": "..."}
    },
    "mcp_avoid_filter_active": true,
    "earnings_ranking_used": ["solo:$45k", "b/g:$38k", "lingerie:$32k"],
    "ppv_content_rotation": [
      {"slot": "Mon-08:47", "content_type": "solo", "position": 1}
    ]
  }
}
```

**Verification**:
- `vault_types_fetched` must be non-empty
- `avoid_types_fetched` must be present (can be empty if no AVOID types)
- `mcp_calls_executed` must show required calls were made
- `mcp_avoid_filter_active` must be true

---

## ValidationCertificate Structure (Layer 3 Output)

Generated by **quality-validator** agent, validated by **save_schedule** gatekeeper.

**Required Fields**:
```json
{
  "validation_certificate": {
    "certificate_version": "1.0",
    "creator_id": "grace_bennett",
    "validation_timestamp": "2025-12-19T10:30:45Z",
    "schedule_hash": "a1b2c3d4e5f67890",
    "avoid_types_hash": "f9e8d7c6b5a43210",
    "vault_types_hash": "1234567890abcdef",
    "items_validated": 54,
    "quality_score": 92,
    "validation_status": "APPROVED",
    "checks_performed": {
      "vault_compliance": true,
      "avoid_tier_exclusion": true,
      "send_type_diversity": true,
      "timing_validation": true,
      "caption_quality": true,
      "volume_config": true
    },
    "violations_found": {
      "vault": 0,
      "avoid_tier": 0,
      "critical": 0
    },
    "upstream_proof_verified": true,
    "certificate_signature": "qv-a1b2c3d4-103045"
  }
}
```

**Gatekeeper Validation**:
- Certificate must be present
- Freshness: `validation_timestamp` < 5 minutes ago
- Status: `APPROVED` or `NEEDS_REVIEW` only
- Violations: `vault` and `avoid_tier` must be 0
- Item count: `items_validated` must match `len(schedule.items)`

---

## v3.0 Pipeline Supercharge Validation Rules

### Preflight Validation (Phase 0)

**Agent**: preflight-checker (haiku)
**Authority**: BLOCKS pipeline if critical data missing

| Check | Threshold | Failure Action |
|-------|-----------|----------------|
| Creator active | `creators.is_active = 1` | BLOCK - Creator inactive |
| Vault entries exist | `vault_matrix` has entries | BLOCK - No vault data |
| Minimum captions | >= 50 captions available | BLOCK - Insufficient captions |
| Persona defined | `creator_personas` exists | BLOCK - No persona |
| Analytics available | `mass_messages` has data | WARN - Limited analytics |

**Output**:
```json
{
  "preflight_status": "READY|BLOCKED|WARN",
  "checks_passed": 5,
  "checks_failed": 0,
  "blockers": [],
  "warnings": []
}
```

### Variety Enforcement (Phase 2.5)

**Agent**: variety-enforcer (sonnet)
**Purpose**: Ensure content diversity and prevent repetitive patterns

| Rule | Threshold | Failure Action |
|------|-----------|----------------|
| Unique send types | >= 12 per week | REJECT - Insufficient variety |
| Max send type concentration | <= 20% of weekly total | REJECT - Over-concentrated |
| Max content type concentration | <= 25% of PPV slots | REJECT - Content repetition |
| Variety score | >= 75 | REJECT - Low variety score |

**Variety Score Calculation**:
```
variety_score = (unique_types / 22) * 40 +
                (1 - max_type_concentration) * 30 +
                (1 - max_content_concentration) * 30
```

### Schedule Critic Review (Phase 8.5)

**Agent**: schedule-critic (opus)
**Authority**: BLOCK authority for strategic concerns

| Metric | Block Threshold | Action |
|--------|-----------------|--------|
| Revenue aggressiveness | > 80 | BLOCK - Too aggressive |
| Subscriber health score | < 40 | BLOCK - Health risk |
| Brand consistency score | < 50 | BLOCK - Brand risk |
| Major strategic concerns | 3+ | BLOCK - Multiple issues |

**Critic Decision**:
```json
{
  "critic_decision": "APPROVE|REVISE|BLOCK",
  "strategic_score": 78,
  "revenue_aggressiveness": 65,
  "subscriber_health": 72,
  "brand_consistency": 85,
  "concerns": ["Consider reducing PPV frequency on Mondays"],
  "recommendations": ["Add more engagement content on weekends"]
}
```

### Anomaly Detection (Phase 9.5)

**Agent**: anomaly-detector (haiku)
**Purpose**: Statistical anomaly detection before save

| Category | Detection | Action |
|----------|-----------|--------|
| **ERROR** (BLOCK) | Price > 3σ from mean | BLOCK - Price outlier |
| **ERROR** (BLOCK) | Volume > 2x normal | BLOCK - Volume anomaly |
| **ERROR** (BLOCK) | Unknown content type | BLOCK - Invalid content |
| **WARNING** | Time clustering (3+ within 30 min) | WARN - Time bunching |
| **WARNING** | Revenue concentration > 60% | WARN - Revenue risk |
| **WARNING** | Low freshness average < 25 | WARN - Stale content |
| **OPPORTUNITY** | Underutilized high-performers | INFO - Optimization |
| **OPPORTUNITY** | Unused peak slots | INFO - Missed opportunity |

**Anomaly Report**:
```json
{
  "anomaly_status": "PASS|WARN|BLOCK",
  "errors": [],
  "warnings": [
    {
      "type": "TIME_CLUSTERING",
      "message": "3 items scheduled within 30 minutes on Tuesday",
      "severity": "WARNING"
    }
  ],
  "opportunities": [
    {
      "type": "UNDERUTILIZED_CONTENT",
      "message": "lingerie content performs well but only 2 slots",
      "potential_lift": "+15%"
    }
  ]
}
```

---

## Updated Rejection Criteria (v3.0)

| Condition | Phase | Severity | Status | Action |
|-----------|-------|----------|--------|--------|
| Preflight blocked | 0 | CRITICAL | BLOCKED | Stop pipeline |
| ANY vault violation | 3/9 | CRITICAL | REJECTED | Return to caption-selection-pro |
| ANY AVOID tier violation | 3/9 | CRITICAL | REJECTED | Return to caption-selection-pro |
| < 12 unique send types | 2.5 | HIGH | REJECTED | Return to variety-enforcer |
| Send type > 20% weekly | 2.5 | HIGH | REJECTED | Return to variety-enforcer |
| Content type > 25% PPV | 2.5 | HIGH | REJECTED | Return to variety-enforcer |
| Variety score < 75 | 2.5 | HIGH | REJECTED | Return to variety-enforcer |
| Schedule-critic BLOCK | 8.5 | HIGH | REJECTED | Return to revenue-optimizer |
| Anomaly ERROR | 9.5 | HIGH | REJECTED | Return to schedule-assembler |
| Quality score < 70 | 9 | MODERATE | REJECTED | Return to previous phase |
| Anomaly WARNING | 9.5 | LOW | WARNING | Log, proceed |
| Quality score 70-84 | 9 | LOW | NEEDS_REVIEW | Flag for human review |
| Quality score 85-100 | 9 | NONE | APPROVED | Save and deploy |
