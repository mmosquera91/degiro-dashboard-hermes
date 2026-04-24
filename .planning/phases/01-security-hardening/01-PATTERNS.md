# Phase 01: Security Hardening - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 9 new/modified + 6 deleted
**Analogs found:** 6 / 9 (2 files have no existing analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/main.py` | controller/middleware | request-response | `app/main.py` (self) | exact |
| `.dockerignore` | config | file-I/O | `.dockerignore` (self) | exact |
| `.env.example` | config | file-I/O | `.env.example` (self) | exact |
| `app/degiro_client.py` | service | CRUD | `app/degiro_client.py` (self) | partial |
| `scripts/debug_portfolio.py` | utility | file-I/O | None | no-analog |
| `scripts/debug_raw_portfolio.py` | utility | file-I/O | None | no-analog |
| `scripts/debug_from_session.py` | utility | file-I/O | None | no-analog |
| `scripts/debug_int_account.py` | utility | file-I/O | None | no-analog |
| `scripts/test_auth_methods.py` | utility | file-I/O | None | no-analog |
| `scripts/test_login.py` | utility | file-I/O | None | no-analog |

## Pattern Assignments

### `app/main.py` (controller + middleware, request-response)

**Analog:** `app/main.py` (self — modification of existing file)

This is the primary file being modified. It already contains FastAPI route handlers that follow a consistent pattern. The modifications add auth dependency, security headers middleware, CORS middleware, remove debug endpoint, and sanitize error messages.

**Existing imports pattern** (lines 1-17):
```python
"""Brokr — FastAPI application with all routes."""

import logging
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .degiro_client import DeGiroClient, debug_login_variants
from .market_data import enrich_positions, get_fx_rate
from .scoring import compute_scores, compute_portfolio_weights, get_top_candidates
from .context_builder import build_hermes_context
```

**Existing session lock pattern** (line 28):
```python
_session_lock = threading.Lock()
```

**Existing exception handling pattern** (lines 233-237):
```python
    except ConnectionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Auth error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")
```

**Pattern to add: Auth dependency** (from FastAPI Depends pattern, see RESEARCH.md lines 147-161):
```python
import hmac
import os
from fastapi import Request, Depends

async def verify_brok_token(request: Request):
    """Validate BROKR_AUTH_TOKEN bearer token on /api/* routes."""
    token = os.getenv("BROKR_AUTH_TOKEN", "")

    if not token:
        logger.warning("BROKR_AUTH_TOKEN not configured — blocking API request")
        raise HTTPException(status_code=401, detail="Authentication required")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth format")

    provided = auth_header[7:]
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Pattern to add: Security headers middleware** (from RESEARCH.md lines 176-182):
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com"
    return response
```

**Pattern to add: CORS middleware** (from RESEARCH.md lines 194-200):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else ["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)
```

**Pattern to modify: Remove debug endpoint** (lines 378-394):
Delete entire `debug_login` function and its route `@app.post("/api/debug-login")`.

**Pattern to modify: Sanitize error messages** (every exception handler):
Replace `detail=str(e)` with generic messages + `logger.error` for server-side logging.
Example from line 237: `raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")`
Should become: `raise HTTPException(status_code=500, detail="Authentication failed")`

---

### `.dockerignore` (config, file-I/O)

**Analog:** `.dockerignore` (self — modification of existing file)

**Existing content** (lines 1-8):
```
.git
.env
__pycache__
*.pyc
.DS_Store
README.md
.env.example
```

**Pattern to add:** Exclude debug scripts from Docker build context:
```
scripts/
app/debug_*.py
app/test_*.py
```

---

### `.env.example` (config, file-I/O)

**Analog:** `.env.example` (self — modification of existing file)

**Existing content** (lines 1-2):
```
HOST_PORT=8000
```

**Pattern to add:** Document BROKR_AUTH_TOKEN:
```
BROKR_AUTH_TOKEN=your-secret-token-here
HOST_PORT=8000
HOST=127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:8000
```

---

### `app/degiro_client.py` (service, CRUD)

**Analog:** `app/degiro_client.py` (self — partial modification)

This file is referenced in RESEARCH.md for the `debug_login_variants` function that is imported by the debug endpoint being removed. The function itself may remain if it has non-debug utility, but the import in `main.py` will be removed.

**Existing import pattern** (line 13):
```python
from .degiro_client import DeGiroClient, debug_login_variants
```

**Pattern to modify:** Remove `debug_login_variants` from import if function is deleted or gated.

---

### `scripts/debug_portfolio.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

This is a development utility script being recreated outside `app/` per D-06. No existing analog in codebase.

**Pattern to use:** Create as standalone Python script with direct DeGiroClient usage, no FastAPI routing.

---

### `scripts/debug_raw_portfolio.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

Same pattern as above.

---

### `scripts/debug_from_session.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

Same pattern as above.

---

### `scripts/debug_int_account.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

Same pattern as above.

---

### `scripts/test_auth_methods.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

Same pattern as above.

---

### `scripts/test_login.py` (utility, file-I/O)

**Analog:** None — new file outside Docker

Same pattern as above.

---

## Shared Patterns

### Authentication

**Source:** `app/main.py` (self) — FastAPI Depends dependency pattern

**Apply to:** All `/api/*` routes in `app/main.py`

```python
from fastapi import Depends

# Add to each protected route:
@app.get("/api/portfolio", dependencies=[Depends(verify_brok_token)])
```

### Error Handling

**Source:** `app/main.py` lines 233-237 (self) — Exception handlers with generic messages

**Apply to:** All exception handlers in `app/main.py`

Current pattern leaks internal details:
```python
raise HTTPException(status_code=500, detail=str(e))  # BAD
```

Should become:
```python
logger.error("Auth error: %s", str(e))  # Log detail server-side
raise HTTPException(status_code=500, detail="Authentication failed")  # Generic client message
```

### Logging

**Source:** `app/main.py` line 18-19 (self)

**Apply to:** All modified exception handlers

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
```

### Thread Safety

**Source:** `app/main.py` line 28 (self)

**Apply to:** Session lock pattern remains unchanged

```python
_session_lock = threading.Lock()
```

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/debug_portfolio.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |
| `scripts/debug_raw_portfolio.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |
| `scripts/debug_from_session.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |
| `scripts/debug_int_account.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |
| `scripts/test_auth_methods.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |
| `scripts/test_login.py` | utility | file-I/O | Dev utility scripts do not exist outside app/ |

---

## Files to Delete

The following files are marked for deletion per D-05:

| File | Reason |
|------|--------|
| `app/debug_portfolio.py` | Debug script — eliminated per D-05 |
| `app/debug_raw_portfolio.py` | Debug script — eliminated per D-05 |
| `app/debug_from_session.py` | Debug script — eliminated per D-05 |
| `app/debug_int_account.py` | Debug script — eliminated per D-05 |
| `app/test_auth_methods.py` | Debug script — eliminated per D-05 |
| `app/test_login.py` | Debug script — eliminated per D-05 |

---

## Metadata

**Analog search scope:** `/home/server/workspace/brokr/app/`, `/home/server/workspace/brokr/`
**Files scanned:** 13 Python files, 2 config files
**Pattern extraction date:** 2026-04-23

**Key patterns identified:**
- All `/api/*` routes use FastAPI Depends for auth
- Error handling uses `logger.error` + generic HTTPException messages
- Session management uses `threading.Lock` for thread safety
- Exception details sanitized per D-10 (no `str(e)` in client responses)
- CORS uses `CORSMiddleware` with environment-driven origins
- Security headers via `@app.middleware("http")`

**Ready for Planning**
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.