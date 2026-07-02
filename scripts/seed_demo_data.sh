#!/usr/bin/env bash
# Register admin/adminadmin and seed the verified "Danel" reference profile
# and its weekly logs, for manual testing. No-op if already seeded.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

conda run -n "${ENV_NAME}" python scripts/seed_demo_data.py "${1:-${JUSTFITTING_DB_PATH:-justfitting.db}}"
