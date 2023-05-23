#!/usr/bin/env bash
set -euf -o pipefail

SELF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SELF_DIR/.."

source "$SELF_DIR/common.sh"

assertPython
enterVenv
poetryInstall

echo
echo "===Installing pre-commit hooks==="
pre-commit install
# Always run pre-commit inside the venv.
ORIG_PATH="$(python -c "import os;print(f'{os.pathsep}\$PATH')")"
REPLACE="VIRTUAL_ENV=\"$VIRTUAL_ENV\"\nPATH=\"$VIRTUAL_ENV/bin$ORIG_PATH\""
sed -ie "s^# start templated.*^$REPLACE^" .git/hooks/pre-commit

echo
echo "===Running pre-commit checks==="
pre-commit run --all-files

echo
echo "===Test with pytest and coverage==="
coverage run -m pytest --vcr-record=none
coverage report --skip-covered
coverage lcov

echo
echo "===Building package==="
poetry build

if [[ ! -z "${OUTPUT_ENV_VAR:-}" ]]; then
  echo
  echo "===Generating output variables for CI==="
  echo "version=$(poetry version -s)" | tee -a "${!OUTPUT_ENV_VAR}"
  echo "coverage-lcov=$(coverage debug config | sed -ne 's/^.*lcov_output: \(.*\)$/\1/p')" | tee -a "${!OUTPUT_ENV_VAR}"
fi

echo
echo "Build complete"
