#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <make-target>" >&2
    exit 2
fi

. /app/.cron-env
cd /app

target="$1"
echo "$(date -Is) starting ${target}"
make "$target"
echo "$(date -Is) finished ${target}"
