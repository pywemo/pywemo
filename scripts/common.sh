VENV_DIR=".venv"
PYTHON_BIN="python3"
LINT_PATHS="./pywemo"

function assertPython() {
  if ! [[ $(which "$PYTHON_BIN") ]]; then
    echo "Error: '$PYTHON_BIN' is not in your path."
    exit 1
  fi
}

function enterVenv() {
  # Not sure why I couldn't use "if ! [[ `"$PYTHON_BIN" -c 'import venv'` ]]" below. It just never worked when venv was
  # present.
  VENV_NOT_INSTALLED=$("$PYTHON_BIN" -c 'import venv' 2>&1 | grep -ic ' No module named' || true)
  if [[ "$VENV_NOT_INSTALLED" -gt "0" ]]; then
    echo "Error: The $PYTHON_BIN 'venv' module is not installed."
    exit 1
  fi

  if ! [[ -e "$VENV_DIR" ]]; then
    echo "Creating venv."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  else
    echo Using existing venv.
  fi

  if ! [[ $(env | grep VIRTUAL_ENV) ]]; then
    echo "Entering venv."
    set +uf
    source "$VENV_DIR/bin/activate"
    set -uf
  else
    echo Already in venv.
  fi

}