#!/usr/bin/env python3
"""Локальный мост: HTML-редактор  <->  движок python-lottie.

Только stdlib (http.server). Запуск:  ./.venv/bin/python server.py  [--port 8000]
Открой http://localhost:8000/  — редактор с живым превью.

Endpoints:
  GET  /                     -> editor.html
  GET  /<file>               -> статика из папки проекта (editor.html, preview.html, assets/, output/)
  GET  /api/effects          -> каталог эффектов (категории, doc, комбо)
  POST /api/upload           -> {name, data_url}  сохраняет PNG в assets/uploads/, отдаёт {path,w,h}
  POST /api/generate         -> spec JSON -> {ok, lottie:{...}}  (+ save=path => пишет файл)
"""

from __future__ import annotations

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import export  # noqa: E402
import effects  # noqa: E402,F401
from generator import catalog  # noqa: E402
from spec import build_from_spec, write_player_html  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(ROOT, "assets", "uploads")

_CTYPE = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript",
    ".css": "text/css", ".json": "application/json", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
    ".lottie": "application/zip",
}


def _effects_payload():
    cats, combos = catalog()
    # добавим хинт по параметрам из doc-строки (после "params:")
    def params_hint(doc):
        if "params:" in doc:
            return doc.split("params:", 1)[1].strip()
        return ""
    out = {"categories": {}, "combos": combos}
    for cat, items in cats.items():
        out["categories"][cat] = [
            {"name": n, "doc": d, "params": params_hint(d)} for n, d in items
        ]
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # тише в консоль
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    # ---- GET ----
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            path = "/editor.html"
        if path == "/api/effects":
            return self._send(200, _effects_payload())

        # статика (только внутри ROOT)
        rel = path.lstrip("/")
        fp = os.path.normpath(os.path.join(ROOT, rel))
        if not fp.startswith(ROOT) or not os.path.isfile(fp):
            return self._send(404, {"error": f"not found: {path}"})
        ext = os.path.splitext(fp)[1].lower()
        with open(fp, "rb") as f:
            data = f.read()
        return self._send(200, data, _CTYPE.get(ext, "application/octet-stream"))

    # ---- POST ----
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/upload":
                return self._upload()
            if path == "/api/generate":
                return self._generate()
            return self._send(404, {"error": f"unknown endpoint {path}"})
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return self._send(400, {"error": f"{type(e).__name__}: {e}"})

    def _upload(self):
        body = self._read_json()
        name = os.path.basename(body.get("name", "upload.png"))
        data_url = body["data_url"]
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(b64)
        os.makedirs(UPLOADS, exist_ok=True)
        fp = os.path.join(UPLOADS, name)
        with open(fp, "wb") as f:
            f.write(raw)
        from PIL import Image as PILImage
        w, h = PILImage.open(fp).size
        rel = os.path.relpath(fp, ROOT)
        return self._send(200, {"ok": True, "path": rel, "w": w, "h": h})

    def _generate(self):
        body = self._read_json()
        spec = body.get("spec", body)
        save = body.get("save")          # опц. путь для сохранения .json
        player = body.get("player")      # опц. путь для HTML-плеера
        an = build_from_spec(spec)
        lottie = an.to_dict()
        if save:
            export(an, os.path.join(ROOT, save), "json")
            if player:
                write_player_html(os.path.join(ROOT, save),
                                  os.path.join(ROOT, player),
                                  trigger=spec.get("trigger", "loop"),
                                  segments=spec.get("segments"))
        return self._send(200, {"ok": True, "lottie": lottie,
                                 "saved": save, "player": player})


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Lottie editor -> http://{args.host}:{args.port}/  (Ctrl+C для выхода)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nстоп")
        srv.shutdown()


if __name__ == "__main__":
    main()
