# E2E run on a real thesis — results log (Task 9)

Date: 2026-07-12 · Branch: `dev/v1` · CLI: 2.1.207 · Model (headless run): claude-fable-5
Inputs: a real 6-chapter MSc thesis (ML-benchmarking / design-science, ~140 pp incl. front matter and two appendices) with a 97-slide defense deck, both under `<test-assets>`. Output dir: `<output-dir>`. No marking scheme supplied (PROVISIONAL defaults expected).

## Verdict at a glance

| Step | Result |
|---|---|
| 1 — Documents run (headless, through the plugin) | **PASS** — pipeline completed on the real thesis; all four documents written; three environment interruptions along the way (none a plugin defect, see below). |
| 1v — Verification battery on the generated documents | **PASS** — completeness 44/44 A↔B id match; no numeric-target language; coverage matrix populated; slides module (cats 24/25 + per-slide map) verified against the real deck; anchor spot-check 5/5 (seed 42); PROVISIONAL marking present. |
| 2 — Live-defense loop (server + browser, scripted candidate) | **PASS** — 3 full question→answer→feedback cycles + verdict screen, all SSE-pushed without reload. |

## Pre-run housekeeping

The output dir still held the earlier v1 outputs (Mastery-Brief.md 46 KB, Question-Bank.md 495 KB, Model-Answers.md 1.11 MB, Grading-Kit.md 22 KB, `parts/` 33 files). To avoid the new run overwriting them and to give the E2E a clean slate, they were **moved (not deleted)** to `<output-dir>/v1-archive/v1-outputs/`.

## Step 1 — Documents run: COMPLETED (with three environment interruptions)

Command (prompt via stdin — CLI 2.1.207 swallows trailing args after variadic flags, per Task 7):

```
printf '%s' "Dispatch the thesis-examiner agent on the thesis at '<test-assets>/thesis.pdf' with slides '<test-assets>/deck.pptx', output directory <output-dir>. No marking scheme; extract calibration from the PDF; PROVISIONAL defaults; write each document to disk as finished." \
  | claude -p --plugin-dir <repo> --output-format stream-json --verbose
```

An earlier attempt was blocked by the machine's permission configuration (headless `-p` auto-denies unallowed tools); after the user granted the needed tools the pipeline ran to completion. Fidelity points all held again: plugin sideloaded as `thesis-examiner@inline`, agent `thesis-examiner:thesis-examiner` dispatched with the exact inputs, protocol read via `${CLAUDE_PLUGIN_ROOT}`, §0.2 capability probes passed, documents written to disk as finished.

**Three environment interruptions occurred during the long run — none a plugin defect:**

1. **Duplicate concurrent runs (orchestration error).** Two copies of the pipeline were accidentally launched concurrently by the test controller; the duplicate was killed and the survivor continued. Plugin-side no corruption: document writes are whole-file, and the finished docs verified clean.
2. **Blocked-stdout pipe stall.** The headless process streams `stream-json` to stdout; when the consumer stopped draining the pipe, the run stalled on a full pipe buffer (not hung — resumed as soon as the pipe drained). Lesson: always keep a reader attached (`... | cat > log &` or equivalent) for long runs.
3. **Headless 600 s background-wait ceiling.** In `-p` (print/headless) mode the harness caps waiting on background work at 600 s, which a multi-hour documents pipeline exceeds. Fixed by setting `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` (unlimited) for the run.

> **Headless usage note (for plugin users):** a full examination run on a real thesis takes hours. If you run it headless (`claude -p`), export `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` first, or the harness's 600-second background-wait ceiling will cut the run off; and keep stdout drained (redirect to a file) so the stream can't block the pipe.

**Budget note:** the plan allowed at most TWO continuation rounds after a RESUME-FROM.md before stopping regardless of completeness — the E2E gate verifies the pipeline, not the final exhaustive exam. **2 of 2 continuation rounds were consumed**; the RESUME-FROM.md/resume path is therefore exercised and working.

### Document inventory (as written by the run)

| Document | File | Size | Contents check |
|---|---|---|---|
| Mastery Brief (Doc 0) | `thesis_examination_mastery_brief.md` | 19 KB / 67 lines | 17 numbered mastery sections + Pass-4/Pass-5 forensic notes (8 discrepancies f1–f8) + Section-4 ledger (7 external items) |
| Question Bank (Doc A) | `thesis_examination_question_bank.md` | 75 KB / 639 lines | 44 question records (Q1–Q40 + Q-D1…Q-D4; Q-D5 = Q7), Decisive-Five, slides module, per-slide map; ends with its End-of-Document line |
| Model Answers (Doc B) | `thesis_examination_model_answers.md` | 162 KB / 542 lines | 44 entries, one per A record; ends with "End of Document B" |
| Grading Kit (Doc C) | `thesis_examination_grading_kit.md` | 25 KB / 216 lines | C.1 weighted rubric · C.2 outcome ladder · C.3 red-flag caps · C.4 running order · C.5 coverage matrix · C.6 self-verification; ends with "End of Document C" |

## Step 1v — Verification battery on the generated documents

1. **Completeness — PASS.** Doc A ends with "*End of Document A. Every question has a matching Document B entry…*"; Doc B ends with "*End of Document B. All 44 Document A records…*". Scripted id-set comparison of `### Q<id>` headings: A = 44 unique ids, B = 44 unique ids, A−B = ∅, B−A = ∅, no duplicates. Grading Kit contains all four required parts (C.1 weighted rubric with paradigm-tuned weights ×0.9 + Presentation 10%; C.2 outcome ladder; C.3 red-flag grade caps; C.5 coverage checklist/matrix).
2. **No numeric target — PASS.** Grep battery for goal/floor/ceiling/quota/target question-count language over all four docs: no hits. The number 44 appears only as an achieved statistic, and the Grading Kit says so explicitly: "achieved count **44 questions** (statistic, not target)".
3. **Coverage matrix — PASS.** Grading Kit C.5: five sub-tables (chapters+appendices ×8 rows, central claims ×8, contributions ×7, limitations/sources ×12, slides row) — every pre-filled "Question ids" cell is populated. The blank checkbox columns are, per the section's own header, "live columns to be completed during Document D" — by design, not omissions.
4. **Slides module — PASS.** Category 24 (Slides↔Thesis consistency: Q36–Q38) and Category 25 (Presentation-delivery: Q39–Q40) present; per-slide question map covers S1–S97. Deck cross-check via `scripts/extract_pptx.py --json` (fresh extraction, `slideCount: 97` — matches Q39's "97 slides"): **Q37/Q40 cite slide 49** → extracted body contains "Qwen3-8B / YES / Llama-3.1-8B / YES / Mistral-7B / NO" and "Offline training made Mistral worse." — exactly as quoted; **Q38 cites slide 52** → extracted body contains "80 points from scoring alone; the winner never changes." and the footnote "Measured under an older, permissive decoding setup that the production protocol forbids." — quoted verbatim in the question.
5. **Anchor spot-check — 5/5 VERIFIED** (seeded random, seed 42, over the 44 v2 records; 5 distinct document sections, tiers T3–T7). Method: `pdftotext` full text; cited quote/table located; printed folio on the containing PDF page compared against the thesis's chapter page map (constant offset PDF index = printed folio + 15 held on every hit).

   | Q (tier) | Section sampled | Cited anchor | Evidence found | Verdict |
   |---|---|---|---|---|
   | Q-D2 (T7) | Ch. 3 protocol | §4.3 quote; §4.1 checkpoint-confound quote; joint 0.287 vs frozen 0.513 | quote verbatim @ PDF 86/folio 71; both quote fragments @ PDF 79/folio 64; table row "Joint training (ceiling) 0.616 0.568 0.287" + "Frozen 0.523 0.555 0.513" @ PDF 84/folio 69 | VERIFIED |
   | Q4 (T3) | Ch. 2 background | §2.2 Table 2.1; deck slides 7 + 22 | "Table 2.1: Taxonomy of continual learning strategy f…" @ PDF 34/folio 19; slide 7 "not in the roster: capacity grows with the task count; assumes task identity" exact; slide 22 "Deliberate Exclusions" + architecture/Bayesian exclusion exact | VERIFIED |
   | Q30 (T4) | Future work | §4.4 quote; App. B ~77 A100-hrs | quote verbatim @ PDF 91/folio 76; Table B.1 totals 64.6 + 12.4 h with "about 77 A100-hours in all" @ PDF 129/folio 114 | VERIFIED |
   | Q36 (T4) | Slides module | slide 7 method names; Table 3.7; §3.3.1 quote | slide 7 "here: O-LoRA · InfLoRA" and "here: LwF" exact in extraction; Table 3.7 @ PDF 62/folio 47; "never as elastic weight consolidation" @ PDF 63/folio 48 | VERIFIED |
   | Q16 (T5) | Ch. 4 results | §5.4 Table 5.3 caption quote; joint 0.568 ties frozen 0.555 | Table 5.3 caption @ PDF 113/folio 98; numbers confirmed in ladder table @ PDF 84/folio 69 and prose "Joint training collapses to 0.568, statistically tied with the fr[ozen]" @ PDF 85/folio 70 | VERIFIED* |

   \* One quote-fidelity nit on Q16: the bank's elided caption quote reads "sits at the floor on Llama-3.1-8B" where the thesis reads "sits at the **frozen** floor on Llama-3.1-8B" — a word dropped mid-quote without ellipsis. Anchor real, location and meaning correct.
6. **PROVISIONAL marking — PASS.** Grading Kit opens with "**STATUS: PROVISIONAL.** The official marking scheme was **not supplied** … Every grade mapping below is therefore **PROVISIONAL**"; C.2 outcome ladder and C.4 running order carry PROVISIONAL in their headings; C.6 confirms unstated intake items were "marked PROVISIONAL".

## Anchor spot-check (v1 bank) — superseded

An earlier 5/5 spot-check (seed 9) ran against the archived v1 bank while the documents run was blocked; it is superseded by the seed-42 v2 check above and kept only as history in the repo log.

## Step 2 — Live-defense loop: PASS (3 cycles + verdict)

Server: `python3 scripts/defense_server.py --dir <output-dir>/.live --no-open` → `DEFENSE CONSOLE: http://127.0.0.1:8420`. Browser: Playwright MCP. Every state write was atomic (`state.json.tmp` → `os.replace`). Questions were REAL generated questions for this thesis, taken from the archived v1 bank (the v2 bank did not yet exist at loop time); fields per protocol §7.4.

| Cycle | State written | Browser observed (accessibility snapshot, no reload after initial load) | Inbox |
|---|---|---|---|
| 1 | seed `phase:question` Q3B-6 (T3/Skeptic/4 Framework-concepts) + grounding, 90-min timer, 4-dim scoreboard, 3-row coverage | Question text + grounding render; chips Q3B-6/T3/Skeptic/category; timer counting ("90 min left"); coverage shows ▸ current | `answer-0001.json`: qid 3B-6, 1055 chars, exact submitted text |
| 2 | feedback for 3B-6 ("Adequate-to-strong") + next Q1-6 (T4/Methodologist), scoreboard 2/2/3/2, coverage Ch3→done | **Updated via SSE without reload**: new question + T4 chips, "Examiner's remark — Q3B-6 — Adequate-to-strong" banner, bars updated, ✓/▸ coverage, textarea auto-cleared, timer continuous (02:24) | `answer-0002.json`: qid 1-6, 1041 chars |
| 3 | feedback for 1-6 ("Strong") + Q1-3 (T5/Domain-Expert, Decisive-Five) + 1 red flag | New question + banner + red-flag list (⚑) render, still no reload (04:26) | `answer-0003.json`: qid 1-3, 1178 chars |
| End | `phase:"verdict"` with outcome/summary/perDimension | **Verdict screen renders**: "Committee decision — PASS WITH MINOR CORRECTIONS (PROVISIONAL)" + summary; question card and answer area hidden; final scoreboard/coverage/red-flags persist | — |

Teardown: server killed (port 8420 confirmed closed), browser tab closed. `.live/` left in place with the final verdict state + 3 inbox answers as the artifact of the run.

Round-trip integrity: all three inbox files carried the correct `qid` and byte-exact answer text; inbox numbering sequential; no missed SSE updates; the qid-change answer-box reset behaved per `ui/index.html` design.

## Defects found

**In plugin code: none.** Server, UI, SSE push, inbox writer, atomic-state handling, resume loop, and the documents pipeline all behaved to spec on a real thesis + deck.

**In generated documents (minor, non-blocking):**
1. Doc A header states an "achieved difficulty distribution" of "61 headline questions" (9+15+21+16=61) while the bank holds 44 headline records — the tally appears to count probe-chain branches without saying so. Internal inconsistency, not target language.
2. Dangling cross-reference: the Decisive-Five footnote cites "Q45", which does not exist (bank runs Q1–Q40 + Q-D1…Q-D4).
3. Q16's elided Table 5.3 caption quote drops the word "frozen" mid-quote without ellipsis (see spot-check note above).

**Environment findings:** the three interruptions above (duplicate concurrent launch, blocked-stdout pipe, 600 s headless background-wait ceiling) are all environment/orchestration issues with known mitigations — see the headless usage note.

**Remaining untested surface:** `Defense-Transcript.md` writing by a real examiner session (Step 2 exercised the transport with this test as scripted examiner+candidate).

## v2.1 regeneration — full re-run on the real thesis (same day)

**Why.** User feedback on the v2.0 documents produced two hard mandates, folded into the protocol as constraints 10–11: **SEMANTIC QUESTIONS ONLY** (no continue-the-text / fill-in / quote-completion / recall-the-value questions — the examiner supplies every specific and asks for interpretation, justification, critique) and **VERIFIED CITATIONS ONLY** (every external claim carries a working URL obtained from a live search this session — never composed from memory), plus a new mandatory **Slides Critique report** deliverable (§7.5). The v2.0 outputs were archived to `<output-dir>/v1-archive/v2.0-outputs/` and the full examination regenerated under the v2.1 protocol.

**Run.** Single clean headless run, **~40 minutes, zero interruptions** — no RESUME-FROM.md, no continuation rounds, no environment stalls. `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` exported per the headless usage note above (with stdout drained to a log); with those mitigations in place none of the v2.0 run's three environment issues recurred.

### Document inventory (as written by the run)

| Document | File | Size | Contents check |
|---|---|---|---|
| Mastery Brief (Doc 0) | `thesis_examination_mastery_brief.md` | 19 KB / 86 lines | RESEARCH-ENABLED mode; intake calibration; paradigm router; Section-4 ledger with **12 external items, every one with a live URL** and the trail statement "All URLs below were returned by live searches/fetches performed during this session" |
| Question Bank (Doc A) | `thesis_examination_question_bank.md` | 123 KB / 868 lines | **70 question records (Q1–Q70)**, Decisive-Five, per-slide map covering all 97 slides, COVERAGE REPORT (category×tier matrix, loop-until-dry, count as "Statistic only") |
| Model Answers (Doc B) | `thesis_examination_model_answers.md` | 76 KB / 524 lines | 70 entries (one per A record, 70× IDEAL + hidden targets) + per-slide-map guidance |
| Grading Kit (Doc C) | `thesis_examination_grading_kit.md` | 11 KB / 83 lines | 8.1 weighted rubric (+Presentation 10%, dims ×0.9) · 8.2 outcome ladder (PROVISIONAL) · 8.3 red-flag caps · 8.4 running order (PROVISIONAL) · 8.5 coverage checklist |
| Slides Critique (new, §7.5) | `thesis_examination_slides_critique.md` | 10 KB / 41 lines | 6 genuine thesis-content gaps · 11 dual-anchored deck↔thesis fidelity fixes · concrete structure/design/time-allocation recommendations, MSc-calibrated, constructive tone |

### Verification battery (independent gate; full evidence in `.superpowers/sdd/task-v21-verification.md`)

1. **Completeness — PASS.** Scripted id-set comparison: A = 70 unique ids, B = 70, A−B = ∅, B−A = ∅, no duplicates; no CONTINUATION-POINT markers; no RESUME-FROM.md; grading kit carries all five parts. (Nit: the literal "*End of Document*" sentinel lines of v2.0 are absent; both docs end at clean, complete structural boundaries.)
2. **Semantic sweep — PASS (the mandate held).** Programmatic scan of all 70 headlines against 10 banned-pattern families: **0 hits**. Full-record scan (probe chains + deflections): 1 lexical hit, adjudicated non-violation (a deflection asking the candidate to commit to a kill-criterion threshold for an experiment they are designing live — Create-level, value not in the thesis). Seeded random sample (seed 7) of 12 full records read end-to-end: **12/12 PASS** — every record supplies the numbers/quotes and asks for interpretation, justification, or critique.
3. **Citations — PASS.** 33 URL occurrences, 15 unique, 7 domains. Seeded sample of 10 (seed 3) live-checked: **10/10 HTTP 200**; the 5 remaining checked as bonus: 4 alive, 1 publisher bot-wall (403 to curl) on a real, correct DOI with an alive companion explainer. Three cited claims cross-checked against fetched sources (TRACE; Spurious Forgetting ICLR 2025; a June-2026 CL benchmark): **3/3 supported**, near-verbatim quotes confirmed. No fabricated-looking citation.
4. **Anchor spot-check — 5/5 VERIFIED** (seed 42): every cited quote/section/table found at the cited location via pdftotext, printed-folio = PDF-page − 15 held on every hit.
5. **Slides critique — PASS.** All three mandated parts present; 2 slide references spot-checked against fresh extractor output (the run-to-run-variation concession and the small-sample-generalization bullet) — both verbatim-real.
6. **Slide-question semantics — PASS.** Both spot-checked slide-anchored questions quote the slide content inside the question and demand reconciliation with the document — no recall.
7. **No numeric-target language; PROVISIONAL — PASS.** Zero target/quota phrasing; count stated twice as "statistic, not a target"; PROVISIONAL ×3 in the grading kit.

**Defects (minor, non-blocking):** missing end-of-document sentinel lines (cosmetic); one bot-walled (real) DOI link; a one-day arXiv date discrepancy on one ledger entry; per-slide-map entry count stated as 40 vs 39 top-level bullets (extras grouped inline). None affects the mandates.

**v2.0 → v2.1 regression note:** the three v2.0 document defects (inflated "61 headline questions" tally, dangling Q45 cross-reference, dropped word in an elided quote) are all absent from the v2.1 documents.
