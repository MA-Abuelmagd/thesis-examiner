#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# structure
# NOTE: one check per line — under `set -e`, a non-final failure inside an
# `A && B && C` list short-circuits without aborting the script.
jq -e '.name == "thesis-examiner"' .claude-plugin/plugin.json >/dev/null
jq -e '.plugins[0].source == "./"' .claude-plugin/marketplace.json >/dev/null
[ -f skills/thesis-examiner/SKILL.md ]
[ -f skills/thesis-examiner/references/protocol.md ]
[ -f agents/thesis-examiner.md ]
[ -f ui/index.html ]
[ -f scripts/defense_server.py ]
[ -f scripts/extract_pptx.py ]
# all unit/integration suites green
bash tests/test_extract.sh >/dev/null
bash tests/test_server.sh >/dev/null
bash tests/test_console.sh >/dev/null
# headless sideload: the skill must be visible to a fresh claude session
# (prompt goes via stdin: --allowedTools is variadic and would swallow a trailing prompt argument)
RC=0
OUT=$(echo "Reply with ONLY the exact name of any available skill whose name contains 'thesis'." \
  | claude -p --plugin-dir "$PWD" --allowedTools "" 2>&1) || RC=$?
# Match the namespaced token, not the bare name: OUT captures stderr and $PWD
# ends in "thesis-examiner", so an error message echoing the plugin dir would
# false-positive a bare-name grep. A sideloaded skill reports as plugin:skill.
echo "$OUT" | grep -qi "thesis-examiner:thesis-examiner" \
  || { echo "SIDELOAD CHECK FAILED (claude exit=$RC): $OUT"; exit 1; }
echo "PASS test_plugin_smoke"
