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
pip install poetry


echo
echo "===Installing dependencies==="
poetry install


echo
echo "===Installing black==="
pip install black


echo
echo "===Sorting imports==="
ISORT_ARGS="--apply"
if [[ "${CI:-}" = "1" ]]; then
  ISORT_ARGS="--check-only --exclude ouimeaux_device"
fi

# isort $ISORT_ARGS


echo
echo "===Formatting code==="
if [[ `which black` ]]; then
  BLACK_ARGS=""
  if [[ "${CI:-}" = "1" ]]; then
    BLACK_ARGS="--check"
  fi

  black $BLACK_ARGS .
else
  echo "Warning: Skipping code formatting. You should use python >= 3.6."
fi


echo
echo "===Lint with flake8==="
flake8

echo
echo "===Lint with pylint==="
pylint $LINT_PATHS


# echo
# echo "===Test with pytest==="
# pytest


echo
echo "===Building package==="
poetry build



echo
echo "Build complete"
