# EROS Security Documentation

## Overview

Security practices and credential management for the EROS Schedule Generator system.

## Credential Management

### Database Credentials

| Credential | Location | Rotation Frequency | Owner |
|------------|----------|-------------------|-------|
| SQLite database | Local file (`database/eros_sd_main.db`) | N/A (file-based) | System |
| Google Sheets API | `database/google_sheets_sync/credentials/` | Annually | DevOps |

### Google Sheets API Credentials

**Location**: `database/google_sheets_sync/credentials/service_account.json`

**Rotation Procedure**:
1. Generate new service account key in Google Cloud Console
2. Save as `service_account_new.json` in credentials directory
3. Test with dry-run:
   ```bash
   python -m database.google_sheets_sync.cli test-auth --credentials service_account_new.json
   ```
4. If successful, rotate:
   ```bash
   mv service_account.json service_account_old.json
   mv service_account_new.json service_account.json
   ```
5. Revoke old key in Google Cloud Console within 24 hours
6. Update rotation log (see below)

**Never Commit**:
- `service_account.json`
- `*.pem`
- `*.key`
- `.env` files with secrets
- Any file in `credentials/`

### Environment Variables

| Variable | Purpose | Contains Secrets | Rotation |
|----------|---------|------------------|----------|
| `EROS_DB_PATH` | Database location | No | N/A |
| `EROS_METRICS_PORT` | Prometheus port | No | N/A |
| `GOOGLE_APPLICATION_CREDENTIALS` | Sheets auth path | No (path only) | N/A |
| `EROS_CB_*` | Circuit breaker config | No | N/A |

## Network Security

### Prometheus Metrics Endpoint

- **Binding**: `127.0.0.1:9090` (localhost only)
- **External access**: Disabled by default
- **To enable external access**: Requires explicit code change in `mcp/metrics.py`
- **Authentication**: None (localhost only)

### MCP Server

- **Protocol**: stdio (local process communication)
- **Network exposure**: None (process-to-process only)
- **Authentication**: Claude Code MCP permissions in `.claude/settings.local.json`
- **Rate limiting**: 500 RPM global, per-tool limits defined in `mcp/rate_limiter.py`

## File Permissions

| Path | Recommended Permissions | Notes |
|------|------------------------|-------|
| `database/eros_sd_main.db` | 640 | Read/write owner, read group |
| `database/google_sheets_sync/credentials/` | 700 | Owner only |
| `mcp/` | 755 | Executable owner, read others |
| `.claude/settings.local.json` | 600 | Owner only |

## Audit Logging

All MCP tool calls are logged via the `@track_request` decorator in `mcp/metrics.py`.

**Logged Information**:
- Tool name
- Execution time
- Success/failure status
- Error type (if failure)
- Request timestamp

**Log Location**: Standard Python logging (configure via `python/logging_config.py`)

## Input Validation

All agents validate inputs per the Security Constraints in their `.md` files:

- `creator_id`: Alphanumeric + underscore/hyphen, max 100 chars
- `send_type_key`: Alphanumeric + underscore/hyphen, max 50 chars
- SQL inputs: Always parameterized via MCP tools (never raw SQL)

## Incident Response

### For Security Incidents:

1. **Immediate**: Rotate affected credentials
2. **Within 1 hour**: Check audit logs for unauthorized access
3. **Within 4 hours**: Document in `INCIDENT_LOG.md` (create if needed)
4. **Within 24 hours**: Notify stakeholders
5. **Within 1 week**: Complete post-mortem

### Credential Rotation Log

Maintain in `docs/CREDENTIAL_ROTATION_LOG.md`:

```markdown
## Credential Rotation Log

| Date | Credential | Operator | Reason | Notes |
|------|------------|----------|--------|-------|
| 2025-12-20 | Google Sheets API | @operator | Annual rotation | Completed successfully |
```

## Security Contacts

- **Security Issues**: [security contact]
- **Credential Rotation**: [devops contact]
- **Incident Response**: [on-call contact]
