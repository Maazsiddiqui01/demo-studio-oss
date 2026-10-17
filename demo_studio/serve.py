"""Serve a demo app folder on localhost while recording (storyboard key `serve:`).

Unknown paths fall back to index.html, so client-side routes like /agent/outreach load.
"""
from __future__ import annotations

import contextlib
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import home


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.exists():
            self.path = "/index.html"
        return super().send_head()


def serve_forever(folder: str, port: int) -> None:
    root = (home() / folder).resolve()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(_Handler, directory=str(root)))
    print(f"Serving {root} at http://localhost:{port} (Ctrl+C to stop)", flush=True)
    httpd.serve_forever()


@contextlib.contextmanager
def serving(sb):
    folder = sb.raw.get("serve")
    if not folder:
        yield None
        return
    # relative to the storyboard's own folder first, then to the workspace
    root = (Path(sb.path).resolve().parent / folder).resolve()
    if not (root / "index.html").exists():
        root = (home() / folder).resolve()
    if not (root / "index.html").exists():
        raise FileNotFoundError(f"serve: {root} has no index.html")
    u = urlparse(sb.base_url)
    if u.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError("serve: only for a localhost base_url")
    httpd = ThreadingHTTPServer(("127.0.0.1", u.port or 80), functools.partial(_Handler, directory=str(root)))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
