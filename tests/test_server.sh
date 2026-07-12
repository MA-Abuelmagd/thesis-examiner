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
# one check per line: a non-final failure in `A && B` would not abort under set -e
[ "$CODE" = "400" ]
[ ! -f "$DIR/inbox/answer-0003.json" ]
# empty answer -> 400
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8431/answer \
  -H 'Content-Type: application/json' -d '{"qid":3,"answer":"  "}')
[ "$CODE" = "400" ]
# foreign Host header -> 403 before routing (DNS-rebinding guard), SSE included
CODE=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example.com' http://127.0.0.1:8431/state)
[ "$CODE" = "403" ]
CODE=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example.com:8431' http://127.0.0.1:8431/events)
[ "$CODE" = "403" ]
# stray non-numbered inbox files must not break the answer counter
touch "$DIR/inbox/answer-stray.json" "$DIR/inbox/answer-9999.json.tmp"
curl -sf -X POST http://127.0.0.1:8431/answer -H 'Content-Type: application/json' \
  -d '{"qid":4,"answer":"y"}' | jq -e '.file == "answer-0003.json"' >/dev/null
# SSE: update state.json -> event with the new question arrives within 3s
# (capture the stream to a file: the SSE connection is persistent by design, so a
#  curl|grep pipeline never exits 0 under pipefail -- timeout's 124 would win)
( sleep 0.5; printf '%s' '{"phase":"question","qid":1,"question":"Why 5-fold?"}' > "$DIR/state.json.tmp"; mv "$DIR/state.json.tmp" "$DIR/state.json" ) &
timeout 3 curl -sN http://127.0.0.1:8431/events > tests/tmp/sse.out || true
grep -q "Why 5-fold?" tests/tmp/sse.out
echo "PASS test_server"
