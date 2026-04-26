#!/bin/sh
mkdir -p /data/snapshots
touch /data/symbol_overrides.json 2>/dev/null || true
chown -R appuser:appgroup /data
exec gosu appuser python /app/start.py