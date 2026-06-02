# Backup & Restore
Backup: ./scripts/backup.sh
Restore: ./scripts/restore.sh backup_FILE.tar.gz
Cron: 0 2 * * * /opt/devops-app/scripts/backup.sh
