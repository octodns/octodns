#!/bin/bash

set -e

SOURCES="$(find *.py octodns tests -name '*.py') $(grep --files-with-matches '^#!.*python' script/*)"

. env/bin/activate

isort "$@" $SOURCES
black "$@" $SOURCES
