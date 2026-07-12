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
# one check per line: a non-final failure in `A && B` would not abort under set -e
echo "$PAGE" | grep -q "EventSource"
echo "$PAGE" | grep -q "prefers-color-scheme"
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
