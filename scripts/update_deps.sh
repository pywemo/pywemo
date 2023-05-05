#!/usr/bin/env bash
set -euf -o pipefail

SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SELF_DIR/.."

source "$SELF_DIR/common.sh"

assertPython

echo
echo "===Settting up venv==="
enterVenv

echo
echo "===Installing poetry==="
pip install "poetry$(sed -n 's/^poetry = "\([^"]\+\)"$/\1/p' pyproject.toml)"

echo
echo "===Installing dependencies==="
poetry install

echo
echo "===Updating poetry lock file==="
poetry update --lock

echo
echo "===Updating bootstrap_requirements.txt==="
poetry export --only=bootstrap > "$SELF_DIR/bootstrap_requirements.txt"
