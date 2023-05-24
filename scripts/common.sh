#!/usr/bin/env bash

VENV_DIR=".venv"
PYTHON_BIN="$(which python3)"
# The .txt_ extension is used to avoid changes by Dependabot.
BOOTSTRAP_REQUIREMENTS="scripts/bootstrap-requirements.txt_"

function assertPython() {
  if [[ -z "$PYTHON_BIN" ]]; then
    echo "Error: '$PYTHON_BIN' is not in your path."
    exit 1
  fi
}

function enterVenv() {
  echo
  echo "===Settting up venv==="
  # Not sure why I couldn't use "if ! [[ `"$PYTHON_BIN" -c 'import venv'` ]]" below. It just never worked when venv was
  # present.
  VENV_NOT_INSTALLED=$("$PYTHON_BIN" -c 'import venv' 2>&1 | grep -ic ' No module named' || true)
  if [[ "$VENV_NOT_INSTALLED" -gt "0" ]]; then
    echo "Error: The $PYTHON_BIN 'venv' module is not installed."
    exit 1
  fi

  if [[ ! -e "$VENV_DIR" ]]; then
    echo "Creating venv."
    VENV_ARGS=("$VENV_DIR")
    if [[ ! -z "${CI:-}" ]]; then
      VENV_ARGS+=(--symlink)
    fi
    "$PYTHON_BIN" -m venv "${VENV_ARGS[@]}"
  else
    echo Using existing venv.
  fi

  if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo "Entering venv."
    set +uf
    if [[ -f "$VENV_DIR/Scripts/activate" ]]; then
      source "$VENV_DIR/Scripts/activate"
    else
      source "$VENV_DIR/bin/activate"
    fi
    set -uf
  else
    echo Already in venv.
  fi
}

function poetryInstall() {
  echo
  echo "===Installing poetry==="
  pip install \
    --require-hashes \
    --no-deps \
    --only-binary :all: \
    -r "$BOOTSTRAP_REQUIREMENTS"

  echo
  echo "===Installing dependencies==="
  poetry install
}
