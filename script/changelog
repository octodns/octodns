#!/bin/bash

set -e

VERSION=v$(grep __version__ octodns/__init__.py | sed -e "s/^[^']*'//" -e "s/'$//")
echo $VERSION
git log --pretty="%h - %cr - %s (%an)" "${VERSION}..HEAD"
