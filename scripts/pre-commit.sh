#!/usr/bin/env bash
set -euf -o pipefail

SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SELF_DIR/.."

source "$SELF_DIR/common.sh"

assertPython
enterVenv

if [ "${1:-}" == "-mpre_commit" ]; then
    shift
fi

exec python -mpre_commit "$@"
