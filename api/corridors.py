"""GET /api/corridors - the list of corridors the models can price."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from _data import CORS, load


class handler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        if urlparse(self.path).path.rstrip("/") not in ("/api/corridors", ""):
            self._send({"detail": "not found"}, 404)
            return
        try:
            self._send(load()["corridors"])
        except FileNotFoundError as e:
            self._send({"detail": str(e)}, 500)

    def log_message(self, *args):
        pass
