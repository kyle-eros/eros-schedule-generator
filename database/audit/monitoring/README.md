# EROS Active Creator Monitoring Tools

Production-ready monitoring tools for validating creator data integrity in the EROS database.

## Overview

This directory contains automated validation tools designed for continuous monitoring of active creator page_name integrity. These tools are optimized for scheduled execution (cron) with multiple output formats for dashboards, alerts, and reporting.

## Tools

### active_creator_validator.py

**Purpose**: Validates page_name integrity for all active creators in the database.

**Key Features**:
- 5 comprehensive validation checks
- Multiple output formats (text, JSON, HTML)
- Configurable coverage threshold
- Proper exit codes for automation
- Verbose debug mode
- Production-ready error handling

**Quick Start**:
```bash
# Basic validation
python3 active_creator_validator.py --db ../eros_sd_main.db

# JSON output for parsing
python3 active_creator_validator.py --db ../eros_sd_main.db --format json

# HTML report for dashboards
python3 active_creator_validator.py --db ../eros_sd_main.db --format html --output report.html

# Verbose mode with detailed debug info
python3 active_creator_validator.py --db ../eros_sd_main.db --verbose

# Custom coverage threshold (default 95%)
python3 active_creator_validator.py --db ../eros_sd_main.db --threshold 0.80
```

## Validation Checks

The validator performs 5 core checks:

### 1. Active Creator Fragmentation Check
**Purpose**: Detects if any active creator has multiple page_name values in the database.

**Query Logic**:
- Groups messages by creator_id and page_name
- Identifies creators with >1 distinct page_name
- Returns fragmentation details with occurrence counts

**Pass Criteria**: Zero fragmented creators

**Failure Impact**: CRITICAL - data integrity compromised

### 2. Case Consistency Validation
**Purpose**: Ensures page_name values match canonical case from creators table.

**Query Logic**:
- Compares message page_names to canonical creator page_name
- Case-insensitive match but case-sensitive comparison
- Identifies cosmetic case mismatches

**Pass Criteria**: All page_names match canonical case

**Failure Impact**: WARNING - cosmetic issue only

### 3. Canonical Name Match
**Purpose**: Verifies all messages with creator_id use the correct canonical page_name.

**Query Logic**:
- Joins mass_messages with creators on creator_id
- Compares page_name values (case-insensitive)
- Identifies incorrect name assignments

**Pass Criteria**: 100% canonical match

**Failure Impact**: CRITICAL - reference integrity issue

### 4. NULL Page Name Check
**Purpose**: Detects messages with creator_id but NULL page_name.

**Query Logic**:
- Filters for creator_id IS NOT NULL AND page_name IS NULL
- Groups by creator_id

**Pass Criteria**: Zero NULL page_names for active creators

**Failure Impact**: CRITICAL - missing required data

### 5. Coverage Analysis
**Purpose**: Measures percentage of messages with creator_id assignment.

**Query Logic**:
- Calculates total messages vs. messages with creator_id
- Provides coverage percentage

**Pass Criteria**: Above configured threshold (default 95%)

**Failure Impact**: WARNING - potential orphaned data

## Output Formats

### Text Format (Default)
Human-readable console output with unicode symbols and formatted sections.

**Use Cases**:
- Manual inspection
- Console monitoring
- Quick validation checks

**Example**:
```
======================================================================
EROS Active Creator Page Name Validation Report
======================================================================
Timestamp: 2025-12-17 10:30:45 UTC
Database: /path/to/eros_sd_main.db
Active Creators: 37

OVERALL STATUS: ✅ PASS
Quality Grade: A (EXCELLENT)
...
```

### JSON Format
Structured JSON for programmatic parsing and integration.

**Use Cases**:
- API endpoints
- Data pipelines
- Automated parsing
- Dashboard integration

**Schema**:
```json
{
  "timestamp": "ISO-8601 timestamp",
  "database_path": "absolute path",
  "total_active_creators": 37,
  "overall_status": "PASS|WARNING|FAIL",
  "quality_grade": "A|B|C|D|F",
  "results": [
    {
      "check_name": "Check Name",
      "status": "PASS|WARNING|FAIL",
      "affected_count": 0,
      "details": [],
      "recommendation": "Action to take",
      "metadata": {}
    }
  ],
  "recommendations": ["list of actions"]
}
```

### HTML Format
Styled HTML report for dashboards and email reporting.

**Use Cases**:
- Email reports
- Web dashboards
- Management reporting
- Historical archives

**Features**:
- Responsive CSS styling
- Color-coded status badges
- Collapsible sections
- Printable format

## Exit Codes

The validator uses standard exit codes for automation:

| Exit Code | Meaning | Action Required |
|-----------|---------|-----------------|
| `0` | All validations passed | None - clean state |
| `1` | Validation failures detected | Review and fix issues |
| `2` | Script error | Check database connection, permissions |

**Usage in Scripts**:
```bash
# Run validator and check exit code
python3 active_creator_validator.py --db eros_sd_main.db
if [ $? -eq 1 ]; then
    echo "Validation failed - sending alert"
    # Send alert email or notification
fi

# Or use && and || operators
python3 active_creator_validator.py --db eros_sd_main.db && echo "Clean!" || echo "Issues detected"
```

## Quality Grades

Reports include a letter grade based on validation results:

| Grade | Criteria | Interpretation |
|-------|----------|----------------|
| **A** (Excellent) | All PASS, no warnings | Perfect data integrity |
| **B** (Good) | All PASS, 1 warning | Minor cosmetic issues |
| **C** (Fair) | 1 failure or 2+ warnings | Action recommended |
| **D** (Poor) | 2 failures | Urgent action required |
| **F** (Critical) | 3+ failures | Critical data integrity issues |

## Scheduled Monitoring

See `cron_example.txt` for cron job examples.

**Recommended Schedules**:
- **Daily**: Full validation at 3 AM for comprehensive monitoring
- **Hourly**: Quick checks during business hours for rapid detection
- **Weekly**: Detailed HTML reports for management review

**Log Management**:
```bash
# Create log directory
mkdir -p ~/logs/eros

# Daily validation with JSON logging
0 3 * * * cd /path/to/database && python3 audit/monitoring/active_creator_validator.py \
  --db eros_sd_main.db \
  --format json \
  --output ~/logs/eros/validation_$(date +\%Y\%m\%d).json

# Weekly HTML report
0 9 * * 1 cd /path/to/database && python3 audit/monitoring/active_creator_validator.py \
  --db eros_sd_main.db \
  --format html \
  --output ~/logs/eros/weekly_report.html
```

## Alerting Integration

### Email Alerts
```bash
# Alert on failure
python3 active_creator_validator.py --db eros_sd_main.db || \
  echo "Validation failed at $(date)" | mail -s "EROS Alert" admin@example.com

# Daily HTML report via email
python3 active_creator_validator.py --db eros_sd_main.db --format html --output /tmp/report.html && \
  mail -s "EROS Daily Report" admin@example.com < /tmp/report.html
```

### Slack/Discord Webhooks
```bash
# Send JSON to webhook on failure
python3 active_creator_validator.py --db eros_sd_main.db --format json --output /tmp/result.json
if [ $? -eq 1 ]; then
    curl -X POST -H 'Content-Type: application/json' \
      -d @/tmp/result.json \
      https://hooks.slack.com/services/YOUR/WEBHOOK/URL
fi
```

### Monitoring Systems (Prometheus, Datadog, etc.)
```bash
# Parse JSON and push metrics
RESULT=$(python3 active_creator_validator.py --db eros_sd_main.db --format json)
EXIT_CODE=$?

# Extract metrics from JSON
TOTAL_CREATORS=$(echo $RESULT | jq '.total_active_creators')
GRADE=$(echo $RESULT | jq -r '.quality_grade')

# Push to monitoring system
echo "eros_validator_exit_code $EXIT_CODE" | curl --data-binary @- http://pushgateway:9091/metrics/job/eros_validator
```

## Troubleshooting

### "command not found: python"
**Solution**: Use `python3` instead or create alias: `alias python=python3`

### "Database file not found"
**Solution**: Provide absolute path or use `cd` to database directory first
```bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db
```

### "Permission denied"
**Solution**: Make script executable
```bash
chmod +x audit/monitoring/active_creator_validator.py
```

### Cron job not running
**Solutions**:
1. Check cron service is running: `systemctl status cron` (Linux) or `launchctl list | grep cron` (macOS)
2. Verify crontab entry: `crontab -l`
3. Check cron logs: `/var/log/syslog` (Linux) or `/var/log/system.log` (macOS)
4. Use absolute paths in cron commands
5. Test command manually first

### Coverage warning persists
**Explanation**: Low coverage (74% in current database) is due to historical orphaned messages without creator_id. This is expected and does not indicate active creator fragmentation.

**Options**:
1. Lower threshold: `--threshold 0.70` to acknowledge expected state
2. Backfill creator_id for historical messages (separate project)
3. Focus on the 4 critical checks (fragmentation, consistency, canonical match, NULL check)

## Development

### Requirements
- Python 3.7+
- SQLite3
- No external dependencies (uses stdlib only)

### Code Quality
- Full type hints
- Google-style docstrings
- PEP 8 compliant
- Comprehensive error handling
- Context manager usage
- Dataclass-based result structures

### Testing
```bash
# Basic smoke test
python3 active_creator_validator.py --db eros_sd_main.db

# Test all output formats
python3 active_creator_validator.py --db eros_sd_main.db --format text
python3 active_creator_validator.py --db eros_sd_main.db --format json
python3 active_creator_validator.py --db eros_sd_main.db --format html --output test.html

# Test exit codes
python3 active_creator_validator.py --db eros_sd_main.db && echo "Pass" || echo "Fail"
python3 active_creator_validator.py --db nonexistent.db; echo "Exit: $?"

# Test verbose mode
python3 active_creator_validator.py --db eros_sd_main.db --verbose
```

## File Structure

```
monitoring/
├── active_creator_validator.py    # Main validator tool
├── cron_example.txt               # Cron job examples
└── README.md                      # This file
```

## Version History

**1.0.0** (2025-12-17)
- Initial production release
- 5 core validation checks
- Text, JSON, and HTML output formats
- Configurable coverage threshold
- Proper exit codes
- Comprehensive documentation
- Cron examples

## Support

For issues or questions:
1. Check this README and cron examples
2. Test manually before scheduling
3. Review error messages and exit codes
4. Verify database path and permissions
5. Consult main EROS documentation in `/docs`

## Related Documentation

- `/docs/SCHEDULE_GENERATOR_BLUEPRINT.md` - EROS architecture
- `/database/audit/` - Database quality reports
- `CLAUDE.md` - Project instructions
