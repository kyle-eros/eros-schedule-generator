# EROS MCP Server - Deployment Guide

**Version**: 2.2.0
**Last Updated**: 2025-12-17

This guide provides step-by-step instructions for deploying the EROS database MCP server in production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Configuration](#configuration)
3. [Systemd Deployment (Linux)](#systemd-deployment-linux)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Security Hardening](#security-hardening)
7. [Monitoring Setup](#monitoring-setup)
8. [Health Checks](#health-checks)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, Debian 11+) or macOS
- **Python**: 3.11 or higher
- **Memory**: 512MB minimum, 2GB recommended
- **Disk**: 500MB for database, 1GB total recommended
- **Network**: Outbound access for Prometheus metrics (port 9090)

### Python Dependencies

```bash
# Core dependencies
pip install sqlite3  # Included in Python standard library
pip install prometheus-client  # Optional, for metrics

# Development dependencies (testing only)
pip install pytest pytest-cov hypothesis
```

### Database Setup

Ensure the EROS database file exists and is accessible:

```bash
# Check database exists
ls -lh /path/to/database/eros_sd_main.db

# Check database permissions
chmod 0440 /path/to/database/eros_sd_main.db

# Verify database integrity
sqlite3 /path/to/database/eros_sd_main.db "PRAGMA integrity_check;"
```

---

## Configuration

### Environment Variables

The MCP server is configured via environment variables:

```bash
# Database Configuration
export EROS_DB_PATH="/var/lib/eros/eros_sd_main.db"  # Database file location

# Connection Pool Configuration
export EROS_DB_POOL_SIZE=10           # Base connection pool size
export EROS_DB_POOL_OVERFLOW=5        # Max overflow connections
export EROS_DB_POOL_TIMEOUT=30.0      # Connection checkout timeout (seconds)
export EROS_DB_CONN_MAX_AGE=300       # Connection max age (seconds, 5 minutes)

# Logging Configuration
export EROS_LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR
export EROS_LOG_FORMAT=json           # json or text
export EROS_SLOW_QUERY_MS=500         # Slow query threshold (milliseconds)

# Metrics Configuration
export EROS_METRICS_ENABLED=true      # Enable/disable Prometheus metrics
export EROS_METRICS_PORT=9090         # Prometheus HTTP endpoint port
```

### Configuration File (Optional)

Create `/etc/eros-mcp/config.env`:

```bash
# /etc/eros-mcp/config.env
EROS_DB_PATH=/var/lib/eros/eros_sd_main.db
EROS_LOG_LEVEL=INFO
EROS_LOG_FORMAT=json
EROS_METRICS_ENABLED=true
EROS_METRICS_PORT=9090
EROS_DB_POOL_SIZE=10
EROS_DB_POOL_OVERFLOW=5
```

---

## Systemd Deployment (Linux)

### Installation Steps

**1. Create Service User**

```bash
# Create dedicated system user
sudo useradd -r -s /bin/false eros

# Create directories
sudo mkdir -p /opt/eros-mcp
sudo mkdir -p /var/lib/eros
sudo mkdir -p /var/log/eros
sudo mkdir -p /etc/eros-mcp

# Set ownership
sudo chown -R eros:eros /opt/eros-mcp
sudo chown -R eros:eros /var/lib/eros
sudo chown -R eros:eros /var/log/eros
sudo chown -R eros:eros /etc/eros-mcp
```

**2. Install Application**

```bash
# Copy application files
sudo cp -r mcp/ /opt/eros-mcp/
sudo cp -r python/ /opt/eros-mcp/
sudo cp database/eros_sd_main.db /var/lib/eros/

# Set permissions
sudo chown -R eros:eros /opt/eros-mcp
sudo chmod -R 0750 /opt/eros-mcp

# Database should be read-only
sudo chmod 0440 /var/lib/eros/eros_sd_main.db
sudo chown eros:eros /var/lib/eros/eros_sd_main.db
```

**3. Create Systemd Service**

```bash
sudo nano /etc/systemd/system/eros-mcp.service
```

```ini
[Unit]
Description=EROS MCP Database Server
Documentation=https://github.com/your-org/eros-mcp
After=network.target

[Service]
Type=simple
User=eros
Group=eros
WorkingDirectory=/opt/eros-mcp

# Environment configuration
EnvironmentFile=/etc/eros-mcp/config.env

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/eros

# Resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=200%

# Execution
ExecStart=/usr/bin/python3 -m mcp.server
ExecReload=/bin/kill -HUP $MAINPID

# Restart policy
Restart=on-failure
RestartSec=5s
StartLimitInterval=0

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=eros-mcp

[Install]
WantedBy=multi-user.target
```

**4. Enable and Start Service**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable eros-mcp

# Start service
sudo systemctl start eros-mcp

# Check status
sudo systemctl status eros-mcp

# View logs
sudo journalctl -u eros-mcp -f
```

### Service Management

```bash
# Start service
sudo systemctl start eros-mcp

# Stop service
sudo systemctl stop eros-mcp

# Restart service
sudo systemctl restart eros-mcp

# View status
sudo systemctl status eros-mcp

# View logs (tail)
sudo journalctl -u eros-mcp -f

# View logs (last 100 lines)
sudo journalctl -u eros-mcp -n 100

# View logs (since 1 hour ago)
sudo journalctl -u eros-mcp --since "1 hour ago"
```

---

## Docker Deployment

### Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (if you have one)
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir prometheus-client

# Copy application files
COPY mcp/ ./mcp/
COPY python/ ./python/
COPY database/ ./database/

# Create non-root user
RUN useradd -r -u 1000 eros && \
    chown -R eros:eros /app

# Switch to non-root user
USER eros

# Expose Prometheus metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/metrics || exit 1

# Run server
CMD ["python", "-m", "mcp.server"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  eros-mcp:
    build: .
    container_name: eros-mcp-server
    image: eros-mcp:2.2.0

    environment:
      - EROS_DB_PATH=/data/eros_sd_main.db
      - EROS_LOG_LEVEL=INFO
      - EROS_LOG_FORMAT=json
      - EROS_METRICS_ENABLED=true
      - EROS_METRICS_PORT=9090
      - EROS_DB_POOL_SIZE=10
      - EROS_DB_POOL_OVERFLOW=5

    volumes:
      # Mount database as read-only
      - ./database:/data:ro

    ports:
      - "9090:9090"  # Prometheus metrics

    restart: unless-stopped

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
        labels: "service=eros-mcp"
```

### Building and Running

```bash
# Build image
docker build -t eros-mcp:2.2.0 .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Stop
docker-compose down

# Restart
docker-compose restart
```

### Docker Run (without compose)

```bash
docker run -d \
  --name eros-mcp \
  -p 9090:9090 \
  -v $(pwd)/database:/data:ro \
  -e EROS_DB_PATH=/data/eros_sd_main.db \
  -e EROS_LOG_LEVEL=INFO \
  -e EROS_METRICS_ENABLED=true \
  --restart unless-stopped \
  eros-mcp:2.2.0
```

---

## Kubernetes Deployment

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: eros-mcp-config
  namespace: production
data:
  EROS_LOG_LEVEL: "INFO"
  EROS_LOG_FORMAT: "json"
  EROS_METRICS_ENABLED: "true"
  EROS_METRICS_PORT: "9090"
  EROS_DB_POOL_SIZE: "10"
  EROS_DB_POOL_OVERFLOW: "5"
```

### PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: eros-db-pvc
  namespace: production
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eros-mcp-server
  namespace: production
  labels:
    app: eros-mcp
    version: "2.2.0"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: eros-mcp
  template:
    metadata:
      labels:
        app: eros-mcp
        version: "2.2.0"
    spec:
      containers:
      - name: eros-mcp
        image: eros-mcp:2.2.0
        imagePullPolicy: IfNotPresent

        ports:
        - containerPort: 9090
          name: metrics
          protocol: TCP

        env:
        - name: EROS_DB_PATH
          value: /data/eros_sd_main.db

        envFrom:
        - configMapRef:
            name: eros-mcp-config

        volumeMounts:
        - name: database
          mountPath: /data
          readOnly: true

        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"

        livenessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3

      volumes:
      - name: database
        persistentVolumeClaim:
          claimName: eros-db-pvc

      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: eros-mcp-metrics
  namespace: production
  labels:
    app: eros-mcp
spec:
  type: ClusterIP
  selector:
    app: eros-mcp
  ports:
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: metrics
```

### ServiceMonitor (for Prometheus Operator)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: eros-mcp
  namespace: production
  labels:
    app: eros-mcp
spec:
  selector:
    matchLabels:
      app: eros-mcp
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
```

### Deploying to Kubernetes

```bash
# Create namespace
kubectl create namespace production

# Apply ConfigMap
kubectl apply -f configmap.yaml

# Apply PVC
kubectl apply -f pvc.yaml

# Apply Deployment
kubectl apply -f deployment.yaml

# Apply Service
kubectl apply -f service.yaml

# Apply ServiceMonitor (if using Prometheus Operator)
kubectl apply -f servicemonitor.yaml

# Check deployment
kubectl get all -n production -l app=eros-mcp

# View logs
kubectl logs -n production -l app=eros-mcp -f

# Port forward for local testing
kubectl port-forward -n production svc/eros-mcp-metrics 9090:9090
```

---

## Security Hardening

### File Permissions

```bash
# Application files (read-only for service user)
sudo chown -R root:eros /opt/eros-mcp
sudo chmod -R 0750 /opt/eros-mcp

# Database file (read-only)
sudo chown eros:eros /var/lib/eros/eros_sd_main.db
sudo chmod 0440 /var/lib/eros/eros_sd_main.db

# Log directory (write access for service user)
sudo chown -R eros:eros /var/log/eros
sudo chmod 0750 /var/log/eros
```

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow from 10.0.1.0/24 to any port 9090 proto tcp comment 'Prometheus metrics'
sudo ufw deny 9090

# iptables
sudo iptables -A INPUT -s 10.0.1.0/24 -p tcp --dport 9090 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9090 -j DROP
```

### SELinux Configuration (RHEL/CentOS)

```bash
# Create SELinux policy
sudo semanage fcontext -a -t bin_t "/opt/eros-mcp(/.*)?"
sudo restorecon -Rv /opt/eros-mcp

# Allow network access
sudo setsebool -P nis_enabled 1
```

### AppArmor Profile (Ubuntu/Debian)

Create `/etc/apparmor.d/opt.eros-mcp.server`:

```
#include <tunables/global>

/opt/eros-mcp/mcp/server.py {
  #include <abstractions/base>
  #include <abstractions/python>

  # Application files
  /opt/eros-mcp/** r,

  # Database (read-only)
  /var/lib/eros/*.db r,

  # Logs (write)
  /var/log/eros/** w,

  # Python interpreter
  /usr/bin/python3* rix,

  # Deny everything else
  deny /** w,
}
```

Load the profile:

```bash
sudo apparmor_parser -r /etc/apparmor.d/opt.eros-mcp.server
```

---

## Monitoring Setup

### Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'eros-mcp'
    static_configs:
      - targets: ['localhost:9090']  # Or your server IP
    scrape_interval: 15s
    scrape_timeout: 10s
```

Reload Prometheus:

```bash
curl -X POST http://localhost:9090/-/reload
```

### Grafana Dashboard

Import the following dashboard JSON or create manually:

**Key Panels:**

1. **Request Rate**
   - Query: `rate(mcp_requests_total{status="success"}[5m])`
   - Type: Graph

2. **Error Rate**
   - Query: `rate(mcp_errors_total[5m])`
   - Type: Graph

3. **P95 Latency**
   - Query: `histogram_quantile(0.95, rate(mcp_request_latency_seconds_bucket[5m]))`
   - Type: Graph

4. **Connection Pool Utilization**
   - Query: `mcp_db_pool_in_use / mcp_db_pool_size * 100`
   - Type: Gauge

5. **Active Requests**
   - Query: `mcp_requests_in_progress`
   - Type: Gauge

### Alerting Rules

Create `alerts.yml`:

```yaml
groups:
  - name: eros_mcp_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(mcp_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in EROS MCP server"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"

      - alert: SlowQueries
        expr: rate(mcp_slow_queries_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Excessive slow queries detected"
          description: "Slow query rate is {{ $value }} queries/second"

      - alert: PoolExhaustion
        expr: mcp_db_pool_in_use / mcp_db_pool_size > 0.8
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Connection pool near capacity"
          description: "Pool utilization is {{ $value | humanizePercentage }} (threshold: 80%)"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(mcp_request_latency_seconds_bucket[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High request latency detected"
          description: "P95 latency is {{ $value }}s (threshold: 1s)"

      - alert: ServiceDown
        expr: up{job="eros-mcp"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "EROS MCP server is down"
          description: "Service has been down for more than 1 minute"
```

---

## Health Checks

### Health Check Endpoint

The server provides a `health` JSON-RPC method:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "health"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "healthy",
    "version": "2.2.0",
    "protocol_version": "2024-11-05",
    "database": "connected",
    "pool_health": {
      "status": "healthy",
      "utilization": 25.5,
      "stats": {
        "pool_size": 10,
        "available": 8,
        "in_use": 2
      }
    },
    "tools_registered": 17,
    "timestamp": "2025-12-18T01:00:00Z"
  }
}
```

### Monitoring Health

**Docker Health Check:**
```bash
docker exec eros-mcp curl -f http://localhost:9090/metrics || exit 1
```

**Kubernetes Health Check:**
```yaml
livenessProbe:
  httpGet:
    path: /metrics
    port: 9090
  initialDelaySeconds: 10
  periodSeconds: 30
```

**Systemd Health Check:**
```bash
# Add to systemd service
ExecHealthCheck=/bin/sh -c 'curl -f http://localhost:9090/metrics || exit 1'
```

---

## Backup & Recovery

### Database Backup

**Backup Script (`/opt/eros-mcp/backup.sh`):**

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/eros"
DB_PATH="/var/lib/eros/eros_sd_main.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/eros_sd_main_${TIMESTAMP}.db"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Backup database (with integrity check)
sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

# Verify backup
sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" > /dev/null

# Compress backup
gzip "${BACKUP_FILE}"

# Remove backups older than 30 days
find "${BACKUP_DIR}" -name "eros_sd_main_*.db.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

**Automated Backups (Cron):**

```bash
# Add to crontab
crontab -e

# Backup daily at 2 AM
0 2 * * * /opt/eros-mcp/backup.sh >> /var/log/eros/backup.log 2>&1
```

### Database Restore

```bash
#!/bin/bash
set -euo pipefail

BACKUP_FILE="$1"
DB_PATH="/var/lib/eros/eros_sd_main.db"

# Validate backup exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Stop service
sudo systemctl stop eros-mcp

# Create backup of current database
cp "${DB_PATH}" "${DB_PATH}.pre-restore.$(date +%Y%m%d_%H%M%S)"

# Restore from backup
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    gunzip -c "${BACKUP_FILE}" > "${DB_PATH}"
else
    cp "${BACKUP_FILE}" "${DB_PATH}"
fi

# Verify restored database
sqlite3 "${DB_PATH}" "PRAGMA integrity_check;"

# Set permissions
sudo chown eros:eros "${DB_PATH}"
sudo chmod 0440 "${DB_PATH}"

# Start service
sudo systemctl start eros-mcp

echo "Restore completed from: ${BACKUP_FILE}"
```

### Disaster Recovery Plan

**1. Database Corruption**
```bash
# Detect corruption
sqlite3 /var/lib/eros/eros_sd_main.db "PRAGMA integrity_check;"

# Restore from latest backup
sudo /opt/eros-mcp/restore.sh /var/backups/eros/latest.db.gz
```

**2. Service Failure**
```bash
# Check service status
sudo systemctl status eros-mcp

# View logs
sudo journalctl -u eros-mcp -n 100

# Restart service
sudo systemctl restart eros-mcp
```

**3. Complete System Failure**
```bash
# Prerequisites:
# - Latest database backup
# - Configuration files backup
# - Application code backup

# Restore on new system
1. Install OS dependencies
2. Create service user
3. Restore application files
4. Restore database
5. Restore configuration
6. Start service
```

---

## Troubleshooting

### Common Issues

**1. Service Won't Start**

```bash
# Check service status
sudo systemctl status eros-mcp

# View logs
sudo journalctl -u eros-mcp -n 100

# Common causes:
# - Database path incorrect
# - Database file not readable
# - Port 9090 already in use
# - Missing Python dependencies
```

**2. Database Connection Errors**

```bash
# Verify database exists
ls -l /var/lib/eros/eros_sd_main.db

# Check permissions
sudo -u eros test -r /var/lib/eros/eros_sd_main.db && echo "OK" || echo "FAIL"

# Verify database integrity
sqlite3 /var/lib/eros/eros_sd_main.db "PRAGMA integrity_check;"
```

**3. High Memory Usage**

```bash
# Check memory usage
ps aux | grep mcp.server

# Reduce pool size
export EROS_DB_POOL_SIZE=5
export EROS_DB_POOL_OVERFLOW=2

# Restart service
sudo systemctl restart eros-mcp
```

**4. Slow Queries**

```bash
# Check slow query metrics
curl http://localhost:9090/metrics | grep slow_queries

# View slow query logs
sudo journalctl -u eros-mcp | grep "Slow response"

# Increase threshold
export EROS_SLOW_QUERY_MS=1000
```

**5. Port Already in Use**

```bash
# Check what's using port 9090
sudo lsof -i :9090

# Change metrics port
export EROS_METRICS_PORT=9091

# Restart service
sudo systemctl restart eros-mcp
```

### Debug Mode

Enable debug logging:

```bash
# Set debug level
export EROS_LOG_LEVEL=DEBUG

# View detailed logs
sudo journalctl -u eros-mcp -f
```

### Logs to Check

```bash
# Service logs (systemd)
sudo journalctl -u eros-mcp -f

# Application logs (if file logging configured)
tail -f /var/log/eros/eros-mcp.log

# Docker logs
docker logs -f eros-mcp

# Kubernetes logs
kubectl logs -f -n production -l app=eros-mcp
```

---

## Support & Contact

For issues, questions, or contributions:

- GitHub Issues: https://github.com/your-org/eros-mcp/issues
- Documentation: https://docs.eros-mcp.com
- Email: support@eros-mcp.com

---

**End of Deployment Guide**

Version: 2.2.0
Last Updated: 2025-12-17
