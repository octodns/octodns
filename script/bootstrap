#!/bin/bash
# Usage: script/bootstrap
# Ensures all dependencies are installed locally.

set -e

cd "$(dirname "$0")"/..
ROOT=$(pwd)

if [ -z "$VENV_NAME" ]; then
    VENV_NAME="env"
fi

if [ ! -d "$VENV_NAME" ]; then
    if [ -z "$VENV_PYTHON" ]; then
        VENV_PYTHON=$(command -v python3)
    fi
    "$VENV_PYTHON" -m venv "$VENV_NAME"
fi
. "$VENV_NAME/bin/activate"

# We're in the venv now, so use the first Python in $PATH. In particular, don't
# use $VENV_PYTHON - that's the Python that *created* the venv, not the python
# *inside* the venv
python -m pip install -U 'pip>=10.0.1'
python -m pip install -r requirements.txt

if [ "$ENV" != "production" ]; then
    python -m pip install -r requirements-dev.txt
fi

if [ -d ".git" ]; then
    if [ -f ".git-blame-ignore-revs" ]; then
        echo ""
        echo "Setting blame.ignoreRevsFile to .git-blame-ingore-revs"
        git config --local blame.ignoreRevsFile .git-blame-ignore-revs
    fi
    if [ ! -L ".git/hooks/pre-commit" ]; then
        echo ""
        echo "Installing pre-commit hook"
        ln -s "$ROOT/.git_hooks_pre-commit" ".git/hooks/pre-commit"
    fi
fi

echo ""
echo "Run source env/bin/activate to get your shell in to the virtualenv"
echo "See README.md for more information."
echo ""
