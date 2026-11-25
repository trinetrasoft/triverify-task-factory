#!/bin/bash
# Oracle: apply the reference implementation to the starting commit.
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
echo "reference solution applied"
