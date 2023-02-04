#!/bin/sh
set -e

cd "$(dirname "$0")/.."

if [ -z "$VENV_NAME" ]; then
    VENV_NAME="env"
fi

ACTIVATE="$VENV_NAME/bin/activate"
if [ ! -f "$ACTIVATE" ]; then
    echo "$ACTIVATE does not exist, run ./script/bootstrap" >&2
    exit 1
fi
. "$ACTIVATE"

# Just to be sure/safe
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=
export CLOUDFLARE_EMAIL=
export CLOUDFLARE_TOKEN=
export DNSIMPLE_ACCOUNT=
export DNSIMPLE_TOKEN=
export DYN_CUSTOMER=
export DYN_PASSWORD=
export DYN_USERNAME=
export GOOGLE_APPLICATION_CREDENTIALS=
export ARM_CLIENT_ID=
export ARM_CLIENT_SECRET=
export ARM_TENANT_ID=
export ARM_SUBSCRIPTION_ID=

SOURCE_DIR="octodns/"

# Don't allow disabling coverage
grep -r -I --line-number "# pragma: +no.*cover" $SOURCE_DIR && {
    echo "Code coverage should not be disabled"
    exit 1
}

pytest \
  --disable-network \
  --cov-reset \
  --cov=$SOURCE_DIR \
  --cov-fail-under=100 \
  --cov-report=html \
  --cov-report=xml \
  --cov-report=term \
  --cov-branch \
  "$@"
