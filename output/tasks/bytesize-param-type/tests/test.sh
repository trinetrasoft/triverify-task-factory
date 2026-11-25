#!/bin/bash
# TriVerify verifier (separate container, clean checkout of the base commit):
# apply the agent's changes (collected without tests/), add the feature tests,
# run the whole suite once and score it with the shared reward formula.
cd /app
mkdir -p /logs/verifier
if [ -s /tmp/triverify/agent.patch ]; then
  if git apply --whitespace=nowarn /tmp/triverify/agent.patch; then
    echo "agent patch applied ($(wc -l < /tmp/triverify/agent.patch) lines)" > /logs/verifier/agent-patch.txt
  else
    echo "agent patch did not apply" > /logs/verifier/agent-patch.txt
  fi
else
  echo "no agent changes" > /logs/verifier/agent-patch.txt
fi
cp /tests/feature/*.py /app/tests/
python /tests/grade.py --repo /app --tests-dir /tests --out /logs/verifier --target tests
# grade.py always writes /logs/verifier/reward.txt; never fail the script itself.
exit 0
