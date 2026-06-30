#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Backup LectureVoice data: PostgreSQL dump + SeaweedFS guidance.
#
# Usage:
#   ./scripts/backup.sh [--output-dir <dir>]
#
# The postgres dump is performed via docker compose exec so no pg_dump binary
# is required on the host — only Docker and the running compose stack.
#
# Exit codes: 0 = success, 1 = failure.
set -euo pipefail

OUTPUT_DIR="./backups"

# Parse --output-dir flag
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# PostgreSQL dump
# ---------------------------------------------------------------------------
PG_DUMP_FILE="${OUTPUT_DIR}/postgres_${TIMESTAMP}.sql.gz"

echo "[backup] Dumping PostgreSQL → ${PG_DUMP_FILE}"
docker compose exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-lecturevoice}" "${POSTGRES_DB:-lecturevoice}" \
    | gzip > "$PG_DUMP_FILE"

if [[ ! -s "$PG_DUMP_FILE" ]]; then
    echo "[backup] ERROR: dump file is empty — check that postgres container is running." >&2
    exit 1
fi

echo "[backup] PostgreSQL dump complete: ${PG_DUMP_FILE} ($(du -sh "$PG_DUMP_FILE" | cut -f1))"

# ---------------------------------------------------------------------------
# SeaweedFS
# ---------------------------------------------------------------------------
echo ""
echo "[backup] SeaweedFS note:"
echo "  SeaweedFS stores blobs in Docker volumes — there is no pg_dump equivalent."
echo "  See docs/runbook.md §8 'SeaweedFS volume backup' for the full procedure."
echo "  Short form:"
echo "    1. Stop write traffic (optional but safer)."
echo "    2. docker run --rm --volumes-from <seaweedfs-container> -v \$(pwd)/backups:/backup \\"
echo "         alpine tar czf /backup/seaweedfs_${TIMESTAMP}.tar.gz /data"
echo "    3. Verify the archive is non-empty before re-enabling write traffic."

echo ""
echo "[backup] Done. All outputs in: ${OUTPUT_DIR}"
