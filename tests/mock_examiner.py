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
