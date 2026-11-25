"""Variation gate: proves the tasks are substantively different.

Three independent signals, all reported as pairwise matrices:

* **axis**            – each task must come from a distinct variation axis;
* **code footprint**  – Jaccard overlap of the functions/classes the reference
  patches modify (from the patched source, not the prompt);
* **behaviour**       – cosine similarity of the instructions' content words and
  Jaccard overlap of the public API the feature tests exercise.

Rewording one idea fails the footprint and behaviour checks even if the titles
differ; that is the point.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations

_STOP = set(
    """a an the and or of to in on for with without by is are be been it its this that these those
    as at from when if then else must should may can will not no any all each every new existing
    value values option options command commands click user users return returns returned""".split()
)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tokens(text: str) -> Counter:
    words = re.findall(r"[a-z_][a-z0-9_]{3,}", text.lower())
    return Counter(w for w in words if w not in _STOP)


def cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    num = sum(a[w] * b[w] for w in common)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def assess(specs: list[dict], reports: dict[str, dict], max_symbol_jaccard: float, max_text: float) -> dict:
    ids = [s["id"] for s in specs]
    axes = {s["id"]: s["axis"] for s in specs}
    symbols = {i: set(reports.get(i, {}).get("touched_symbols", [])) for i in ids}
    api = {i: set(reports.get(i, {}).get("api_refs", [])) - {"testing", "CliRunner", "command", "option", "echo"} for i in ids}
    text = {s["id"]: _tokens(s["instruction"]) for s in specs}

    pairs = []
    for a, b in combinations(ids, 2):
        pairs.append(
            {
                "a": a,
                "b": b,
                "same_axis": axes[a] == axes[b],
                "symbol_jaccard": round(jaccard(symbols[a], symbols[b]), 3),
                "api_jaccard": round(jaccard(api[a], api[b]), 3),
                "text_cosine": round(cosine(text[a], text[b]), 3),
            }
        )
    worst_symbol = max((p["symbol_jaccard"] for p in pairs), default=0.0)
    worst_text = max((p["text_cosine"] for p in pairs), default=0.0)
    distinct_axes = len(set(axes.values())) == len(ids)
    passed = distinct_axes and worst_symbol <= max_symbol_jaccard and worst_text <= max_text
    return {
        "passed": passed,
        "distinct_axes": distinct_axes,
        "max_symbol_jaccard": worst_symbol,
        "max_text_cosine": worst_text,
        "thresholds": {"symbol_jaccard": max_symbol_jaccard, "text_cosine": max_text},
        "pairs": pairs,
        "axes": axes,
    }
