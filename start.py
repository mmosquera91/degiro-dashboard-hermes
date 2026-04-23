"""Startup wrapper that catches and logs startup errors."""
import sys
import traceback

if __name__ == "__main__":
    try:
        import socket
        socket.gethostbyname("google.com")
        print("DNS: OK")
    except Exception as e:
        print(f"DNS: FAILED - {e}")

    try:
        import uvicorn
        print("uvicorn: OK")
    except Exception as e:
        print(f"uvicorn import: FAILED - {e}")
        sys.exit(1)

    try:
        from app.main import app
        print("app.main: OK")
    except Exception as e:
        print(f"app.main import: FAILED - {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        import os
        host = os.getenv("HOST", "127.0.0.1")
        port = int(os.getenv("PORT", "8000"))
        print(f"Starting uvicorn on {host}:{port}")
        uvicorn.run("app.main:app", host=host, port=port, log_level="info")
    except Exception as e:
        print(f"uvicorn.run failed: {e}")
        traceback.print_exc()
        sys.exit(1)
