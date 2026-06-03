#!/bin/sh
set -eu

mkdir -p /app/logs
touch /app/logs/cron.log

python - <<'PY' > /app/.cron-env
import os
import shlex

for key, value in sorted(os.environ.items()):
    print(f"export {key}={shlex.quote(value)}")
PY

crontab /app/docker/cron/crontab
exec cron -f
