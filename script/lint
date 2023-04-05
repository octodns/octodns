#!/bin/sh
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)

if [ -z "$VENV_NAME" ]; then
    VENV_NAME="env"
fi

ACTIVATE="$VENV_NAME/bin/activate"
if [ ! -f "$ACTIVATE" ]; then
    echo "$ACTIVATE does not exist, run ./script/bootstrap" >&2
    exit 1
fi
. "$ACTIVATE"

SOURCES="$(find *.py octodns tests -name '*.py') $(grep --files-with-matches '^#!.*python' script/*)"

pyflakes $SOURCES
