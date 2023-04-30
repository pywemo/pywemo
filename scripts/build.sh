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
echo "===Installing pre-commit hooks==="
pre-commit install

echo
echo "===Validate with rstcheck==="
rstcheck README.rst

echo
echo "===Sort imports with isort==="
ISORT_ARGS=""
if [[ "${CI:-}" = "1" ]]; then
  ISORT_ARGS="--check-only"
fi
isort $ISORT_ARGS .

echo
echo "===Format with black==="
BLACK_ARGS=""
if [[ "${CI:-}" = "1" ]]; then
  BLACK_ARGS="--check"
fi
black $BLACK_ARGS .

echo
echo "===Lint with flake8==="
flake8

echo
echo "===Lint with pylint==="
pylint pywemo scripts

echo
echo "===Lint with mypy==="
mypy .

echo
echo "===Test with pytest and coverage==="
coverage run -m pytest --vcr-record=none
coverage report --skip-covered

echo
echo "===Building package==="
poetry build

echo
echo "Build complete"
