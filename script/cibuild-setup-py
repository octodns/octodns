#!/bin/sh
set -e

cd "$(dirname "$0")/.."

VERSION="$(grep "^__version__" "./octodns/__init__.py" | sed -e "s/.* = '//" -e "s/'$//")"

echo "## create test venv ############################################################"
TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)
python3 -m venv $TMP_DIR
. "$TMP_DIR/bin/activate"
pip install build setuptools
echo "## environment & versions ######################################################"
python --version
pip --version
echo "## validate setup.py build #####################################################"
python -m build --sdist --wheel
echo "## validate wheel install ###################################################"
pip install dist/*$VERSION*.whl
echo "## validate tests can run against installed code ###############################"
pip install pytest pytest-network
pytest --disable-network
echo "## complete ####################################################################"
