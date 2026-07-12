#!/usr/bin/env python3
"""Live Defense console server. Stdlib only.

Bridges the examiner session and the browser console:
  examiner -> browser : writes <dir>/state.json  (served via SSE /events)
  browser  -> examiner: POST /answer -> <dir>/inbox/answer-NNNN.json

Usage: defense_server.py --dir STATE_DIR [--port N] [--no-open]
"""
import argparse, json, re, socket, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UI_FILE = Path(__file__).resolve().parent.parent / "ui" / "index.html"
PLACEHOLDER = "<!doctype html><title>Defense Console</title><h1>Defense console UI not built yet</h1>"
_inbox_lock = threading.Lock()

def pick_port(preferred):
    candidates = [preferred] if preferred else list(range(8420, 8470))
    for port in candidates:
        with socket.socket() as s:
            # Match ThreadingHTTPServer's allow_reuse_address so a port held only
            # by TIME_WAIT sockets (e.g. from a just-killed server) is not skipped.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def read_state_compact(state_file):
    """Compact single-line JSON of state.json, or None while mid-write/missing."""
    try:
        return json.dumps(json.loads(state_file.read_text()), separators=(",", ":"), ensure_ascii=False)
    except (OSError, ValueError):  # ValueError covers JSONDecodeError + UnicodeDecodeError
        return None

class Handler(BaseHTTPRequestHandler):
    state_dir = None  # set in main()

    def log_message(self, *args):
        pass

    def _forbidden_host(self):
        """DNS-rebinding guard: only loopback Host headers may route (port ignored)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip().lower()
        if host in ("127.0.0.1", "localhost"):
            return False
        self._reply(403, {"error": "forbidden host"})
        return True

    def _reply(self, code, data, ctype="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self._forbidden_host():
            return
        state_file = self.state_dir / "state.json"
        if self.path == "/":
            html = UI_FILE.read_bytes() if UI_FILE.exists() else PLACEHOLDER.encode()
            self._reply(200, html, "text/html; charset=utf-8")
        elif self.path == "/state":
            compact = read_state_compact(state_file)
            self._reply(200, (compact or "{}").encode())
        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last_sent = None
            try:
                while True:
                    compact = read_state_compact(state_file)
                    if compact is not None and compact != last_sent:
                        last_sent = compact
                        self.wfile.write(f"data: {compact}\n\n".encode())
                        self.wfile.flush()
                    time.sleep(0.25)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self._forbidden_host():
            return
        if self.path != "/answer":
            self._reply(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            answer = str(payload.get("answer", "")).strip()
            if not answer:
                raise ValueError("empty answer")
        except (ValueError, json.JSONDecodeError):
            self._reply(400, {"ok": False, "error": "body must be JSON with a non-empty 'answer'"})
            return
        inbox = self.state_dir / "inbox"
        with _inbox_lock:
            # counter scan: only answer-<digits>.json counts — stray files and
            # in-flight *.tmp writes must never 500 the POST path
            taken = [int(m.group(1)) for f in inbox.glob("answer-*.json")
                     if (m := re.fullmatch(r"answer-(\d+)", f.stem))]
            n = 1 + max(taken, default=0)
            name = f"answer-{n:04d}.json"
            record = {"qid": payload.get("qid"), "answer": answer, "receivedAt": int(time.time())}
            tmp = inbox / (name + ".tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False))
            tmp.rename(inbox / name)  # atomic: the examiner never sees a half-written answer
        self._reply(200, {"ok": True, "file": name})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    state_dir = Path(args.dir).resolve()
    (state_dir / "inbox").mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    if not state_file.exists():
        state_file.write_text(json.dumps({"phase": "briefing"}))

    Handler.state_dir = state_dir
    port = pick_port(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"DEFENSE CONSOLE: {url}", flush=True)
    if not args.no_open:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    server.serve_forever()

if __name__ == "__main__":
    main()
