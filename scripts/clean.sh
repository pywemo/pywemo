#!/usr/bin/env bash
set -euf -o pipefail

SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SELF_DIR/.."

if [[ `env | grep VIRTUAL_ENV` ]]; then
  echo "Error: deactivate your venv first."
  exit 1
fi

find . -regex '^.*\(__pycache__\|\.py[co]\)$' -delete
rm .coverage .eggs .tox build dist withings*.egg-info .venv venv -rf

echo "Clean complete."
