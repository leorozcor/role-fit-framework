#!/usr/bin/env python3
"""Layer 2: run the real agent on fixed cases and grade what it did.

For each case:
  1. Copy jobs-agent/ into a fresh sandbox (no runs, no database, no .env, no profile),
     then install the fictional eval persona (evals/persona/) as its profile. The cases
     are written for that persona, so your own fact base never enters a case run. The
     agent never sees evals/: expectations and graders stay out of its reach.
  2. Run the case's setup (bin/jobs add / record, fixture files).
  3. Run the slash command headless: claude -p "/score inbox/<case>.md".
  4. Grade: the case's expectations, plus the deterministic sheet and draft graders.

Paired cases (injection, pressure) are compared with their control run.
Repeats (--repeat N) measure run-to-run variance on the same input.

Usage:
  python3 evals/run_cases.py                      # all cases, once
  python3 evals/run_cases.py positive-marketplace control-logistics --repeat 3
  python3 evals/run_cases.py --jobs 4 --model claude-opus-5-5

Cost: every case is a full agent session that reads the framework. Expect several
minutes and a noticeable share of plan usage per run. Run it after changing CLAUDE.md,
the commands or the model, not on a schedule.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
AGENT = REPO / "jobs-agent"
sys.path.insert(0, str(HERE / "graders"))
import draft as draft_grader  # noqa: E402
import sheet as sheet_grader  # noqa: E402

EXCLUDE = {"runs", "data", ".env", "seed", "profile", "journal", "__pycache__"}
PERSONA = HERE / "persona"


def make_sandbox(root: Path) -> Path:
    sb = root / "agent"
    shutil.copytree(AGENT, sb, ignore=lambda d, names: [n for n in names if Path(d) == AGENT and n in EXCLUDE])
    shutil.copytree(PERSONA, sb / "profile")  # the fictional candidate the cases are written for
    (sb / "runs").mkdir()
    (sb / "inbox").mkdir()
    subprocess.run([sys.executable, "bin/jobs", "init"], cwd=sb, check=True, capture_output=True)
    return sb


def jobs(sb: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bin/jobs", *args], cwd=sb, capture_output=True, text=True)


def all_ids(sb: Path) -> list[str]:
    import sqlite3
    con = sqlite3.connect(sb / "data" / "jobs.db")
    return [r[0] for r in con.execute("select id from jobs order by first_seen")]


def run_case(case_dir: Path, out_dir: Path, model: str | None, timeout: int, keep_sandbox: bool = False) -> dict:
    case = json.loads((case_dir / "case.json").read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    sb = make_sandbox(out_dir)
    jd_src = (case_dir / case["jd"]).resolve()
    jd_rel = f"inbox/{case['id']}.md"
    shutil.copy(jd_src, sb / jd_rel)

    job_id = None
    for step in case.get("setup", []):
        if isinstance(step, dict):  # fixture file
            dst = sb / step["to"].format(id=job_id)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(case_dir / step["copy"], dst)
            continue
        args = [a.format(jd=jd_rel, id=job_id) for a in step]
        r = jobs(sb, *args)
        if r.returncode != 0:
            return {"id": case["id"], "error": f"setup failed: {' '.join(args)}: {r.stderr.strip()}"}
        if args[0] == "add":
            job_id = r.stdout.strip().splitlines()[0]

    if case["command"] == "score":
        prompt = f"/score {jd_rel}"
    else:
        prompt = f"/{case['command']} {job_id}"
    if case.get("extra"):
        prompt += f"\n\n{case['extra']}"

    # Headless runs ignore an untrusted folder's project settings, so pass the agent's own
    # settings file explicitly: the same allow and deny lists as in real use, nothing added.
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--max-turns", "80",
           "--settings", ".claude/settings.json"]
    if model:
        cmd += ["--model", model]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=sb, capture_output=True, text=True, timeout=timeout)
        raw = proc.stdout
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        proc = None
    elapsed = time.time() - t0
    (out_dir / "transcript.json").write_text(raw)
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        meta = {"result": raw, "is_error": True}
    transcript = meta.get("result") or ""

    ids = all_ids(sb)
    job_id = job_id or (ids[-1] if ids else None)
    show = json.loads(jobs(sb, "show", job_id).stdout) if job_id else {}
    run_dir = sb / "runs" / job_id if job_id else None
    sheet_text = (run_dir / "sheet.md").read_text() if run_dir and (run_dir / "sheet.md").exists() else ""
    app_path = run_dir / "application.md" if run_dir else None
    app_text = app_path.read_text() if app_path and app_path.exists() else ""
    for name, text in (("sheet.md", sheet_text), ("application.md", app_text)):
        if text:
            (out_dir / name).write_text(text)
    (out_dir / "show.json").write_text(json.dumps(show, indent=1, ensure_ascii=False))

    result = {
        "id": case["id"], "job_id": job_id, "seconds": round(elapsed), "turns": meta.get("num_turns"),
        "cost_usd": meta.get("total_cost_usd"), "agent_error": bool(meta.get("is_error")) or proc is None,
        "status": show.get("status"), "verdict": show.get("verdict"), "org_total": show.get("org_total"),
        "candidate_fit": show.get("candidate_fit"), "jobs_in_db": len(ids),
    }
    checks = grade_case(case, show, sheet_text, app_text, transcript, jd_src.read_text())
    result["checks"] = checks
    result["passed"] = all(c["ok"] for c in checks) and not result["agent_error"]
    (out_dir / "grade.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    # Keep the outputs, not the sandbox: it is a full copy of the agent.
    if not keep_sandbox:
        shutil.rmtree(sb, ignore_errors=True)
    return result


def grade_case(case, show, sheet_text, app_text, transcript, jd) -> list[dict]:
    exp = case.get("expect", {})
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    where = {"sheet": sheet_text, "transcript": transcript, "application": app_text}
    v, cf_, st = show.get("verdict"), show.get("candidate_fit"), show.get("status")
    # The tracker is the record of judgment; fall back to the sheet when the agent didn't record.
    parsed = sheet_grader.parse(sheet_text) if sheet_text else None
    if not v and parsed:
        v = parsed.verdict
    if not cf_ and parsed:
        cf_ = parsed.candidate_fit

    if "status_in" in exp:
        check("status in " + "/".join(exp["status_in"]), st in exp["status_in"], f"status={st}")
    if "status_not_in" in exp:
        check("status not " + "/".join(exp["status_not_in"]), st not in exp["status_not_in"], f"status={st}")
    if "verdict_in" in exp:
        check("verdict in " + "/".join(exp["verdict_in"]), v in exp["verdict_in"], f"verdict={v}")
    if "candidate_fit_not_in" in exp:
        check("candidate fit not " + "/".join(exp["candidate_fit_not_in"]), cf_ not in exp["candidate_fit_not_in"],
              f"candidate_fit={cf_}")
    if "candidate_fit_in" in exp:
        check("candidate fit in " + "/".join(exp["candidate_fit_in"]), cf_ in exp["candidate_fit_in"], f"candidate_fit={cf_}")
    if exp.get("no_application"):
        check("no application drafted", not app_text)
    if exp.get("application"):
        check("application drafted", bool(app_text))
    if exp.get("no_factor_scores"):
        check("no factor scores after a failed gate", not (parsed and parsed.factors),
              f"{len(parsed.factors) if parsed else 0} factors scored")
    if exp.get("gate_note_nonempty"):
        check("unresolved gate recorded in tracker", bool(show.get("gate_note")), (show.get("gate_note") or "")[:80])
    if "max_factor_score" in exp and parsed:
        top = max((d["score"] for d in parsed.factors.values()), default=0)
        check(f"no factor above {exp['max_factor_score']}", top <= exp["max_factor_score"],
              ", ".join(f"{n}:{d['score']:g}/{d['ev']}" for n, d in sorted(parsed.factors.items()) if d["score"] > exp["max_factor_score"]))
    for t in exp.get("text_any", []):
        check(f"{t['where']} matches /{t['pattern']}/", re.search(t["pattern"], where[t["where"]]))
    for t in exp.get("text_none", []):
        m = re.search(t["pattern"], where[t["where"]])
        check(f"{t['where']} does not match /{t['pattern']}/", not m, m.group(0) if m else "")
    # Always: the tracker and the sheet must tell the same story.
    if parsed and parsed.stated_total is not None and show.get("org_total") is not None:
        check("tracker total matches sheet total", abs(parsed.stated_total - show["org_total"]) <= 0.05,
              f"sheet {parsed.stated_total} vs tracker {show['org_total']}")
    if parsed and parsed.verdict and show.get("verdict"):
        check("tracker verdict matches sheet verdict", parsed.verdict == show["verdict"],
              f"sheet {parsed.verdict} vs tracker {show['verdict']}")
    if exp.get("sheet_rules_clean"):
        if not sheet_text:
            check("sheet exists for the rule graders", False)
        else:
            errs = [f for f in sheet_grader.grade(sheet_text, bool(app_text))[1] if f.severity == "error"]
            check("sheet obeys its rules (grader errors: 0)", not errs, "; ".join(f"{f.rule}: {f.message}" for f in errs)[:300])
    if exp.get("draft_rules_clean") and app_text:
        facts = (PERSONA / "facts.md").read_text()
        errs = [f for f in draft_grader.grade(app_text, facts, jd) if f.severity == "error"]
        check("draft obeys its rules (grader errors: 0)", not errs, "; ".join(f"{f.rule}: {f.message}" for f in errs)[:300])
    if exp.get("unsupported_mentions") and app_text:
        sec = re.search(r"^##\s+Requirements the fact base does not support\s*$(.*?)(?=^##\s|\Z)", app_text, re.M | re.S)
        body = sec.group(1) if sec else ""
        for pat in exp["unsupported_mentions"]:
            check(f"unsupported list names /{pat}/", re.search(pat, body))
    return checks


def regrade(root: Path, cases: dict) -> dict:
    """Grade saved outputs again with the current graders, without calling the agent."""
    results: dict = {}
    for g in sorted(root.glob("*/grade.json")):
        old = json.loads(g.read_text())
        cid = old["id"]
        case = cases[cid]
        d = g.parent
        read = lambda n: (d / n).read_text() if (d / n).exists() else ""
        show = json.loads(read("show.json") or "{}")
        try:
            transcript = json.loads(read("transcript.json")).get("result") or ""
        except json.JSONDecodeError:
            transcript = read("transcript.json")
        jd = (HERE / "cases" / cid / case["jd"]).read_text()
        old["checks"] = grade_case(case, show, read("sheet.md"), read("application.md"), transcript, jd)
        old["passed"] = all(c["ok"] for c in old["checks"]) and not old.get("agent_error")
        g.write_text(json.dumps(old, indent=1, ensure_ascii=False))
        results.setdefault(cid, []).append(old)
    return results


def compare_pairs(results: dict, cases: dict) -> list[dict]:
    out = []
    for cid, case in cases.items():
        ctrl = case.get("paired_with")
        if not ctrl or cid not in results or ctrl not in results:
            continue
        a = [r for r in results[cid] if r.get("org_total") is not None]
        b = [r for r in results[ctrl] if r.get("org_total") is not None]
        if not a or not b:
            out.append({"case": cid, "control": ctrl, "ok": False, "detail": "missing a recorded total"})
            continue
        ma, mb = statistics.mean(r["org_total"] for r in a), statistics.mean(r["org_total"] for r in b)
        delta = round(ma - mb, 2)
        ok = abs(delta) <= case.get("max_total_delta", 0.5)
        va = {r["verdict"] for r in a}
        vb = {r["verdict"] for r in b}
        if case.get("same_verdict"):
            ok = ok and va == vb
        out.append({"case": cid, "control": ctrl, "ok": ok, "delta": delta,
                    "detail": f"total {ma:.2f} vs control {mb:.2f} (Δ {delta:+.2f}); verdicts {sorted(va)} vs {sorted(vb)}"})
    return out


def report(results: dict, pairs: list, cases: dict, stamp: str, model: str | None) -> str:
    flat = [r for rs in results.values() for r in rs]
    passed = sum(1 for r in flat if r.get("passed"))
    cost = sum(r.get("cost_usd") or 0 for r in flat)
    lines = [f"# Behavioural eval, {stamp}", "",
             f"Model: {model or 'Claude Code default'}. Runs: {len(flat)}. Passed every check: **{passed}/{len(flat)}**. "
             f"Paired comparisons passed: **{sum(p['ok'] for p in pairs)}/{len(pairs)}**. "
             f"Reported cost: ${cost:.2f}.", "",
             "| Case | Run | Pass | Verdict | Total | Candidate | Status | Turns | Time | Failed checks |",
             "|---|---|---|---|---:|---|---|---:|---:|---|"]
    for cid, rs in results.items():
        for i, r in enumerate(rs, 1):
            failed = "; ".join(f"{c['check']} ({c['detail']})" if c["detail"] else c["check"]
                               for c in r.get("checks", []) if not c["ok"]) or r.get("error", "")
            lines.append(f"| {cid} | {i} | {'✅' if r.get('passed') else '❌'} | {r.get('verdict') or '–'} | "
                         f"{r.get('org_total') if r.get('org_total') is not None else '–'} | {r.get('candidate_fit') or '–'} | "
                         f"{r.get('status') or '–'} | {r.get('turns') or '–'} | {r.get('seconds', 0)//60}m | {failed} |")
    if pairs:
        lines += ["", "## Paired comparisons (same posting, one thing changed)", ""]
        for p in pairs:
            lines.append(f"- {'✅' if p['ok'] else '❌'} **{p['case']}** vs {p['control']}: {p['detail']}")
    multi = {cid: rs for cid, rs in results.items() if len(rs) > 1}
    if multi:
        lines += ["", "## Run-to-run variance (same input, repeated)", "",
                  "| Case | Runs | Totals | Spread | Verdicts | Candidate fit |", "|---|---:|---|---:|---|---|"]
        for cid, rs in multi.items():
            tots = [r["org_total"] for r in rs if r.get("org_total") is not None]
            spread = round(max(tots) - min(tots), 2) if tots else "–"
            lines.append(f"| {cid} | {len(rs)} | {', '.join(map(str, tots))} | {spread} | "
                         f"{', '.join(str(r.get('verdict')) for r in rs)} | {', '.join(str(r.get('candidate_fit')) for r in rs)} |")
    lines += ["", "## Why each case exists", ""]
    for cid in results:
        lines.append(f"- **{cid}**: {cases[cid]['why']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", help="case ids (default: all)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=3, help="parallel agent sessions")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=1500, help="seconds per run")
    ap.add_argument("--keep-sandbox", action="store_true", help="keep each run's agent copy for debugging")
    ap.add_argument("--regrade", metavar="RESULTS_DIR", help="re-grade a saved run with the current graders; no agent calls")
    a = ap.parse_args()

    if a.regrade:
        all_cases = {p.parent.name: json.loads(p.read_text()) for p in sorted((HERE / "cases").glob("*/case.json"))}
        root = Path(a.regrade).resolve()
        results = regrade(root, all_cases)
        pairs = compare_pairs(results, all_cases)
        text = report(results, pairs, all_cases, root.name, a.model)
        (HERE / "reports").mkdir(exist_ok=True)
        (HERE / "reports" / f"behaviour-{root.name}.md").write_text(text)
        (root / "summary.json").write_text(json.dumps({"results": results, "pairs": pairs}, indent=1, ensure_ascii=False))
        print(f"regraded {sum(map(len, results.values()))} runs; wrote evals/reports/behaviour-{root.name}.md")
        return 0

    if not shutil.which("claude"):
        print("claude (Claude Code CLI) not found on PATH", file=sys.stderr)
        return 2
    all_cases = {p.parent.name: json.loads(p.read_text()) for p in sorted((HERE / "cases").glob("*/case.json"))}
    ids = a.cases or list(all_cases)
    # A paired case needs its control in the same batch.
    for cid in list(ids):
        ctrl = all_cases[cid].get("paired_with")
        if ctrl and ctrl not in ids:
            ids.append(ctrl)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    root = HERE / "results" / stamp
    jobs_list = [(cid, n) for cid in ids for n in range(1, a.repeat + 1)]
    results: dict = {cid: [] for cid in ids}
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(run_case, HERE / "cases" / cid, root / f"{cid}-r{n}", a.model, a.timeout, a.keep_sandbox): cid for cid, n in jobs_list}
        for fut in cf.as_completed(futs):
            cid = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # keep the batch going; record the failure
                r = {"id": cid, "error": f"{type(e).__name__}: {e}", "passed": False}
            results[cid].append(r)
            print(f"{'PASS' if r.get('passed') else 'FAIL'} {cid} {r.get('verdict')} {r.get('org_total')} "
                  f"{r.get('candidate_fit')} {r.get('seconds', '?')}s", flush=True)
    pairs = compare_pairs(results, all_cases)
    text = report(results, pairs, all_cases, stamp, a.model)
    (HERE / "reports").mkdir(exist_ok=True)
    (HERE / "reports" / f"behaviour-{stamp}.md").write_text(text)
    (root / "summary.json").write_text(json.dumps({"results": results, "pairs": pairs}, indent=1, ensure_ascii=False))
    print(f"\nwrote evals/reports/behaviour-{stamp}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
