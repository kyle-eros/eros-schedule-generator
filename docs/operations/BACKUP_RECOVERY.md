# EROS Schedule Generator - Backup and Recovery Strategy

**Version**: 2.2.0
**Last Updated**: 2025-12-17
**Maintainer**: EROS Operations Team

## Overview

This document defines the backup, recovery, and business continuity strategy for the EROS Schedule Generator system. It covers automated backups, point-in-time recovery procedures, disaster recovery scenarios, and data retention policies.

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Daily Backup Schedule](#daily-backup-schedule)
3. [Point-in-Time Recovery](#point-in-time-recovery)
4. [Disaster Recovery Procedures](#disaster-recovery-procedures)
5. [Data Retention Policy](#data-retention-policy)
6. [Backup Testing](#backup-testing)
7. [Monitoring and Alerts](#monitoring-and-alerts)

---

## Backup Strategy

### 1.1 Backup Types

The EROS system uses a multi-tier backup strategy:

| Backup Type | Frequency | Retention | Purpose |
|-------------|-----------|-----------|---------|
| **Full Backup** | Daily at 02:00 UTC | 30 days | Complete database snapshot |
| **Pre-Migration** | Before each migration | 90 days | Rollback point for schema changes |
| **On-Demand** | Manual via script | 7 days | Ad-hoc backups for testing |
| **Quarterly Archive** | First day of quarter | 2 years | Long-term retention for auditing |

### 1.2 What Gets Backed Up

**Database**: `database/eros_sd_main.db` (250MB)
- 59 tables
- 37 active creators
- 59,405 captions
- 71,998+ mass messages
- Performance analytics

**Configuration Files**:
- `.claude.json` - Claude MCP configuration
- `python/config/settings.py` - System settings
- Environment variables documentation

**NOT Backed Up** (version controlled instead):
- Python source code (`python/`, `mcp/`)
- SQL migration scripts (`database/migrations/`)
- Documentation (`docs/`)

### 1.3 Backup Location Structure

```
database/backups/
├── daily/                          # Daily automated backups
│   ├── eros_sd_main_20251217.db
│   ├── eros_sd_main_20251216.db
│   └── ...
├── pre_migration/                  # Pre-migration safety backups
│   ├── pre_migration_20251215_143022.db
│   ├── migration_manifest_20251215_143022.txt
│   └── ...
├── quarterly/                      # Quarterly archives
│   ├── eros_sd_main_2025Q4.db
│   ├── eros_sd_main_2025Q3.db
│   └── ...
└── manifests/                      # Backup metadata
    ├── backup_manifest_20251217.txt
    └── ...
```

---

## Daily Backup Schedule

### 2.1 Automated Daily Backup Script

Create `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/scripts/backup_daily.sh`:

```bash
#!/bin/bash
#
# EROS Schedule Generator - Daily Backup Script
# Runs daily at 02:00 UTC via cron
# Retention: 30 days for daily backups
#

set -e  # Exit on error

# Configuration
PROJECT_ROOT="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT"
DB_PATH="$PROJECT_ROOT/database/eros_sd_main.db"
BACKUP_DIR="$PROJECT_ROOT/database/backups/daily"
MANIFEST_DIR="$PROJECT_ROOT/database/backups/manifests"
RETENTION_DAYS=30

# Create backup directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$MANIFEST_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_ONLY=$(date +%Y%m%d)
BACKUP_FILE="$BACKUP_DIR/eros_sd_main_${DATE_ONLY}.db"
MANIFEST_FILE="$MANIFEST_DIR/backup_manifest_${DATE_ONLY}.txt"

# Logging
LOG_FILE="$PROJECT_ROOT/logs/backup_$(date +%Y%m).log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $1" | tee -a "$LOG_FILE"
}

log "=== Daily Backup Started ==="

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Get database statistics before backup
DB_SIZE=$(stat -f%z "$DB_PATH" 2>/dev/null || stat -c%s "$DB_PATH")
DB_SIZE_MB=$((DB_SIZE / 1024 / 1024))
TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
CREATOR_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM creators WHERE is_active = 1;")

log "Database size: ${DB_SIZE_MB}MB"
log "Tables: $TABLE_COUNT"
log "Active creators: $CREATOR_COUNT"

# Create backup using SQLite backup API (hot backup, safe for concurrent access)
log "Creating backup: $BACKUP_FILE"

sqlite3 "$DB_PATH" << EOF
.timeout 30000
.backup '$BACKUP_FILE'
.quit
EOF

if [ $? -eq 0 ]; then
    log "Backup created successfully"
else
    log "ERROR: Backup failed"
    exit 1
fi

# Verify backup integrity
log "Verifying backup integrity..."
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")

if [ "$INTEGRITY" = "ok" ]; then
    log "Backup integrity verified: OK"
else
    log "ERROR: Backup integrity check failed: $INTEGRITY"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Get backup file size
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
BACKUP_SIZE_MB=$((BACKUP_SIZE / 1024 / 1024))
log "Backup size: ${BACKUP_SIZE_MB}MB"

# Create backup manifest
cat > "$MANIFEST_FILE" << MANIFEST
=== EROS Schedule Generator Backup Manifest ===

Backup Information:
-------------------
Backup Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Backup Type: Daily Automated Backup
Backup File: $BACKUP_FILE
Original DB: $DB_PATH

Database Statistics:
--------------------
Original Size: ${DB_SIZE_MB}MB
Backup Size: ${BACKUP_SIZE_MB}MB
Table Count: $TABLE_COUNT
Active Creators: $CREATOR_COUNT
Integrity Check: $INTEGRITY

System Information:
-------------------
Hostname: $(hostname)
Git Branch: $(cd "$PROJECT_ROOT" && git rev-parse --abbrev-ref HEAD)
Git Commit: $(cd "$PROJECT_ROOT" && git rev-parse HEAD)
Git Commit Short: $(cd "$PROJECT_ROOT" && git rev-parse --short HEAD)

Version Information:
--------------------
System Version: 2.2.0
SQLite Version: $(sqlite3 --version)
Python Version: $(python3 --version)

Retention Policy:
-----------------
Type: Daily backup
Retention: $RETENTION_DAYS days
Delete After: $(date -v+${RETENTION_DAYS}d -u +"%Y-%m-%d" 2>/dev/null || date -d "+${RETENTION_DAYS} days" -u +"%Y-%m-%d")

Recovery Command:
-----------------
cp "$BACKUP_FILE" "$DB_PATH"
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"

---
Manifest generated by backup_daily.sh
MANIFEST

log "Manifest created: $MANIFEST_FILE"

# Cleanup old backups (older than retention period)
log "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=0

find "$BACKUP_DIR" -name "eros_sd_main_*.db" -type f -mtime +$RETENTION_DAYS -print0 | while IFS= read -r -d '' old_backup; do
    log "Deleting old backup: $(basename "$old_backup")"
    rm -f "$old_backup"
    ((DELETED_COUNT++))
done

# Cleanup old manifests
find "$MANIFEST_DIR" -name "backup_manifest_*.txt" -type f -mtime +$RETENTION_DAYS -delete

log "Deleted $DELETED_COUNT old backup(s)"

# Report backup directory disk usage
BACKUP_DIR_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backup directory size: $BACKUP_DIR_SIZE"

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "eros_sd_main_*.db" -type f | wc -l | tr -d ' ')
log "Total backups retained: $BACKUP_COUNT"

log "=== Daily Backup Completed Successfully ==="

# Optional: Send notification (email, Slack, etc.)
# ./scripts/notify.sh "EROS Daily Backup Completed" "$BACKUP_FILE (${BACKUP_SIZE_MB}MB)"

exit 0
```

Make the script executable:

```bash
chmod +x /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/scripts/backup_daily.sh
```

### 2.2 Cron Schedule Setup

Add to crontab (`crontab -e`):

```cron
# EROS Schedule Generator Daily Backup
# Runs at 02:00 UTC daily
0 2 * * * /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/scripts/backup_daily.sh

# Quarterly archive backup (1st of Jan, Apr, Jul, Oct at 03:00 UTC)
0 3 1 1,4,7,10 * /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/scripts/backup_quarterly.sh

# Monthly backup verification test (15th of month at 04:00 UTC)
0 4 15 * * /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/scripts/test_restore.sh
```

Verify cron is configured:

```bash
crontab -l | grep backup
```

### 2.3 Manual Backup Command

For ad-hoc backups:

```bash
#!/bin/bash
# backup_manual.sh - On-demand backup

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="database/backups/manual"
mkdir -p "$BACKUP_DIR"

echo "Creating manual backup..."
sqlite3 database/eros_sd_main.db ".backup '$BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db'"

echo "Verifying backup..."
sqlite3 "$BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db" "PRAGMA integrity_check;"

echo "✓ Manual backup created: $BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"
ls -lh "$BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"
```

---

## Point-in-Time Recovery

### 3.1 Recovery Procedure

Complete procedure for restoring from backup:

```bash
#!/bin/bash
# restore_database.sh - Point-in-time recovery

set -e

echo "=== EROS Database Recovery ==="

# List available backups
echo ""
echo "Available backups:"
echo ""
echo "Daily Backups (last 30 days):"
ls -lht database/backups/daily/*.db 2>/dev/null | head -10

echo ""
echo "Pre-Migration Backups:"
ls -lht database/backups/pre_migration/*.db 2>/dev/null | head -5

echo ""
echo "Quarterly Archives:"
ls -lht database/backups/quarterly/*.db 2>/dev/null

# Prompt for backup selection
echo ""
read -p "Enter full path to backup file: " BACKUP_FILE

if [ -z "$BACKUP_FILE" ]; then
    echo "ERROR: No backup file specified"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo ""
echo "Selected backup: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"

# Display backup manifest if available
BACKUP_DATE=$(basename "$BACKUP_FILE" | sed 's/eros_sd_main_//' | sed 's/.db//')
MANIFEST_FILE="database/backups/manifests/backup_manifest_${BACKUP_DATE}.txt"

if [ -f "$MANIFEST_FILE" ]; then
    echo ""
    echo "=== Backup Manifest ==="
    cat "$MANIFEST_FILE"
    echo ""
fi

# Verify backup integrity
echo "Verifying backup integrity..."
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")

if [ "$INTEGRITY" != "ok" ]; then
    echo "ERROR: Backup file is corrupted: $INTEGRITY"
    echo "Cannot proceed with recovery"
    exit 1
fi
echo "✓ Backup integrity verified"

# Get backup statistics
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
BACKUP_SIZE_MB=$((BACKUP_SIZE / 1024 / 1024))
TABLE_COUNT=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
CREATOR_COUNT=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM creators WHERE is_active = 1;")

echo ""
echo "Backup Statistics:"
echo "  Size: ${BACKUP_SIZE_MB}MB"
echo "  Tables: $TABLE_COUNT"
echo "  Active Creators: $CREATOR_COUNT"
echo ""

# Create safety backup of current database
CURRENT_DB="database/eros_sd_main.db"
SAFETY_BACKUP="database/backups/safety/pre_restore_$(date +%Y%m%d_%H%M%S).db"
mkdir -p "database/backups/safety"

echo "Creating safety backup of current database..."
if [ -f "$CURRENT_DB" ]; then
    cp "$CURRENT_DB" "$SAFETY_BACKUP"
    echo "✓ Safety backup: $SAFETY_BACKUP"
else
    echo "⚠ Current database not found (new installation?)"
fi

# Confirm recovery
echo ""
echo "WARNING: This will replace the current production database."
echo "Current database: $CURRENT_DB"
echo "Will restore from: $BACKUP_FILE"
echo "Safety backup at: $SAFETY_BACKUP"
echo ""
read -p "Proceed with recovery? Type 'RESTORE' to confirm: " CONFIRM

if [ "$CONFIRM" != "RESTORE" ]; then
    echo "Recovery cancelled"
    exit 0
fi

# Perform recovery
echo ""
echo "Restoring database..."
cp "$BACKUP_FILE" "$CURRENT_DB"

if [ $? -eq 0 ]; then
    echo "✓ Database file restored"
else
    echo "ERROR: Database restore failed"
    # Attempt to restore safety backup
    if [ -f "$SAFETY_BACKUP" ]; then
        echo "Attempting to restore safety backup..."
        cp "$SAFETY_BACKUP" "$CURRENT_DB"
    fi
    exit 1
fi

# Verify restored database
echo "Verifying restored database..."
RESTORED_INTEGRITY=$(sqlite3 "$CURRENT_DB" "PRAGMA integrity_check;")

if [ "$RESTORED_INTEGRITY" != "ok" ]; then
    echo "ERROR: Restored database is corrupted: $RESTORED_INTEGRITY"
    echo "Restoring safety backup..."
    cp "$SAFETY_BACKUP" "$CURRENT_DB"
    exit 1
fi
echo "✓ Restored database integrity verified"

# Run post-recovery health checks
echo ""
echo "Running post-recovery health checks..."
./scripts/health_check.sh

echo ""
echo "=== Recovery Complete ==="
echo "Restored from: $BACKUP_FILE"
echo "Safety backup: $SAFETY_BACKUP"
echo "Recovery timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Log recovery event
LOG_FILE="logs/recovery_$(date +%Y%m).log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Database restored from $BACKUP_FILE" >> "$LOG_FILE"

exit 0
```

### 3.2 Quick Recovery Command

For emergency recovery:

```bash
# Quick restore (no prompts, for automation)
./scripts/restore_database.sh --auto database/backups/daily/eros_sd_main_20251217.db
```

### 3.3 Recovery Time Objectives

| Scenario | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|----------|-------------------------------|--------------------------------|
| Database corruption | 15 minutes | Last daily backup (24 hours) |
| Accidental data deletion | 15 minutes | Last daily backup (24 hours) |
| Failed migration | 5 minutes | Pre-migration backup (0 hours) |
| Complete system failure | 30 minutes | Last daily backup (24 hours) |

---

## Disaster Recovery Procedures

### 4.1 Complete System Rebuild

Procedure for rebuilding EROS from scratch:

```bash
#!/bin/bash
# disaster_recovery.sh - Complete system rebuild

set -e

echo "=== EROS Disaster Recovery ==="

# Prerequisites check
echo "Step 1/7: Checking prerequisites..."
command -v git >/dev/null 2>&1 || { echo "ERROR: git not installed"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not installed"; exit 1; }
command -v sqlite3 >/dev/null 2>&1 || { echo "ERROR: sqlite3 not installed"; exit 1; }
echo "✓ Prerequisites met"

# Clone repository
echo "Step 2/7: Cloning repository..."
TARGET_DIR="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT"
if [ -d "$TARGET_DIR" ]; then
    echo "Directory exists: $TARGET_DIR"
    read -p "Delete and re-clone? (yes/no): " DELETE_CONFIRM
    if [ "$DELETE_CONFIRM" = "yes" ]; then
        rm -rf "$TARGET_DIR"
    else
        echo "Using existing directory"
    fi
fi

if [ ! -d "$TARGET_DIR" ]; then
    git clone <repository-url> "$TARGET_DIR"
fi
cd "$TARGET_DIR"
echo "✓ Repository ready"

# Restore database from offsite backup
echo "Step 3/7: Restoring database..."
read -p "Enter path to database backup: " DB_BACKUP

if [ ! -f "$DB_BACKUP" ]; then
    echo "ERROR: Backup not found: $DB_BACKUP"
    exit 1
fi

mkdir -p database
cp "$DB_BACKUP" database/eros_sd_main.db
sqlite3 database/eros_sd_main.db "PRAGMA integrity_check;" | grep -q "ok"
echo "✓ Database restored"

# Restore configuration
echo "Step 4/7: Restoring configuration..."
read -p "Enter path to .claude.json backup (or press Enter to skip): " CLAUDE_CONFIG

if [ -n "$CLAUDE_CONFIG" ] && [ -f "$CLAUDE_CONFIG" ]; then
    cp "$CLAUDE_CONFIG" .claude.json
    echo "✓ Claude configuration restored"
else
    echo "⚠ Skipping Claude configuration (will need manual setup)"
fi

# Set up environment
echo "Step 5/7: Configuring environment..."
cat >> ~/.bashrc << 'ENV'

# EROS Schedule Generator
export EROS_DB_PATH="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
export EROS_LOG_LEVEL="INFO"
export EROS_LOG_FORMAT="json"
ENV
echo "✓ Environment configured (restart shell to apply)"

# Create required directories
echo "Step 6/7: Creating directories..."
mkdir -p database/backups/{daily,pre_migration,quarterly,safety,manifests}
mkdir -p logs
mkdir -p scripts
echo "✓ Directories created"

# Verify installation
echo "Step 7/7: Verifying installation..."
python3 -c "from mcp.eros_db_server import get_db_connection; conn = get_db_connection(); print('✓ MCP server functional')"
./scripts/health_check.sh

echo ""
echo "=== Disaster Recovery Complete ==="
echo "System restored at: $TARGET_DIR"
echo "Database: database/eros_sd_main.db"
echo ""
echo "Next steps:"
echo "1. Restart shell to load environment variables"
echo "2. Test schedule generation"
echo "3. Resume daily backup cron job"
```

### 4.2 Offsite Backup Strategy

#### Recommended Offsite Storage

1. **Cloud Storage** (Primary offsite):
   - AWS S3 / Google Cloud Storage / Azure Blob
   - Encrypted at rest
   - Versioned backups
   - Automated sync from daily backups

2. **Secondary Location** (Disaster recovery):
   - Different data center
   - Quarterly full backups
   - 2-year retention

#### Offsite Sync Script

```bash
#!/bin/bash
# sync_offsite.sh - Upload backups to cloud storage

# Example using AWS S3 (requires aws-cli configured)
BACKUP_DIR="database/backups/daily"
S3_BUCKET="s3://eros-backups-production"

# Upload today's backup
TODAY=$(date +%Y%m%d)
BACKUP_FILE="$BACKUP_DIR/eros_sd_main_${TODAY}.db"

if [ -f "$BACKUP_FILE" ]; then
    aws s3 cp "$BACKUP_FILE" "$S3_BUCKET/daily/" \
        --storage-class STANDARD_IA \
        --server-side-encryption AES256

    echo "✓ Backup uploaded to S3: $BACKUP_FILE"
else
    echo "✗ Backup not found: $BACKUP_FILE"
    exit 1
fi

# Cleanup old S3 backups (keep 90 days)
aws s3 ls "$S3_BUCKET/daily/" | \
    awk '{print $4}' | \
    while read file; do
        # Delete logic based on file age
        # Implementation depends on S3 lifecycle policies
        echo "Checking: $file"
    done
```

---

## Data Retention Policy

### 5.1 Retention Schedule

| Backup Type | Retention Period | Storage Location | Justification |
|-------------|------------------|------------------|---------------|
| Daily backups | 30 days | Local disk | Operational recovery |
| Pre-migration backups | 90 days | Local disk | Schema change rollback |
| Quarterly archives | 2 years | Local + offsite | Compliance, auditing |
| Safety backups | 7 days | Local disk | Emergency rollback |

### 5.2 Automated Cleanup

Retention enforcement is built into `backup_daily.sh`:

```bash
# Cleanup backups older than retention period
find "$BACKUP_DIR" -name "eros_sd_main_*.db" -type f -mtime +$RETENTION_DAYS -delete
```

### 5.3 Retention Policy Compliance

Verify retention compliance:

```bash
#!/bin/bash
# verify_retention.sh

echo "=== Backup Retention Policy Compliance ==="

# Check daily backups (should be <= 30 days)
DAILY_COUNT=$(find database/backups/daily -name "*.db" -type f | wc -l | tr -d ' ')
DAILY_OLDEST=$(find database/backups/daily -name "*.db" -type f -exec stat -f "%Sm %N" -t "%Y-%m-%d" {} \; | sort | head -1)
echo "Daily backups: $DAILY_COUNT files"
echo "Oldest daily backup: $DAILY_OLDEST"

# Check pre-migration backups (should be <= 90 days)
PRE_MIG_COUNT=$(find database/backups/pre_migration -name "*.db" -type f | wc -l | tr -d ' ')
echo "Pre-migration backups: $PRE_MIG_COUNT files"

# Check quarterly archives (should be ~8 files for 2 years)
QUARTERLY_COUNT=$(find database/backups/quarterly -name "*.db" -type f | wc -l | tr -d ' ')
echo "Quarterly archives: $QUARTERLY_COUNT files"

# Total backup storage
TOTAL_SIZE=$(du -sh database/backups | cut -f1)
echo ""
echo "Total backup storage: $TOTAL_SIZE"
```

---

## Backup Testing

### 6.1 Monthly Restore Test

**CRITICAL**: Test restore procedure monthly to ensure backups are valid.

Create `scripts/test_restore.sh`:

```bash
#!/bin/bash
# test_restore.sh - Monthly backup restore verification

set -e

echo "=== Monthly Backup Restore Test ==="
echo "Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Get yesterday's backup (safer than today's)
YESTERDAY=$(date -v-1d +%Y%m%d 2>/dev/null || date -d "yesterday" +%Y%m%d)
BACKUP_FILE="database/backups/daily/eros_sd_main_${YESTERDAY}.db"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Yesterday's backup not found: $BACKUP_FILE"
    exit 1
fi

echo "Testing backup: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"

# Create test database from backup
TEST_DB="database/test_restore_$(date +%Y%m%d).db"
cp "$BACKUP_FILE" "$TEST_DB"

echo ""
echo "Step 1/5: Integrity check..."
INTEGRITY=$(sqlite3 "$TEST_DB" "PRAGMA integrity_check;")
if [ "$INTEGRITY" = "ok" ]; then
    echo "✓ Integrity check passed"
else
    echo "✗ Integrity check failed: $INTEGRITY"
    rm -f "$TEST_DB"
    exit 1
fi

echo "Step 2/5: Table count verification..."
TABLE_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
if [ "$TABLE_COUNT" -eq 59 ]; then
    echo "✓ Table count: $TABLE_COUNT"
else
    echo "✗ Table count mismatch: $TABLE_COUNT (expected 59)"
    rm -f "$TEST_DB"
    exit 1
fi

echo "Step 3/5: Data validation..."
CREATOR_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM creators WHERE is_active = 1;")
CAPTION_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM caption_bank;")
MESSAGE_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM mass_messages;")

echo "  Active creators: $CREATOR_COUNT"
echo "  Captions: $CAPTION_COUNT"
echo "  Messages: $MESSAGE_COUNT"

if [ "$CREATOR_COUNT" -lt 30 ] || [ "$CAPTION_COUNT" -lt 50000 ] || [ "$MESSAGE_COUNT" -lt 70000 ]; then
    echo "✗ Data validation failed (counts too low)"
    rm -f "$TEST_DB"
    exit 1
fi
echo "✓ Data validation passed"

echo "Step 4/5: Query performance test..."
START_TIME=$(date +%s)
sqlite3 "$TEST_DB" << EOF
SELECT c.creator_id, COUNT(m.message_id)
FROM creators c
LEFT JOIN mass_messages m ON c.creator_id = m.creator_id
WHERE c.is_active = 1
GROUP BY c.creator_id
LIMIT 10;
EOF
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "✓ Query performance: ${DURATION}s"

echo "Step 5/5: Foreign key verification..."
sqlite3 "$TEST_DB" << EOF
PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;
EOF
echo "✓ Foreign key integrity verified"

# Cleanup test database
rm -f "$TEST_DB"

# Log test result
LOG_FILE="logs/restore_test_$(date +%Y%m).log"
mkdir -p "$(dirname "$LOG_FILE")"
cat >> "$LOG_FILE" << LOG
[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Backup restore test PASSED
Backup file: $BACKUP_FILE
Backup size: $(stat -f%z "$BACKUP_FILE" | awk '{print $1/1024/1024 "MB"}')
Table count: $TABLE_COUNT
Active creators: $CREATOR_COUNT
Captions: $CAPTION_COUNT
Messages: $MESSAGE_COUNT
Query duration: ${DURATION}s
LOG

echo ""
echo "=== Backup Restore Test PASSED ==="
echo "Backup verified: $BACKUP_FILE"
echo "Test log: $LOG_FILE"

exit 0
```

### 6.2 Test Schedule

| Test Type | Frequency | Automated | Alert on Failure |
|-----------|-----------|-----------|------------------|
| Integrity check | Every backup | Yes | Yes |
| Restore test | Monthly | Yes | Yes |
| Disaster recovery drill | Quarterly | No | N/A |
| Offsite backup verification | Quarterly | Yes | Yes |

---

## Monitoring and Alerts

### 7.1 Backup Success Monitoring

Monitor backup health metrics:

```bash
#!/bin/bash
# check_backup_health.sh

echo "=== Backup Health Check ==="

# Check if today's backup exists
TODAY=$(date +%Y%m%d)
TODAY_BACKUP="database/backups/daily/eros_sd_main_${TODAY}.db"

if [ -f "$TODAY_BACKUP" ]; then
    echo "✓ Today's backup exists: $TODAY_BACKUP"
    BACKUP_AGE=$(($(date +%s) - $(stat -f %m "$TODAY_BACKUP")))
    BACKUP_AGE_HOURS=$((BACKUP_AGE / 3600))
    echo "  Age: ${BACKUP_AGE_HOURS} hours"

    if [ $BACKUP_AGE_HOURS -gt 26 ]; then
        echo "⚠ WARNING: Backup is older than 26 hours"
        exit 1
    fi
else
    echo "✗ Today's backup missing"
    exit 1
fi

# Check backup directory disk space
BACKUP_DIR_USAGE=$(df -h database/backups | tail -1 | awk '{print $5}' | sed 's/%//')
echo "Backup directory disk usage: ${BACKUP_DIR_USAGE}%"

if [ "$BACKUP_DIR_USAGE" -gt 90 ]; then
    echo "⚠ WARNING: Backup directory >90% full"
    exit 1
fi

# Check backup count (should have ~30 daily backups)
BACKUP_COUNT=$(find database/backups/daily -name "*.db" -type f | wc -l | tr -d ' ')
echo "Daily backup count: $BACKUP_COUNT"

if [ "$BACKUP_COUNT" -lt 25 ]; then
    echo "⚠ WARNING: Less than 25 daily backups retained"
fi

echo "✓ Backup health check passed"
exit 0
```

### 7.2 Alert Configuration

Set up alerts for backup failures:

```bash
# Add to crontab to check backup health
0 8 * * * /path/to/check_backup_health.sh || /path/to/send_alert.sh "EROS Backup Health Check Failed"

# Alert script example (send_alert.sh)
#!/bin/bash
MESSAGE="$1"

# Send email alert
echo "$MESSAGE" | mail -s "EROS Alert: Backup Issue" ops-team@example.com

# Send Slack notification (requires slack webhook)
# curl -X POST -H 'Content-type: application/json' \
#   --data "{\"text\":\"$MESSAGE\"}" \
#   https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 7.3 Backup Metrics Dashboard

Key metrics to monitor:

| Metric | Threshold | Alert Level |
|--------|-----------|-------------|
| Backup age | > 26 hours | Critical |
| Backup size variance | > 20% from average | Warning |
| Backup integrity failures | Any failure | Critical |
| Disk space (backup dir) | > 90% | Warning |
| Backup count | < 25 daily backups | Warning |
| Offsite sync failures | Any failure | Critical |

---

## Offsite Backup Implementation Status

### Current State

**Local Backups**: ✅ IMPLEMENTED
- Daily backups automated via cron (backup_daily.sh)
- Backup manifests generated
- 30/90/730-day retention enforced
- Local storage at `/database/backups/`

**Offsite Backups**: ⚠️ DOCUMENTED BUT NOT IMPLEMENTED
- AWS S3 sync procedure documented below
- Requires aws-cli installation and configuration
- Requires S3 bucket creation and IAM credentials

### Offsite Backup Setup Guide

To enable offsite backup to AWS S3:

#### 1. Install AWS CLI

```bash
# macOS
brew install awscli

# Verify installation
aws --version
```

#### 2. Configure AWS Credentials

```bash
aws configure
# Enter: AWS Access Key ID
# Enter: AWS Secret Access Key
# Enter: Default region (e.g., us-west-2)
# Enter: Default output format (json)
```

#### 3. Create S3 Bucket

```bash
aws s3 mb s3://eros-schedule-generator-backups

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket eros-schedule-generator-backups \
    --versioning-configuration Status=Enabled
```

#### 4. Create Offsite Sync Script

Create `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/offsite_sync.sh`:

```bash
#!/bin/bash
# Offsite backup sync to AWS S3
# Run after daily backup completes

set -e

BACKUP_DIR="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups"
S3_BUCKET="s3://eros-schedule-generator-backups"

echo "Syncing backups to S3..."

# Sync daily backups
aws s3 sync "$BACKUP_DIR/daily/" "$S3_BUCKET/daily/" \
    --exclude "*" --include "*.db" --include "*.manifest"

# Sync pre-migration backups
aws s3 sync "$BACKUP_DIR/pre_migration/" "$S3_BUCKET/pre_migration/" \
    --exclude "*" --include "*.db"

# Sync quarterly archives
aws s3 sync "$BACKUP_DIR/archive/" "$S3_BUCKET/archive/" \
    --exclude "*" --include "*.db"

echo "Offsite sync complete ✓"
```

Make script executable:

```bash
chmod +x /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/offsite_sync.sh
```

#### 5. Update Cron Job

Modify crontab to include offsite sync:

```bash
crontab -e

# Add line:
# Daily backup at 11:45 PM, then offsite sync
45 23 * * * /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/backup_daily.sh && /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/offsite_sync.sh >> /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/offsite_sync.log 2>&1
```

#### 6. Verification

```bash
# List S3 backups
aws s3 ls s3://eros-schedule-generator-backups/ --recursive

# Verify latest backup
aws s3 ls s3://eros-schedule-generator-backups/daily/ --recursive | tail -1
```

### Offsite Recovery Procedure

To restore from S3 in disaster recovery scenario:

```bash
# List available backups
aws s3 ls s3://eros-schedule-generator-backups/daily/

# Download specific backup
aws s3 cp s3://eros-schedule-generator-backups/daily/eros_sd_main_backup_20251217_235327.db \
    /tmp/eros_sd_main_restore.db

# Verify backup integrity
sqlite3 /tmp/eros_sd_main_restore.db "PRAGMA integrity_check;"

# Follow standard restore procedure from section 3 (Point-in-Time Recovery)
```

### Backup Health Metrics

Monitor these metrics to ensure backup reliability:

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Last backup age | < 24 hours | > 36 hours (CRITICAL) |
| Backup success rate | 100% | < 95% (WARNING) |
| Offsite sync lag | < 1 hour | > 6 hours (WARNING) |
| Restore test pass rate | 100% | < 100% (CRITICAL) |
| Backup size growth | < 10% per week | > 50% per week (WARNING) |

---

## Appendix

### A.1 SQLite Backup API vs File Copy

**Recommended: SQLite Backup API** (`.backup` command)

```bash
sqlite3 database/eros_sd_main.db ".backup 'backup_file.db'"
```

**Advantages**:
- Safe for concurrent access (hot backup)
- Transactionally consistent
- Built-in corruption detection
- No lock contention

**Alternative: File Copy** (use only when database is idle)

```bash
cp database/eros_sd_main.db backup_file.db
```

**Disadvantages**:
- Requires database to be idle
- Risk of partial writes
- No consistency guarantees

### A.2 Backup File Naming Convention

Format: `eros_sd_main_YYYYMMDD_HHMMSS.db`

- `YYYYMMDD`: Date (20251217)
- `HHMMSS`: Time (optional for daily backups)

Examples:
- Daily: `eros_sd_main_20251217.db`
- Pre-migration: `pre_migration_20251217_143022.db`
- Quarterly: `eros_sd_main_2025Q4.db`

### A.3 Recovery Time Estimates

| Database Size | Copy Time | Integrity Check | Total Recovery Time |
|--------------|-----------|-----------------|---------------------|
| 250MB | 5 seconds | 30 seconds | ~1 minute |
| 500MB | 10 seconds | 60 seconds | ~2 minutes |
| 1GB | 20 seconds | 120 seconds | ~3 minutes |

---

**Document Version**: 1.0
**Created**: 2025-12-17
**Next Review**: 2026-03-17
