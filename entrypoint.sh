#!/bin/sh
mkdir -p /data/snapshots
chown -R appuser:appgroup /data
exec gosu appuser python /app/start.py