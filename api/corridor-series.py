"""GET /api/corridor-series - observed weekly rates plus the forecast band."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from _data import CORS, key, load


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
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/corridor-series":
            self._send({"detail": "not found"}, 404)
            return

        q = parse_qs(parsed.query)
        origin = (q.get("origin") or [""])[0].strip()
        destination = (q.get("destination") or [""])[0].strip()
        vessel_class = (q.get("vessel_class") or [""])[0].strip()

        if not (origin and destination and vessel_class):
            self._send({"detail": "origin, destination and vessel_class are required"}, 400)
            return

        try:
            data = load()
        except FileNotFoundError as e:
            self._send({"detail": str(e)}, 500)
            return

        k = key(origin, destination, vessel_class)
        found = data.get("series", {}).get(k)
        if found is None:
            self._send({
                "available": False,
                "reason": f"no recorded series for corridor "
                          f"'{origin} -> {destination}' / {vessel_class}",
            }, 200)
            return
        self._send(found)

    def log_message(self, *args):
        pass
