#!/bin/sh
set -eu

CUSTOM_CA_DIR="${STACKBRIDGE_CA_DIR:-/usr/local/share/ca-certificates/stackbridge}"

if [ -d "$CUSTOM_CA_DIR" ] && find "$CUSTOM_CA_DIR" -type f -name '*.crt' -print -quit | grep -q .; then
    echo "[StackBridge] Installation des autorités de certification locales..."
    update-ca-certificates >/dev/null
fi

exec "$@"
