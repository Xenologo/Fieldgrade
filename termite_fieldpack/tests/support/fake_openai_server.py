from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeOpenAI/0.1"

    def _send(self, status: int, obj) -> None:
        body = _json_bytes(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/models":
            model_id = getattr(self.server, "model_id", "fake-model")
            return self._send(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": model_id,
                            "object": "model",
                            "owned_by": "fake",
                        }
                    ],
                },
            )
        return self._send(404, {"error": {"message": "not_found", "path": self.path}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/chat/completions":
            try:
                n = int(self.headers.get("Content-Length", "0") or "0")
            except Exception:
                n = 0
            raw = self.rfile.read(n) if n > 0 else b""
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                payload = {}

            model = str(payload.get("model") or getattr(self.server, "model_id", "fake-model"))
            # Best-effort user prompt extraction.
            user = ""
            try:
                msgs = payload.get("messages") or []
                if msgs:
                    user = str(msgs[-1].get("content") or "")
            except Exception:
                user = ""

            content = f"fake-ok: {user}".strip()
            return self._send(
                200,
                {
                    "id": "chatcmpl-fake",
                    "object": "chat.completion",
                    "created": 0,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        return self._send(404, {"error": {"message": "not_found", "path": self.path}})

    def log_message(self, fmt: str, *args) -> None:
        # Keep tests quiet.
        return


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tiny fake OpenAI-compatible server for tests")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--model", default="fake-model")
    args = p.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, int(args.port)), _Handler)
    httpd.model_id = str(args.model)

    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
