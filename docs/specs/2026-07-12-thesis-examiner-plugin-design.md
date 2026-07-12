# Thesis Examiner Plugin — Design Spec

**Date:** 2026-07-12 · **Status:** Approved by Mohamed (this session)
**Repo:** `MA-Abuelmagd/thesis-examiner` (public GitHub; local at `~/WS/thesis-examiner/`)

## 1. Purpose

Upgrade the existing thesis-defense examiner (skill + subagent + portable prompt, built 2026-07-07)
into a single installable Claude Code **plugin** that:

1. accepts an **optional PowerPoint deck** alongside the thesis PDF,
2. adds a **two-way Live Defense web console** for Document D (mock viva),
3. installs **anywhere** via a public GitHub marketplace repo,
4. is **tested end-to-end on a real thesis** before the v1.0.0 deploy.

## 2. Decisions (locked)

| Decision                 | Choice                                                                                                                                                   |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live Defense UI          | Two-way viva console: question in browser, answer typed in browser, examiner scores live                                                                 |
| Server tech              | Pure Python **stdlib** (`http.server` + SSE + file bridge). No pip/node deps                                                                             |
| Distribution             | Public repo `MA-Abuelmagd/thesis-examiner`; repo is both marketplace and plugin                                                                          |
| Slides features          | Slides↔thesis cross-examination + presentation-delivery critique + per-slide question map                                                                |
| Slides optionality       | **Optional.** Absent PPTX ⇒ exam identical to today. Present ⇒ features activate                                                                         |
| Protocol source of truth | ONE `references/protocol.md`; skill and agent are thin wrappers that read it                                                                             |
| Old loose copies         | Deleted after plugin verified (`~/.claude/skills/thesis-examiner/`, `~/.claude/agents/thesis-examiner.md`). Portable prompt file upgraded to v2 and kept |
| Test asset               | Mohamed's real thesis PDF (path provided at test time)                                                                                                   |

## 3. Repo / plugin layout

```
thesis-examiner/
├── .claude-plugin/
│   ├── plugin.json              # name "thesis-examiner", version 1.0.0, author, description
│   └── marketplace.json         # lists this plugin, source "./"
├── skills/thesis-examiner/
│   ├── SKILL.md                 # interactive wrapper: intake, then read references/protocol.md
│   └── references/protocol.md   # examiner protocol v2 — SINGLE SOURCE OF TRUTH
├── agents/thesis-examiner.md    # headless wrapper: reads protocol via ${CLAUDE_PLUGIN_ROOT}
├── scripts/
│   ├── defense_server.py        # stdlib HTTP server: static UI, SSE state push, answer inbox
│   └── extract_pptx.py          # PPTX → JSON {slides: [{n, title, body, notes}]} via zipfile+XML
├── ui/index.html                # single-file viva console; all CSS/JS inline; light/dark aware
├── docs/specs/                  # this spec
├── README.md                    # install + usage
└── LICENSE                      # MIT
```

Install flow: `/plugin marketplace add MA-Abuelmagd/thesis-examiner` → `/plugin install thesis-examiner@thesis-examiner`.

## 4. Protocol v2 — slides module

All changes are **conditional on a PPTX being supplied**; without one, protocol behaves exactly as v1.

- **Section 0 intake**: optional `slides` input (path to .pptx or pre-extracted text). Run
  `extract_pptx.py` when given a path; on corrupt/image-only deck, warn by name, skip slides
  features, continue thesis-only. Never fabricate slide content.
- **Ingestion Pass 5 — deck forensics**: compare every slide claim/number/figure against the
  thesis: discrepancies (slide says 97%, Table 4.2 says 94%), over-simplifications,
  results on slides absent from the document, prettified/truncated-axis figures,
  contribution claims stated more strongly on slides than in text. Every discrepancy → grounded question.
- **New question categories** (added to every paradigm bank):
  **24 Slides↔Thesis consistency** and **25 Presentation-delivery critique**
  (clarity, figure honesty, time allocation, hostile-committee-member probes per slide).
- **Document A addition**: a **Per-Slide Question Map** subsection — for each slide, the probes
  an examiner would fire off it, so the candidate can rehearse the talk in running order.
- **Rubric**: paradigm-tunable **Presentation quality** dimension, scored only when slides exist
  (weights renormalize; document-only grading unchanged).
- **Document D**: new **web-console mode** (Section 5 below) as the preferred live-defense
  transport, with chat-mode fallback.
- **Question volume — no numeric target (v2 change, applies always)**: the v1 protocol's
  "target 150+" is REMOVED. No number may appear as a goal, floor, or ceiling. The only
  stopping rule is **coverage saturation**: every populated coverage-matrix cell filled,
  every chapter/claim/contribution/limitation (and, when slides exist, every slide) examined,
  every central claim pressed to ≥T3, then **loop-until-dry** — keep generating until two
  consecutive passes surface no new grounded, non-generic question. The achieved count is
  reported as an output statistic only. Grounding and non-genericity constraints still apply
  (no padding — exhaustive ≠ repetitive).

## 4b. Protocol v2.1 — semantic-questions mandate (Mohamed's E2E feedback, 2026-07-12)

Added after reviewing generated output on the real thesis; gates the v1.0.0 deploy.

- **SEMANTIC QUESTIONS ONLY (hard constraint).** Banned outright: continue-the-text, fill-in-the-blank,
  quote-completion, and recall-the-number questions ("what value is in Table X?"). Every question must be
  open-ended discussion measuring understanding and mastery — justification, mechanism, critique, cases,
  trade-offs, what-ifs. Bloom floor: Understand and above; Remember-level questions are forbidden.
  The examiner SUPPLIES specifics (numbers, quotes, tables) in the question and asks the candidate to
  interpret / justify / defend / extend them — never to reproduce them from memory.
- **Ownership battery reframed semantically:** authenticity is probed by "walk me through WHY you chose X /
  explain the mechanism behind Y" — never by recitation or completion of the candidate's own text.
- **Slides module reframed:** (a) slide-anchored QUESTIONS obey the same semantic mandate; (b) a new
  deliverable, `thesis_examination_slides_critique.md` — genuine gaps between deck and thesis, thesis
  content missing from the deck that would better showcase the work to examiners, and concrete
  improvement recommendations (structure, narrative, design, professionalism) at the pursued degree's level.
- **Deep-research + citation mandate (RESEARCH-ENABLED):** the exceed-the-author phase must research the
  thesis's OWN reference list plus semantically-related papers/journals/books/documentation. Every external
  claim in any question, model answer, or note carries a citation WITH a working URL (arXiv/DOI preferred),
  link-verified live before inclusion. Inventing a citation, DOI, or link is a protocol violation; anything
  unverifiable is tagged [NEEDS-VERIFICATION] or omitted. No hallucinated content anywhere in the deliverables.

## 5. Live Defense web console

### Data flow

```
Examiner session                defense_server.py              Browser (ui/index.html)
   │  writes state.json  ──────►  watches mtime  ── SSE ────►  renders question/scoreboard
   │                                                                │ candidate types answer
   │  bg watcher wakes  ◄──────  writes inbox/answer-N.json ◄── POST /answer
   │  scores, writes next state.json  ──────────────────────►  feedback + next question
```

- **State dir**: `<output-dir>/.live/` → `state.json` + `inbox/`.
- **state.json** fields: `phase` (briefing|question|feedback|verdict), `qid`, `question`,
  `tier`, `lens`, `category`, `grounding`, `timerStartedAt`, `scoreboard` (per rubric dim),
  `coverage` (per chapter: pending|partial|done|current), `redFlags[]`, `feedback`.
- **Server**: stdlib only. Endpoints: `GET /` (UI), `GET /events` (SSE of state.json),
  `POST /answer` (→ inbox file), `GET /state` (poll fallback). Auto-picks a free port,
  prints URL, opens browser (`xdg-open`/`open`), `--no-open` flag for tests.
- **Examiner wake-up**: background Bash watcher loop blocks until a new inbox file exists,
  then exits → session wakes → scores answer per rubric → updates state.json (feedback +
  next question, difficulty spiked off weak answers per Constraint 9 / Section 5.2).
- **End of viva**: `phase: verdict` renders verdict screen; session writes
  `Defense-Transcript.md` (full Q/A/score log) next to Documents A–C.
- **UI** (single file, inline assets): header (title, timer, Q-counter, tier+lens chips),
  question card with grounding line, answer textarea + send, live rubric bars, chapter
  coverage strip, red-flag toasts, verdict screen. Responsive; `prefers-color-scheme` aware.

### Error handling

- No `python3` → fall back to chat-based Document D with a clear message; Docs A–C unaffected.
- Port busy → next free port. Browser closed → state persists; same URL resumes.
- Malformed inbox JSON → server rejects with 400; examiner never sees it.
- Answer arrives while examiner is mid-scoring → inbox files are numbered; processed in order.

## 6. Wrappers

- **SKILL.md** (~40 lines): frontmatter (name, description incl. slides + live-defense triggers),
  activation steps (gather thesis path, optional PPTX path, optional calibration facts),
  then: read `references/protocol.md` and execute it. Interactive segmentation preserved.
- **agents/thesis-examiner.md**: headless overrides (no pauses, PROVISIONAL defaults, write files,
  RESUME-FROM on budget exhaustion — as v1) + "read protocol at
  `${CLAUDE_PLUGIN_ROOT}/skills/thesis-examiner/references/protocol.md` before starting".
- Both wrappers must NOT duplicate protocol text.

## 7. Test plan (gates deploy)

1. **Script level**: `extract_pptx.py` on a sample deck (assert slide count, titles, notes);
   `defense_server.py` headless — curl `/state`, POST `/answer`, verify inbox file + SSE event.
2. **Local install**: `/plugin marketplace add ~/WS/thesis-examiner` (after removing loose
   copies to avoid name collision) → verify skill triggers, agent dispatches, protocol loads.
3. **E2E on real thesis** (path from Mohamed): full A/B/C generation; then a scripted
   3-question live defense with Playwright driving the browser as the candidate
   (type answer → assert feedback + next question renders).
4. **Deploy**: push to GitHub → `/plugin marketplace add MA-Abuelmagd/thesis-examiner` →
   reinstall from GitHub → smoke test → tag `v1.0.0`.

## 8. Out of scope (v1) / roadmap

- Out of scope for v1: multi-candidate sessions; persistence beyond the state dir; PDF slide
  decks (PPTX only in v1 — PDF decks can be passed as the thesis appendix); auto-submission
  to the official Anthropic marketplace.
- **Deferred to future versions by Mohamed (v2+ roadmap)**: voice input/output in the live
  console (candidate answers by speaking, examiner questions read aloud) and further live-mode
  enhancements. The v1 console's file-bridge design should not preclude adding a voice layer later.
