#!/bin/bash
# ============================================================================
# EROS Caption Type Taxonomy Migration Runner
# Usage: ./006_run_migration.sh [--dry-run] [--validate-only]
# ============================================================================

set -e

DB_PATH="${EROS_DATABASE_PATH:-/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_FILE="$SCRIPT_DIR/006_caption_type_taxonomy_migration.sql"
VALIDATION_FILE="$SCRIPT_DIR/006_caption_type_validation_queries.sql"

DRY_RUN=false
VALIDATE_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--validate-only]"
            exit 1
            ;;
    esac
done

echo "=============================================="
echo "EROS Caption Type Taxonomy Migration"
echo "=============================================="
echo "Database: $DB_PATH"
echo "Dry Run: $DRY_RUN"
echo "Validate Only: $VALIDATE_ONLY"
echo ""

# Check database exists
if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup
if [[ "$DRY_RUN" == "false" && "$VALIDATE_ONLY" == "false" ]]; then
    BACKUP_PATH="${DB_PATH}.backup_migration_006_$(date +%Y%m%d_%H%M%S)"
    echo "Creating backup: $BACKUP_PATH"
    cp "$DB_PATH" "$BACKUP_PATH"
    echo "Backup created successfully"
    echo ""
fi

# Run pre-migration validation
echo "Running pre-migration validation..."
echo ""
sqlite3 "$DB_PATH" <<'EOF'
.mode column
.headers on

-- Total records
SELECT 'Total Records' as check_name, COUNT(*) as count FROM caption_bank;

-- Type distribution
SELECT caption_type, send_type, COUNT(*) as cnt
FROM caption_bank
GROUP BY caption_type, send_type
ORDER BY cnt DESC
LIMIT 15;

-- NULL/empty checks
SELECT
    'NULL/Empty Check' as check_name,
    SUM(CASE WHEN send_type IS NULL THEN 1 ELSE 0 END) as null_send_type,
    SUM(CASE WHEN send_type = '' THEN 1 ELSE 0 END) as empty_send_type
FROM caption_bank;
EOF
echo ""

if [[ "$VALIDATE_ONLY" == "true" ]]; then
    echo "Validate-only mode: Skipping migration"
    exit 0
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Dry-run mode: Simulating migration..."
    echo ""

    # Create temp database for dry run
    TEMP_DB="/tmp/eros_migration_test_$(date +%s).db"
    cp "$DB_PATH" "$TEMP_DB"

    # Check if columns already exist
    HAS_V2=$(sqlite3 "$TEMP_DB" "SELECT COUNT(*) FROM pragma_table_info('caption_bank') WHERE name = 'caption_type_v2';")

    if [[ "$HAS_V2" == "0" ]]; then
        echo "Adding new columns..."
        sqlite3 "$TEMP_DB" "ALTER TABLE caption_bank ADD COLUMN caption_type_v2 TEXT;"
        sqlite3 "$TEMP_DB" "ALTER TABLE caption_bank ADD COLUMN send_type_v2 TEXT;"
        sqlite3 "$TEMP_DB" "ALTER TABLE caption_bank ADD COLUMN is_paid_page_only INTEGER DEFAULT 0;"
    fi

    # Run migration on temp database
    echo "Executing migration on temporary database..."
    sqlite3 "$TEMP_DB" < "$MIGRATION_FILE" 2>&1 || true

    echo ""
    echo "Post-migration validation (dry-run):"
    sqlite3 "$TEMP_DB" <<'EOF'
.mode column
.headers on

-- Migration coverage
SELECT
    'Migration Coverage' as check_name,
    COUNT(*) as total,
    SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) as migrated,
    SUM(CASE WHEN caption_type_v2 IS NULL THEN 1 ELSE 0 END) as not_migrated
FROM caption_bank;

-- New type distribution
SELECT caption_type_v2, COUNT(*) as count
FROM caption_bank
WHERE caption_type_v2 IS NOT NULL
GROUP BY caption_type_v2
ORDER BY count DESC;

-- Paid page only
SELECT
    'Paid Page Only' as check_name,
    caption_type_v2,
    COUNT(*) as count
FROM caption_bank
WHERE is_paid_page_only = 1
GROUP BY caption_type_v2;

-- Mapping comparison sample
SELECT
    caption_type as old_type,
    send_type as old_send,
    caption_type_v2 as new_type,
    send_type_v2 as new_send,
    is_paid_page_only as paid_only,
    COUNT(*) as count
FROM caption_bank
GROUP BY caption_type, send_type, caption_type_v2, send_type_v2, is_paid_page_only
ORDER BY count DESC
LIMIT 20;
EOF

    # Cleanup temp database
    rm -f "$TEMP_DB"

    echo ""
    echo "Dry-run complete. No changes made to production database."
    echo "Run without --dry-run to execute migration."
    exit 0
fi

# Execute actual migration
echo "Executing migration..."
echo ""

# Check if columns already exist
HAS_V2=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pragma_table_info('caption_bank') WHERE name = 'caption_type_v2';")

if [[ "$HAS_V2" == "0" ]]; then
    echo "Adding new columns to caption_bank..."
    sqlite3 "$DB_PATH" "ALTER TABLE caption_bank ADD COLUMN caption_type_v2 TEXT;"
    sqlite3 "$DB_PATH" "ALTER TABLE caption_bank ADD COLUMN send_type_v2 TEXT;"
    sqlite3 "$DB_PATH" "ALTER TABLE caption_bank ADD COLUMN is_paid_page_only INTEGER DEFAULT 0;"
    echo "Columns added successfully"
else
    echo "New columns already exist, skipping ALTER TABLE"
fi

echo ""
echo "Running migration script..."
sqlite3 "$DB_PATH" < "$MIGRATION_FILE"

echo ""
echo "=============================================="
echo "POST-MIGRATION VALIDATION"
echo "=============================================="
sqlite3 "$DB_PATH" <<'EOF'
.mode column
.headers on

-- Migration coverage
SELECT
    'RESULT: Migration Coverage' as check_name,
    COUNT(*) as total,
    SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) as migrated,
    ROUND(100.0 * SUM(CASE WHEN caption_type_v2 IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as pct
FROM caption_bank;

-- NULL checks
SELECT
    'RESULT: NULL Checks' as check_name,
    SUM(CASE WHEN caption_type_v2 IS NULL THEN 1 ELSE 0 END) as null_caption_type_v2,
    SUM(CASE WHEN send_type_v2 IS NULL THEN 1 ELSE 0 END) as null_send_type_v2
FROM caption_bank;

-- New type distribution
SELECT 'RESULT: caption_type_v2 Distribution' as heading;
SELECT caption_type_v2, COUNT(*) as count
FROM caption_bank
GROUP BY caption_type_v2
ORDER BY count DESC;

-- Paid page only verification
SELECT 'RESULT: Paid Page Only Records' as heading;
SELECT caption_type_v2, COUNT(*) as count
FROM caption_bank
WHERE is_paid_page_only = 1
GROUP BY caption_type_v2;
EOF

echo ""
echo "=============================================="
echo "Migration complete!"
echo "Backup saved to: $BACKUP_PATH"
echo "=============================================="
