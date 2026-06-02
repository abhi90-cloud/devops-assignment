#!/bin/bash
set -e

BACKUP_DIR="/opt/backups"

if [ -z "$1" ]; then
    BACKUP_FILE=$(ls -t $BACKUP_DIR/backup_*.tar.gz | head -1)
else
    BACKUP_FILE=$1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "========================================="
echo "  Restoring from: $BACKUP_FILE"
echo "========================================="

TEMP_DIR=$(mktemp -d)
tar -xzf $BACKUP_FILE -C $TEMP_DIR

# Restore PostgreSQL
echo "📦 Restoring PostgreSQL..."
gunzip -c $TEMP_DIR/postgres_*.sql.gz | docker exec -i postgres_db psql -U devopsadmin -d devopsdb
echo "✅ PostgreSQL restored"

# Restore Redis
echo "📦 Restoring Redis..."
docker cp $TEMP_DIR/redis_*.rdb redis_cache:/data/dump.rdb
docker restart redis_cache
echo "✅ Redis restored"

rm -rf $TEMP_DIR
echo "========================================="
echo "  ✅ Restore completed!"
echo "========================================="
