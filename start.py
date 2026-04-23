"""Startup wrapper that catches and logs startup errors."""
import sys
import os
import pathlib
import traceback

if __name__ == "__main__":
    # DNS check
    try:
        socket.gethostbyname("google.com")
        print("DNS: OK")
    except Exception as e:
        print(f"DNS: FAILED - {e}")

    # uvicorn import
    try:
        import uvicorn
        print("uvicorn: OK")
    except Exception as e:
        print(f"uvicorn import: FAILED - {e}")
        sys.exit(1)

    # Path diagnostics
    print(f"sys.path: {sys.path}")
    print(f"cwd: {os.getcwd()}")
    p = pathlib.Path("/app")
    print(f"/app exists: {p.exists()}")
    if p.exists():
        print(f"/app contents: {list(p.iterdir())}")
    p2 = pathlib.Path("/app/app")
    print(f"/app/app exists: {p2.exists()}")
    if p2.exists():
        print(f"/app/app contents: {list(p2.iterdir())}")
    if pathlib.Path("/app/app/main.py").exists():
        sys.path.insert(0, "/app")
        print("Found /app/app/main.py, added /app to sys.path")
    else:
        print("WARNING: /app/app/main.py not found")

    # App import
    try:
        from app.main import app
        print("app.main: OK")
    except Exception as e:
        print(f"app.main import: FAILED - {e}")
        traceback.print_exc()
        sys.exit(1)

    # Start server
    try:
        host = os.getenv("HOST", "127.0.0.1")
        port = int(os.getenv("PORT", "8000"))
        print(f"Starting uvicorn on {host}:{port}")
        uvicorn.run("app.main:app", host=host, port=port, log_level="info")
    except Exception as e:
        print(f"uvicorn.run failed: {e}")
        traceback.print_exc()
        sys.exit(1)
