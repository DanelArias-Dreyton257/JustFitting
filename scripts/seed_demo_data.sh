#!/usr/bin/env bash
# Register admin_cut/admin_bulk (both adminadmin) and seed their Danel
# (cut) and Sergio (bulk) reference profiles and logs, for manual testing.
# No-op per-account if already seeded.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

conda run -n "${ENV_NAME}" python scripts/seed_demo_data.py "${1:-${JUSTFITTING_DB_PATH:-justfitting.db}}"
