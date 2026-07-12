# Thesis Examiner Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the thesis-defense examiner as an installable Claude Code plugin with an optional PPTX slides module and a two-way Live Defense web console, tested end-to-end, deployed to `MA-Abuelmagd/thesis-examiner`.

**Architecture:** One canonical examiner protocol (`skills/thesis-examiner/references/protocol.md`) consumed by two thin wrappers (interactive skill, headless agent). A stdlib-only Python HTTP server bridges the examiner session and a single-file browser console via `state.json` (examiner → browser over SSE) and a numbered `inbox/` of answer files (browser → examiner).

**Tech Stack:** Python 3 stdlib only (http.server, zipfile, xml.etree, webbrowser). Single-file HTML/CSS/JS UI (no frameworks, no CDN). Claude Code plugin format (`.claude-plugin/plugin.json` + `marketplace.json`). Bash test scripts + curl.

## Global Constraints

- Python: **stdlib only** — no pip installs anywhere (spec §2). Target `python3` ≥ 3.8.
- XML safety without defusedxml: PPTX parts are untrusted input, and OOXML forbids DTDs in parts — therefore **reject any XML part containing `<!DOCTYPE` or `<!ENTITY`** and cap part size at 10 MB before parsing (blocks XXE and billion-laughs within stdlib).
- UI: **one file** `ui/index.html`, all CSS/JS inline, no external requests, `prefers-color-scheme` aware (spec §5).
- Protocol text exists in **exactly one file**: `skills/thesis-examiner/references/protocol.md`. Wrappers must not duplicate it (spec §6).
- **No numeric question targets** anywhere in protocol v2 — no goal, floor, or ceiling. Stopping rule is coverage saturation + loop-until-dry (spec §4).
- Slides are **optional**: without a PPTX the exam must behave exactly as v1 (spec §4).
- Plugin name: `thesis-examiner`, version `1.0.0`, license MIT (spec §3).
- Graceful degradation: no `python3` → chat-mode Document D; corrupt PPTX → named warning, thesis-only (spec §5).
- The v1 protocol source to transform lives at `<v1-skill-source>` (everything after the line `--- BEGIN EXAMINER PROTOCOL ---`).
- Repo root (and cwd for all commands unless stated): `~/WS/thesis-examiner/`.
- Every commit message ends with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## Shared interface contracts (referenced by Tasks 3, 4, 5, 7)

**`state.json`** (examiner writes atomically: write `state.json.tmp`, then `mv` over):

```json
{
  "phase": "briefing | question | feedback | verdict",
  "qid": 7,
  "question": "Your Table 4.2 reports 94% but slide 9 claims 97% — reconcile these.",
  "tier": "T5", "lens": "Methodologist", "category": "24 Slides-Thesis consistency",
  "grounding": "Table 4.2, p.61 vs Slide 9",
  "timerStartedAt": 1783300000, "durationMin": 60,
  "scoreboard": [{"dim": "Rigor", "score": 2.5, "max": 3}],
  "coverage": [{"label": "Ch.1", "status": "done | partial | current | pending"}],
  "redFlags": ["Deferred a specific on own headline result"],
  "feedback": {"forQid": 6, "verdict": "acceptable", "note": "Correct core, no alternative named."},
  "verdict": {"outcome": "Pass with minor corrections", "summary": "...", "perDimension": [{"dim": "Rigor", "score": 2, "max": 3}]}
}
```

Only `phase` is mandatory; UI must tolerate any other field being absent.

**Answer POST** `POST /answer` body `{"qid": 7, "answer": "non-empty text"}` → server writes `inbox/answer-0001.json` (zero-padded, strictly increasing) containing `{"qid":7,"answer":"...","receivedAt":<epoch-seconds>}` and responds `{"ok":true,"file":"answer-0001.json"}`.

**Server CLI** `python3 scripts/defense_server.py --dir <state-dir> [--port N] [--no-open]` → serves UI at `/`, state at `/state`, SSE at `/events`, answers at `POST /answer`; prints exactly one line `DEFENSE CONSOLE: http://127.0.0.1:<port>` to stdout then keeps running.

**Extractor CLI** `python3 scripts/extract_pptx.py <deck.pptx> [--json]` → markdown per slide to stdout (or JSON with `--json`): `{"slideCount": N, "slides": [{"n":1,"title":"...","body":["line",...],"notes":"..."}]}`. Exit 0 on success; exit 2 with a one-line `ERROR: ...` on unreadable/empty deck.

---

### Task 1: Repo scaffold and plugin manifests

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `LICENSE`
- Create: `.gitignore`

**Interfaces:**
- Produces: plugin identity `thesis-examiner@thesis-examiner` that Tasks 6–10 install and reference.

- [ ] **Step 1: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "thesis-examiner",
  "version": "1.0.0",
  "description": "Universal thesis-defense examiner: exhaustive viva question bank, model answers, grading kit, optional slides cross-examination, and a live two-way defense console in your browser.",
  "author": { "name": "Mohamed Aboelmagd", "url": "https://github.com/MA-Abuelmagd" }
}
```

- [ ] **Step 2: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "thesis-examiner",
  "owner": { "name": "Mohamed Aboelmagd", "url": "https://github.com/MA-Abuelmagd" },
  "plugins": [
    {
      "name": "thesis-examiner",
      "source": "./",
      "description": "Universal thesis-defense examiner: question bank, model answers, grading kit, slides cross-examination, live defense console."
    }
  ]
}
```

- [ ] **Step 3: Write `LICENSE`** — standard MIT text, year 2026, holder `Mohamed Aboelmagd`.

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.live/
tests/tmp/
```

- [ ] **Step 5: Validate both JSON files**

Run: `jq -e .name .claude-plugin/plugin.json && jq -e '.plugins[0].source' .claude-plugin/marketplace.json`
Expected: prints `"thesis-examiner"` and `"./"`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: plugin + marketplace manifests, MIT license"
```

---

### Task 2: PPTX extractor (`extract_pptx.py`) with generated fixture

**Files:**
- Create: `scripts/extract_pptx.py`
- Create: `tests/make_fixture_pptx.py`
- Create: `tests/test_extract.sh`

**Interfaces:**
- Produces: Extractor CLI contract (see Shared interface contracts). Protocol v2 (Task 5) tells the examiner to run it; the agent wrapper (Task 6) references it via `${CLAUDE_PLUGIN_ROOT}/scripts/extract_pptx.py`.

- [ ] **Step 1: Write the fixture generator `tests/make_fixture_pptx.py`**

A `.pptx` is a zip; the extractor only reads `ppt/slides/slideN.xml` and `ppt/notesSlides/notesSlideN.xml`, so the fixture zips exactly those parts (plus a minimal `[Content_Types].xml`).

```python
#!/usr/bin/env python3
"""Generate tests/tmp/sample.pptx — 3 slides with titles, bodies, and one notes slide."""
import sys, zipfile
from pathlib import Path

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')

def sp(ph_type, *lines):
    paras = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines)
    ph = f'<p:ph type="{ph_type}"/>' if ph_type else "<p:ph/>"
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="1" name=""/><p:cNvSpPr/><p:nvPr>{ph}'
            f'</p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/>{paras}</p:txBody></p:sp>')

def slide(*shapes):
    return (f'<?xml version="1.0"?><p:sld {NS}><p:cSld><p:spTree>'
            f'{"".join(shapes)}</p:spTree></p:cSld></p:sld>')

def notes(*shapes):
    return (f'<?xml version="1.0"?><p:notes {NS}><p:cSld><p:spTree>'
            f'{"".join(shapes)}</p:spTree></p:cSld></p:notes>')

EVIL = ('<?xml version="1.0"?><!DOCTYPE bomb [<!ENTITY a "xx"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">'
        '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]>'
        f'<p:sld {NS}><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="1" name=""/><p:cNvSpPr/>'
        '<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/>'
        '<a:p><a:r><a:t>&c;</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')

out = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/tmp/sample.pptx")
evil = "--evil" in sys.argv
out.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out, "w") as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    if evil:
        z.writestr("ppt/slides/slide1.xml", EVIL)
    else:
        z.writestr("ppt/slides/slide1.xml", slide(sp("ctrTitle", "Model X: A Better Approach"), sp("subTitle", "Defense Presentation")))
        z.writestr("ppt/slides/slide2.xml", slide(sp("title", "Results"), sp("body", "Accuracy: 97%", "Beats baseline by 12 points")))
        z.writestr("ppt/slides/slide3.xml", slide(sp("title", "Future Work"), sp("body", "Scale to production")))
        z.writestr("ppt/notesSlides/notesSlide2.xml", notes(sp("body", "Mention the ablation only if asked.")))
print(out)
```

- [ ] **Step 2: Write the failing test `tests/test_extract.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tests/make_fixture_pptx.py tests/tmp/sample.pptx >/dev/null
OUT=$(python3 scripts/extract_pptx.py tests/tmp/sample.pptx --json)
echo "$OUT" | jq -e '.slideCount == 3' >/dev/null
echo "$OUT" | jq -e '.slides[0].title == "Model X: A Better Approach"' >/dev/null
echo "$OUT" | jq -e '.slides[1].body | index("Accuracy: 97%") != null' >/dev/null
echo "$OUT" | jq -e '.slides[1].notes | contains("ablation")' >/dev/null
echo "$OUT" | jq -e '.slides[2].title == "Future Work"' >/dev/null
# markdown mode prints a "## Slide 2" header
python3 scripts/extract_pptx.py tests/tmp/sample.pptx | grep -q "## Slide 2"
# entity-bomb slide (XXE/billion-laughs guard): completes fast, slide marked unparseable
python3 tests/make_fixture_pptx.py tests/tmp/evil.pptx --evil >/dev/null
timeout 10 python3 scripts/extract_pptx.py tests/tmp/evil.pptx --json | jq -e \
  '.slides[0].body | index("[unparseable slide XML]") != null' >/dev/null
# unreadable file -> exit 2 with ERROR line
set +e
python3 scripts/extract_pptx.py tests/make_fixture_pptx.py --json 2>&1 | grep -q "^ERROR:"; G=$?
python3 scripts/extract_pptx.py tests/make_fixture_pptx.py --json >/dev/null 2>&1; C=$?
set -e
[ "$G" -eq 0 ] && [ "$C" -eq 2 ]
echo "PASS test_extract"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `chmod +x tests/test_extract.sh && bash tests/test_extract.sh`
Expected: FAIL — `python3: can't open file .../scripts/extract_pptx.py`.

- [ ] **Step 4: Write `scripts/extract_pptx.py`**

```python
#!/usr/bin/env python3
"""Extract per-slide text + speaker notes from a .pptx. Stdlib only.

Usage: extract_pptx.py DECK.pptx [--json]
Exit 0 on success; exit 2 with "ERROR: ..." on unreadable/empty deck.
"""
import json, re, sys, zipfile
import xml.etree.ElementTree as ET

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
TITLE_TYPES = {"title", "ctrTitle"}
MAX_PART_BYTES = 10 * 1024 * 1024

def safe_fromstring(xml_bytes):
    """OOXML parts must not contain DTDs — reject them (XXE/billion-laughs guard)."""
    if len(xml_bytes) > MAX_PART_BYTES:
        raise ET.ParseError("part too large")
    if b"<!DOCTYPE" in xml_bytes or b"<!ENTITY" in xml_bytes:
        raise ET.ParseError("DTD/entity declarations are not allowed in OOXML parts")
    return ET.fromstring(xml_bytes)

def shape_paragraphs(sp):
    """List of paragraph strings in one shape (runs joined, empty dropped)."""
    out = []
    for para in sp.iter(A + "p"):
        text = "".join(t.text or "" for t in para.iter(A + "t")).strip()
        if text:
            out.append(text)
    return out

def parse_slide(xml_bytes):
    root = safe_fromstring(xml_bytes)
    title, body = "", []
    for sp in root.iter(P + "sp"):
        ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
        ptype = ph.get("type", "") if ph is not None else ""
        paras = shape_paragraphs(sp)
        if not paras:
            continue
        if ptype in TITLE_TYPES and not title:
            title = paras[0]
            body.extend(paras[1:])
        else:
            body.extend(paras)
    return title, body

def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    if len(args) != 1:
        print("ERROR: usage: extract_pptx.py DECK.pptx [--json]", file=sys.stderr); return 2
    try:
        z = zipfile.ZipFile(args[0])
    except (zipfile.BadZipFile, OSError) as e:
        print(f"ERROR: not a readable .pptx: {e}", file=sys.stderr); return 2
    slide_re = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
    notes_re = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")
    slides, notes = {}, {}
    for name in z.namelist():
        m = slide_re.match(name)
        if m:
            slides[int(m.group(1))] = name
        m = notes_re.match(name)
        if m:
            notes[int(m.group(1))] = name
    if not slides:
        print("ERROR: no slides found (image-only or not a presentation?)", file=sys.stderr); return 2
    result = []
    for n in sorted(slides):
        try:
            title, body = parse_slide(z.read(slides[n]))
        except ET.ParseError:
            title, body = "", ["[unparseable slide XML]"]
        note_text = ""
        if n in notes:
            try:
                _, nbody = parse_slide(z.read(notes[n]))
                note_text = " ".join(nbody)
            except ET.ParseError:
                pass
        result.append({"n": n, "title": title, "body": body, "notes": note_text})
    if as_json:
        print(json.dumps({"slideCount": len(result), "slides": result}, ensure_ascii=False))
    else:
        for s in result:
            print(f"## Slide {s['n']}: {s['title']}".rstrip(": "))
            for line in s["body"]:
                print(f"- {line}")
            if s["notes"]:
                print(f"> Speaker notes: {s['notes']}")
            print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `bash tests/test_extract.sh`
Expected: `PASS test_extract`

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_pptx.py tests/make_fixture_pptx.py tests/test_extract.sh
git commit -m "feat: stdlib PPTX extractor with generated fixture + tests"
```

---

### Task 3: Defense server (`defense_server.py`)

**Files:**
- Create: `scripts/defense_server.py`
- Create: `tests/test_server.sh`

**Interfaces:**
- Consumes: `ui/index.html` (Task 4) — serves it at `/`; until Task 4 lands it serves a placeholder if the file is missing.
- Produces: Server CLI + Answer POST contracts (see Shared interface contracts). Protocol v2 (Task 5) instructs the examiner to launch it and watch `inbox/`.

- [ ] **Step 1: Write the failing test `tests/test_server.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=tests/tmp/live; rm -rf "$DIR"; mkdir -p "$DIR"
python3 scripts/defense_server.py --dir "$DIR" --port 8431 --no-open > tests/tmp/server.log 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 20); do curl -sf http://127.0.0.1:8431/state >/dev/null 2>&1 && break; sleep 0.25; done
grep -q "DEFENSE CONSOLE: http://127.0.0.1:8431" tests/tmp/server.log
# initial state auto-created with phase briefing
curl -sf http://127.0.0.1:8431/state | jq -e '.phase == "briefing"' >/dev/null
# UI served (Task 4 file, or built-in placeholder before it exists)
curl -sf http://127.0.0.1:8431/ | grep -qi "defense"
# post an answer -> numbered inbox file with receivedAt
curl -sf -X POST http://127.0.0.1:8431/answer -H 'Content-Type: application/json' \
  -d '{"qid":1,"answer":"Because the ablation isolates the encoder."}' | jq -e '.ok == true' >/dev/null
[ -f "$DIR/inbox/answer-0001.json" ]
jq -e '.qid == 1 and (.answer|length) > 0 and .receivedAt > 0' "$DIR/inbox/answer-0001.json" >/dev/null
# second answer increments
curl -sf -X POST http://127.0.0.1:8431/answer -H 'Content-Type: application/json' \
  -d '{"qid":2,"answer":"x"}' >/dev/null
[ -f "$DIR/inbox/answer-0002.json" ]
# malformed body -> 400, no file
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8431/answer -d 'not json')
[ "$CODE" = "400" ] && [ ! -f "$DIR/inbox/answer-0003.json" ]
# empty answer -> 400
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8431/answer \
  -H 'Content-Type: application/json' -d '{"qid":3,"answer":"  "}')
[ "$CODE" = "400" ]
# SSE: update state.json -> event with the new question arrives within 3s
( sleep 0.5; printf '%s' '{"phase":"question","qid":1,"question":"Why 5-fold?"}' > "$DIR/state.json.tmp"; mv "$DIR/state.json.tmp" "$DIR/state.json" ) &
timeout 5 curl -sN http://127.0.0.1:8431/events | head -c 2000 | grep -q "Why 5-fold?"
echo "PASS test_server"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_server.sh && bash tests/test_server.sh`
Expected: FAIL — `can't open file .../scripts/defense_server.py`.

- [ ] **Step 3: Write `scripts/defense_server.py`**

```python
#!/usr/bin/env python3
"""Live Defense console server. Stdlib only.

Bridges the examiner session and the browser console:
  examiner -> browser : writes <dir>/state.json  (served via SSE /events)
  browser  -> examiner: POST /answer -> <dir>/inbox/answer-NNNN.json

Usage: defense_server.py --dir STATE_DIR [--port N] [--no-open]
"""
import argparse, json, socket, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UI_FILE = Path(__file__).resolve().parent.parent / "ui" / "index.html"
PLACEHOLDER = "<!doctype html><title>Defense Console</title><h1>Defense console UI not built yet</h1>"
_inbox_lock = threading.Lock()

def pick_port(preferred):
    candidates = [preferred] if preferred else list(range(8420, 8470))
    for port in candidates:
        with socket.socket() as s:
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
    except (OSError, json.JSONDecodeError):
        return None

class Handler(BaseHTTPRequestHandler):
    state_dir = None  # set in main()

    def log_message(self, *args):
        pass

    def _reply(self, code, data, ctype="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
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
            n = 1 + max([int(f.stem.split("-")[1]) for f in inbox.glob("answer-*.json")] or [0])
            name = f"answer-{n:04d}.json"
            record = {"qid": payload.get("qid"), "answer": answer, "receivedAt": int(time.time())}
            (inbox / name).write_text(json.dumps(record, ensure_ascii=False))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test_server.sh`
Expected: `PASS test_server`

- [ ] **Step 5: Commit**

```bash
git add scripts/defense_server.py tests/test_server.sh
git commit -m "feat: live-defense bridge server (SSE state push, numbered answer inbox)"
```

---

### Task 4: Viva console UI (`ui/index.html`) + round-trip harness

**Files:**
- Create: `ui/index.html`
- Create: `tests/mock_examiner.py`
- Create: `tests/test_console.sh`

**Interfaces:**
- Consumes: Server endpoints and `state.json` schema (Task 3 / Shared contracts).
- Produces: the console UI that protocol v2's Document D web mode (Task 5) opens for the candidate.

> **REQUIRED at execution time:** before writing or styling this file, read the `dataviz` skill (the rubric bars/coverage strip are meters) and the `frontend-design` skill (visual direction). The code below is the working contract baseline — improve its aesthetics freely, but keep every `id`, endpoint, and behavior.

- [ ] **Step 1: Write the failing round-trip test**

`tests/mock_examiner.py` — stands in for the examiner session: waits for one inbox answer, then writes feedback + the next question:

```python
#!/usr/bin/env python3
"""Wait for the next inbox answer, then write feedback + next question to state.json."""
import json, sys, time
from pathlib import Path

state_dir = Path(sys.argv[1])
inbox = state_dir / "inbox"
baseline = len(list(inbox.glob("answer-*.json")))
deadline = time.time() + 15
while len(list(inbox.glob("answer-*.json"))) <= baseline:
    if time.time() > deadline:
        sys.exit("TIMEOUT waiting for answer")
    time.sleep(0.2)
latest = sorted(inbox.glob("answer-*.json"))[-1]
answer = json.loads(latest.read_text())
new_state = {
    "phase": "question", "qid": 2,
    "question": "Name the strongest baseline you did NOT compare against, and why.",
    "tier": "T5", "lens": "Domain Expert", "category": "13 Comparison to alternatives",
    "grounding": "Ch.5 baselines table",
    "scoreboard": [{"dim": "Rigor", "score": 2, "max": 3}],
    "coverage": [{"label": "Ch.4", "status": "done"}, {"label": "Ch.5", "status": "current"}],
    "feedback": {"forQid": answer["qid"], "verdict": "acceptable", "note": "Mechanism named; no quantity given."},
}
tmp = state_dir / "state.json.tmp"
tmp.write_text(json.dumps(new_state))
tmp.rename(state_dir / "state.json")
print("mock examiner responded")
```

`tests/test_console.sh` — no browser needed; proves the full loop and that the UI file carries its required elements:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=tests/tmp/console; rm -rf "$DIR"; mkdir -p "$DIR"
python3 scripts/defense_server.py --dir "$DIR" --port 8432 --no-open >/dev/null 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 20); do curl -sf http://127.0.0.1:8432/state >/dev/null 2>&1 && break; sleep 0.25; done
# UI structural contract: required ids + behaviors present in served page
PAGE=$(curl -sf http://127.0.0.1:8432/)
for id in question-card answer-input send-btn scoreboard coverage timer feedback-banner verdict-view; do
  echo "$PAGE" | grep -q "id=\"$id\"" || { echo "MISSING #$id"; exit 1; }
done
echo "$PAGE" | grep -q "EventSource" && echo "$PAGE" | grep -q "prefers-color-scheme"
# seed a question
printf '%s' '{"phase":"question","qid":1,"question":"Why 5-fold?","tier":"T3","lens":"Methodologist","timerStartedAt":1783300000,"durationMin":60}' > "$DIR/state.json.tmp"
mv "$DIR/state.json.tmp" "$DIR/state.json"
# candidate answers (as the UI's fetch would) while mock examiner waits
python3 tests/mock_examiner.py "$DIR" &
MOCK=$!
sleep 0.5
curl -sf -X POST http://127.0.0.1:8432/answer -H 'Content-Type: application/json' \
  -d '{"qid":1,"answer":"It balances variance and compute for our N."}' >/dev/null
wait $MOCK
# examiner's new state reaches the polling endpoint (same JSON the SSE pushes)
curl -sf http://127.0.0.1:8432/state | jq -e '.qid == 2 and .feedback.forQid == 1' >/dev/null
echo "PASS test_console"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_console.sh && bash tests/test_console.sh`
Expected: FAIL at the UI structural check (placeholder page has no `#question-card`).

- [ ] **Step 3: Write `ui/index.html`**

Complete baseline (single file, no external requests). Behavior contract: connect SSE, render each phase, POST answers, lock input while awaiting feedback, count timer up from `timerStartedAt` with `durationMin` remaining, tolerate missing fields.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thesis Defense — Live Console</title>
<style>
  :root {
    --bg: #f6f4ef; --panel: #ffffff; --ink: #1d1c1a; --muted: #6d675e;
    --accent: #7a1f2b; --accent-ink: #fff; --line: #e2ddd3;
    --ok: #2e6e4e; --warn: #a8672a; --bad: #a8322f;
    font-size: 16px;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#171614; --panel:#201f1c; --ink:#ece8e0; --muted:#9a938a;
            --accent:#c9505e; --line:#33312c; }
  }
  * { box-sizing: border-box; margin: 0; }
  body { background: var(--bg); color: var(--ink);
         font-family: Georgia, "Times New Roman", serif;
         min-height: 100vh; display: flex; flex-direction: column; }
  header { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap;
           padding: 1rem 1.5rem; border-bottom: 2px solid var(--accent); }
  header h1 { font-size: 1.1rem; letter-spacing: .12em; text-transform: uppercase; }
  #timer { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--muted); }
  #qmeta { display: flex; gap: .5rem; flex-wrap: wrap; padding: 1rem 1.5rem 0; }
  .chip { font-family: system-ui, sans-serif; font-size: .72rem; letter-spacing: .05em;
          padding: .2rem .6rem; border: 1px solid var(--line); border-radius: 999px;
          color: var(--muted); }
  .chip.tier { border-color: var(--accent); color: var(--accent); font-weight: 700; }
  main { flex: 1; max-width: 54rem; width: 100%; margin: 0 auto; padding: 0 1.5rem 2rem; }
  #question-card { background: var(--panel); border: 1px solid var(--line);
                   border-left: 4px solid var(--accent); border-radius: 6px;
                   padding: 1.5rem; margin-top: 1rem; }
  #question-text { font-size: 1.35rem; line-height: 1.45; }
  #grounding { margin-top: .75rem; font-size: .85rem; color: var(--muted); font-style: italic; }
  #feedback-banner { display: none; margin-top: 1rem; padding: .9rem 1.2rem; border-radius: 6px;
                     background: var(--panel); border: 1px solid var(--line);
                     font-family: system-ui, sans-serif; font-size: .9rem; }
  #feedback-banner.show { display: block; }
  #answer-area { margin-top: 1rem; display: flex; flex-direction: column; gap: .6rem; }
  #answer-input { min-height: 7.5rem; padding: .9rem; font: inherit; font-size: 1rem;
                  background: var(--panel); color: var(--ink);
                  border: 1px solid var(--line); border-radius: 6px; resize: vertical; }
  #send-btn { align-self: flex-end; font-family: system-ui, sans-serif; font-weight: 600;
              background: var(--accent); color: var(--accent-ink); border: 0;
              padding: .6rem 1.6rem; border-radius: 6px; cursor: pointer; }
  #send-btn:disabled { opacity: .45; cursor: wait; }
  #status-line { font-family: system-ui, sans-serif; font-size: .8rem; color: var(--muted); }
  section h2 { font-family: system-ui, sans-serif; font-size: .75rem; letter-spacing: .1em;
               text-transform: uppercase; color: var(--muted); margin: 1.6rem 0 .5rem; }
  #scoreboard .row { display: grid; grid-template-columns: 11rem 1fr 2.5rem;
                     align-items: center; gap: .6rem; margin: .3rem 0;
                     font-family: system-ui, sans-serif; font-size: .85rem; }
  .bar { height: .55rem; background: var(--line); border-radius: 999px; overflow: hidden; }
  .bar > i { display: block; height: 100%; background: var(--accent); }
  #coverage { display: flex; gap: .4rem; flex-wrap: wrap; }
  .cov { font-family: system-ui, sans-serif; font-size: .78rem; padding: .25rem .7rem;
         border-radius: 4px; border: 1px solid var(--line); color: var(--muted); }
  .cov.done    { background: var(--ok);   color: #fff; border-color: transparent; }
  .cov.partial { background: var(--warn); color: #fff; border-color: transparent; }
  .cov.current { outline: 2px solid var(--accent); color: var(--ink); font-weight: 700; }
  #red-flags li { color: var(--bad); font-family: system-ui, sans-serif; font-size: .85rem; }
  #verdict-view { display: none; background: var(--panel); border: 2px solid var(--accent);
                  border-radius: 6px; padding: 2rem; margin-top: 1.5rem; text-align: center; }
  #verdict-view.show { display: block; }
  #verdict-outcome { font-size: 1.6rem; color: var(--accent); margin-bottom: .6rem; }
  #briefing { color: var(--muted); font-style: italic; padding: 2.5rem 0; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>⚖ Thesis Defense — Live</h1>
  <span class="chip" id="qcount"></span>
  <span id="timer">—</span>
</header>
<div id="qmeta"></div>
<main>
  <p id="briefing">Waiting for the examiner to open the session…</p>
  <div id="question-card" hidden>
    <p id="question-text"></p>
    <p id="grounding"></p>
  </div>
  <div id="feedback-banner"></div>
  <div id="answer-area" hidden>
    <textarea id="answer-input" placeholder="Answer as you would in the viva room — specifics, numbers, named alternatives."></textarea>
    <button id="send-btn">Submit answer ➤</button>
    <span id="status-line"></span>
  </div>
  <div id="verdict-view">
    <div id="verdict-outcome"></div>
    <p id="verdict-summary"></p>
  </div>
  <section><h2>Scoreboard</h2><div id="scoreboard"></div></section>
  <section><h2>Coverage</h2><div id="coverage"></div></section>
  <section><h2>Red flags</h2><ul id="red-flags"></ul></section>
</main>
<script>
  const $ = id => document.getElementById(id);
  let current = {}, awaiting = false, timerHandle = null;

  function esc(s) { const d = document.createElement("span"); d.textContent = s ?? ""; return d.innerHTML; }

  function renderTimer(state) {
    clearInterval(timerHandle);
    if (!state.timerStartedAt) { $("timer").textContent = "—"; return; }
    const tick = () => {
      const el = Math.max(0, Math.floor(Date.now() / 1000 - state.timerStartedAt));
      const mm = String(Math.floor(el / 60)).padStart(2, "0"), ss = String(el % 60).padStart(2, "0");
      let rem = "";
      if (state.durationMin) {
        const left = state.durationMin * 60 - el;
        rem = left >= 0 ? ` · ${Math.ceil(left / 60)} min left` : " · overtime";
      }
      $("timer").textContent = `⏱ ${mm}:${ss}${rem}`;
    };
    tick(); timerHandle = setInterval(tick, 1000);
  }

  function render(state) {
    current = state;
    $("briefing").hidden = state.phase !== "briefing";
    const isQ = state.phase === "question" || state.phase === "feedback";
    $("question-card").hidden = !isQ;
    $("answer-area").hidden = !isQ;
    if (isQ) {
      $("question-text").textContent = state.question || "";
      $("grounding").textContent = state.grounding ? `Grounding: ${state.grounding}` : "";
      $("qcount").textContent = state.qid ? `Q${state.qid}` : "";
      $("qmeta").innerHTML = ["tier", "lens", "category"]
        .filter(k => state[k])
        .map(k => `<span class="chip ${k === "tier" ? "tier" : ""}">${esc(state[k])}</span>`).join("");
      if (awaiting && state.qid !== awaiting.qid) {           // examiner moved on
        awaiting = false; $("answer-input").value = ""; $("send-btn").disabled = false;
        $("status-line").textContent = "";
      }
    }
    const fb = state.feedback;
    $("feedback-banner").className = fb ? "show" : "";
    if (fb) $("feedback-banner").innerHTML =
      `<strong>Q${esc(fb.forQid)} — ${esc(fb.verdict || "")}</strong>: ${esc(fb.note || "")}`;
    $("scoreboard").innerHTML = (state.scoreboard || []).map(r =>
      `<div class="row"><span>${esc(r.dim)}</span><span class="bar"><i style="width:${100 * (r.score || 0) / (r.max || 3)}%"></i></span><span>${esc(r.score)}/${esc(r.max)}</span></div>`).join("");
    $("coverage").innerHTML = (state.coverage || []).map(c =>
      `<span class="cov ${esc(c.status)}">${esc(c.label)}</span>`).join("");
    $("red-flags").innerHTML = (state.redFlags || []).map(f => `<li>${esc(f)}</li>`).join("");
    const v = state.phase === "verdict" ? (state.verdict || {}) : null;
    $("verdict-view").className = v ? "show" : "";
    if (v) {
      $("verdict-outcome").textContent = v.outcome || "Verdict";
      $("verdict-summary").textContent = v.summary || "";
      $("answer-area").hidden = true; $("question-card").hidden = true;
    }
    renderTimer(state);
  }

  async function send() {
    const answer = $("answer-input").value.trim();
    if (!answer || awaiting) return;
    awaiting = { qid: current.qid };
    $("send-btn").disabled = true;
    $("status-line").textContent = "Submitted — the examiner is deliberating…";
    try {
      const r = await fetch("/answer", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qid: current.qid, answer }) });
      if (!r.ok) throw new Error();
    } catch {
      awaiting = false; $("send-btn").disabled = false;
      $("status-line").textContent = "Send failed — is the server still running?";
    }
  }
  $("send-btn").addEventListener("click", send);
  $("answer-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
  });

  const es = new EventSource("/events");
  es.onmessage = e => { try { render(JSON.parse(e.data)); } catch {} };
  es.onerror = () => { $("status-line").textContent = "Reconnecting…"; };
  fetch("/state").then(r => r.json()).then(render).catch(() => {});
</script>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test_console.sh`
Expected: `PASS test_console`

- [ ] **Step 5: Also re-run the server test (placeholder branch no longer exercised, must still pass)**

Run: `bash tests/test_server.sh`
Expected: `PASS test_server`

- [ ] **Step 6: Commit**

```bash
git add ui/index.html tests/mock_examiner.py tests/test_console.sh
git commit -m "feat: live viva console UI + full answer round-trip harness"
```

---

### Task 5: Protocol v2 (`skills/thesis-examiner/references/protocol.md`)

**Files:**
- Create: `skills/thesis-examiner/references/protocol.md` (from v1 source, then 9 edits)

**Interfaces:**
- Consumes: v1 protocol text from `<v1-skill-source>` (after `--- BEGIN EXAMINER PROTOCOL ---`).
- Produces: the single protocol file both wrappers (Task 6) load. Section names referenced by wrappers: "SECTION 0", "Document D", "Web Console mode".

- [ ] **Step 1: Extract v1 protocol into the new file**

```bash
mkdir -p skills/thesis-examiner/references
sed -n '/^--- BEGIN EXAMINER PROTOCOL ---$/,$p' <v1-skill-source> \
  | tail -n +2 > skills/thesis-examiner/references/protocol.md
head -1 skills/thesis-examiner/references/protocol.md
```
Expected: first line is blank or starts `You are **Professor Examiner**`. If the source file is missing, STOP and report — do not reconstruct from memory.

- [ ] **Step 2: Edit A — remove the numeric target (Constraint 8)**

Replace the sentence beginning `Target **150+ questions**` (in constraint 8, Section 1) — the old text reads:

> Target **150+ questions** for a full-length thesis, scaled up for longer/richer work. For shorter or narrower theses, produce the **maximum number of fully-grounded, non-generic questions the material genuinely supports**, and report the achieved count with a one-line justification. Constraints 1–2 always override the numeric target — **never pad to hit a number.**

with:

> There is **NO numeric target, floor, or ceiling** on question count. The only stopping rule is **coverage saturation**: every populated coverage-matrix cell filled, every chapter, central claim, contribution, and stated limitation (and, when slides are supplied, every slide) examined, every central claim pressed to ≥T3 — and then **loop-until-dry**: keep generating until two consecutive passes over the thesis surface no new fully-grounded, non-generic question. Report the achieved count as an output statistic only. Constraints 1–2 always govern — **never pad; exhaustive ≠ repetitive.**

- [ ] **Step 3: Edit B — Section 0.5 count language**

Replace `Batching does **not** relax the question-count or full-matrix requirements` with `Batching does **not** relax the coverage-saturation or full-matrix requirements`.

- [ ] **Step 4: Edit C — Section 9 checklist count item**

Replace the checklist line beginning `- [ ] Question count meets 150+` with:

> - [ ] Coverage saturation reached: matrix reported with per-cell counts; no populated cell empty; every chapter + central claim + contribution + stated limitation (+ every slide, if supplied) examined; every central claim/contribution pressed to ≥T3; loop-until-dry confirmed (two consecutive dry passes); achieved question count reported as a statistic.

- [ ] **Step 5: Edit D — Section 0: optional slides input (insert as new subsection 0.1b, immediately after 0.1)**

> **0.1b Optional second input — presentation slides (.pptx).** The user MAY supply the defense slide deck. If given a `.pptx` path and you can execute scripts, run `python3 "$CLAUDE_PLUGIN_ROOT/scripts/extract_pptx.py" <deck.pptx> --json` (fall back to the same script under the plugin's install directory, or to any pasted slide text). If extraction fails or the deck is image-only, say so by name, skip all slides features, and proceed thesis-only — never fabricate slide content. When slides ARE available, activate: ingestion Pass 5 (deck forensics), question categories 24–25, the Per-Slide Question Map, and the Presentation-quality rubric dimension. When absent, this protocol behaves exactly as if the slides module did not exist.

- [ ] **Step 6: Edit E — Section 2: Pass 5 (append after Pass 4)**

> - **Pass 5 — Deck forensics (only when slides are supplied):** compare every slide claim, number, and figure against the thesis. Hunt: numbers that differ between deck and document; claims stated more strongly on slides than in the text; results shown on slides that appear nowhere in the thesis; prettified figures (truncated axes, cherry-picked subsets, removed error bars); omissions of stated limitations; contribution statements that grew in transit. **Every discrepancy becomes a grounded question anchored to both the slide number and the thesis location.**

- [ ] **Step 7: Edit F — Section 5.4: categories 24–25 (append after Category 23)**

> **Categories 24–25 — SLIDES MODULE (add to every paradigm bank when slides are supplied):**
> **(24) Slides↔Thesis consistency** — reconcile every deck/document discrepancy from Pass 5: "Slide 9 claims 97%; Table 4.2 reports 94% — which is correct, and why does the other exist?"
> **(25) Presentation-delivery critique** — clarity and honesty of the deck itself: figure honesty (axes, error bars), time allocation across the argument, what each slide invites a hostile committee member to ask, what the deck omits that the committee will notice.

- [ ] **Step 8: Edit G — Section 6 matrix rows + Section 7.1 Document A subsection**

In Section 6, extend the sentence enumerating matrix rows (`Also enumerate every chapter/section, every central claim, every contribution statement, and every self-stated limitation.`) to end: `..., and — when slides are supplied — every slide as its own row.`

In Section 7.1, extend the dedicated-subsections sentence (`**Dedicated subsections** for: scenario/case-based "what-ifs" ...`) to include: `; and — when slides are supplied — a **Per-Slide Question Map** (for each slide in running order: the probes an examiner would fire off it, so the candidate can rehearse the talk).`

- [ ] **Step 9: Edit H — Section 8.1 rubric dimension**

Append after the rubric table:

> **Slides supplied?** Add dimension **8 — Presentation quality (slides↔thesis fidelity, figure honesty, clarity of the spoken argument), weight 10%**, and renormalize the other weights proportionally (multiply each by 0.9). Document-only examinations keep the original seven dimensions and weights.

- [ ] **Step 10: Edit I — Section 7.4 Document D: Web Console mode (append to 7.4)**

> **Web Console mode (preferred when the plugin's scripts are available).** Run the live defense in the browser:
> 1. Launch: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/defense_server.py" --dir <output-dir>/.live` (background). It prints `DEFENSE CONSOLE: <url>` and opens the browser.
> 2. You (the examiner) communicate ONLY by atomically writing `<output-dir>/.live/state.json` (write `state.json.tmp`, then rename). Fields: `phase` (briefing|question|feedback|verdict), `qid`, `question`, `tier`, `lens`, `category`, `grounding`, `timerStartedAt` (epoch s), `durationMin`, `scoreboard` [{dim,score,max}], `coverage` [{label,status: pending|partial|current|done}], `redFlags` [], `feedback` {forQid,verdict,note}, `verdict` {outcome,summary,perDimension}.
> 3. The candidate answers in the browser; each answer lands as `<output-dir>/.live/inbox/answer-NNNN.json`. Wait for it with a background watcher, e.g.:
>    `D=<output-dir>/.live/inbox; B=$(ls "$D" | wc -l); while [ "$(ls "$D" | wc -l)" -le "$B" ]; do sleep 2; done` (run in background; when it exits, read the newest inbox file).
> 4. Score the answer against the Section 8 rubric, then write the next `state.json`: `feedback` for the answered qid + the next `question` (difficulty spiked off weak answers per Constraint 9 and Section 5.2). Update `scoreboard`, `coverage`, `redFlags` every turn.
> 5. To end: write `phase: "verdict"` with the full verdict object, then write `Defense-Transcript.md` (every Q, answer, score, and flag) next to Documents A–C.
> **Fallback:** if `python3` is unavailable or the server cannot start, say so and run Document D in chat exactly as described above (one question per turn), which requires no infrastructure.

- [ ] **Step 11: Edit J — Section 9 checklist: slides items (append to the checklist)**

> - [ ] SLIDES (only when supplied): Pass 5 deck forensics completed; every discrepancy converted to a question; categories 24–25 populated; Per-Slide Question Map present covering every slide; Presentation-quality rubric dimension added and weights renormalized.

- [ ] **Step 12: Verify all edits**

```bash
F=skills/thesis-examiner/references/protocol.md
! grep -q "150+" "$F"                      # no numeric target survives
grep -q "coverage saturation" "$F"
grep -q "Pass 5" "$F"
grep -q "Categories 24–25" "$F"
grep -q "Per-Slide Question Map" "$F"
grep -q "Presentation quality" "$F"
grep -q "Web Console mode" "$F"
grep -q "0.1b" "$F"
grep -c "defense_server.py" "$F"           # expect 1
echo OK
```
Expected: `OK` (and the grep -c prints 1).

- [ ] **Step 13: Commit**

```bash
git add skills/thesis-examiner/references/protocol.md
git commit -m "feat: examiner protocol v2 — slides module, web-console Document D, no numeric question target"
```

---

### Task 6: Wrappers (SKILL.md + agent) and README

**Files:**
- Create: `skills/thesis-examiner/SKILL.md`
- Create: `agents/thesis-examiner.md`
- Create: `README.md`

**Interfaces:**
- Consumes: `references/protocol.md` (Task 5), scripts (Tasks 2–3).
- Produces: the plugin's user-facing entry points; installed names `thesis-examiner` (skill) and `thesis-examiner` (agent).

- [ ] **Step 1: Write `skills/thesis-examiner/SKILL.md`**

```markdown
---
name: thesis-examiner
description: Turn this session into a rigorous external thesis-defense (viva) examiner. Use when the user supplies a thesis/dissertation (PDF path or pasted text), optionally with PowerPoint defense slides (.pptx), and wants exhaustive defense questions from easy to extreme, model answers, a grading kit, slides cross-examination, or a live mock defense in the browser. Trigger: /thesis-examiner.
---

# Thesis Defense Examiner

The user invoked `/thesis-examiner`. You will run the full examiner protocol.

**Step 1 — Load the protocol.** Read `references/protocol.md` (relative to this skill's directory) IN FULL before doing anything else. It is the complete examination protocol; this file is only the activation wrapper.

**Step 2 — Gather inputs (interactive mode):**
1. Thesis: PDF path (you can Read PDFs) or pasted text. Required — never proceed without it, never invent content.
2. Slides: optional `.pptx` path. Extract with `python3 "$CLAUDE_PLUGIN_ROOT/scripts/extract_pptx.py" <deck> --json`. If it fails, follow protocol §0.1b (warn, continue thesis-only).
3. Calibration facts (protocol §0.3) if the user knows them; otherwise proceed on stated PROVISIONAL defaults.

**Step 3 — Execute the protocol** with its interactive segmentation (pause for "continue" between documents). For Document D, prefer the Web Console mode (protocol §7.4); the server lives at `$CLAUDE_PLUGIN_ROOT/scripts/defense_server.py`.
```

- [ ] **Step 2: Write `agents/thesis-examiner.md`**

```markdown
---
name: thesis-examiner
description: Generate a rigorous thesis-defense examination from a thesis PDF/text (optionally plus a .pptx slide deck) — exhaustive viva question bank, model answers, grading kit, slides cross-examination. Dispatch with the thesis file path or text, optional slides path, any calibration facts (degree level, institution, format, duration), and an output directory.
tools: Read, Write, Grep, Glob, Bash, WebSearch, WebFetch, TodoWrite
---

# Thesis Defense Examiner (headless subagent)

**FIRST ACTION — load the protocol.** Read `${CLAUDE_PLUGIN_ROOT}/skills/thesis-examiner/references/protocol.md` in full. If that path did not expand or does not exist, locate it with Glob: `~/.claude/plugins/**/skills/thesis-examiner/references/protocol.md`. Execute that protocol under these headless overrides:

- Inputs (thesis path/text, optional .pptx path, calibration facts, output directory) arrive in your dispatch prompt. If the thesis is missing, return a one-line request for it and stop. Never fabricate thesis or slide content.
- Do NOT pause for "continue". Produce Document 0, the Section-4 ledger, Documents A, B, C in sequence until complete; note Document D is available on request (do not run it headless — it needs a live candidate).
- Missing calibration facts: state assumptions, mark grade mappings PROVISIONAL, proceed — never block.
- Slides given: extract with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extract_pptx.py" <deck> --json`; on failure follow protocol §0.1b.
- Output directory given: write each document to disk AS YOU FINISH IT and report exact paths; if you run low on output budget, finish the current file cleanly and write RESUME-FROM.md naming the exact continuation point.
- Web tools available → MODE: RESEARCH-ENABLED, else MODE: REASONING-ONLY with [NEEDS-VERIFICATION] tags (protocol §0.2).
```

- [ ] **Step 3: Write `README.md`**

Sections (write actual prose, ~80 lines): what it is (one paragraph + the four documents it produces); install (`/plugin marketplace add MA-Abuelmagd/thesis-examiner` then `/plugin install thesis-examiner@thesis-examiner`); usage — interactive (`/thesis-examiner` + thesis path + optional pptx), headless (dispatch the `thesis-examiner` agent with paths + output dir), live defense (what the console looks like, answer in browser, Ctrl/Cmd+Enter to send); inputs table (thesis required, slides optional, marking scheme optional); how it works (protocol → mastery brief → research → question bank → model answers → grading kit → live defense); requirements (`python3` for slides + console; degrades gracefully); roadmap (voice I/O in v2); license MIT.

- [ ] **Step 4: Verify wrappers carry no protocol text**

```bash
wc -l skills/thesis-examiner/SKILL.md agents/thesis-examiner.md   # each well under 60 lines
! grep -q "Professor Examiner" skills/thesis-examiner/SKILL.md
! grep -q "Professor Examiner" agents/thesis-examiner.md
echo OK
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add skills/thesis-examiner/SKILL.md agents/thesis-examiner.md README.md
git commit -m "feat: skill + agent wrappers over single protocol; README"
```

---

### Task 7: Retire loose copies and smoke-test the plugin locally

**Files:**
- Delete (outside repo): `~/.claude/skills/thesis-examiner/` and `~/.claude/agents/thesis-examiner.md`
- Create: `tests/test_plugin_smoke.sh`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: verified local installability; the removal that prevents skill/agent name collisions.

- [ ] **Step 1: Archive then remove the loose v1 copies** (v1 protocol text is preserved in git history AND still the extraction source was archived)

```bash
mkdir -p <output-dir>/v1-archive
cp <v1-skill-source> <output-dir>/v1-archive/SKILL-v1.md
cp ~/.claude/agents/thesis-examiner.md <output-dir>/v1-archive/agent-v1.md
rm -rf ~/.claude/skills/thesis-examiner
rm ~/.claude/agents/thesis-examiner.md
```

- [ ] **Step 2: Write `tests/test_plugin_smoke.sh`** — structural validation + headless sideload probe

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# structure
jq -e '.name == "thesis-examiner"' .claude-plugin/plugin.json >/dev/null
jq -e '.plugins[0].source == "./"' .claude-plugin/marketplace.json >/dev/null
[ -f skills/thesis-examiner/SKILL.md ]
[ -f skills/thesis-examiner/references/protocol.md ]
[ -f agents/thesis-examiner.md ]
[ -f ui/index.html ] && [ -f scripts/defense_server.py ] && [ -f scripts/extract_pptx.py ]
# all unit/integration suites green
bash tests/test_extract.sh >/dev/null && bash tests/test_server.sh >/dev/null && bash tests/test_console.sh >/dev/null
# headless sideload: the skill must be visible to a fresh claude session
OUT=$(claude -p --plugin-dir "$PWD" --allowedTools "" \
  "Reply with ONLY the exact name of any available skill whose name contains 'thesis'." 2>&1) || true
echo "$OUT" | grep -qi "thesis-examiner" || { echo "SIDELOAD CHECK FAILED: $OUT"; exit 1; }
echo "PASS test_plugin_smoke"
```

- [ ] **Step 3: Run it**

Run: `chmod +x tests/test_plugin_smoke.sh && bash tests/test_plugin_smoke.sh`
Expected: `PASS test_plugin_smoke`. If the `claude -p` probe fails because `--plugin-dir` is unsupported in the installed CLI version, replace that probe with `claude plugin validate .` and re-run; if neither exists, mark the step BLOCKED and surface to Mohamed rather than skipping silently.

- [ ] **Step 4: Commit**

```bash
git add tests/test_plugin_smoke.sh
git commit -m "test: plugin structure + headless sideload smoke test"
```

---

### Task 8: Portable prompt v2 + memory update

**Files:**
- Create: `docs/portable-prompt.md` (in repo)
- Overwrite: `~/WS/thesis-defense-examiner-prompt.md`
- Overwrite: `<output-dir>/RUN-ME-overnight-prompt.txt` (remove `150+`, add optional slides line)
- Modify: the account memory note for this tool

**Interfaces:**
- Consumes: `references/protocol.md` (Task 5).
- Produces: v2 portable prompt (usable outside Claude Code — no plugin scripts assumed).

- [ ] **Step 1: Build `docs/portable-prompt.md`**: the v1 "HOW TO USE" header block (updated to mention the optional PPTX: "attach the thesis PDF and optionally paste your slide text or attach the .pptx") followed by the FULL text of `references/protocol.md`, with one adaptation: in §0.1b and §7.4, note that outside the plugin, slides text may be pasted directly and Document D runs in chat mode (the web console needs the installed plugin). Generate by script, not by hand:

```bash
python3 - <<'EOF'
from pathlib import Path
proto = Path("skills/thesis-examiner/references/protocol.md").read_text()
header = """# UNIVERSAL THESIS DEFENSE EXAMINER — PORTABLE META-PROMPT (v2)

> **HOW TO USE:** Paste everything below into a fresh AI session, attach the thesis PDF
> (or paste its text) in the same message, and optionally add your defense slides —
> paste the slide text, or attach the .pptx if your session can read files. If you have
> the program's marking scheme, attach that too. Web tools on if available.
>
> Outside the Claude Code plugin: the Live Defense web console is unavailable — Document D
> runs in chat mode instead, as the protocol's fallback describes. Everything else is identical.
>
> `>>> ATTACH THE THESIS PDF HERE (+ optional slides) <<<`

---
"""
Path("docs/portable-prompt.md").write_text(header + proto)
print("wrote docs/portable-prompt.md", len(header + proto), "chars")
EOF
cp docs/portable-prompt.md ~/WS/thesis-defense-examiner-prompt.md
```

- [ ] **Step 2: Update the overnight prompt**: edit `<output-dir>/RUN-ME-overnight-prompt.txt` — replace the `Be EXHAUSTIVE: target 150+ grounded...` bullet with `Be EXHAUSTIVE: no question-count target or cap — stop only at coverage saturation (every chapter, claim, contribution, limitation, and slide examined; loop-until-dry), then report the achieved count.` and add a bullet `- Slides (optional): if I provide a .pptx path, extract it with the plugin's extract_pptx.py and run the slides module (Pass 5, categories 24-25, per-slide map).`

- [ ] **Step 3: Update the account memory note**: rewrite the "Installed in three interchangeable forms" section to say the tool is now a **plugin** at `~/WS/thesis-examiner` (GitHub `MA-Abuelmagd/thesis-examiner` once deployed), loose copies retired, portable prompt at the same path (v2), and add one line for the live console + slides module + no-numeric-target change.

- [ ] **Step 4: Verify + commit**

```bash
grep -q "0.1b" docs/portable-prompt.md && ! grep -q "150+" docs/portable-prompt.md
! grep -q "150+" <output-dir>/RUN-ME-overnight-prompt.txt
git add docs/portable-prompt.md
git commit -m "feat: portable meta-prompt v2 (slides-aware, chat-mode live defense)"
```

---

### Task 9: E2E on the real thesis — GATE: requires Mohamed's file path(s)

**Files:**
- Create: `tests/e2e-notes.md` (results log, committed)

This task cannot start until Mohamed provides the thesis PDF path (and optional PPTX). **Ask for it when reaching this task.**

- [ ] **Step 1: Documents run** — dispatch the plugin's `thesis-examiner` agent (headless) with the real thesis path (+ slides if given), output dir `<output-dir>/`. Verify: Mastery-Brief/Question-Bank/Model-Answers/Grading-Kit written; Question Bank shows the coverage matrix, no numeric-target language, per-slide map iff slides given; spot-check 5 random questions for real anchors (open the PDF at the cited location).
- [ ] **Step 2: Live-defense loop (scripted candidate)** — start `defense_server.py --dir <output-dir>/.live --no-open`; seed `state.json` with a real generated T3 question; use the Playwright MCP browser to open the URL, verify the question renders, type an answer, click Submit; confirm `inbox/answer-0001.json` appears; write a feedback+next-question state; verify the browser updates without reload; repeat for 3 questions; write `phase: verdict` and verify the verdict screen.
- [ ] **Step 3: Log results** in `tests/e2e-notes.md` (what ran, what was found, any fixes made) and commit:

```bash
git add tests/e2e-notes.md && git commit -m "test: E2E run on real thesis — results log"
```

---

### Task 10: Deploy to GitHub — GATE: confirm with Mohamed before pushing (public, outward-facing)

- [ ] **Step 1: Confirm** with Mohamed: repo will be public at `MA-Abuelmagd/thesis-examiner`; confirm the account has auth (`gh auth status`).
- [ ] **Step 2: Create + push**

```bash
gh repo create MA-Abuelmagd/thesis-examiner --public --source . --push
```
(If `gh` is authed to the work account instead, STOP and surface — do not push to the wrong account.)
- [ ] **Step 3: Install from GitHub** — Mohamed (or a headless probe if supported) runs: `/plugin marketplace add MA-Abuelmagd/thesis-examiner` → `/plugin install thesis-examiner@thesis-examiner` → verify `/thesis-examiner` triggers from the GitHub-installed copy.
- [ ] **Step 4: Tag**

```bash
git tag v1.0.0 && git push origin v1.0.0
```

---

## Self-review notes

- **Spec coverage:** §3 layout → Tasks 1,5,6; §4 slides module + no-count → Task 5 (Edits A–J), extractor Task 2; §5 console → Tasks 3,4; §5 error handling → server 400s (T3 test), chat fallback (Edit I), corrupt deck (extractor exit 2 + §0.1b); §6 wrappers → Task 6 (+ no-duplication grep); §7 tests → Tasks 2,3,4,7,9,10; §8 roadmap → README roadmap line (Task 6). Old-copy retirement (spec §2 table) → Task 7. Portable-prompt upgrade (spec §2 table) → Task 8.
- **Placeholders:** none — every script/test/UI file is complete; README and memory steps specify concrete content.
- **Type consistency:** `state.json` fields, `answer-NNNN.json`, endpoint names, and CLI flags are identical across Tasks 3, 4, 5 (Edit I), and 9 — all drawn from the Shared interface contracts block.
