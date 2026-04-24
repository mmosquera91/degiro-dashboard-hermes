---
name: 20260424-dockerfile-perms
status: complete
type: quick
---

## Summary

Fixed Dockerfile by replacing the entire file.

### Changes
- `COPY start.py` moved before `USER appuser` so it runs as root
- `start.py` copied to `/app/start.py` (inside chowned /app directory)
- `CMD` updated to `python /app/start.py`
- `/data/snapshots` created and chowned to `appuser:appgroup`
- Single `RUN chown` covers both `/app` and `/data`

### Verification
- start.py exists at /home/server/workspace/brokr/start.py
- Dockerfile COPY paths verified: app/ → ./app/ and start.py → ./start.py
- /data/snapshots directory created and chowned before USER switch
