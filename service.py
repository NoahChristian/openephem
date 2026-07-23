#!/usr/bin/env python3
"""
service.py — minimal HTTP API for natal charts.  [SHIP]

Zero external deps (stdlib http.server), so it runs anywhere Python does —
including shared/cPanel hosting behind the WordPress/WooCommerce site.

Endpoints
---------
GET  /health            -> {"status":"ok"}
POST /chart             -> JSON body -> chart JSON (+ "svg" unless svg=false)
POST /chart.svg         -> JSON body -> image/svg+xml

Request body (JSON):
    {
      "date": [1990,5,15],           # required [Y,M,D]
      "time": [14,30],               # optional [H,M(,S)]; omit => houseless noon
      "place": "New York, NY, USA",  # OR "lat"/"lon"
      "lat": 40.7128, "lon": -74.006,
      "tz": null,                    # optional IANA name / fixed offset; else derived
      "house_system": "Placidus",
      "provider": "nominatim",       # or "google" (+ "api_key")
      "svg": true, "theme": "auto"
    }

Run:  python service.py --port 8080
Security: bind to localhost and put behind the web server / a reverse proxy;
add auth there. This service performs no auth itself.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import timeplace as tp
import chart as chartmod
import wheel as wheelmod

MAX_BODY = 64 * 1024


def build_chart(req: dict) -> dict:
    if "date" not in req:
        raise ValueError("'date' [Y,M,D] is required")
    resolved = tp.resolve(
        date=tuple(req["date"]),
        time=tuple(req["time"]) if req.get("time") else None,
        place=req.get("place"),
        lat=req.get("lat"), lon=req.get("lon"),
        tz=req.get("tz"),
        calendar=req.get("calendar", "auto"),
        fold=int(req.get("fold", 0)),
        provider=req.get("provider", "nominatim"),
        api_key=req.get("api_key"),
        user_agent=req.get("user_agent", "elpis-astrology"),
    )
    return chartmod.assemble(
        resolved,
        house_system=req.get("house_system", "Placidus"),
        de440=req.get("de440", "de440.bsp"),
        kernel_dir=req.get("kernel_dir", "./kernels"),
        include_minor_aspects=bool(req.get("include_minor_aspects", False)),
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "ElpisChart/1.0"

    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, (bytes, bytearray)) else \
            json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # tighten in prod
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > MAX_BODY:
            raise ValueError("empty or oversized request body")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            return self._send(200, {"status": "ok"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        try:
            req = self._read_json()
        except Exception as exc:  # noqa: BLE001
            return self._send(400, {"error": f"bad request: {exc}"})
        try:
            chart = build_chart(req)
        except Exception as exc:  # noqa: BLE001
            return self._send(400, {"error": str(exc)})

        if path == "/chart.svg":
            svg = wheelmod.render_svg(chart, theme=req.get("theme", "auto"),
                                      title=req.get("title"))
            return self._send(200, svg.encode("utf-8"), ctype="image/svg+xml")
        if path == "/chart":
            out = dict(chart)
            if req.get("svg", True):
                out["svg"] = wheelmod.render_svg(chart, theme=req.get("theme", "auto"),
                                                 title=req.get("title"))
            return self._send(200, out)
        return self._send(404, {"error": "not found"})

    def log_message(self, *a):  # quiet by default
        pass


def create_server(host="127.0.0.1", port=8080):
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Natal chart HTTP API (stdlib).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    srv = create_server(args.host, args.port)
    print(f"chart API on http://{args.host}:{args.port}  (POST /chart, /chart.svg; GET /health)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
