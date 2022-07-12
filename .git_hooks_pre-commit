#!/bin/sh

set -e

HOOKS=$(dirname "$0")
GIT=$(dirname "$HOOKS")
ROOT=$(dirname "$GIT")

. "$ROOT/env/bin/activate"
"$ROOT/script/lint"
"$ROOT/script/format" --check --quiet || (echo "Formatting check failed, run ./script/format" && exit 1)
"$ROOT/script/coverage"
