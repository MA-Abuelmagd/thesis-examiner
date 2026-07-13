# thesis-examiner

A Claude Code plugin that turns a session into a rigorous external thesis-defense (viva) examiner. Give it a thesis — PDF path or pasted text — and optionally the PowerPoint defense deck, and it reads the whole document, calibrates to your degree level and institution, and interrogates the work the way a hostile-but-fair committee would: exhaustive questions from softball to extreme, model answers grounded in the actual text, a weighted grading kit, and an optional live mock defense you answer from your browser.

It produces four documents:

- **Document A — Question Bank.** Exhaustive viva questions, each tagged with difficulty tier, examiner lens, Bloom level, and the exact thesis passage it attacks.
- **Document B — Model Answers.** A strong-candidate answer for every question in A, bound to this thesis, not generic advice.
- **Document C — Grading Kit.** A weighted rubric, outcome ladder mapped to real decision categories, red-flag grade caps, and a time-boxed viva running order.
- **Document D — Live Defense.** An adaptive mock viva: one question at a time, the next generated from your actual answer, scored live against the rubric.

## Install

```
/plugin marketplace add MA-Abuelmagd/thesis-examiner
/plugin install thesis-examiner@thesis-examiner
```

## Usage

### Interactive

```
/thesis-examiner
```

Then give it the thesis (a PDF path or pasted text) and, if you have one, the `.pptx` slide deck. The examiner works through the documents in order, pausing for you to say "continue" between them. Slides activate extra machinery: deck forensics, thesis-vs-slides contradiction hunting, and a per-slide question map.

### Headless (subagent)

Dispatch the `thesis-examiner` agent with the thesis path, optional slides path, any calibration facts (degree level, institution, exam format, duration), and an output directory. It runs the full protocol without pausing and writes each document to disk as it finishes, reporting exact paths.

### Live defense (browser console)

For Document D, the examiner launches a local web console and opens it in your browser:

```
┌─────────────────────────────────────────────────────┐
│ ⚖ Thesis Defense — Live          Q4 · 12 · 38:22    │
├─────────────────────────────────────────────────────┤
│ [Tier: Hostile] [Lens: Methodologist] [Ch. 4]       │
│                                                     │
│ "Your ablation removes the attention layer but      │
│  keeps the positional encoding — why is that a      │
│  fair isolation of the mechanism you claim?"        │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Answer as you would in the viva room…           │ │
│ └─────────────────────────────────────────────────┘ │
│                              [ Submit answer ➤ ]    │
├──────────────┬──────────────────┬───────────────────┤
│ Scoreboard   │ Coverage         │ Red flags         │
│ Rigor  ██ 2/3│ Ch1 ✓ Ch2 ✓ Ch3 ◐│ • overclaimed     │
└──────────────┴──────────────────┴───────────────────┘
```

You type each answer in the browser and send it with the button or **Ctrl/Cmd+Enter**. Answers land in a numbered inbox the examiner watches; it scores each one against the weighted rubric, gives verdict feedback, and spikes the difficulty of the next question off weak answers. The console is a single self-contained HTML file — zero dependencies, localhost-only, with light and dark themes — and the session ends with a full written transcript and verdict.

## Inputs

| Input | Required | Form |
|---|---|---|
| Thesis | Yes | PDF path or pasted text |
| Defense slides | No | `.pptx` path (extracted locally; a 97-slide real deck parses in ~47 ms) |
| Marking scheme / calibration facts | No | Degree level, institution, exam format, official rubric, viva duration — assumptions are stated and grades marked PROVISIONAL if absent |

## How it works

Everything lives in one protocol file (`skills/thesis-examiner/references/protocol.md`); the skill and agent are thin wrappers that load it. The pipeline: multi-pass ingestion of the thesis (and slide forensics if a deck is given) → a **mastery brief** proving the examiner understood the work before judging it → independent **research** into the field when web tools are available (otherwise reasoning-only, with unverified claims flagged) → the **question bank** built against a coverage matrix so no chapter or angle escapes → **model answers** for every question → the **grading kit** calibrated to your institution's actual outcome categories → the optional **live defense**.

## Requirements

- Claude Code with plugin support.
- `python3` (stdlib only) — needed for slide extraction and the live defense console. Without it, the examiner tells you, skips slides, and runs the live defense in chat instead. Everything else degrades gracefully; nothing is fabricated to fill a gap.

## Roadmap

- **Voice I/O (planned):** speak your answers in the live defense instead of typing them.

## License

MIT — see [LICENSE](LICENSE).
