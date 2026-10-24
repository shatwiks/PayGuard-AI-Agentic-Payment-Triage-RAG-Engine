#!/usr/bin/env bash
# ==============================================================================
# PayGuard AI — Staging Database Backup and Disaster Recovery Utility
# Usage:
#   ./scripts/backup_restore.sh backup [backup_file_path]
#   ./scripts/backup_restore.sh restore <backup_file_path> [target_database]
# ==============================================================================

set -euo pipefail

CONTAINER_NAME="${STAGING_DB_CONTAINER:-payguard_staging_db}"
DB_USER="${POSTGRES_USER:-payguard_staging_user}"
DB_NAME="${POSTGRES_DB:-payguard_staging_db}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

ACTION="${1:-help}"

case "${ACTION}" in
  backup)
    BACKUP_FILE="${2:-payguard_backup_${TIMESTAMP}.dump}"
    echo "=== Initiating Staging PostgreSQL Backup ==="
    echo "Container: ${CONTAINER_NAME}"
    echo "Database:  ${DB_NAME}"
    echo "Target:    ${BACKUP_FILE}"

    docker exec -t "${CONTAINER_NAME}" pg_dump -Fc -U "${DB_USER}" -d "${DB_NAME}" > "${BACKUP_FILE}"
    echo "-> Backup completed successfully: $(ls -lh "${BACKUP_FILE}")"
    ;;

  restore)
    if [ -z "${2:-}" ]; then
      echo "ERROR: Backup file path required for restore!"
      echo "Usage: $0 restore <backup_file_path> [target_database]"
      exit 1
    fi
    BACKUP_FILE="$2"
    TARGET_DB="${3:-${DB_NAME}}"

    if [ ! -f "${BACKUP_FILE}" ]; then
      echo "ERROR: Backup file not found: ${BACKUP_FILE}"
      exit 1
    fi

    echo "=== Initiating Staging PostgreSQL Restore ==="
    echo "Container: ${CONTAINER_NAME}"
    echo "Target DB: ${TARGET_DB}"
    echo "Source:    ${BACKUP_FILE}"

    # Copy dump into container
    docker cp "${BACKUP_FILE}" "${CONTAINER_NAME}:/tmp/restore_temp.dump"

    # Restore with clean switch
    docker exec -t "${CONTAINER_NAME}" pg_restore -U "${DB_USER}" -d "${TARGET_DB}" --clean --if-exists /tmp/restore_temp.dump
    docker exec -t "${CONTAINER_NAME}" rm -f /tmp/restore_temp.dump

    echo "-> Restore completed successfully into ${TARGET_DB}."
    ;;

  *)
    echo "PayGuard AI Backup and Restore Utility"
    echo "Usage:"
    echo "  $0 backup [output_filename.dump]"
    echo "  $0 restore <backup_file.dump> [target_db_name]"
    exit 1
    ;;
esac
