#!/bin/bash
set -e

BACKUP_DIR="/opt/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p $BACKUP_DIR

echo "========================================="
echo "  Starting Backup - $(date)"
echo "========================================="

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
docker exec postgres_db pg_dump -U devopsadmin devopsdb | gzip > $BACKUP_DIR/postgres_$TIMESTAMP.sql.gz
echo "PostgreSQL backup: postgres_$TIMESTAMP.sql.gz"

# Backup Redis
echo "Backing up Redis..."
docker exec redis_cache redis-cli -a RedisProd2024! --rdb /data/dump.rdb SAVE 2>/dev/null
docker cp redis_cache:/data/dump.rdb $BACKUP_DIR/redis_$TIMESTAMP.rdb
echo "Redis backup: redis_$TIMESTAMP.rdb"

# Create archive
tar -czf $BACKUP_DIR/backup_$TIMESTAMP.tar.gz -C $BACKUP_DIR postgres_$TIMESTAMP.sql.gz redis_$TIMESTAMP.rdb
rm $BACKUP_DIR/postgres_$TIMESTAMP.sql.gz $BACKUP_DIR/redis_$TIMESTAMP.rdb

# Remove old backups
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

BACKUP_SIZE=$(du -h $BACKUP_DIR/backup_$TIMESTAMP.tar.gz | cut -f1)
echo "Backup complete: backup_$TIMESTAMP.tar.gz ($BACKUP_SIZE)"
echo "========================================="
