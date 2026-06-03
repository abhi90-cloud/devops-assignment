# Backup & Restore Guide — AI Sentiment Analysis Platform

> **Repository:** https://github.com/abhi90-cloud/devops-assignment
> **Production URL:** https://ai-backend.astrodirectory.in

---

## Table of Contents

1. [Backup Strategy Overview](#backup-strategy-overview)
2. [Backup Objectives](#backup-objectives)
3. [Backup Scope](#backup-scope)
4. [Backup Schedule and Retention](#backup-schedule-and-retention)
5. [PostgreSQL Backup](#postgresql-backup)
6. [Redis Backup](#redis-backup)
7. [Configuration Backup](#configuration-backup)
8. [Backup Storage Structure](#backup-storage-structure)
9. [Cron Job Setup](#cron-job-setup)
10. [Manual Backup Procedure](#manual-backup-procedure)
11. [Restore Procedures](#restore-procedures)
12. [Disaster Recovery](#disaster-recovery)
13. [Backup Validation](#backup-validation)
14. [Recovery Testing](#recovery-testing)
15. [Monitoring Backup Success](#monitoring-backup-success)
16. [Troubleshooting](#troubleshooting)

---

## Backup Strategy Overview

The backup strategy for the AI Sentiment Analysis Platform follows a layered approach covering the data layer (PostgreSQL), cache layer (Redis RDB snapshots), and configuration layer (Docker Compose files, NGINX configs, environment files). All backups are compressed and stored locally on the EC2 instance with an optional S3 offload for disaster recovery.

Backups run automatically via cron at 02:00 UTC daily with a 7-day local retention policy. Each backup is verified with SHA-256 checksums to detect corruption.

---

## Backup Objectives

| Objective | Target | Description |
|-----------|--------|-------------|
| Recovery Time Objective (RTO) | 30 minutes | Maximum acceptable time to restore service after a failure |
| Recovery Point Objective (RPO) | 24 hours | Maximum acceptable data loss (one day's worth of analysis results) |
| Backup Success Rate | 99.9% | Automated alerts fire if any backup fails |
| Backup Integrity | 100% | Every backup is checksum-verified before retention |

**Business Continuity Rationale:** The platform processes sentiment analysis requests. Data loss of up to 24 hours is acceptable since analysis results can be recomputed on demand from client-side data. A 30-minute RTO ensures the service can be restored within a single on-call response window.

---

## Backup Scope

| Component | What Is Backed Up | Priority |
|-----------|------------------|----------|
| PostgreSQL | Full database dump (all tables, schemas, sequences) | Critical |
| Redis | RDB snapshot (`.rdb` file) | High |
| Docker Compose | `docker-compose.yml`, `docker-compose.override.yml` | Critical |
| Environment Files | `.env` (encrypted) | Critical |
| NGINX Config | `nginx/conf.d/`, `nginx/nginx.conf` | High |
| Prometheus Config | `prometheus/prometheus.yml`, alert rules | Medium |
| Grafana Dashboards | Exported JSON dashboard definitions | Medium |
| Let's Encrypt Certs | `/etc/letsencrypt/` | High |

---

## Backup Schedule and Retention

### Schedule

| Backup Type | Schedule | Retention |
|-------------|----------|-----------|
| Full PostgreSQL dump | Daily at 02:00 UTC | 7 days |
| Redis RDB snapshot | Daily at 02:15 UTC | 7 days |
| Configuration bundle | Daily at 02:30 UTC | 14 days |
| Let's Encrypt certs | Daily at 02:45 UTC | 14 days |
| Weekly consolidated | Every Sunday at 03:00 UTC | 4 weeks |

### Retention Policy

```
/opt/backups/
├── daily/          # 7 most recent daily backups
├── weekly/         # 4 most recent weekly backups
└── configs/        # 14 most recent config backups
```

Backups older than their retention period are automatically pruned by the backup script.

---

## PostgreSQL Backup

### Manual Dump

```bash
# Full database dump using pg_dump inside container
docker compose exec -T postgres pg_dump \
    -U $POSTGRES_USER \
    -d $POSTGRES_DB \
    --format=custom \
    --compress=9 \
    --no-password \
    > /opt/backups/daily/postgres_$(date +%Y%m%d_%H%M%S).dump

# Verify dump file was created and is non-empty
ls -lh /opt/backups/daily/postgres_*.dump | tail -1
```

### Compressed SQL Format (human-readable alternative)

```bash
docker compose exec -T postgres pg_dump \
    -U $POSTGRES_USER \
    -d $POSTGRES_DB \
    --format=plain \
    | gzip -9 \
    > /opt/backups/daily/postgres_$(date +%Y%m%d_%H%M%S).sql.gz
```

### All-Databases Dump (includes roles and tablespaces)

```bash
docker compose exec -T postgres pg_dumpall \
    -U postgres \
    --clean \
    | gzip -9 \
    > /opt/backups/daily/postgres_all_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Automated Backup Script

```bash
#!/bin/bash
# /opt/scripts/backup_postgres.sh

set -euo pipefail

BACKUP_DIR="/opt/backups/daily"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/postgres_${TIMESTAMP}.dump"
LOG_FILE="/var/log/backup.log"
RETENTION_DAYS=7

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "Starting PostgreSQL backup..."

mkdir -p "$BACKUP_DIR"

# Perform dump
docker compose -f /opt/ai-sentiment/docker-compose.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    --format=custom --compress=9 \
    > "$BACKUP_FILE"

# Verify backup size
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE")
if [ "$BACKUP_SIZE" -lt 1024 ]; then
    log "ERROR: Backup file too small (${BACKUP_SIZE} bytes). Possible failure."
    exit 1
fi

# Generate checksum
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"

log "Backup complete: ${BACKUP_FILE} ($(du -sh "$BACKUP_FILE" | cut -f1))"

# Prune old backups
find "$BACKUP_DIR" -name "postgres_*.dump" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "postgres_*.sha256" -mtime +${RETENTION_DAYS} -delete

log "Pruned backups older than ${RETENTION_DAYS} days."
```

### Backup Verification

```bash
# Verify backup integrity
pg_restore --list /opt/backups/daily/postgres_latest.dump | head -20

# Test restore to a temporary database
docker compose exec -T postgres createdb -U postgres backup_test

docker compose exec -T postgres pg_restore \
    -U postgres \
    -d backup_test \
    --no-owner \
    /opt/backups/daily/postgres_latest.dump

# Verify row counts match production
docker compose exec postgres psql -U postgres -d backup_test \
    -c "SELECT COUNT(*) FROM sentiment_analysis;"

# Cleanup test database
docker compose exec postgres dropdb -U postgres backup_test
```

---

## Redis Backup

### Manual RDB Snapshot

```bash
# Force Redis to write RDB snapshot immediately
docker compose exec redis redis-cli BGSAVE

# Wait for save to complete
docker compose exec redis redis-cli LASTSAVE

# Copy snapshot out of container
docker cp $(docker compose ps -q redis):/data/dump.rdb \
    /opt/backups/daily/redis_$(date +%Y%m%d_%H%M%S).rdb

# Compress the snapshot
gzip -9 /opt/backups/daily/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### Automated Redis Backup Script

```bash
#!/bin/bash
# /opt/scripts/backup_redis.sh

set -euo pipefail

BACKUP_DIR="/opt/backups/daily"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/backup.log"
RETENTION_DAYS=7

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "/var/log/backup.log"; }

log "Starting Redis backup..."

mkdir -p "$BACKUP_DIR"

# Trigger background save
docker compose -f /opt/ai-sentiment/docker-compose.yml exec -T redis \
    redis-cli BGSAVE

# Wait for save to complete (poll LASTSAVE)
SAVE_START=$(date +%s)
while true; do
    LAST_SAVE=$(docker compose -f /opt/ai-sentiment/docker-compose.yml exec -T redis \
        redis-cli LASTSAVE | tr -d '\r')
    if [ "$LAST_SAVE" -gt "$SAVE_START" ]; then
        break
    fi
    sleep 1
done

# Copy and compress RDB file
REDIS_CONTAINER=$(docker compose -f /opt/ai-sentiment/docker-compose.yml ps -q redis)
docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "/tmp/redis_tmp.rdb"
gzip -9 -c /tmp/redis_tmp.rdb > "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb.gz"
rm -f /tmp/redis_tmp.rdb

# Checksum
sha256sum "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb.gz" > "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb.gz.sha256"

log "Redis backup complete: redis_${TIMESTAMP}.rdb.gz"

# Prune old backups
find "$BACKUP_DIR" -name "redis_*.rdb.gz" -mtime +${RETENTION_DAYS} -delete
```

### Verification

```bash
# Inspect RDB file header (should start with "REDIS")
zcat /opt/backups/daily/redis_latest.rdb.gz | head -c 10

# Check backup size is reasonable (non-zero)
ls -lh /opt/backups/daily/redis_*.rdb.gz | tail -1
```

---

## Configuration Backup

```bash
#!/bin/bash
# /opt/scripts/backup_configs.sh

BACKUP_DIR="/opt/backups/configs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
APP_DIR="/opt/ai-sentiment"
ARCHIVE="${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

tar -czf "$ARCHIVE" \
    "${APP_DIR}/docker-compose.yml" \
    "${APP_DIR}/nginx/" \
    "${APP_DIR}/prometheus/" \
    "${APP_DIR}/grafana/provisioning/" \
    /etc/letsencrypt/ \
    2>/dev/null || true

# NOTE: .env is excluded from tar due to secrets — back up separately with encryption
gpg --symmetric --cipher-algo AES256 \
    --passphrase-file /root/.backup_passphrase \
    --batch \
    -o "${BACKUP_DIR}/env_${TIMESTAMP}.gpg" \
    "${APP_DIR}/.env"

sha256sum "$ARCHIVE" > "${ARCHIVE}.sha256"

# Prune configs older than 14 days
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +14 -delete
find "$BACKUP_DIR" -name "env_*.gpg" -mtime +14 -delete
```

---

## Backup Storage Structure

```
/opt/backups/
├── daily/
│   ├── postgres_20260601_020001.dump
│   ├── postgres_20260601_020001.dump.sha256
│   ├── postgres_20260602_020001.dump
│   ├── postgres_20260602_020001.dump.sha256
│   ├── redis_20260601_021501.rdb.gz
│   ├── redis_20260601_021501.rdb.gz.sha256
│   └── ... (7 days rolling)
├── weekly/
│   ├── weekly_20260525_030001.tar.gz
│   └── ... (4 weeks rolling)
├── configs/
│   ├── config_20260601_023001.tar.gz
│   ├── config_20260601_023001.tar.gz.sha256
│   ├── env_20260601_023001.gpg
│   └── ... (14 days rolling)
└── logs/
    └── backup.log
```

---

## Cron Job Setup

```bash
# Edit the crontab for the ubuntu user
crontab -e

# Add the following lines:

# PostgreSQL daily backup at 02:00 UTC
0 2 * * * /opt/scripts/backup_postgres.sh >> /var/log/backup.log 2>&1

# Redis daily backup at 02:15 UTC
15 2 * * * /opt/scripts/backup_redis.sh >> /var/log/backup.log 2>&1

# Configuration backup at 02:30 UTC
30 2 * * * /opt/scripts/backup_configs.sh >> /var/log/backup.log 2>&1

# Weekly consolidated backup every Sunday at 03:00 UTC
0 3 * * 0 /opt/scripts/backup_weekly.sh >> /var/log/backup.log 2>&1

# Verify backup integrity daily at 04:00 UTC
0 4 * * * /opt/scripts/verify_backups.sh >> /var/log/backup.log 2>&1
```

```bash
# Make all scripts executable
chmod +x /opt/scripts/backup_*.sh
chmod +x /opt/scripts/verify_backups.sh

# Verify cron is configured
crontab -l

# Test a script manually
/opt/scripts/backup_postgres.sh
```

---

## Manual Backup Procedure

Run these steps in sequence when performing an out-of-cycle manual backup:

```bash
# Step 1: Navigate to application directory
cd /opt/ai-sentiment

# Step 2: Verify containers are running
docker compose ps

# Step 3: Run PostgreSQL backup
/opt/scripts/backup_postgres.sh

# Step 4: Run Redis backup
/opt/scripts/backup_redis.sh

# Step 5: Run configuration backup
/opt/scripts/backup_configs.sh

# Step 6: Verify all backup files exist and have checksums
ls -lh /opt/backups/daily/
ls -lh /opt/backups/configs/

# Step 7: Validate checksums
cd /opt/backups/daily
for f in *.sha256; do sha256sum --check "$f" && echo "OK: $f"; done

# Step 8: Record backup completion in log
echo "[$(date)] Manual backup completed by operator" >> /var/log/backup.log
```

---

## Restore Procedures

### PostgreSQL Restore

```bash
# Step 1: Identify backup to restore
ls -lhtr /opt/backups/daily/postgres_*.dump

# Step 2: Verify checksum integrity before restoring
sha256sum --check /opt/backups/daily/postgres_<TIMESTAMP>.dump.sha256

# Step 3: Stop the application to prevent writes during restore
docker compose stop fastapi

# Step 4: Drop and recreate the database
docker compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS sentiment_db;"
docker compose exec postgres psql -U postgres -c "CREATE DATABASE sentiment_db OWNER sentiment_user;"

# Step 5: Restore from dump
docker compose exec -T postgres pg_restore \
    -U sentiment_user \
    -d sentiment_db \
    --no-owner \
    --no-acl \
    < /opt/backups/daily/postgres_<TIMESTAMP>.dump

# Step 6: Verify row counts
docker compose exec postgres psql -U sentiment_user -d sentiment_db \
    -c "SELECT COUNT(*) FROM sentiment_analysis;"

# Step 7: Restart the application
docker compose start fastapi

# Step 8: Verify health
curl -s https://ai-backend.astrodirectory.in/health
```

### Redis Restore

```bash
# Step 1: Identify backup to restore
ls -lhtr /opt/backups/daily/redis_*.rdb.gz

# Step 2: Verify checksum
sha256sum --check /opt/backups/daily/redis_<TIMESTAMP>.rdb.gz.sha256

# Step 3: Stop Redis container
docker compose stop redis

# Step 4: Decompress and copy RDB to container volume
zcat /opt/backups/daily/redis_<TIMESTAMP>.rdb.gz > /tmp/restore.rdb

REDIS_CONTAINER=$(docker compose ps -q redis)
docker cp /tmp/restore.rdb "${REDIS_CONTAINER}:/data/dump.rdb"
rm -f /tmp/restore.rdb

# Step 5: Start Redis (it will load dump.rdb on startup)
docker compose start redis

# Step 6: Verify restore
docker compose exec redis redis-cli DBSIZE
```

### Configuration Restore

```bash
# Step 1: Identify config backup
ls -lhtr /opt/backups/configs/config_*.tar.gz

# Step 2: Stop all services
docker compose down

# Step 3: Extract configuration archive
tar -xzf /opt/backups/configs/config_<TIMESTAMP>.tar.gz -C /

# Step 4: Restore .env file from encrypted backup
gpg --decrypt \
    --passphrase-file /root/.backup_passphrase \
    --batch \
    -o /opt/ai-sentiment/.env \
    /opt/backups/configs/env_<TIMESTAMP>.gpg

# Step 5: Restart all services
docker compose up -d

# Step 6: Verify
docker compose ps
curl -s https://ai-backend.astrodirectory.in/health
```

---

## Disaster Recovery

Complete recovery procedure for total system loss (e.g., terminated EC2 instance):

```bash
# Phase 1: Provision New Infrastructure (5 minutes)
# - Launch new EC2 t2.medium with Ubuntu 22.04 LTS
# - Assign existing Elastic IP to new instance
# - Configure security groups (ports 22, 80, 443)

# Phase 2: Baseline System Setup (10 minutes)
# Follow Server Preparation steps from DEPLOYMENT.md

# Phase 3: Restore Application Files (5 minutes)
git clone https://github.com/abhi90-cloud/devops-assignment /opt/ai-sentiment

# Phase 4: Restore Configurations from S3 or off-site backup
aws s3 cp s3://your-backup-bucket/latest/ /opt/backups/ --recursive
# OR transfer from another server via SCP

# Phase 5: Restore PostgreSQL (5 minutes)
sha256sum --check /opt/backups/daily/postgres_latest.dump.sha256
docker compose up -d postgres
sleep 10  # Wait for PostgreSQL to initialize
# Run PostgreSQL restore procedure above

# Phase 6: Restore Redis (2 minutes)
# Run Redis restore procedure above

# Phase 7: Restore SSL Certificates (3 minutes)
# Either restore from backup or re-issue with Certbot:
sudo certbot --nginx \
    -d ai-backend.astrodirectory.in \
    -d monitoring.astrodirectory.in \
    --non-interactive --agree-tos --email admin@astrodirectory.in

# Phase 8: Start All Services
docker compose up -d

# Phase 9: Verification (2 minutes)
docker compose ps
curl -s https://ai-backend.astrodirectory.in/health

# Total estimated time: ~30 minutes (meeting 30-minute RTO)
```

---

## Backup Validation

### Checksum Verification Script

```bash
#!/bin/bash
# /opt/scripts/verify_backups.sh

BACKUP_DIR="/opt/backups/daily"
ERRORS=0

echo "[$(date)] Starting backup verification..."

for checksum_file in "${BACKUP_DIR}"/*.sha256; do
    backup_file="${checksum_file%.sha256}"
    if [ ! -f "$backup_file" ]; then
        echo "ERROR: Missing backup file for checksum: $checksum_file"
        ((ERRORS++))
        continue
    fi
    if sha256sum --check "$checksum_file" --quiet; then
        echo "OK: $backup_file"
    else
        echo "CORRUPTED: $backup_file"
        ((ERRORS++))
    fi
done

if [ "$ERRORS" -gt 0 ]; then
    echo "ALERT: ${ERRORS} backup(s) failed validation!"
    exit 1
else
    echo "All backups passed integrity checks."
fi
```

---

## Recovery Testing

Monthly disaster recovery drills ensure restore procedures remain functional and within RTO.

### Monthly Drill Checklist

```bash
# Schedule: First Sunday of each month, 06:00 UTC (low-traffic window)

# 1. Create a test EC2 instance
# 2. Deploy application fresh from repository
# 3. Restore PostgreSQL from previous day's backup
# 4. Restore Redis from previous day's backup
# 5. Measure total time from start to verified health check
# 6. Record results in drill log: /opt/logs/dr_drills.log
# 7. Terminate test instance

# Pass criteria:
# - Full restore completes in < 30 minutes (RTO)
# - Row counts match production snapshot (RPO)
# - Health endpoint returns 200
# - At least 5 API calls succeed post-restore
```

---

## Monitoring Backup Success

### Prometheus Alert Rules

```yaml
# prometheus/alerts/backup_alerts.yml
groups:
  - name: backup_alerts
    rules:
      - alert: BackupFileMissing
        expr: |
          (time() - backup_last_success_timestamp_seconds) > 90000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Backup has not run in over 25 hours"
          description: "Last successful backup was {{ $value | humanizeDuration }} ago"

      - alert: BackupFileSizeTooSmall
        expr: backup_file_size_bytes < 1024
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Backup file is suspiciously small"
```

### Custom Metric from Backup Script

```bash
# At the end of backup_postgres.sh, push metric to Prometheus Pushgateway:
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE")
echo "backup_last_success_timestamp_seconds $(date +%s)" | \
    curl --data-binary @- http://localhost:9091/metrics/job/postgres_backup

echo "backup_file_size_bytes ${BACKUP_SIZE}" | \
    curl --data-binary @- http://localhost:9091/metrics/job/postgres_backup
```

---

## Troubleshooting

### Backup Script Fails Silently

```bash
# Test script manually with verbose output
bash -x /opt/scripts/backup_postgres.sh

# Check docker compose connectivity
docker compose ps

# Verify PostgreSQL credentials
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"
```

### Backup Disk Full

```bash
# Check disk usage
df -h /opt/backups

# Remove old backups immediately
find /opt/backups/daily -mtime +3 -delete

# Prune Docker unused images to reclaim space
docker system prune -af

# Long-term: Add EBS volume for backups or configure S3 offload
```

### Restore Fails Due to Version Mismatch

```bash
# Check PostgreSQL version of dump
pg_restore --list /opt/backups/daily/postgres_latest.dump | grep "PostgreSQL"

# Ensure restore target matches major version
docker compose exec postgres psql -U postgres -c "SELECT version();"

# If versions differ, use pg_upgrade or logical replication for migration
```

### Checksum Verification Failure

```bash
# File is likely corrupted during transfer or write
# Do not use this backup for restore
# Use the next most recent backup instead

ls -lhtr /opt/backups/daily/postgres_*.dump

# Re-run manual backup to get a fresh copy
/opt/scripts/backup_postgres.sh
```

---

*DevOps Engineer Assignment — Deepak Sharma — June 2026*
