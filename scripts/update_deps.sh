#!/usr/bin/env bash
set -euf -o pipefail

SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SELF_DIR/.."

source "$SELF_DIR/common.sh"

assertPython
enterVenv
poetryInstall

echo
echo "===Updating poetry lock file==="
poetry update --lock

echo
echo "===Updating bootstrap_requirements.txt==="
poetry export --only=bootstrap --output="$SELF_DIR/bootstrap-requirements.txt"
