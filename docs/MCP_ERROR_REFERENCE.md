# MCP Server Error Reference

Quick reference guide for MCP tool error codes, causes, and resolutions.

**Version**: 2.2.0
**Last Updated**: December 17, 2025

---

## Error Response Format

All MCP tools return errors in a consistent JSON format:

```json
{
  "error": "Human-readable error message describing the problem"
}
```

**Checking for Errors**:
```python
result = get_creator_profile("alexia")

if "error" in result:
    # Handle error
    print(f"Error: {result['error']}")
else:
    # Process successful result
    creator = result["creator"]
```

---

## Error Categories

| Category | HTTP Equivalent | Typical Causes |
|----------|-----------------|----------------|
| **Validation Error** | 400 Bad Request | Invalid input format, missing required fields |
| **Not Found** | 404 Not Found | Resource doesn't exist in database |
| **Security Error** | 403 Forbidden | Dangerous SQL, blocked keywords |
| **Database Error** | 500 Internal Server Error | SQLite errors, connection issues |

---

## Common Errors by Tool

### Creator Data Tools

#### Invalid creator_id

**Error**: `Invalid creator_id: creator_id contains invalid characters`

**Cause**: Creator ID contains characters outside allowed set

**Tools Affected**:
- get_creator_profile
- get_persona_profile
- get_vault_availability
- get_performance_trends
- get_content_type_rankings
- get_best_timing
- get_volume_config
- get_volume_assignment
- get_top_captions
- get_send_type_captions
- save_schedule

**Resolution**:
```python
# INVALID
creator_id = "alexia@onlyfans"  # @ not allowed
creator_id = "alexia.page"      # . not allowed
creator_id = "alexia jones"     # space not allowed

# VALID
creator_id = "alexia"           # ✓
creator_id = "miss_alexa"       # ✓ underscore allowed
creator_id = "jade-rose"        # ✓ hyphen allowed
creator_id = "creator_123"      # ✓ numbers allowed
```

**Validation Rules**:
- Alphanumeric characters only (a-z, A-Z, 0-9)
- Underscore (_) and hyphen (-) allowed
- Maximum 100 characters
- Cannot be empty

---

#### Creator not found

**Error**: `Creator not found: invalid_creator`

**Cause**: Creator ID doesn't exist in database

**Tools Affected**: Same as Invalid creator_id

**Resolution**:
```python
# Step 1: Get list of valid creators
creators = get_active_creators()
print(f"Available creators: {[c['creator_id'] for c in creators['creators']]}")

# Step 2: Use valid creator_id
result = get_creator_profile("alexia")  # Use existing creator
```

**Common Mistakes**:
- Typo in creator_id
- Using display_name instead of creator_id
- Creator not yet added to database
- Creator marked as inactive (is_active = 0)

---

### Send Type Configuration Tools

#### Invalid send_type_key

**Error**: `Invalid send_type_key: send_type_key contains invalid characters`

**Cause**: Send type key contains invalid characters

**Tools Affected**:
- get_send_type_details
- get_top_captions (when send_type_key parameter used)
- get_send_type_captions

**Resolution**:
```python
# INVALID
send_type_key = "ppv video"     # space not allowed
send_type_key = "ppv.unlock"    # . not allowed

# VALID
send_type_key = "ppv_unlock"    # ✓
send_type_key = "bump_normal"   # ✓
send_type_key = "game_post"     # ✓
```

**Validation Rules**:
- Alphanumeric characters (a-z, A-Z, 0-9)
- Underscore (_) and hyphen (-) allowed
- Maximum 50 characters
- Cannot be empty

---

#### Send type not found

**Error**: `Send type not found: invalid_send_type`

**Cause**: Send type key doesn't exist in database

**Tools Affected**: Same as Invalid send_type_key

**Resolution**:
```python
# Step 1: Get list of valid send types
send_types = get_send_types()
print(f"Available send types: {[st['send_type_key'] for st in send_types['send_types']]}")

# Step 2: Use valid send_type_key
details = get_send_type_details("ppv_unlock")  # Use existing send type
```

**Valid Send Types** (v2.1):

**Revenue** (9):
- ppv_unlock
- ppv_wall
- tip_goal
- bundle
- flash_bundle
- game_post
- first_to_tip
- vip_program
- snapchat_bundle

**Engagement** (9):
- link_drop
- wall_link_drop
- bump_normal
- bump_descriptive
- bump_text_only
- bump_flyer
- dm_farm
- like_farm
- live_promo

**Retention** (4):
- renew_on_post
- renew_on_message
- ppv_followup
- expired_winback

---

### Targeting & Channel Tools

#### Invalid channel_key

**Error**: `Invalid channel_key: channel_key contains invalid characters`

**Cause**: Channel key contains invalid characters

**Tools Affected**:
- get_audience_targets (when channel_key parameter used)

**Resolution**:
```python
# Get list of valid channels
channels = get_channels()
print(f"Available channels: {[ch['channel_key'] for ch in channels['channels']]}")

# Use valid channel_key
targets = get_audience_targets(channel_key="mass_message")
```

**Valid Channel Keys**:
- mass_message
- wall_post
- targeted_message
- story
- live

---

#### Invalid page_type

**Error**: `page_type must be 'paid' or 'free'`

**Cause**: Invalid page_type value provided

**Tools Affected**:
- get_active_creators
- get_send_types
- get_audience_targets

**Resolution**:
```python
# INVALID
result = get_active_creators(page_type="premium")  # Not valid
result = get_active_creators(page_type="PAID")     # Case-sensitive

# VALID
result = get_active_creators(page_type="paid")     # ✓
result = get_active_creators(page_type="free")     # ✓
```

**Valid Values**: `"paid"` or `"free"` (lowercase only)

---

### Performance & Analytics Tools

#### Invalid period

**Error**: `period must be '7d', '14d', or '30d'`

**Cause**: Invalid period value for performance trends

**Tools Affected**:
- get_performance_trends

**Resolution**:
```python
# INVALID
trends = get_performance_trends("alexia", period="1w")    # Wrong format
trends = get_performance_trends("alexia", period="14")    # Missing 'd'

# VALID
trends = get_performance_trends("alexia", period="7d")    # ✓
trends = get_performance_trends("alexia", period="14d")   # ✓
trends = get_performance_trends("alexia", period="30d")   # ✓
```

**Valid Values**: `"7d"`, `"14d"`, or `"30d"`

---

#### Invalid category

**Error**: `category must be 'revenue', 'engagement', or 'retention'`

**Cause**: Invalid category value for send types

**Tools Affected**:
- get_send_types

**Resolution**:
```python
# INVALID
send_types = get_send_types(category="income")      # Wrong term
send_types = get_send_types(category="Revenue")     # Case-sensitive

# VALID
send_types = get_send_types(category="revenue")     # ✓
send_types = get_send_types(category="engagement")  # ✓
send_types = get_send_types(category="retention")   # ✓
```

**Valid Values**: `"revenue"`, `"engagement"`, or `"retention"` (lowercase only)

---

### Schedule Operations Tools

#### Invalid week_start format

**Error**: `week_start must be in YYYY-MM-DD format`

**Cause**: Week start date not in ISO format

**Tools Affected**:
- save_schedule

**Resolution**:
```python
# INVALID
save_schedule("alexia", "12/16/2025", items)        # Wrong format
save_schedule("alexia", "2025-12-16T00:00:00", items)  # Has time

# VALID
save_schedule("alexia", "2025-12-16", items)        # ✓ ISO date
```

**Format**: `YYYY-MM-DD` (ISO 8601 date format)

**Examples**:
- `"2025-12-16"` ✓
- `"2025-01-01"` ✓
- `"2025-12-31"` ✓

---

### Query Execution Tool

#### Only SELECT queries allowed

**Error**: `Only SELECT queries are allowed for security reasons`

**Cause**: Attempted to execute non-SELECT query

**Tools Affected**:
- execute_query

**Resolution**:
```python
# INVALID - Write operations not allowed
execute_query("UPDATE creators SET page_name = 'new_name'")
execute_query("INSERT INTO creators VALUES (...)")
execute_query("DELETE FROM creators WHERE creator_id = 'alexia'")

# VALID - Read-only SELECT queries
execute_query("SELECT * FROM creators WHERE performance_tier = 1")
execute_query("SELECT COUNT(*) FROM mass_messages WHERE creator_id = ?", ["alexia"])
```

**Allowed**: Only `SELECT` queries
**Blocked**: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, etc.

---

#### Query contains disallowed keyword

**Error**: `Query contains disallowed keyword: INSERT`

**Cause**: Query contains dangerous SQL keyword

**Tools Affected**:
- execute_query

**Blocked Keywords**:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE
- TRUNCATE
- GRANT
- REVOKE
- ATTACH
- DETACH
- PRAGMA
- VACUUM
- REINDEX
- ANALYZE

**Resolution**: Use SELECT-only queries for data retrieval

---

#### Query contains disallowed comment syntax

**Error**: `Query contains disallowed comment syntax (/* */ or --)`

**Cause**: Query contains SQL comment patterns

**Tools Affected**:
- execute_query

**Resolution**:
```python
# INVALID - Comments blocked for security
execute_query("SELECT * FROM creators -- get all")
execute_query("SELECT /* inline comment */ * FROM creators")

# VALID - Remove comments
execute_query("SELECT * FROM creators")
```

**Blocked Patterns**: `/*`, `*/`, `--`

---

#### Query exceeds maximum JOIN limit

**Error**: `Query exceeds maximum JOIN limit of 5 (found 7)`

**Cause**: Query has too many JOINs

**Tools Affected**:
- execute_query

**Limit**: Maximum 5 JOINs per query

**Resolution**: Simplify query by:
1. Breaking into multiple queries
2. Using subqueries (max 3)
3. Denormalizing data
4. Using views (pre-joined tables)

---

#### Query exceeds maximum subquery limit

**Error**: `Query exceeds maximum subquery limit of 3 (found 5)`

**Cause**: Query has too many nested subqueries

**Tools Affected**:
- execute_query

**Limit**: Maximum 3 subqueries per query

**Resolution**: Simplify query by:
1. Using JOINs instead of subqueries
2. Breaking into multiple queries
3. Using temporary tables
4. Flattening nested logic

---

#### Query LIMIT exceeds maximum

**Error**: `Query LIMIT exceeds maximum of 10000 (requested 50000)`

**Cause**: Query requests too many rows

**Tools Affected**:
- execute_query

**Limit**: Maximum 10,000 rows per query

**Resolution**:
```python
# INVALID - Too many rows
execute_query("SELECT * FROM caption_bank LIMIT 50000")

# VALID - Within limits
execute_query("SELECT * FROM caption_bank LIMIT 10000")
execute_query("SELECT * FROM caption_bank WHERE creator_id = ? LIMIT 1000", ["alexia"])

# BETTER - Use specific filters to reduce results
execute_query("""
    SELECT * FROM caption_bank
    WHERE creator_id = ? AND performance_score > 60
    LIMIT 100
""", ["alexia"])
```

---

#### Query execution error

**Error**: `Query execution error: near "FROM": syntax error`

**Cause**: SQL syntax error in query

**Tools Affected**:
- execute_query

**Common Causes**:
1. Missing SELECT keyword
2. Typo in table/column name
3. Missing FROM clause
4. Unmatched parentheses
5. Invalid SQL syntax

**Resolution**:
```python
# INVALID - Syntax errors
execute_query("* FROM creators")           # Missing SELECT
execute_query("SELECT * FRM creators")     # Typo in FROM
execute_query("SELECT * FROM creatorz")    # Wrong table name

# VALID - Correct syntax
execute_query("SELECT * FROM creators")
execute_query("SELECT creator_id, page_name FROM creators")
```

**Debugging Tips**:
1. Test query in SQLite CLI first
2. Check table/column names with `PRAGMA table_info(table_name)`
3. Use parameterized queries for values
4. Validate SQL syntax with linter

---

## Error Handling Best Practices

### 1. Always Check for Errors

```python
result = get_creator_profile("alexia")

if "error" in result:
    logger.error(f"Error getting creator profile: {result['error']}")
    return None
else:
    return result["creator"]
```

### 2. Categorize Errors

```python
def handle_error(result: dict) -> str:
    """Convert technical errors to user-friendly messages."""
    if "error" not in result:
        return None

    error = result["error"].lower()

    if "not found" in error:
        return "Resource doesn't exist"
    elif "invalid" in error:
        return "Invalid input format"
    elif "database error" in error:
        return "System error - please try again"
    else:
        return "Unknown error occurred"
```

### 3. Implement Retry Logic

```python
import time

def get_with_retry(func, *args, max_retries=3, **kwargs):
    """Retry on database errors."""
    for attempt in range(max_retries):
        result = func(*args, **kwargs)

        if "error" not in result:
            return result

        if "database error" in result["error"].lower():
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue

        return result  # Non-retryable error or max retries
```

### 4. Log Errors with Context

```python
import logging

logger = logging.getLogger(__name__)

result = get_creator_profile(creator_id)

if "error" in result:
    logger.error(
        "Creator profile fetch failed",
        extra={
            "creator_id": creator_id,
            "error": result["error"],
            "tool": "get_creator_profile"
        }
    )
```

### 5. Validate Before Calling

```python
from mcp.utils.security import validate_creator_id

def safe_get_creator_profile(creator_id: str):
    """Validate before calling MCP tool."""
    is_valid, error_msg = validate_creator_id(creator_id)

    if not is_valid:
        return {"error": f"Invalid input: {error_msg}"}

    return get_creator_profile(creator_id)
```

---

## Error Resolution Flowchart

```
Error Received
    ↓
Contains "invalid"?
    ├─ Yes → Check input format/validation rules
    └─ No
        ↓
    Contains "not found"?
        ├─ Yes → Verify resource exists in database
        └─ No
            ↓
        Contains "disallowed" or "exceeds"?
            ├─ Yes → Check security constraints
            └─ No
                ↓
            Contains "database error"?
                ├─ Yes → Retry operation, check connection
                └─ No → Log and investigate
```

---

## Testing Error Conditions

```python
import pytest

def test_invalid_creator_id():
    """Test error handling for invalid creator ID."""
    result = get_creator_profile("alexia@onlyfans")
    assert "error" in result
    assert "invalid" in result["error"].lower()

def test_creator_not_found():
    """Test error handling for non-existent creator."""
    result = get_creator_profile("nonexistent_creator_xyz")
    assert "error" in result
    assert "not found" in result["error"].lower()

def test_invalid_period():
    """Test error handling for invalid period."""
    result = get_performance_trends("alexia", period="invalid")
    assert "error" in result
    assert "period must be" in result["error"].lower()

def test_sql_injection_blocked():
    """Test SQL injection protection."""
    result = execute_query("SELECT * FROM creators; DROP TABLE creators;")
    assert "error" in result
    assert "disallowed" in result["error"].lower()
```

---

## Related Documentation

- **MCP API Reference**: [MCP_API_REFERENCE.md](MCP_API_REFERENCE.md) - Complete tool documentation
- **Type Definitions**: [mcp/types.py](../mcp/types.py) - TypedDict definitions
- **Security Module**: [mcp/utils/security.py](../mcp/utils/security.py) - Validation functions
- **User Guide**: [USER_GUIDE.md](USER_GUIDE.md) - End-user documentation

---

*EROS MCP Server Error Reference v2.2.0*
*Last Updated: December 17, 2025*
