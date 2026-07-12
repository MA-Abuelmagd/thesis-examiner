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
# zip-bomb guard: a part whose DECLARED file_size exceeds the cap is never read —
# oversized slide marked unparseable, oversized notes skipped, rest of deck intact
python3 tests/make_fixture_pptx.py tests/tmp/bomb.pptx --bomb >/dev/null
BOUT=$(timeout 10 python3 scripts/extract_pptx.py tests/tmp/bomb.pptx --json)
echo "$BOUT" | jq -e '.slides[0].body | index("[unparseable slide XML]") != null' >/dev/null
echo "$BOUT" | jq -e '.slides[1].title == "Safe Slide"' >/dev/null
echo "$BOUT" | jq -e '.slides[1].notes == ""' >/dev/null
# OOXML relationship ordering: p:sldIdLst order (slide3, slide1, slide2) governs the
# display order, and notes pair via each slide part's own rels — never filename numbers.
# (The sample.pptx checks above have no ppt/presentation.xml, proving the
#  filename-order fallback still works unchanged.)
python3 tests/make_fixture_pptx.py tests/tmp/reordered.pptx --reordered >/dev/null
ROUT=$(python3 scripts/extract_pptx.py tests/tmp/reordered.pptx --json)
echo "$ROUT" | jq -e '.slideCount == 3' >/dev/null
echo "$ROUT" | jq -e '.slides[0].title == "Reordered Opening"' >/dev/null
echo "$ROUT" | jq -e '.slides[0].n == 1' >/dev/null
echo "$ROUT" | jq -e '.slides[0].notes | length > 0' >/dev/null
# unreadable file -> exit 2 with ERROR line
# (capture output and exit code separately: piping the exit-2 extractor into grep
#  would poison the pipeline status under pipefail even when grep matches)
set +e
ERR_OUT=$(python3 scripts/extract_pptx.py tests/make_fixture_pptx.py --json 2>&1)
C=$?
set -e
# one check per line: under `set -e`, a non-final failure in an `A && B` list
# short-circuits without aborting the script
echo "$ERR_OUT" | grep -q "^ERROR:"
[ "$C" -eq 2 ]
echo "PASS test_extract"
