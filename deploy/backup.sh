#!/bin/sh
# Nightly PostgreSQL dump at 03:00 Addis Ababa time (00:00 UTC), kept for
# BACKUP_KEEP_DAYS days. Copy /backups off the server (S3, another site) for
# the off-site copy the plan requires; see docs/DEPLOYMENT.md.
set -eu
while true; do
  now=$(date -u +%H)
  if [ "$now" = "00" ]; then
    file="/backups/vora-$(date -u +%Y%m%d-%H%M).sql.gz"
    pg_dump -h db -U vora vora | gzip > "$file"
    echo "Backup written: $file"
    find /backups -name 'vora-*.sql.gz' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
    sleep 3600
  fi
  sleep 600
done
