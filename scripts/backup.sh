#!/bin/bash

# Configuration
BACKUP_DIR="/opt/companyai/backups"
DB_NAME="companyai"
DB_USER="companyai"
DB_HOST="localhost"
DB_PORT="5433"
DATE=$(date +"%Y%m%d_%H%M%S")
FILENAME="$BACKUP_DIR/backup_$DATE.sql.gz"
LOG_FILE="$BACKUP_DIR/backup.log"

# Create backup directory
mkdir -p $BACKUP_DIR

# Logging function
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

log_message "Starting backup for $DB_NAME..."

# Execute backup
# Note: Requires .pgpass file or PGPASSWORD env variable to run without interaction
export PGPASSWORD="companyai"

if pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME | gzip > $FILENAME; then
    log_message "Backup successful: $FILENAME"
    log_message "Size: $(du -h $FILENAME | cut -f1)"
else
    log_message "Backup FAILED!"
    # Send email or notification here if configured
    exit 1
fi

# Cleanup old backups (keep last 7 days)
log_message "Cleaning up old backups..."
find $BACKUP_DIR -name "backup_*.sql.gz" -type f -mtime +7 -delete

log_message "Backup process completed."
