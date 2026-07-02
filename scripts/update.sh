#!/usr/bin/env bash
# Update the conda env and apply pending database migrations.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

conda env update -n "${ENV_NAME}" -f environment.yml --prune

echo "Applying pending database migrations..."
conda run -n "${ENV_NAME}" python -c "
import os
from server.src.data.db.DB import DB
DB(os.environ.get('JUSTFITTING_DB_PATH', 'justfitting.db'))
print('Migrations applied.')
"
