"""``triverify`` command line.

    triverify run      --config configs/click.toml       # everything below, end to end
    triverify generate --config … [--provider replay|handoff|anthropic|openai]
    triverify validate --config … [--only ID]
    triverify package  --config …
    triverify harbor   --config …                        # official nop/oracle matrix
    triverify report   --config …
    triverify answer KEY FILE                            # store a hand-off response
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import config as config_mod
from . import diversity, generate, harbor_runner, packager, report, validate
from .llm import CacheMiss, PendingHandoff, extract_json, make_provider
from .repo import ensure_base


def _provider(cfg):
    g = cfg.generation
    return make_provider(g.provider, g.model, cfg.root / g.cache_dir, cfg.root / g.pending_dir)


def _paths(cfg):
    out = cfg.output
    return {
        "specs": out / "specs",
        "validation": out / "validation",
        "tasks": out / "tasks",
        "harbor": out / "harbor",
        "baseline": out / "baseline.json",
        "proposals": out / "proposals.json",
    }


def cmd_generate(cfg, args) -> int:
    p = _paths(cfg)
    base = ensure_base(cfg)
    provider = _provider(cfg)
    pending = []
    try:
        proposals, prov = generate.propose(cfg, provider, base)
    except PendingHandoff as exc:
        print(f"[handoff] proposal prompt written to {cfg.generation.pending_dir}/{exc.key}.md")
        return 3
    p["proposals"].parent.mkdir(parents=True, exist_ok=True)
    p["proposals"].write_text(json.dumps({"provenance": prov, "proposals": proposals}, indent=2))
    p["specs"].mkdir(parents=True, exist_ok=True)
    for prop in proposals:
        dest = p["specs"] / f"{prop['id']}.json"
        if dest.exists() and not args.force:
            continue
        try:
            spec = generate.author(cfg, provider, base, prop)
        except PendingHandoff as exc:
            pending.append(exc.key)
            continue
        dest.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
        print(f"[author] {prop['id']}")
    if pending:
        print(f"[handoff] {len(pending)} authoring prompt(s) pending: {pending}")
        return 3
    return 0


def _load_specs(cfg, only=None) -> list[dict]:
    p = _paths(cfg)
    order = [x["id"] for x in json.loads(p["proposals"].read_text())["proposals"]]
    specs = [json.loads((p["specs"] / f"{i}.json").read_text()) for i in order]
    return [s for s in specs if not only or s["id"] in only]


def cmd_validate(cfg, args) -> int:
    p = _paths(cfg)
    base = ensure_base(cfg)
    if args.runner == "docker" and not validate.docker_image(cfg):
        tag = validate.build_image(cfg)
        os.environ["TRIVERIFY_DOCKER_IMAGE"] = tag
        print(f"[env] gates run inside the task image {tag} (network disabled)")
    if p["baseline"].exists() and not args.rebaseline:
        bl = json.loads(p["baseline"].read_text())
    else:
        print("[baseline] running the starting commit's test suite")
        bl = validate.baseline(cfg, base)
        p["baseline"].write_text(json.dumps(bl, indent=1))
    print(f"[baseline] {len(bl['pass_to_pass'])} pass-to-pass of {bl['collected']} collected")
    provider = _provider(cfg)
    status = 0
    for spec in _load_specs(cfg, args.only):
        for round_no in range(cfg.factory.max_repair_rounds + 1):
            t0 = time.monotonic()
            rep = validate.validate(cfg, base, spec, bl["pass_to_pass"])
            rep["seconds"] = round(time.monotonic() - t0, 1)
            rep["round"] = round_no
            validate.save(rep, p["validation"])
            mark = "PASS" if rep["passed"] else "FAIL"
            print(f"[validate] {spec['id']} round {round_no}: {mark} {rep['gates']}")
            if rep["passed"] or round_no == cfg.factory.max_repair_rounds:
                break
            try:
                spec = generate.repair(cfg, provider, spec, rep["failures"], round_no + 1)
            except PendingHandoff as exc:
                print(f"[handoff] repair prompt for {spec['id']} pending: {exc.key}")
                status = 3
                break
            except CacheMiss as exc:
                print(f"[repair] no cached repair for {spec['id']} ({exc.key}); keeping failure")
                break
            (p["specs"] / f"{spec['id']}.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False))
        if not rep["passed"] and status == 0:
            status = 1
    return status


def cmd_package(cfg, args) -> int:
    p = _paths(cfg)
    bl = json.loads(p["baseline"].read_text())
    for spec in _load_specs(cfg):
        rep = json.loads((p["validation"] / f"{spec['id']}.json").read_text())
        d = packager.write(cfg, spec, rep, bl["pass_to_pass"], p["tasks"])
        print(f"[package] {d.relative_to(cfg.root)}")
    return 0


def cmd_harbor(cfg, args) -> int:
    p = _paths(cfg)
    if not harbor_runner.available():
        print("[harbor] CLI not found; install with: pip install 'harbor==0.25.*'")
        return 2
    p["harbor"].mkdir(parents=True, exist_ok=True)
    jobs = cfg.workdir / "harbor-jobs"
    status = 0
    for spec in _load_specs(cfg, args.only):
        task_dir = p["tasks"] / spec["id"]
        res = {}
        res["lint"] = harbor_runner.lint(task_dir)
        print(f"[harbor] {spec['id']} lint: exit={res['lint']['exit_code']} findings={len(res['lint']['findings'])}")
        for agent in ("nop", "oracle"):
            r = harbor_runner.run(task_dir, agent, jobs)
            res[agent] = r
            print(f"[harbor] {spec['id']} {agent}: reward={r['reward']} expected={r['expected']} ok={r['ok']}")
            status |= 0 if r["ok"] else 1
        (p["harbor"] / f"{spec['id']}.json").write_text(json.dumps(res, indent=2))
    return status


def cmd_report(cfg, args) -> int:
    p = _paths(cfg)
    bl = json.loads(p["baseline"].read_text())
    specs = _load_specs(cfg)
    reps = {s["id"]: json.loads((p["validation"] / f"{s['id']}.json").read_text()) for s in specs}
    div = diversity.assess(specs, reps, cfg.factory.max_symbol_jaccard, cfg.factory.max_text_similarity)
    tasks = []
    for s in specs:
        hp = p["harbor"] / f"{s['id']}.json"
        harbor = json.loads(hp.read_text()) if hp.exists() else {}
        runs = {k: v for k, v in harbor.items() if k in ("nop", "oracle")}
        harbor_ok = all(v.get("ok") for v in runs.values()) if runs else None
        tasks.append({
            "id": s["id"], "title": s["title"], "axis": s["axis"], "difficulty": s.get("difficulty"),
            "validation": reps[s["id"]], "harbor": harbor, "provenance": s.get("provenance", []),
            "passed": reps[s["id"]]["passed"] and harbor_ok is not False,
        })
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": {"repo": cfg.target.url, "ref": cfg.target.ref, "base_commit": cfg.target.base_commit},
        "provider": cfg.generation.provider,
        "model": cfg.generation.model,
        "harbor_version": harbor_runner.version() if harbor_runner.available() else "not run",
        "baseline": bl,
        "diversity": div,
        "tasks": tasks,
        "all_passed": div["passed"] and all(t["passed"] for t in tasks),
    }
    report.build(summary, cfg.output)
    print(f"[report] {cfg.output / 'REPORT.md'} all_passed={summary['all_passed']}")
    return 0 if summary["all_passed"] else 1


def cmd_answer(args) -> int:
    """Store an external agent's answer to a pending hand-off prompt."""
    cfg = config_mod.load(args.config)
    pending = cfg.root / cfg.generation.pending_dir / f"{args.key}.md"
    head = pending.read_text().split("\n", 1)[0]
    stage = head.split("stage=")[1].split()[0]
    prompt = pending.read_text().split("-->\n\n", 2)[-1]
    response = Path(args.file).read_text()
    extract_json(response)  # must be valid JSON before it is accepted
    provider = make_provider("handoff", cfg.generation.model, cfg.root / cfg.generation.cache_dir, cfg.root / cfg.generation.pending_dir)
    provider.store(stage, prompt, response, {"answered_by": args.answered_by})
    pending.unlink()
    print(f"[answer] stored {args.key} ({stage})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="triverify", description="TriVerify Task Factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "generate", "validate", "package", "harbor", "report"):
        sp = sub.add_parser(name)
        sp.add_argument("--config", default="configs/click.toml")
        sp.add_argument("--provider", default=None)
        sp.add_argument("--only", nargs="*", default=None)
        sp.add_argument("--force", action="store_true")
        sp.add_argument("--rebaseline", action="store_true")
        sp.add_argument("--skip-harbor", action="store_true")
        sp.add_argument("--runner", choices=["local", "docker"], default=os.environ.get("TRIVERIFY_RUNNER", "local"))
    ans = sub.add_parser("answer")
    ans.add_argument("key")
    ans.add_argument("file")
    ans.add_argument("--config", default="configs/click.toml")
    ans.add_argument("--answered-by", default="coding-agent")
    args = ap.parse_args(argv)

    if args.cmd == "answer":
        return cmd_answer(args)
    cfg = config_mod.load(args.config, provider=args.provider)
    steps = {
        "generate": [cmd_generate],
        "validate": [cmd_validate],
        "package": [cmd_package],
        "harbor": [cmd_harbor],
        "report": [cmd_report],
        "run": [cmd_generate, cmd_validate, cmd_package] + ([] if args.skip_harbor else [cmd_harbor]) + [cmd_report],
    }[args.cmd]
    status = 0
    for step in steps:
        rc = step(cfg, args)
        if rc == 3:
            return 3  # waiting for a hand-off answer
        status |= rc
    return status


if __name__ == "__main__":
    sys.exit(main())
