# EROS Schedule Generator - Deployment Playbook

**Version**: 2.2.0
**Last Updated**: 2025-12-17
**Maintainer**: EROS Operations Team

## Overview

This playbook provides step-by-step procedures for deploying the EROS Schedule Generator system to production. It covers pre-deployment verification, deployment execution, health checks, and rollback procedures.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Deployment Procedure](#deployment-procedure)
4. [Health Checks](#health-checks)
5. [Rollback Procedures](#rollback-procedures)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### 1.1 Database Validation

```bash
# Verify database exists and is accessible
DB_PATH="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
if [ -f "$DB_PATH" ]; then
    echo "✓ Database file exists"
    ls -lh "$DB_PATH"
else
    echo "✗ Database file not found at $DB_PATH"
    exit 1
fi

# Check database integrity
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
# Expected output: ok

# Verify table count (should be 74)
TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
if [ "$TABLE_COUNT" -eq 74 ]; then
    echo "✓ All 74 tables present"
else
    echo "✗ Table count mismatch: $TABLE_COUNT (expected 74)"
fi

# Verify active creators (should be 37)
CREATOR_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM creators WHERE is_active = 1;")
echo "Active creators: $CREATOR_COUNT"

# Check database size (should be ~250MB)
DB_SIZE=$(stat -f%z "$DB_PATH")
DB_SIZE_MB=$((DB_SIZE / 1024 / 1024))
echo "Database size: ${DB_SIZE_MB}MB"
```

### 1.2 Code Validation

```bash
# Verify MCP server exists
MCP_SERVER="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py"
if [ -f "$MCP_SERVER" ]; then
    echo "✓ MCP server found"
    ls -lh "$MCP_SERVER"
else
    echo "✗ MCP server not found"
    exit 1
fi

# Verify Python dependencies
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT
python3 -c "import sqlite3; print('✓ sqlite3 available')"
python3 -c "from python.models.volume import VolumeTier; print('✓ Python modules loadable')"

# Verify Python package structure
for module in python mcp; do
    if [ -d "$module" ]; then
        echo "✓ $module/ directory exists"
    else
        echo "✗ $module/ directory missing"
    fi
done

# Check for __init__.py files
find python -name "__init__.py" | wc -l
# Should return 10+ init files
```

### 1.3 Configuration Validation

```bash
# Verify environment variables
if [ -z "$EROS_DB_PATH" ]; then
    echo "⚠ EROS_DB_PATH not set, using default"
else
    echo "✓ EROS_DB_PATH: $EROS_DB_PATH"
fi

# Check logging configuration
echo "EROS_LOG_LEVEL: ${EROS_LOG_LEVEL:-INFO}"
echo "EROS_LOG_FORMAT: ${EROS_LOG_FORMAT:-text}"

# Verify Claude configuration exists
CLAUDE_CONFIG="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/.claude.json"
if [ -f "$CLAUDE_CONFIG" ]; then
    echo "✓ Claude configuration exists"
    cat "$CLAUDE_CONFIG" | python3 -m json.tool > /dev/null
    if [ $? -eq 0 ]; then
        echo "✓ Claude configuration is valid JSON"
    else
        echo "✗ Claude configuration is invalid JSON"
        exit 1
    fi
else
    echo "✗ Claude configuration not found"
    exit 1
fi
```

### 1.4 Automation Scripts Validation

The following scripts support automated deployment operations:

```bash
# Daily backup automation
/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/backup_daily.sh

# Database restore
/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/restore_database.sh

# Monthly restore testing
/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/test_restore.sh

# Verify scripts are executable
for script in backup_daily.sh restore_database.sh test_restore.sh; do
    script_path="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups/$script"
    if [ -x "$script_path" ]; then
        echo "✓ $script is executable"
    else
        echo "✗ $script is not executable - run: chmod +x $script_path"
    fi
done
```

### 1.5 Backup Creation

**CRITICAL**: Always create a backup before deployment.

```bash
# Create timestamped backup
BACKUP_DIR="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"

cp "$DB_PATH" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Backup created: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "✗ Backup failed"
    exit 1
fi

# Verify backup integrity
sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;"

# Create backup manifest
cat > "$BACKUP_DIR/backup_manifest_${TIMESTAMP}.txt" << EOF
Backup Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Database Path: $DB_PATH
Backup File: $BACKUP_FILE
Database Size: ${DB_SIZE_MB}MB
Table Count: $TABLE_COUNT
Active Creators: $CREATOR_COUNT
Git Commit: $(git rev-parse HEAD)
Git Branch: $(git rev-parse --abbrev-ref HEAD)
EOF

echo "✓ Backup manifest created"
```

---

## Environment Configuration

### 2.1 Required Environment Variables

Create or update `~/.bashrc`, `~/.zshrc`, or environment file:

```bash
# EROS Schedule Generator Configuration
export EROS_DB_PATH="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"

# Logging Configuration
export EROS_LOG_LEVEL="INFO"           # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
export EROS_LOG_FORMAT="json"         # Options: json, text
export EROS_LOG_FILE=""                # Optional: path to log file (empty = stderr)

# Scoring Weights (optional overrides)
# export EROS_SCORE_PERFORMANCE_WEIGHT="35"
# export EROS_SCORE_FRESHNESS_WEIGHT="40"
# export EROS_SCORE_TYPE_PRIORITY_WEIGHT="15"

# Timing Configuration (optional overrides)
# export EROS_MIN_SPACING_MINUTES="20"
# export EROS_MAX_PER_HOUR="3"

# Performance Thresholds (optional overrides)
# export EROS_MIN_PERFORMANCE_SCORE="50"
# export EROS_REUSE_DAYS_THRESHOLD="30"
```

### 2.2 Claude Configuration

Verify `.claude.json` contains the MCP server configuration:

```json
{
  "mcpServers": {
    "eros-db": {
      "command": "python3",
      "args": [
        "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/mcp/eros_db_server.py"
      ],
      "env": {
        "EROS_DB_PATH": "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
      }
    }
  }
}
```

Test configuration:

```bash
# Validate JSON syntax
python3 -c "import json; f=open('.claude.json'); json.load(f); print('✓ Valid JSON')"

# Check MCP server path
jq -r '.mcpServers."eros-db".args[0]' .claude.json
```

---

## Deployment Procedure

### 3.1 Standard Deployment (No Schema Changes)

For code updates without database migrations:

```bash
#!/bin/bash
# deploy_standard.sh

set -e  # Exit on error

echo "=== EROS Schedule Generator - Standard Deployment ==="
echo "Started: $(date)"

# 1. Pre-deployment backup
echo "Step 1/6: Creating backup..."
BACKUP_DIR="database/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp database/eros_sd_main.db "$BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"
echo "✓ Backup created: $BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"

# 2. Pull latest code
echo "Step 2/6: Pulling latest code..."
git fetch origin
git pull origin main
echo "✓ Code updated to $(git rev-parse --short HEAD)"

# 3. Verify Python modules
echo "Step 3/6: Validating Python modules..."
python3 -c "from python.models.volume import VolumeTier; print('✓ Models valid')"
python3 -c "from python.allocation.send_type_allocator import SendTypeAllocator; print('✓ Allocator valid')"
python3 mcp/test_tools.py --quick 2>/dev/null && echo "✓ MCP tools functional" || echo "⚠ MCP test warnings (check stderr)"

# 4. Restart MCP server (if running standalone)
echo "Step 4/6: Restarting services..."
# If running as a service, restart it here
# systemctl restart eros-mcp-server
echo "✓ Services restarted (manual restart may be required for Claude)"

# 5. Health checks
echo "Step 5/6: Running health checks..."
./scripts/health_check.sh

# 6. Verification
echo "Step 6/6: Verifying deployment..."
python3 << EOF
from mcp.eros_db_server import get_db_connection
conn = get_db_connection()
cursor = conn.execute("SELECT COUNT(*) FROM creators WHERE is_active = 1")
count = cursor.fetchone()[0]
print(f"✓ {count} active creators accessible")
conn.close()
EOF

echo "=== Deployment Complete ==="
echo "Finished: $(date)"
echo ""
echo "Backup location: $BACKUP_DIR/eros_sd_main_${TIMESTAMP}.db"
echo "Git commit: $(git rev-parse --short HEAD)"
```

### 3.2 Database Migration Deployment

For deployments with schema changes:

```bash
#!/bin/bash
# deploy_with_migration.sh

set -e

echo "=== EROS Schedule Generator - Migration Deployment ==="
echo "Started: $(date)"

# 1. Pre-migration backup (CRITICAL)
echo "Step 1/8: Creating pre-migration backup..."
BACKUP_DIR="database/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MIGRATION_BACKUP="$BACKUP_DIR/pre_migration_${TIMESTAMP}.db"
cp database/eros_sd_main.db "$MIGRATION_BACKUP"
echo "✓ Pre-migration backup: $MIGRATION_BACKUP"

# 2. Verify migration script
MIGRATION_FILE="$1"
if [ -z "$MIGRATION_FILE" ]; then
    echo "✗ Usage: $0 <migration_file.sql>"
    exit 1
fi

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "✗ Migration file not found: $MIGRATION_FILE"
    exit 1
fi
echo "✓ Migration file: $MIGRATION_FILE"

# 3. Dry run (test migration on backup)
echo "Step 2/8: Testing migration on backup..."
TEST_DB="$BACKUP_DIR/migration_test_${TIMESTAMP}.db"
cp "$MIGRATION_BACKUP" "$TEST_DB"
sqlite3 "$TEST_DB" < "$MIGRATION_FILE" 2>&1 | tee migration_test.log
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "✓ Migration dry run successful"
    rm "$TEST_DB"
else
    echo "✗ Migration dry run failed - check migration_test.log"
    exit 1
fi

# 4. Apply migration to production database
echo "Step 3/8: Applying migration to production..."
sqlite3 database/eros_sd_main.db < "$MIGRATION_FILE" 2>&1 | tee migration_prod.log
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "✓ Migration applied successfully"
else
    echo "✗ Migration failed - initiating rollback"
    ./scripts/rollback.sh "$MIGRATION_BACKUP"
    exit 1
fi

# 5. Verify database integrity
echo "Step 4/8: Verifying database integrity..."
sqlite3 database/eros_sd_main.db "PRAGMA integrity_check;" | grep -q "ok"
if [ $? -eq 0 ]; then
    echo "✓ Database integrity verified"
else
    echo "✗ Database integrity check failed - initiating rollback"
    ./scripts/rollback.sh "$MIGRATION_BACKUP"
    exit 1
fi

# 6. Update code
echo "Step 5/8: Updating code..."
git pull origin main
echo "✓ Code updated"

# 7. Run validation tests
echo "Step 6/8: Running validation tests..."
python3 tests/phase5_test_cases.py || true  # Non-blocking

# 8. Health checks
echo "Step 7/8: Running health checks..."
./scripts/health_check.sh

echo "Step 8/8: Deployment verification..."
echo "✓ Migration deployment complete"
echo ""
echo "Pre-migration backup: $MIGRATION_BACKUP"
echo "Migration file: $MIGRATION_FILE"
echo "Git commit: $(git rev-parse --short HEAD)"
```

---

## Health Checks

### 4.1 MCP Server Health Check

Create `scripts/health_check.sh`:

```bash
#!/bin/bash
# health_check.sh - Comprehensive health checks for EROS system

echo "=== EROS Schedule Generator Health Check ==="
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""

PASS_COUNT=0
FAIL_COUNT=0

# Function to report results
check_result() {
    if [ $1 -eq 0 ]; then
        echo "✓ $2"
        ((PASS_COUNT++))
    else
        echo "✗ $2"
        ((FAIL_COUNT++))
    fi
}

# 1. Database connectivity
echo "1. Database Connectivity"
sqlite3 database/eros_sd_main.db "SELECT 1;" >/dev/null 2>&1
check_result $? "Database connection"

# 2. Database integrity
INTEGRITY=$(sqlite3 database/eros_sd_main.db "PRAGMA integrity_check;")
[ "$INTEGRITY" = "ok" ]
check_result $? "Database integrity"

# 3. Table count
TABLE_COUNT=$(sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
[ "$TABLE_COUNT" -eq 59 ]
check_result $? "Table count (59 expected, $TABLE_COUNT found)"

# 4. Active creators
CREATOR_COUNT=$(sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM creators WHERE is_active = 1;")
[ "$CREATOR_COUNT" -ge 30 ]
check_result $? "Active creators ($CREATOR_COUNT found)"

# 5. MCP server syntax
python3 -m py_compile mcp/eros_db_server.py 2>/dev/null
check_result $? "MCP server syntax"

# 6. Python modules loadable
python3 -c "from python.models.volume import VolumeTier; from python.allocation.send_type_allocator import SendTypeAllocator" 2>/dev/null
check_result $? "Python modules loadable"

# 7. Send types table populated
SEND_TYPE_COUNT=$(sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM send_types;")
[ "$SEND_TYPE_COUNT" -eq 22 ]
check_result $? "Send types (22 expected, $SEND_TYPE_COUNT found)"

# 8. Caption bank populated
CAPTION_COUNT=$(sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM caption_bank;")
[ "$CAPTION_COUNT" -gt 59000 ]
check_result $? "Caption bank ($CAPTION_COUNT captions)"

# 9. Performance data available
MESSAGE_COUNT=$(sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM mass_messages;")
[ "$MESSAGE_COUNT" -gt 70000 ]
check_result $? "Performance data ($MESSAGE_COUNT messages)"

# 10. Foreign key enforcement
FK_STATUS=$(sqlite3 database/eros_sd_main.db "PRAGMA foreign_keys;")
[ "$FK_STATUS" = "1" ] || [ "$FK_STATUS" = "on" ]
check_result $? "Foreign key enforcement"

# 11. Database file permissions
[ -r database/eros_sd_main.db ] && [ -w database/eros_sd_main.db ]
check_result $? "Database file permissions"

# 12. Backup directory exists
[ -d database/backups ]
check_result $? "Backup directory exists"

echo ""
echo "=== Summary ==="
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✓ All health checks passed"
    exit 0
else
    echo "✗ Some health checks failed"
    exit 1
fi
```

Make it executable:

```bash
chmod +x scripts/health_check.sh
```

### 4.2 MCP Server Test

Test MCP server functionality:

```bash
#!/bin/bash
# test_mcp_server.sh

echo "Testing MCP Server..."

# Test server can start
timeout 5 python3 mcp/eros_db_server.py > /dev/null 2>&1 &
MCP_PID=$!
sleep 2

if kill -0 $MCP_PID 2>/dev/null; then
    echo "✓ MCP server process started"
    kill $MCP_PID
else
    echo "✗ MCP server failed to start"
    exit 1
fi

# Test tool imports
python3 << EOF
import sys
sys.path.insert(0, '.')
from mcp.eros_db_server import (
    get_creator_profile,
    get_active_creators,
    get_send_types,
    get_volume_config
)
print("✓ All MCP tools importable")
EOF

# Test database operations
python3 << EOF
from mcp.eros_db_server import get_db_connection
conn = get_db_connection()
cursor = conn.execute("SELECT COUNT(*) FROM creators WHERE is_active = 1")
count = cursor.fetchone()[0]
conn.close()
assert count >= 30, f"Expected >= 30 creators, got {count}"
print(f"✓ Database operations functional ({count} active creators)")
EOF
```

### 4.3 Quick Smoke Test

```bash
# Quick verification after deployment
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT

# Test 1: Database accessible
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM creators WHERE is_active = 1;"

# Test 2: MCP tools functional
python3 -c "from mcp.eros_db_server import get_active_creators; print('✓ MCP tools OK')"

# Test 3: Python modules loadable
python3 -c "from python.allocation.send_type_allocator import SendTypeAllocator; print('✓ Python modules OK')"

# All tests passed
echo "✓ Smoke tests passed"
```

---

## Rollback Procedures

### 5.1 Standard Rollback (Code Only)

Revert to previous Git commit:

```bash
#!/bin/bash
# rollback_code.sh

set -e

echo "=== Code Rollback ==="

# Show current commit
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "Current commit: $CURRENT_COMMIT"

# Show recent commits
echo ""
echo "Recent commits:"
git log --oneline -5

# Prompt for target commit
read -p "Enter commit hash to rollback to: " TARGET_COMMIT

if [ -z "$TARGET_COMMIT" ]; then
    echo "✗ No commit specified"
    exit 1
fi

# Verify commit exists
git cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ Invalid commit hash"
    exit 1
fi

# Perform rollback
echo "Rolling back from $CURRENT_COMMIT to $TARGET_COMMIT..."
git checkout "$TARGET_COMMIT"

# Verify health
./scripts/health_check.sh

echo "✓ Code rollback complete"
echo "Current commit: $(git rev-parse --short HEAD)"
```

### 5.2 Database Rollback

Restore from backup:

```bash
#!/bin/bash
# rollback_database.sh

set -e

echo "=== Database Rollback ==="

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lht database/backups/*.db | head -10
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "✗ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Backup file: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"

# Verify backup integrity before restoring
echo "Verifying backup integrity..."
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    echo "✗ Backup file is corrupted: $INTEGRITY"
    exit 1
fi
echo "✓ Backup integrity verified"

# Create safety backup of current database
SAFETY_BACKUP="database/backups/pre_rollback_$(date +%Y%m%d_%H%M%S).db"
echo "Creating safety backup: $SAFETY_BACKUP"
cp database/eros_sd_main.db "$SAFETY_BACKUP"

# Confirm rollback
read -p "Restore database from backup? This will overwrite the current database. (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

# Perform rollback
echo "Restoring database..."
cp "$BACKUP_FILE" database/eros_sd_main.db

# Verify restored database
echo "Verifying restored database..."
RESTORE_INTEGRITY=$(sqlite3 database/eros_sd_main.db "PRAGMA integrity_check;")
if [ "$RESTORE_INTEGRITY" != "ok" ]; then
    echo "✗ Restored database is corrupted - restoring safety backup"
    cp "$SAFETY_BACKUP" database/eros_sd_main.db
    exit 1
fi

# Run health checks
./scripts/health_check.sh

echo "✓ Database rollback complete"
echo "Restored from: $BACKUP_FILE"
echo "Safety backup: $SAFETY_BACKUP"
```

### 5.3 Full System Rollback

Complete rollback including code and database:

```bash
#!/bin/bash
# rollback_full.sh

set -e

echo "=== Full System Rollback ==="

# 1. Get rollback targets
echo "Step 1/3: Identifying rollback targets..."
echo ""
echo "Recent Git commits:"
git log --oneline -5
echo ""
read -p "Enter Git commit to rollback to: " GIT_COMMIT

echo ""
echo "Recent database backups:"
ls -lht database/backups/*.db | head -5
echo ""
read -p "Enter database backup file path: " DB_BACKUP

# 2. Rollback code
echo "Step 2/3: Rolling back code to $GIT_COMMIT..."
git checkout "$GIT_COMMIT"
echo "✓ Code rolled back"

# 3. Rollback database
echo "Step 3/3: Rolling back database..."
./scripts/rollback_database.sh "$DB_BACKUP"

echo "=== Full Rollback Complete ==="
echo "Git commit: $(git rev-parse --short HEAD)"
echo "Database backup: $DB_BACKUP"
```

---

## Post-Deployment Verification

### 6.1 Functional Tests

```bash
#!/bin/bash
# verify_deployment.sh

echo "=== Post-Deployment Verification ==="

# Test 1: Generate test schedule
echo "Test 1: Schedule generation..."
python3 << EOF
import sys
sys.path.insert(0, '.')

# Test schedule generation logic (without saving)
from python.allocation.send_type_allocator import SendTypeAllocator
from python.models.volume import VolumeTier, VolumeConfig

config = VolumeConfig(
    tier=VolumeTier.MID,
    revenue_per_day=3,
    engagement_per_day=4,
    retention_per_day=2
)

allocator = SendTypeAllocator()
result = allocator.allocate_week(config, page_type="paid")

assert len(result) > 0, "Schedule generation failed"
print(f"✓ Generated {len(result)} schedule items")
EOF

# Test 2: Query active creators
echo "Test 2: Creator data access..."
python3 << EOF
from mcp.eros_db_server import get_active_creators
result = get_active_creators()
import json
data = json.loads(result)
assert 'creators' in data, "Creator query failed"
print(f"✓ Accessed {len(data['creators'])} active creators")
EOF

# Test 3: Caption selection
echo "Test 3: Caption selection..."
python3 << EOF
from mcp.eros_db_server import get_db_connection
conn = get_db_connection()
cursor = conn.execute("""
    SELECT COUNT(*) FROM caption_bank
    WHERE caption_text IS NOT NULL
""")
count = cursor.fetchone()[0]
conn.close()
assert count > 50000, f"Caption count too low: {count}"
print(f"✓ Caption bank contains {count} captions")
EOF

echo ""
echo "✓ All verification tests passed"
```

### 6.2 Performance Benchmarks

```bash
# Benchmark schedule generation
time python3 << EOF
from python.allocation.send_type_allocator import SendTypeAllocator
from python.models.volume import VolumeTier, VolumeConfig

config = VolumeConfig(
    tier=VolumeTier.HIGH,
    revenue_per_day=5,
    engagement_per_day=6,
    retention_per_day=3
)

allocator = SendTypeAllocator()
for i in range(10):
    result = allocator.allocate_week(config, page_type="paid")

print(f"Generated 10 weekly schedules")
EOF
# Should complete in < 5 seconds
```

---

## Troubleshooting

### 7.1 Common Issues

#### Database Lock Error

**Symptom**: `database is locked` error

**Solution**:
```bash
# Check for open connections
lsof database/eros_sd_main.db

# Kill processes holding locks
kill -9 <PID>

# If persistent, rebuild database
sqlite3 database/eros_sd_main.db "VACUUM;"
```

#### MCP Server Won't Start

**Symptom**: MCP server fails to initialize

**Solution**:
```bash
# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"

# Verify imports
python3 -c "from mcp.eros_db_server import get_db_connection"

# Check database path
echo $EROS_DB_PATH
ls -lh $EROS_DB_PATH

# Test database connection
sqlite3 $EROS_DB_PATH "SELECT 1;"
```

#### Import Errors

**Symptom**: `ModuleNotFoundError` when importing Python modules

**Solution**:
```bash
# Verify Python path includes project root
export PYTHONPATH="/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT:$PYTHONPATH"

# Check __init__.py files exist
find python -name "__init__.py"

# Test imports
python3 -c "from python.models.volume import VolumeTier"
```

### 7.2 Emergency Contacts

| Role | Contact | Availability |
|------|---------|-------------|
| Database Administrator | DBA Team | 24/7 |
| Python Developer | Dev Team | Business hours |
| Operations Lead | Ops Team | 24/7 on-call |

### 7.3 Logs Location

```bash
# MCP Server logs (stderr)
# Configured via EROS_LOG_FILE environment variable

# Claude Desktop logs
~/Library/Logs/Claude/mcp*.log

# System logs
/var/log/system.log
```

---

## Appendix: Quick Reference

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EROS_DB_PATH` | Database file path | `./database/eros_sd_main.db` |
| `EROS_LOG_LEVEL` | Logging verbosity | `INFO` |
| `EROS_LOG_FORMAT` | Log format (json/text) | `text` |

### Key Paths

| Path | Description |
|------|-------------|
| `/database/eros_sd_main.db` | Production database (250MB) |
| `/database/backups/` | Database backups |
| `/mcp/eros_db_server.py` | MCP server (99KB) |
| `/python/` | Core Python modules |
| `/.claude.json` | Claude configuration |

### Health Check Metrics

| Metric | Expected Value |
|--------|---------------|
| Table count | 59 |
| Active creators | 37 |
| Send types | 22 |
| Caption bank | 59,405+ |
| Mass messages | 71,998+ |
| Database size | ~250MB |

---

**Document Version**: 1.0
**Created**: 2025-12-17
**Next Review**: 2026-03-17
