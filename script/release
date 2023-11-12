#!/bin/bash

set -e

cd "$(dirname "$0")"/..
ROOT=$(pwd)

if [ -z "$VENV_NAME" ]; then
    VENV_NAME="env"
fi

PYPYRC="$HOME/.pypirc"
if [ ! -e "$PYPYRC" ]; then
    cat << EndOfMessage >&2
$PYPYRC does not exist, please create it with the following contents

[pypi]
  username = __token__
  password = [secret-token-goes-here]

EndOfMessage
    exit 1
fi

ACTIVATE="$VENV_NAME/bin/activate"
if [ ! -f "$ACTIVATE" ]; then
    echo "$ACTIVATE does not exist, run ./script/bootstrap" >&2
    exit 1
fi
. "$ACTIVATE"

# Set so that setup.py will create a public release style version number
export OCTODNS_RELEASE=1

VERSION="$(grep "^__version__" "$ROOT/octodns/__init__.py" | sed -e "s/.* = '//" -e "s/'$//")"

git tag -s "v$VERSION" -m "Release $VERSION"
git push origin "v$VERSION"
echo "Tagged and pushed v$VERSION"

TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)
git archive --format tar "v$VERSION" | tar xv -C $TMP_DIR
echo "Created clean room $TMP_DIR and archived $VERSION into it"

(cd "$TMP_DIR" && python -m build --sdist --wheel)

cp $TMP_DIR/dist/*$VERSION.tar.gz $TMP_DIR/dist/*$VERSION*.whl dist/
echo "Copied $TMP_DIR/dists into ./dist"

twine check dist/*$VERSION.tar.gz dist/*$VERSION*.whl
twine upload dist/*$VERSION.tar.gz dist/*$VERSION*.whl
echo "Uploaded $VERSION"
