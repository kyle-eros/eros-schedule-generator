# Active Creator Validator - Quick Reference

## One-Liner Commands

```bash
# Default validation (text output to console)
python3 active_creator_validator.py --db eros_sd_main.db

# JSON for automation
python3 active_creator_validator.py --db eros_sd_main.db --format json

# HTML report
python3 active_creator_validator.py --db eros_sd_main.db --format html --output report.html

# Verbose debug
python3 active_creator_validator.py --db eros_sd_main.db --verbose

# Custom threshold
python3 active_creator_validator.py --db eros_sd_main.db --threshold 0.70
```

## Exit Codes

| Code | Meaning | Example Usage |
|------|---------|---------------|
| `0` | PASS | All validations passed |
| `1` | FAIL | Fragmentation detected |
| `2` | ERROR | Database not found |

## Exit Code Usage

```bash
# Check exit code
python3 active_creator_validator.py --db eros_sd_main.db && echo "Clean!" || echo "Issues!"

# Send alert on failure
python3 active_creator_validator.py --db eros_sd_main.db || \
  echo "Alert: Validation failed" | mail -s "EROS Alert" admin@example.com

# Store exit code
python3 active_creator_validator.py --db eros_sd_main.db
STATUS=$?
if [ $STATUS -eq 1 ]; then echo "Validation failed"; fi
```

## Quality Grades

| Grade | Status | Meaning |
|-------|--------|---------|
| **A** | 🟢 | Perfect - all checks pass |
| **B** | 🟡 | Good - minor warnings only |
| **C** | 🟠 | Fair - 1 failure or 2+ warnings |
| **D** | 🔴 | Poor - 2 failures |
| **F** | 🔴 | Critical - 3+ failures |

## 5 Validation Checks

1. **Fragmentation Check** - Multiple page_names per creator_id? → CRITICAL if fails
2. **Case Consistency** - Page_name case matches canonical? → WARNING if fails
3. **Canonical Match** - All messages use correct page_name? → CRITICAL if fails
4. **NULL Check** - Any NULL page_names for active creators? → CRITICAL if fails
5. **Coverage Analysis** - What % of messages have creator_id? → WARNING if low

## Common Cron Jobs

```bash
# Daily 3 AM validation
0 3 * * * cd /path/to/database && python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format json --output ~/logs/validation_$(date +\%Y\%m\%d).json

# Hourly quick check
0 * * * * cd /path/to/database && python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db >> ~/logs/hourly.log 2>&1

# Weekly HTML report (Monday 9 AM)
0 9 * * 1 cd /path/to/database && python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format html --output ~/logs/weekly_report.html
```

## Output Format Examples

### Text (Console)
```
======================================================================
EROS Active Creator Page Name Validation Report
======================================================================
OVERALL STATUS: ✅ PASS
Quality Grade: A (EXCELLENT)
...
```

### JSON (Automation)
```json
{
  "overall_status": "PASS",
  "quality_grade": "A",
  "total_active_creators": 37,
  "results": [...]
}
```

### HTML (Dashboard)
Styled HTML with color-coded badges, tables, and recommendations.

## File Locations

```
/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/
├── eros_sd_main.db                         # Production database
└── audit/monitoring/
    ├── active_creator_validator.py         # Main tool
    ├── README.md                           # Full documentation
    ├── QUICK_REFERENCE.md                  # This file
    └── cron_example.txt                    # Cron examples
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `command not found: python` | Use `python3` instead |
| `Database file not found` | Use absolute path or `cd` to directory first |
| `Permission denied` | Run `chmod +x active_creator_validator.py` |
| Coverage warning persists | Use `--threshold 0.70` (expected due to orphaned historical data) |

## Help

```bash
python3 active_creator_validator.py --help
python3 active_creator_validator.py --version
```
