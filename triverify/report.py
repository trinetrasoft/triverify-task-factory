"""Run summary as JSON, Markdown (REPORT.md) and a self-contained HTML dashboard."""

from __future__ import annotations

import html
import json
from pathlib import Path


def _gate(v: bool | None) -> str:
    return "✅" if v else ("❌" if v is False else "—")


def build(summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(summary, indent=2))
    (out / "REPORT.md").write_text(markdown(summary))
    (out / "report.html").write_text(dashboard(summary))


def markdown(s: dict) -> str:
    t = s["target"]
    lines = [
        "# TriVerify run report",
        "",
        f"- Target: `{t['repo']}` @ `{t['ref']}` (`{t['base_commit']}`)",
        f"- Generated: {s['generated_at']} · provider `{s['provider']}` · model `{s['model']}`",
        f"- Harbor: {s.get('harbor_version', 'n/a')}",
        f"- Baseline: {s['baseline']['collected']} tests collected, "
        f"{len(s['baseline']['pass_to_pass'])} pass-to-pass (stable across {s['baseline']['runs']} runs)",
        "",
        "## Tasks",
        "",
        "| Task | Axis | F2P | NOP (local) | ORACLE ×3 (local) | Mutation score | Harbor nop | Harbor oracle | All gates |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for task in s["tasks"]:
        r = task["validation"]
        h = task.get("harbor", {})
        mut = r.get("mutation", {})
        oracle = r.get("oracle", [])
        lines.append(
            f"| `{task['id']}` | {task['axis']} | {len(r.get('fail_to_pass', []))} | "
            f"{r.get('nop', {}).get('reward', '—')} | {' / '.join(str(o['reward']) for o in oracle) or '—'} | "
            f"{mut.get('killed', 0)}/{mut.get('total', 0)} = {mut.get('score')} | "
            f"{h.get('nop', {}).get('reward', '—')} | {h.get('oracle', {}).get('reward', '—')} | "
            f"{_gate(task['passed'])} |"
        )
    d = s["diversity"]
    lines += [
        "",
        "## Variation",
        "",
        f"- Distinct axes: {_gate(d['distinct_axes'])}; max code-footprint Jaccard "
        f"{d['max_symbol_jaccard']} (≤ {d['thresholds']['symbol_jaccard']}); max instruction cosine "
        f"{d['max_text_cosine']} (≤ {d['thresholds']['text_cosine']}) → {_gate(d['passed'])}",
        "",
        "| Pair | Footprint Jaccard | API Jaccard | Instruction cosine |",
        "|---|---|---|---|",
    ]
    for p in d["pairs"]:
        lines.append(f"| {p['a']} ↔ {p['b']} | {p['symbol_jaccard']} | {p['api_jaccard']} | {p['text_cosine']} |")
    lines += ["", "## Gate details", ""]
    for task in s["tasks"]:
        r = task["validation"]
        lines.append(f"### {task['id']}")
        lines.append("")
        for g, v in r.get("gates", {}).items():
            lines.append(f"- {_gate(v)} `{g}`")
        if r.get("failures"):
            lines.append("- Failures:")
            lines.extend(f"  - {f[:400]}" for f in r["failures"])
        surv = [m for m in r.get("mutation", {}).get("mutants", []) if not m["killed"]]
        if surv:
            lines.append("- Surviving mutants (reviewed in docs/VALIDATION.md):")
            lines.extend(f"  - `{m['path']}:{m['line']}` {m['description']}" for m in surv)
        prov = task.get("provenance", [])
        if prov:
            lines.append("- Generation trail: " + " → ".join(p["stage"] for p in prov))
        lines.append("")
    return "\n".join(lines) + "\n"


def dashboard(s: dict) -> str:
    rows = []
    for task in s["tasks"]:
        r = task["validation"]
        h = task.get("harbor", {})
        mut = r.get("mutation", {})
        score = mut.get("score") or 0
        rows.append(
            "<tr>"
            f"<td><b>{html.escape(task['id'])}</b><div class=sub>{html.escape(task['title'])}</div></td>"
            f"<td>{html.escape(task['axis'])}</td>"
            f"<td class=num>{len(r.get('fail_to_pass', []))}</td>"
            f"<td class=num>{r.get('nop', {}).get('reward', '—')}</td>"
            f"<td class=num>{' / '.join(str(o['reward']) for o in r.get('oracle', []))}</td>"
            f"<td><div class=bar><span style='width:{score*100:.0f}%'></span></div>"
            f"<div class=sub>{mut.get('killed', 0)}/{mut.get('total', 0)} killed</div></td>"
            f"<td class=num>{h.get('nop', {}).get('reward', '—')}</td>"
            f"<td class=num>{h.get('oracle', {}).get('reward', '—')}</td>"
            f"<td class=gate>{_gate(task['passed'])}</td></tr>"
        )
    d = s["diversity"]
    ids = [t["id"] for t in s["tasks"]]
    pair = {(p["a"], p["b"]): p for p in d["pairs"]}
    heat = ["<tr><th></th>" + "".join(f"<th>{i+1}</th>" for i in range(len(ids))) + "</tr>"]
    for i, a in enumerate(ids):
        cells = []
        for j, b in enumerate(ids):
            if i == j:
                cells.append("<td class=diag>—</td>")
                continue
            p = pair.get((a, b)) or pair.get((b, a))
            v = p["symbol_jaccard"]
            cells.append(f"<td style='background:rgba(27,58,140,{0.08 + v*0.9:.2f})'>{v}</td>")
        heat.append(f"<tr><th>{i+1}. {html.escape(a)}</th>{''.join(cells)}</tr>")
    t = s["target"]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>TriVerify report</title>
<style>body{{font:14px/1.45 Inter,system-ui,sans-serif;margin:32px;color:#14213a;background:#f6f8fc}}
h1{{margin:0}}.meta{{color:#4b5d78;margin:6px 0 20px}}table{{border-collapse:collapse;background:#fff;width:100%;margin-bottom:22px;box-shadow:0 1px 3px #0001}}
td,th{{padding:8px 10px;border-bottom:1px solid #e3e9f2;text-align:left;vertical-align:top}}th{{background:#f0f4fa;font-size:12px;text-transform:uppercase;letter-spacing:.4px}}
.num{{font-family:ui-monospace,monospace}}.sub{{color:#6b7c95;font-size:12px}}.gate{{font-size:18px;text-align:center}}
.bar{{height:8px;background:#e3e9f2;border-radius:4px;overflow:hidden;width:120px}}.bar span{{display:block;height:100%;background:#1f8a4c}}
.diag{{color:#aab}}.k{{display:inline-block;margin-right:18px;background:#fff;padding:10px 16px;border-radius:8px;box-shadow:0 1px 3px #0001}}.k b{{font-size:22px;display:block}}</style></head>
<body><h1>TriVerify Task Factory · run report</h1>
<div class=meta>{html.escape(t['repo'])} @ {html.escape(t['ref'])} ({t['base_commit'][:12]}) · {s['generated_at']} · Harbor {html.escape(s.get('harbor_version', 'n/a'))}</div>
<div><span class=k><b>{sum(1 for x in s['tasks'] if x['passed'])}/{len(s['tasks'])}</b>tasks pass every gate</span>
<span class=k><b>{len(s['baseline']['pass_to_pass'])}</b>regression tests guarded per task</span>
<span class=k><b>{d['max_symbol_jaccard']}</b>max code-footprint overlap</span></div><br>
<table><tr><th>Task</th><th>Axis</th><th>F2P</th><th>NOP</th><th>Oracle ×3</th><th>Mutation</th><th>Harbor nop</th><th>Harbor oracle</th><th>Gates</th></tr>{''.join(rows)}</table>
<h3>Code-footprint overlap (Jaccard)</h3><table style='width:auto'>{''.join(heat)}</table></body></html>"""
