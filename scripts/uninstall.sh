#!/usr/bin/env bash
# Remove the conda environment and optionally the database.
# Usage: scripts/uninstall.sh [db_path]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"
DB_PATH="${1:-${JUSTFITTING_DB_PATH:-justfitting.db}}"

if conda env list | grep -q "^${ENV_NAME}[[:space:]]"; then
  conda env remove -n "${ENV_NAME}"
  echo "Removed conda environment '${ENV_NAME}'."
else
  echo "Conda environment '${ENV_NAME}' not found, skipping."
fi

if [ -f "${DB_PATH}" ]; then
  if [ "${FORCE:-}" = "1" ]; then
    rm -f "${DB_PATH}"
    echo "Deleted ${DB_PATH}."
  else
    read -r -p "Also delete database ${DB_PATH}? [y/N] " reply
    if [[ "${reply}" =~ ^[Yy]$ ]]; then
      rm -f "${DB_PATH}"
      echo "Deleted ${DB_PATH}."
    fi
  fi
fi
