#!/usr/bin/env bash
# One-time setup: create the conda env, .env file and justfitting.db.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

if conda env list | grep -q "^${ENV_NAME}[[:space:]]"; then
  echo "Conda environment '${ENV_NAME}' already exists, skipping creation."
else
  conda env create -f environment.yml
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example -- review it before running the app."
fi

echo "Initializing database..."
conda run -n "${ENV_NAME}" python -c "
import os
from server.src.data.db.DB import DB
DB(os.environ.get('JUSTFITTING_DB_PATH', 'justfitting.db'))
print('Database ready.')
"

echo "Install complete. Run scripts/run.sh to start the app."
