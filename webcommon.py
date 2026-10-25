"""대시보드 서버 공통 부분: 127.0.0.1 전용 HTTP 서버가 화면 파일과 JSON 자료를 내보낸다.

화면(HTML·CSS·JS)은 web/<이름>/ 폴더의 파일이다. 주소는 전부 상대 경로여야
휴대폰 통로(매매자료정리 app.py 의 /risk/, /flow/) 아래에서도 동작한다.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def _static(web_dir: Path, path: str) -> Path | None:
    """주소에 맞는 화면 파일. web_dir 밖이나 모르는 종류는 내보내지 않는다."""
    p = (web_dir / (path.lstrip("/") or "index.html")).resolve()
    if p.parent != web_dir.resolve() or p.suffix not in TYPES or not p.is_file():
        return None
    return p


def make_handler(web_dir: Path, api: dict, files: dict | None = None):
    """api: 주소 -> 자료를 돌려주는 함수 (JSON 으로 보냄). files: 주소 -> 따로 내보낼 HTML 파일."""
    files = files or {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in api:
                try:
                    body = json.dumps(api[path](), ensure_ascii=False).encode("utf-8")
                except Exception as e:
                    self.reply(500, "text/plain; charset=utf-8", f"{type(e).__name__}: {e}".encode("utf-8"))
                    return
                self.reply(200, "application/json; charset=utf-8", body)
                return
            p = files.get(path) or _static(web_dir, path)
            if p is None or not p.is_file():
                self.reply(404, "text/plain; charset=utf-8", b"not found")
                return
            self.reply(200, TYPES[p.suffix], p.read_bytes())

        def reply(self, status, ctype, body):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # pythonw 로 창 없이 돌 때 stderr 가 없어서 기록하지 않는다
            pass

    return Handler


def serve(host: str, port: int, handler, name: str):
    if sys.stderr is None:  # pythonw 는 출력 창이 없다
        sys.stdout = sys.stderr = open(os.devnull, "w")
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError:
        sys.exit(f"{port} 포트가 이미 사용 중입니다. {name}가 이미 켜져 있을 수 있습니다.")
    server.serve_forever()
