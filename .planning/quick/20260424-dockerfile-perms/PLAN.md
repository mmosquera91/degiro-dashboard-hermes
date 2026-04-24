---
name: 20260424-dockerfile-perms
description: Fix Dockerfile ownership and /data/snapshots permissions
type: quick
---

## gsd-fix: Dockerfile — fix file ownership and /data/snapshots permissions

### File
Dockerfile only.

### Problems
1. COPY start.py /start.py runs after USER appuser, so start.py is
   copied as appuser into /, which is root-owned and causes permission
   issues on some systems.
2. /data/snapshots/ is never created or chowned, so snapshot writes
   fail with [Errno 13] Permission denied.

### Fix
Replace the entire Dockerfile with exactly this:

FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY start.py ./start.py

RUN mkdir -p /data/snapshots \
    && chown -R appuser:appgroup /app /data

USER appuser

EXPOSE 8000

CMD ["python", "/app/start.py"]

### Key changes
- COPY start.py moved to BEFORE USER appuser (still root at that point)
- start.py copied to /app/start.py (inside chowned directory)
- CMD updated to python /app/start.py
- /data/snapshots created and chowned to appuser before USER switch
- Single RUN for chown covers both /app and /data

### Constraints
- No other changes.
