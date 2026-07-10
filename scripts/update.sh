#!/usr/bin/env bash
# Update the conda env and apply pending database migrations.
#
# "Migrations" is now literal (Phase 10.1, see README): DB() below runs
# server/src/data/db/migrations/ in order via SQLite's PRAGMA user_version,
# migrating any real, already-populated DB in place rather than recreating
# it -- this is the safe path for an existing deploy/device, unlike
# scripts/reset_db.sh.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

conda env update -n "${ENV_NAME}" -f environment.yml --prune

echo "Applying pending database migrations..."
conda run -n "${ENV_NAME}" python - <<'PY'
import os
from server.src.data.db.DB import DB
DB(os.environ.get('JUSTFITTING_DB_PATH', 'justfitting.db'))
print('Migrations applied.')
PY
