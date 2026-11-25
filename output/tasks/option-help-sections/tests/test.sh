#!/bin/bash
# TriVerify verifier: add the feature tests to the repository's test suite, run the
# whole suite once, and score it with the shared reward formula (grade.py).
cd /app
mkdir -p /logs/verifier
cp /tests/feature/*.py /app/tests/
python /tests/grade.py --repo /app --tests-dir /tests --out /logs/verifier --target tests
# grade.py always writes /logs/verifier/reward.txt; never fail the script itself.
exit 0
