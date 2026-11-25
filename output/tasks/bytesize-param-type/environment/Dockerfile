FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The repository at the exact starting commit only: no upstream history, no refs
# that could leak a future implementation.
WORKDIR /app
RUN git init -q . \
    && git remote add origin https://github.com/pallets/click \
    && git fetch -q --depth 1 origin cf19179e8e2fd54c601378cec9e0d21bb12b6fb1 \
    && git checkout -q --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1" \
    && git remote remove origin \
    && git config --global user.email "agent@example.com" \
    && git config --global user.name "agent"

RUN pip install -e . pytest==8.4.1 \
    && git ls-files --others --exclude-standard >> .git/info/exclude \
    && test -z "$(git status --porcelain)"
