# EROS MCP Server Monitoring Setup

This document describes the monitoring infrastructure for the EROS MCP Server, including metrics collection, dashboards, alerting, and SLI/SLO definitions.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Metrics Collection](#metrics-collection)
- [Grafana Dashboard Setup](#grafana-dashboard-setup)
- [Alert Configuration](#alert-configuration)
- [Key Metrics Reference](#key-metrics-reference)
- [SLI/SLO Definitions](#slislo-definitions)
- [Troubleshooting](#troubleshooting)

---

## Overview

The EROS MCP Server exposes Prometheus metrics on port 9090 (configurable via `EROS_METRICS_PORT`). These metrics provide visibility into:

- Request rates and latency (p50/p95/p99)
- Error rates by tool and error type
- Database connection pool status
- Slow query detection
- Active request tracking

## Implementation Status

### Current State

**Documentation**: ✅ COMPLETE
- All 36+ Prometheus metrics defined
- 24 alert rules documented
- SLI/SLO targets established (99.9% availability, p95 <500ms)
- Grafana dashboard panels specified

**Infrastructure**: ⚠️ REQUIRES DEPLOYMENT
- Prometheus server: NOT DEPLOYED
- Grafana: NOT DEPLOYED
- AlertManager: NOT DEPLOYED

### Quick Start Deployment

For rapid deployment using Docker Compose:

#### 1. Create Monitoring Directory Structure

```bash
mkdir -p /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring
mkdir -p grafana-dashboards
```

#### 2. Create docker-compose.yml

Save as `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring/docker-compose.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: eros-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    restart: unless-stopped
    networks:
      - eros-monitoring

  grafana:
    image: grafana/grafana:10.2.2
    container_name: eros-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=eros_admin_changeme
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana-dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus
    restart: unless-stopped
    networks:
      - eros-monitoring

  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: eros-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager-data:/alertmanager
    restart: unless-stopped
    networks:
      - eros-monitoring

volumes:
  prometheus-data:
  grafana-data:
  alertmanager-data:

networks:
  eros-monitoring:
    driver: bridge
```

#### 3. Create Prometheus Configuration

Save as `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'eros-mcp-server'
    static_configs:
      - targets: ['host.docker.internal:9090']
        labels:
          environment: 'production'
          service: 'eros-mcp-server'
```

#### 4. Create AlertManager Configuration

Save as `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'eros-ops-team'

receivers:
  - name: 'eros-ops-team'
    email_configs:
      - to: 'ops-team@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alertmanager@example.com'
        auth_password: 'changeme'
```

#### 5. Start Monitoring Stack

```bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring
docker-compose up -d

# Verify services
docker-compose ps

# Check logs
docker-compose logs -f
```

#### 6. Access Monitoring Services

- **Grafana**: http://localhost:3000
  - Username: `admin`
  - Password: `eros_admin_changeme` (change immediately)

- **Prometheus**: http://localhost:9090
  - Query interface for metrics exploration

- **AlertManager**: http://localhost:9093
  - Alert status and silencing

#### 7. Import Grafana Dashboard

1. Login to Grafana (http://localhost:3000)
2. Navigate to **Dashboards** → **Import**
3. Upload the dashboard JSON from `grafana-dashboards/eros-mcp-dashboard.json`
4. Select the Prometheus datasource
5. Click **Import**

---

## Architecture

```
+------------------+     +------------------+     +------------------+
|  EROS MCP Server |---->|    Prometheus    |---->|     Grafana      |
|  (port 9090)     |     |  (scrape metrics)|     |   (dashboards)   |
+------------------+     +------------------+     +------------------+
                                   |
                                   v
                         +------------------+
                         |   AlertManager   |
                         |  (notifications) |
                         +------------------+
```

## Prerequisites

1. **Prometheus** (v2.45+) configured to scrape the MCP server
2. **Grafana** (v10.0+) with Prometheus datasource configured
3. **AlertManager** (v0.26+) for alert routing and notifications
4. **prometheus_client** Python package installed (`pip install prometheus-client`)

## Metrics Collection

### Enabling Metrics

Metrics are enabled by default. To control metrics collection:

```bash
# Enable metrics (default)
export EROS_METRICS_ENABLED=true

# Disable metrics
export EROS_METRICS_ENABLED=false

# Change metrics port (default: 9090)
export EROS_METRICS_PORT=9091
```

### Prometheus Scrape Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'eros-mcp'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /
```

For Kubernetes deployments:

```yaml
scrape_configs:
  - job_name: 'eros-mcp'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: eros-mcp
        action: keep
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        regex: "9090"
        action: keep
```

### Verifying Metrics Endpoint

```bash
# Check metrics are being exposed
curl -s http://localhost:9090/metrics | head -20

# Check specific metric
curl -s http://localhost:9090/metrics | grep mcp_requests_total
```

---

## Grafana Dashboard Setup

### Importing the Dashboard

1. Navigate to Grafana > Dashboards > Import
2. Upload `monitoring/dashboards/eros_mcp.json` or paste the JSON content
3. Select your Prometheus datasource when prompted
4. Click "Import"

Alternatively, via Grafana API:

```bash
# Import dashboard via API
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d @monitoring/dashboards/eros_mcp.json \
  http://localhost:3000/api/dashboards/import
```

### Dashboard Panels

The dashboard includes the following sections:

#### Request Overview
- **Request Rate by Tool**: Requests per second for each MCP tool
- **Request Latency Percentiles**: p50/p95/p99 latency over time
- **Total Requests (24h)**: Daily request volume
- **Error Rate (5m)**: Rolling error rate percentage
- **P95 Latency (5m)**: Current p95 latency
- **Active Requests**: Currently processing requests

#### Error Analysis
- **Errors by Tool and Type**: Stacked bar chart of errors
- **Validation Errors by Tool and Field**: Input validation failures
- **Error Rate by Key Tool**: Focused view on critical tools

#### Database Performance
- **DB Pool - In Use**: Gauge showing connections in use
- **DB Pool - Available**: Gauge showing free connections
- **DB Pool - Overflow**: Count of overflow connections
- **Failed DB Connections**: Connection failure counter
- **Query Latency by Type**: p50/p95/p99 query latency
- **Slow Queries by Tool**: Queries exceeding 500ms threshold

#### Key Tools Deep Dive
- **get_creator_profile**: Request rate and latency
- **get_top_captions**: Request rate and latency
- **save_schedule**: Request rate and latency
- **P95 Latency Comparison**: Side-by-side latency comparison

### Dashboard Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `datasource` | Prometheus datasource | Auto-detected |

---

## Dashboard Export Files

### EROS MCP Server Dashboard JSON

Save as `/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/monitoring/grafana-dashboards/eros-mcp-dashboard.json`:

```json
{
  "dashboard": {
    "title": "EROS MCP Server",
    "uid": "eros-mcp-001",
    "timezone": "browser",
    "schemaVersion": 30,
    "version": 1,
    "refresh": "10s",
    "panels": [
      {
        "id": 1,
        "title": "Request Rate by Tool",
        "type": "graph",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(eros_mcp_requests_total[5m])",
            "legendFormat": "{{tool_name}}"
          }
        ]
      },
      {
        "id": 2,
        "title": "Error Rate",
        "type": "graph",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(eros_mcp_errors_total[5m])",
            "legendFormat": "{{error_type}}"
          }
        ]
      },
      {
        "id": 3,
        "title": "P95 Latency",
        "type": "graph",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(eros_mcp_request_duration_seconds_bucket[5m]))",
            "legendFormat": "{{tool_name}}"
          }
        ]
      },
      {
        "id": 4,
        "title": "Database Connection Pool",
        "type": "graph",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "eros_mcp_db_connections_active",
            "legendFormat": "Active"
          },
          {
            "expr": "eros_mcp_db_connections_idle",
            "legendFormat": "Idle"
          }
        ]
      },
      {
        "id": 5,
        "title": "Active Requests",
        "type": "stat",
        "gridPos": {"x": 0, "y": 16, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "eros_mcp_active_requests"
          }
        ]
      },
      {
        "id": 6,
        "title": "Total Requests (24h)",
        "type": "stat",
        "gridPos": {"x": 6, "y": 16, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "increase(eros_mcp_requests_total[24h])"
          }
        ]
      },
      {
        "id": 7,
        "title": "Error Rate (5m)",
        "type": "stat",
        "gridPos": {"x": 12, "y": 16, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "rate(eros_mcp_errors_total[5m])"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 0.05, "color": "yellow"},
                {"value": 0.1, "color": "red"}
              ]
            }
          }
        }
      },
      {
        "id": 8,
        "title": "Slow Queries (>500ms)",
        "type": "stat",
        "gridPos": {"x": 18, "y": 16, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "eros_mcp_slow_queries_total"
          }
        ]
      }
    ]
  }
}
```

**Usage**:
1. Save this JSON to the `monitoring/grafana-dashboards/` directory
2. Import via Grafana UI or use the Docker Compose volume mount for auto-provisioning
3. Customize panels, thresholds, and alerts as needed

---

## Alert Configuration

### Importing Alert Rules

Add the alert rules to your Prometheus configuration:

```yaml
# prometheus.yml
rule_files:
  - "/path/to/monitoring/alerts/eros_alerts.yaml"
```

Or use Prometheus Operator:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: eros-mcp-alerts
  namespace: monitoring
spec:
  groups: <contents of eros_alerts.yaml>
```

### Alert Groups

#### eros_mcp_requests
| Alert | Severity | Threshold | Duration |
|-------|----------|-----------|----------|
| EROSMCPHighErrorRate | critical | >5% errors | 5m |
| EROSMCPErrorRateWarning | warning | >1% errors | 10m |
| EROSMCPHighLatency | critical | p95 >500ms | 5m |
| EROSMCPLatencyWarning | warning | p95 >300ms | 10m |
| EROSMCPExtremeLatency | critical | p99 >2s | 5m |
| EROSMCPToolHighErrorRate | warning | >10% per tool | 5m |
| EROSMCPNoRequests | critical | 0 requests | 10m |

#### eros_mcp_database
| Alert | Severity | Threshold | Duration |
|-------|----------|-----------|----------|
| EROSMCPDBPoolExhaustionWarning | warning | <20% available | 5m |
| EROSMCPDBPoolExhausted | critical | 0 available | 1m |
| EROSMCPDBPoolOverflow | warning | >0 overflow | 5m |
| EROSMCPSlowQueriesHigh | warning | >0.1/s slow queries | 5m |
| EROSMCPSlowQuerySpike | warning | >10 in 5m | immediate |
| EROSMCPQueryLatencyHigh | warning | p95 >500ms | 5m |
| EROSMCPDBConnectionFailures | warning | any failures | 5m |

#### eros_mcp_key_tools
| Alert | Severity | Threshold | Duration |
|-------|----------|-----------|----------|
| EROSMCPCreatorProfileSlow | warning | p95 >500ms | 5m |
| EROSMCPTopCaptionsSlow | warning | p95 >1s | 5m |
| EROSMCPSaveScheduleFailures | critical | any failures | 5m |

#### eros_mcp_slo
| Alert | Severity | Threshold | Duration |
|-------|----------|-----------|----------|
| EROSMCPAvailabilitySLOBreach | critical | <99.9% over 30m | 5m |
| EROSMCPLatencySLOBreach | critical | p95 >500ms over 30m | 10m |
| EROSMCPErrorBudgetFastBurn | critical | 14.4x burn rate | 2m |
| EROSMCPErrorBudgetSlowBurn | warning | 6x burn rate | 15m |

### AlertManager Notification Configuration

Example AlertManager configuration for routing EROS alerts:

```yaml
# alertmanager.yml
route:
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        service: eros-mcp
        severity: critical
      receiver: 'eros-critical'
      continue: true
    - match:
        service: eros-mcp
        severity: warning
      receiver: 'eros-warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'team@example.com'

  - name: 'eros-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#eros-alerts-critical'
        title: '{{ .Status | toUpper }}: {{ .Annotations.summary }}'
        text: '{{ .Annotations.description }}'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        description: '{{ .Annotations.summary }}'

  - name: 'eros-warning'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#eros-alerts'
        title: '{{ .Status | toUpper }}: {{ .Annotations.summary }}'
        text: '{{ .Annotations.description }}'
```

---

## Key Metrics Reference

### Request Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_requests_total` | Counter | tool, status | Total request count |
| `mcp_request_latency_seconds` | Histogram | tool | Request latency distribution |
| `mcp_active_requests` | Gauge | tool | Currently active requests |
| `mcp_requests_in_progress` | Gauge | - | Total in-flight requests |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_errors_total` | Counter | tool, error_type | Error count by type |
| `mcp_validation_errors_total` | Counter | tool, field | Validation failures |

### Database Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_db_pool_size` | Gauge | - | Configured pool size |
| `mcp_db_pool_available` | Gauge | - | Available connections |
| `mcp_db_pool_in_use` | Gauge | - | Connections in use |
| `mcp_db_pool_overflow` | Gauge | - | Overflow connections |
| `mcp_db_connections_created_total` | Counter | - | Total connections created |
| `mcp_db_connections_recycled_total` | Counter | - | Connections recycled |
| `mcp_db_connections_failed_total` | Counter | - | Failed connection attempts |
| `mcp_query_latency_seconds` | Histogram | query_type | Query latency distribution |
| `mcp_queries_total` | Counter | query_type, status | Total query count |
| `mcp_slow_queries_total` | Counter | tool | Queries exceeding 500ms |

### Server Info

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_server_info` | Info | version, name, protocol_version | Server metadata |

---

## SLI/SLO Definitions

### Service Level Indicators (SLIs)

#### Availability SLI
```
availability = 1 - (error_requests / total_requests)
```

Measured using:
```promql
1 - (
  sum(rate(mcp_requests_total{status="error"}[window]))
  /
  sum(rate(mcp_requests_total[window]))
)
```

#### Latency SLI
```
latency_sli = requests_under_threshold / total_requests
```

Measured using P95 latency:
```promql
histogram_quantile(0.95,
  sum(rate(mcp_request_latency_seconds_bucket[window])) by (le)
)
```

### Service Level Objectives (SLOs)

| SLO | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| Availability | 99.9% | 30 days rolling | 43.2 minutes/month |
| P95 Latency | <500ms | 30 days rolling | - |
| P99 Latency | <2s | 30 days rolling | - |

### Error Budget Calculations

Monthly error budget for 99.9% availability:
- Total minutes: 30 * 24 * 60 = 43,200 minutes
- Error budget: 43,200 * 0.001 = 43.2 minutes

Burn rate alerts:
- **Fast burn (14.4x)**: Will exhaust budget in ~2 days
- **Slow burn (6x)**: Will exhaust budget in ~5 days

### SLO Dashboard Queries

Add these to a dedicated SLO dashboard:

```promql
# 30-day availability
1 - (
  sum(increase(mcp_requests_total{status="error"}[30d]))
  /
  sum(increase(mcp_requests_total[30d]))
)

# Remaining error budget (percentage)
1 - (
  (sum(increase(mcp_requests_total{status="error"}[30d])) / sum(increase(mcp_requests_total[30d])))
  /
  0.001
)

# Error budget burn rate (requests/hour)
sum(rate(mcp_requests_total{status="error"}[1h])) * 3600
```

---

## Troubleshooting

### Metrics Not Available

1. **Check if metrics are enabled:**
   ```bash
   echo $EROS_METRICS_ENABLED  # Should be "true" or unset
   ```

2. **Verify prometheus_client is installed:**
   ```bash
   pip show prometheus-client
   ```

3. **Check the metrics endpoint:**
   ```bash
   curl -v http://localhost:9090/metrics
   ```

4. **Check server logs:**
   ```bash
   grep "metrics" /var/log/eros-mcp/server.log
   ```

### High Error Rate

1. **Identify the failing tool:**
   ```promql
   topk(5, sum(rate(mcp_errors_total[5m])) by (tool, error_type))
   ```

2. **Check for specific error patterns:**
   ```promql
   sum(rate(mcp_validation_errors_total[5m])) by (tool, field)
   ```

3. **Review recent changes** that may have introduced bugs

### High Latency

1. **Identify slow tools:**
   ```promql
   topk(5, histogram_quantile(0.95, sum(rate(mcp_request_latency_seconds_bucket[5m])) by (le, tool)))
   ```

2. **Check slow query counts:**
   ```promql
   topk(5, sum(rate(mcp_slow_queries_total[5m])) by (tool))
   ```

3. **Check database pool status:**
   ```promql
   mcp_db_pool_available / mcp_db_pool_size
   ```

### Database Pool Issues

1. **Check pool utilization:**
   ```promql
   mcp_db_pool_in_use / mcp_db_pool_size
   ```

2. **Look for connection churn:**
   ```promql
   sum(rate(mcp_db_connections_created_total[5m]))
   ```

3. **Check for connection failures:**
   ```promql
   sum(rate(mcp_db_connections_failed_total[5m]))
   ```

### Useful PromQL Queries

```promql
# Request rate by tool (last 5m)
sum(rate(mcp_requests_total[5m])) by (tool)

# Success rate by tool
sum(rate(mcp_requests_total{status="success"}[5m])) by (tool)
/
sum(rate(mcp_requests_total[5m])) by (tool)

# Average latency by tool
sum(rate(mcp_request_latency_seconds_sum[5m])) by (tool)
/
sum(rate(mcp_request_latency_seconds_count[5m])) by (tool)

# Top 5 slowest tools (p95)
topk(5, histogram_quantile(0.95, sum(rate(mcp_request_latency_seconds_bucket[5m])) by (le, tool)))
```

---

## Maintenance

### Updating Dashboards

1. Make changes in Grafana UI
2. Export dashboard JSON (Settings > JSON Model)
3. Update `monitoring/dashboards/eros_mcp.json`
4. Commit changes to version control

### Updating Alerts

1. Edit `monitoring/alerts/eros_alerts.yaml`
2. Validate syntax: `promtool check rules eros_alerts.yaml`
3. Reload Prometheus: `curl -X POST http://localhost:9090/-/reload`

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-17 | Initial monitoring setup |

---

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [EROS MCP Server Documentation](/docs/README.md)
