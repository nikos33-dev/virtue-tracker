#!/usr/bin/env python3
"""Virtue Tracker — a local web app for Franklin's method. Stdlib only.

    python3 app/server.py        # opens http://localhost:8765

No pip install, no accounts, no cloud. Your data is a plain-text `log.jsonl` on your
own machine. The charts load Chart.js from a CDN; everything else is local. All the
domain logic lives in core.py; this file is just the HTTP shell around it.
"""
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
sys.path.insert(0, ROOT)
import core  # noqa: E402

PORT = 8765

# keep the sqlite index in sync with the truth file on boot
core.init_db()
core.rebuild_db_from_log()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, payload, status=200):
        self._send(status, json.dumps(payload, ensure_ascii=False))

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):
            with open(core.INDEX_HTML, encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/api/config":
            return self._json(core.config_payload(q.get("date")))
        if u.path == "/api/day":
            return self._json(core.day_payload(q.get("date")))
        if u.path == "/api/charts":
            return self._json(core.chart_payload())
        if u.path == "/api/grid":
            return self._json(core.grid_payload(q.get("date") or core.suggested_day()))
        return self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/save":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            status, payload = core.save_day(body)
            return self._json(payload, status)
        return self._send(404, "not found", "text/plain; charset=utf-8")


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Virtue Tracker → {url}   (Ctrl-C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
