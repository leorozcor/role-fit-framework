#!/usr/bin/env python3
"""Layer 4: check the checkers.

The graders are regexes and arithmetic written by the same model family that writes
the sheets. Their findings are claims, not facts. This script turns them into a
labelling sheet for a human, then measures how often the human agreed.

  sample  write evals/human-review/labels-<date>.csv from the latest reports' raw findings
          (every error and warning, plus up to 20 'check' items)
  score   read a labelled CSV and print agreement per rule

Label column: y (the finding is right), n (false alarm), ? (can't tell).
Add misses by hand as extra rows with rule = MISSED and label = y: that is the
grader's recall problem, which precision alone hides.

Usage:
  python3 evals/human_review.py sample
  python3 evals/human_review.py score evals/human-review/labels-2026-10-30.csv
"""
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "graders"))
import draft as draft_grader  # noqa: E402
import sheet as sheet_grader  # noqa: E402

AGENT = HERE.parent / "jobs-agent"
FIELDS = ["source", "item", "rule", "severity", "message", "label", "note"]


def findings():
    facts_p = AGENT / "profile" / "facts.md"
    facts = facts_p.read_text() if facts_p.exists() else ""
    never = draft_grader.load_never_claim(AGENT / "profile" / "never-claim.json")
    for r in sorted(p for p in (AGENT / "runs").iterdir() if p.is_dir()):
        sp = r / "sheet.md"
        if sp.exists() and sheet_grader.parse(sp.read_text()).is_v62:
            for f in sheet_grader.grade(sp.read_text(), (r / "application.md").exists())[1]:
                yield ("runs", r.name + "/sheet.md", f)
        ap = r / "application.md"
        if ap.exists():
            t = ap.read_text()
            jd = (r / "jd.md").read_text() if (r / "jd.md").exists() else ""
            for f in draft_grader.grade(t, facts, jd, format_checks=draft_grader.is_draft_format(t), never_claim=never):
                yield ("runs", r.name + "/application.md", f)
    results = sorted((HERE / "results").glob("*/"))
    if results:
        latest = results[-1]
        for g in sorted(latest.glob("*/grade.json")):
            d = json.loads(g.read_text())
            for c in d.get("checks", []):
                yield ("cases/" + latest.name, g.parent.name,
                       type("F", (), {"rule": "case: " + c["check"], "severity": "pass" if c["ok"] else "fail",
                                      "message": c["detail"]})())


def sample():
    out = HERE / "human-review" / f"labels-{dt.date.today().isoformat()}.csv"
    out.parent.mkdir(exist_ok=True)
    checks = 0
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        for src, item, f in findings():
            if f.severity == "check":
                checks += 1
                if checks > 20:
                    continue
            if f.severity == "info":
                continue
            w.writerow({"source": src, "item": item, "rule": f.rule, "severity": f.severity,
                        "message": f.message, "label": "", "note": ""})
    print(f"wrote {out.relative_to(HERE.parent)}; fill the label column (y / n / ?)")


def score(path):
    by_rule = defaultdict(Counter)
    for row in csv.DictReader(open(path)):
        lab = (row.get("label") or "").strip().lower()[:1]
        if lab:
            by_rule[row["rule"]][lab] += 1
    if not by_rule:
        print("no labels yet")
        return
    print(f"{'rule':55} {'agree':>6} {'false':>6} {'?':>4}  precision")
    tot = Counter()
    for rule, c in sorted(by_rule.items()):
        tot.update(c)
        dec = c["y"] + c["n"]
        prec = f"{c['y'] / dec:.0%}" if dec else "–"
        print(f"{rule[:55]:55} {c['y']:>6} {c['n']:>6} {c['?']:>4}  {prec}")
    dec = tot["y"] + tot["n"]
    print(f"\noverall: {tot['y']}/{dec} findings confirmed" + (f" ({tot['y'] / dec:.0%})" if dec else "")
          + f"; misses added by hand: {by_rule.get('MISSED', Counter())['y']}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "sample":
        sample()
    elif len(sys.argv) >= 3 and sys.argv[1] == "score":
        score(sys.argv[2])
    else:
        print(__doc__)
