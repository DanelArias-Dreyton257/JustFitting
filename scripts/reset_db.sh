#!/usr/bin/env bash
# Delete the SQLite database. Confirms unless FORCE=1.
# Usage: scripts/reset_db.sh [path]
#
# Local dev convenience only (Phase 10.1, see README): a fresh DB just
# starts at user_version=0 and runs every migration in
# server/src/data/db/migrations/ in order, same as a first-ever install --
# faster than writing/testing a migration while iterating. A real device's
# DB is never reset this way; it always migrates in place on next boot.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

DB_PATH="${1:-${JUSTFITTING_DB_PATH:-justfitting.db}}"

if [ ! -f "${DB_PATH}" ]; then
  echo "No database found at ${DB_PATH}, nothing to reset."
  exit 0
fi

if [ "${FORCE:-}" != "1" ]; then
  read -r -p "This will permanently delete ${DB_PATH}. Continue? [y/N] " reply
  if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

rm -f "${DB_PATH}"
echo "Deleted ${DB_PATH}."
