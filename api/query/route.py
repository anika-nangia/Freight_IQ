"""POST /api/query/route - the full decision pack for one corridor.

Returns the response the real FastAPI backend produced for that corridor, as
recorded by tools/build_api_snapshot.py. The website posts a fixed shape
(origin, destination, vessel_class, cargo type and tonnage); the corridor is
looked up by the first three.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from _data import CORS, key, load, unavailable


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

    def do_POST(self):
        if urlparse(self.path).path.rstrip("/") != "/api/query/route":
            self._send({"detail": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send({"detail": "invalid JSON body"}, 400)
            return

        origin = str(body.get("origin", "")).strip()
        destination = str(body.get("destination", "")).strip()
        vessel_class = str(body.get("vessel_class", "")).strip()

        if not (origin and destination and vessel_class):
            self._send({"detail": "origin, destination and vessel_class are required"}, 400)
            return

        try:
            data = load()
        except FileNotFoundError as e:
            self._send({"detail": str(e)}, 500)
            return

        k = key(origin, destination, vessel_class)
        found = data.get("route", {}).get(k)
        if found is None:
            self._send(unavailable(
                f"no recorded response for corridor '{origin} -> {destination}' "
                f"/ {vessel_class}"), 200)
            return
        self._send(found)

    def log_message(self, *args):
        pass
