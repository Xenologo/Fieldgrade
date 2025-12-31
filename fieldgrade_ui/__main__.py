from __future__ import annotations

import argparse
import os
import ipaddress

def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m fieldgrade_ui")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="Run the Fieldgrade UI/API server (default).")
    sub.add_parser("worker", help="Run the background job worker (process).")
    sub.add_parser("doctor", help="Run environment checks and print JSON.")

    args = parser.parse_args()
    cmd = args.cmd or "serve"

    if cmd == "worker":
        from .worker import main as worker_main
        worker_main()
        return

    if cmd == "doctor":
        from .doctor import main as doctor_main
        doctor_main()
        return

    # default: serve
    host = os.environ.get("FG_HOST") or os.environ.get("FIELDGRADE_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("FG_PORT") or os.environ.get("FIELDGRADE_UI_PORT", "8787"))
    workers = int(os.environ.get("FG_WORKERS") or os.environ.get("FIELDGRADE_UI_WORKERS", "1"))
    log_level = os.environ.get("FG_LOG_LEVEL", "info")
    reload = os.environ.get("FG_RELOAD", "0") == "1"

    # Security: refuse to bind to a non-loopback interface unless an API token is configured.
    # This prevents path-bearing endpoints from being reachable over the network without auth.
    tok = (os.environ.get("FG_API_TOKEN") or os.environ.get("FIELDGRADE_UI_API_TOKEN") or "").strip()

    def _is_loopback(h: str) -> bool:
        hs = (h or "").strip()
        if hs in ("127.0.0.1", "localhost", "::1"):
            return True
        # If it's an IP, check loopback.
        try:
            return ipaddress.ip_address(hs).is_loopback
        except Exception:
            # Hostname or bind-all; treat as non-loopback.
            return False

    if not _is_loopback(host) and not tok:
        raise RuntimeError(
            f"Refusing to bind Fieldgrade UI to host={host!r} without FG_API_TOKEN. "
            "Set FG_API_TOKEN (and supply it as X-API-Key) or bind to 127.0.0.1."
        )

    try:
        import uvicorn
    except Exception as e:
        raise RuntimeError(
            "uvicorn not installed. Run: pip install -r requirements.txt"
        ) from e

    uvicorn.run(
        "fieldgrade_ui.app:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level=log_level,
    )

if __name__ == "__main__":
    main()
