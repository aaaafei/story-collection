# -*- coding: utf-8 -*-
"""本机同步助手：提供静态站、/api/sync，以及带密码的 /api/update。"""
from __future__ import print_function

import json
import os
import posixpath
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from sync_from_notion import (  # noqa: E402
    NotionError,
    list_series_status,
    load_catalog,
    load_env,
    notion_token,
    preview_series,
    sync_series,
)
from update_from_git import UpdateError, password_status, pull_latest  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("SYNC_PORT") or 8765)
SKIP_PREFIXES = ("/story",)
MAX_BODY = 4096
FAIL_LIMIT = 8
FAIL_WINDOW = 600
_update_lock = threading.Lock()
_fail_lock = threading.Lock()
_failures = {}


def client_key(handler):
    return handler.client_address[0] if handler.client_address else "local"


def too_many_failures(key):
    now = time.time()
    with _fail_lock:
        recent = [stamp for stamp in _failures.get(key, []) if now - stamp < FAIL_WINDOW]
        _failures[key] = recent
        return len(recent) >= FAIL_LIMIT


def note_failure(key):
    now = time.time()
    with _fail_lock:
        recent = [stamp for stamp in _failures.get(key, []) if now - stamp < FAIL_WINDOW]
        recent.append(now)
        _failures[key] = recent


def clear_failures(key):
    with _fail_lock:
        _failures.pop(key, None)


def normalize_path(path):
    parsed = path.split("?", 1)[0]
    for prefix in SKIP_PREFIXES:
        if parsed == prefix:
            return "/"
        if parsed.startswith(prefix + "/"):
            parsed = parsed[len(prefix) :]
            break
    if not parsed.startswith("/"):
        parsed = "/" + parsed
    return parsed


class SyncHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super(SyncHandler, self).__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, status, payload, cors=True):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_update(self):
        key = client_key(self)
        if too_many_failures(key):
            self._json(429, {"ok": False, "error": "试太多次了，请过十分钟再试。"}, cors=False)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._json(400, {"ok": False, "error": "请求太长。"}, cors=False)
            return
        try:
            payload = self._read_json()
        except Exception:
            self._json(400, {"ok": False, "error": "请求不是有效的 JSON。"}, cors=False)
            return
        if not isinstance(payload, dict):
            payload = {}
        given = payload.get("password")
        if not isinstance(given, str):
            given = ""
        state = password_status(ROOT, given)
        if state is None:
            self._json(
                503,
                {
                    "ok": False,
                    "error": "服务器还没设置校验密码。请在 tools/.env 写入 UPDATE_PASSWORD。这只用来挡住乱试，不是 Git 密码。",
                },
                cors=False,
            )
            return
        if not state:
            note_failure(key)
            self._json(401, {"ok": False, "error": "校验密码不对。"}, cors=False)
            return
        # 校验到此结束。后面的 git pull 不接收这把密码，只用服务器上已有的 Git 登录。
        del given
        if not _update_lock.acquire(blocking=False):
            self._json(409, {"ok": False, "error": "正在更新，请等这一次结束。"}, cors=False)
            return
        try:
            result = pull_latest(ROOT)
        except UpdateError as err:
            self._json(err.status, {"ok": False, "error": str(err)}, cors=False)
            return
        except Exception:
            traceback.print_exc()
            self._json(500, {"ok": False, "error": "更新失败。"}, cors=False)
            return
        finally:
            _update_lock.release()
        clear_failures(key)
        self._json(200, result, cors=False)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = normalize_path(self.path)
        if path in ("/api/sync/status", "/api/sync"):
            load_env(ROOT)
            data = load_catalog(ROOT)
            token = bool(notion_token())
            self._json(
                200,
                {
                    "ok": True,
                    "notionConfigured": token,
                    "series": list_series_status(ROOT, data),
                    "hint": None
                    if token
                    else "请在 tools/.env 写入 NOTION_TOKEN=你的集成令牌，并把 Notion 里的 story 页面分享给该集成。",
                },
            )
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        path = normalize_path(self.path)
        if path == "/api/update":
            self._handle_update()
            return
        try:
            payload = self._read_json()
        except Exception:
            self._json(400, {"ok": False, "error": "请求不是有效的 JSON。"})
            return
        series_ids = payload.get("seriesIds") or payload.get("series") or []
        if isinstance(series_ids, str):
            series_ids = [series_ids]
        episode_keys = payload.get("episodeKeys") or []
        logs = []

        def collect(message):
            logs.append(message)
            print(message, flush=True)

        try:
            if path == "/api/sync/preview":
                rows = preview_series(ROOT, series_ids, log=collect)
                self._json(200, {"ok": True, "series": rows, "log": logs})
                return
            if path in ("/api/sync", "/api/sync/run"):
                result = sync_series(
                    ROOT, series_ids, episode_keys=episode_keys, log=collect
                )
                result.update({"ok": True, "log": logs})
                self._json(200, result)
                return
        except NotionError as err:
            self._json(err.status or 500, {"ok": False, "error": str(err), "log": logs})
            return
        except Exception as err:
            traceback.print_exc()
            self._json(500, {"ok": False, "error": str(err), "log": logs})
            return
        self._json(404, {"ok": False, "error": "未知接口"})

    def translate_path(self, path):
        path = normalize_path(path)
        path = path.split("?", 1)[0]
        path = posixpath.normpath(urllib_unquote(path))
        words = [word for word in path.split("/") if word]
        dest = ROOT
        for word in words:
            if os.path.dirname(word) or word in (os.curdir, os.pardir):
                continue
            dest = os.path.join(dest, word)
        rel = os.path.relpath(dest, ROOT)
        if rel.startswith("..") or os.path.basename(dest) in {".env", ".git"}:
            return os.path.join(ROOT, "index.html")
        return dest


def urllib_unquote(path):
    from urllib.parse import unquote

    return unquote(path)


def main():
    load_env(ROOT)
    os.chdir(ROOT)
    server = ThreadingHTTPServer((HOST, PORT), SyncHandler)
    print("故事收藏屋同步助手: http://%s:%s/" % (HOST, PORT), flush=True)
    print("首页可点「同步新故事」或「更新故事」。按 Ctrl+C 结束。", flush=True)
    print("更新故事的 UPDATE_PASSWORD 只做校验，不会交给 Git。Git 登录用服务器上已有的配置。", flush=True)
    if not notion_token():
        print("尚未检测到 NOTION_TOKEN。可把令牌写在 tools/.env", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
