#!/bin/sh

set -e

cd "$(dirname "$0")/.."

echo "## bootstrap ###################################################################"
script/bootstrap

if [ -z "$VENV_NAME" ]; then
    VENV_NAME="env"
fi

. "$VENV_NAME/bin/activate"

echo "## environment & versions ######################################################"
python --version
pip --version
echo "## modules: "
pip freeze
echo "## clean up ####################################################################"
find octodns tests -name "*.pyc" -exec rm {} \;
rm -f *.pyc
echo "## begin #######################################################################"
# For now it's just lint...
echo "## lint ########################################################################"
script/lint
echo "## formatting ##################################################################"
script/format --check || (echo "Formatting check failed, run ./script/format" && exit 1)
echo "## tests/coverage ##############################################################"
script/coverage
echo "## complete ####################################################################"
