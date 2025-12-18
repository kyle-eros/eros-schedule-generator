# Active Creator Validator - Deployment Checklist

## Pre-Deployment

### 1. Verify Installation
- [ ] Python 3.7+ is installed and accessible
- [ ] Script is executable: `chmod +x active_creator_validator.py`
- [ ] Database file exists and is readable
- [ ] Script directory is accessible from intended execution location

**Test Command**:
```bash
python3 --version
python3 active_creator_validator.py --version
ls -l eros_sd_main.db
```

### 2. Test Manual Execution
- [ ] Text output works: `python3 active_creator_validator.py --db eros_sd_main.db`
- [ ] JSON output works: `python3 active_creator_validator.py --db eros_sd_main.db --format json`
- [ ] HTML output works: `python3 active_creator_validator.py --db eros_sd_main.db --format html --output test.html`
- [ ] Verbose mode works: `python3 active_creator_validator.py --db eros_sd_main.db --verbose`
- [ ] Exit codes work correctly:
  - [ ] Exit 0 on success
  - [ ] Exit 1 on validation failure (test with `--threshold 0.99`)
  - [ ] Exit 2 on error (test with invalid database path)

**Test Commands**:
```bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database

# Test text
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db

# Test JSON
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format json | python3 -m json.tool

# Test HTML
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format html --output /tmp/test.html
open /tmp/test.html  # macOS
# or: xdg-open /tmp/test.html  # Linux

# Test exit codes
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db; echo "Exit: $?"
python3 audit/monitoring/active_creator_validator.py --db nonexistent.db; echo "Exit: $?"
```

### 3. Setup Log Directories
- [ ] Create log directory with appropriate permissions
- [ ] Test write permissions
- [ ] Setup log rotation if needed

**Setup Commands**:
```bash
# Option A: System logs (may require sudo)
sudo mkdir -p /var/log/eros
sudo chown $(whoami):$(whoami) /var/log/eros

# Option B: User logs (recommended)
mkdir -p ~/logs/eros

# Test write permissions
touch ~/logs/eros/test.log && rm ~/logs/eros/test.log && echo "Permissions OK"
```

## Deployment

### 4. Choose Deployment Type

#### Option A: Manual Execution
No additional setup required. Run as needed.

**Usage**:
```bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database
python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db
```

#### Option B: Scheduled Cron Jobs
- [ ] Test cron command manually first
- [ ] Add to crontab: `crontab -e`
- [ ] Verify cron service is running
- [ ] Test with short interval (every minute for 5 min)
- [ ] Update to production schedule
- [ ] Monitor logs for first 24 hours

**Deployment Steps**:
```bash
# 1. Test the full command manually
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database && \
  python3 audit/monitoring/active_creator_validator.py \
  --db eros_sd_main.db \
  --format json \
  --output ~/logs/eros/test_$(date +%Y%m%d_%H%M%S).json

# 2. Open crontab editor
crontab -e

# 3. Add test entry (runs every minute)
* * * * * cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database && python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format json --output ~/logs/eros/cron_test_$(date +\%Y\%m\%d_\%H\%M).json 2>&1

# 4. Wait 5 minutes, check logs
ls -lht ~/logs/eros/ | head

# 5. If successful, update to production schedule
crontab -e
# Remove test entry, add production entry:
0 3 * * * cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database && python3 audit/monitoring/active_creator_validator.py --db eros_sd_main.db --format json --output ~/logs/eros/validation_$(date +\%Y\%m\%d).json 2>&1
```

#### Option C: Service/Daemon
- [ ] Create systemd service (Linux) or launchd plist (macOS)
- [ ] Configure service parameters
- [ ] Test service start/stop
- [ ] Enable on boot if desired

### 5. Configure Threshold (if needed)
Current database has 74.19% coverage due to historical orphaned data.

**Options**:
- [ ] Use `--threshold 0.70` to match current state (recommended)
- [ ] Use default `--threshold 0.95` and accept WARNING status
- [ ] Backfill creator_id for historical messages (separate project)

**Recommendation**: Use `--threshold 0.70` until historical data backfill is complete.

## Post-Deployment

### 6. Monitoring Setup
- [ ] Configure alerting for exit code 1 (validation failure)
- [ ] Setup log aggregation if applicable
- [ ] Create dashboard for HTML reports (optional)
- [ ] Document alert response procedures

**Alert Examples**:

**Email Alert**:
```bash
# In cron job
python3 active_creator_validator.py --db eros_sd_main.db || \
  echo "EROS validation failed at $(date)" | \
  mail -s "ALERT: EROS Validation Failed" admin@example.com
```

**Slack/Discord Webhook**:
```bash
#!/bin/bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database
python3 audit/monitoring/active_creator_validator.py \
  --db eros_sd_main.db \
  --format json \
  --output /tmp/eros_validation.json

EXIT_CODE=$?
if [ $EXIT_CODE -eq 1 ]; then
    curl -X POST \
      -H 'Content-Type: application/json' \
      -d "{\"text\": \"EROS Validation Failed - Check /tmp/eros_validation.json\"}" \
      YOUR_WEBHOOK_URL
fi
```

### 7. Initial Monitoring Period
- [ ] Monitor for first 24 hours
- [ ] Verify logs are being created
- [ ] Check no unexpected errors
- [ ] Validate output format is correct
- [ ] Confirm exit codes are appropriate

**Monitoring Commands**:
```bash
# Check recent logs
ls -lht ~/logs/eros/ | head -10

# View latest JSON log
cat ~/logs/eros/$(ls -t ~/logs/eros/*.json | head -1) | python3 -m json.tool

# Check cron logs (if using cron)
# macOS:
grep CRON /var/log/system.log | tail -20
# Linux:
grep CRON /var/log/syslog | tail -20
```

### 8. Documentation Update
- [ ] Update team documentation with monitoring procedures
- [ ] Document alert response steps
- [ ] Share log locations with team
- [ ] Document threshold rationale (if changed from default)

## Validation Tests

### Smoke Test Suite
Run all these tests before considering deployment complete:

```bash
# Test 1: Basic execution
python3 active_creator_validator.py --db eros_sd_main.db
echo "Test 1 exit code: $?"

# Test 2: JSON output
python3 active_creator_validator.py --db eros_sd_main.db --format json | python3 -m json.tool > /dev/null
echo "Test 2 exit code: $?"

# Test 3: HTML output
python3 active_creator_validator.py --db eros_sd_main.db --format html --output /tmp/validation_test.html
echo "Test 3 exit code: $?"

# Test 4: Verbose mode
python3 active_creator_validator.py --db eros_sd_main.db --verbose > /dev/null
echo "Test 4 exit code: $?"

# Test 5: Custom threshold
python3 active_creator_validator.py --db eros_sd_main.db --threshold 0.70
echo "Test 5 exit code: $?"

# Test 6: Error handling (should exit 2)
python3 active_creator_validator.py --db nonexistent.db 2>&1 | grep -q "not found"
echo "Test 6 result: $?"

# Test 7: Help text
python3 active_creator_validator.py --help | grep -q "EROS"
echo "Test 7 exit code: $?"

# Test 8: Version
python3 active_creator_validator.py --version | grep -q "1.0.0"
echo "Test 8 exit code: $?"
```

**Expected Results**: All tests should exit 0 (success).

## Rollback Plan

If issues occur:

1. **Remove from cron**:
   ```bash
   crontab -e
   # Comment out or delete the validator entry
   ```

2. **Stop service** (if using systemd/launchd):
   ```bash
   # Linux
   sudo systemctl stop eros-validator

   # macOS
   launchctl unload ~/Library/LaunchAgents/com.eros.validator.plist
   ```

3. **Check logs for errors**:
   ```bash
   tail -100 ~/logs/eros/*.log
   ```

4. **Report issue** with:
   - Error messages from logs
   - Exit codes observed
   - Command that failed
   - Python version (`python3 --version`)
   - OS version (`uname -a`)

## Support Checklist

After deployment, document these for team reference:

- [ ] Log file locations
- [ ] Cron schedule (if applicable)
- [ ] Threshold setting and rationale
- [ ] Alert recipients/channels
- [ ] Response procedures for alerts
- [ ] Contact for validator issues
- [ ] Location of this documentation

## Deployment Sign-Off

- [ ] All pre-deployment tests passed
- [ ] Deployment type chosen and configured
- [ ] Logs are being generated correctly
- [ ] Alerts are configured (if applicable)
- [ ] Team is notified of deployment
- [ ] Documentation is updated

**Deployed By**: ___________________

**Date**: ___________________

**Deployment Type**: [ ] Manual [ ] Cron [ ] Service

**Schedule** (if applicable): ___________________

**Log Location**: ___________________

**Threshold**: ___________________

**Alert Configuration**: ___________________

**Notes**: ___________________
