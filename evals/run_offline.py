#!/usr/bin/env python3
"""Layer 1: grade every existing sheet and draft in jobs-agent/runs/ against the rules.

No model calls, no cost, seconds to run. Writes evals/reports/offline-<date>.md.

Only fresh v6.2 sheets are graded strictly. Older or hand-reconstructed records are
counted, not graded: they were not produced by the agent, so grading them would measure
the reconstruction. Drafts are checked against your own profile/facts.md and, if it
exists, your private profile/never-claim.json.

Usage: python3 evals/run_offline.py [--stdout]
"""
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "graders"))
import draft as draft_grader  # noqa: E402
import sheet as sheet_grader  # noqa: E402

AGENT = HERE.parent / "jobs-agent"


def main() -> int:
    runs = sorted(p for p in (AGENT / "runs").iterdir() if p.is_dir())
    facts_p = AGENT / "profile" / "facts.md"
    facts = facts_p.read_text() if facts_p.exists() else ""
    never = draft_grader.load_never_claim(AGENT / "profile" / "never-claim.json")
    graded, skipped, rows, by_rule = [], Counter(), [], Counter()

    for r in runs:
        sp = r / "sheet.md"
        if not sp.exists():
            skipped["no sheet"] += 1
            continue
        text = sp.read_text()
        parsed = sheet_grader.parse(text)
        if not parsed.is_v62:
            skipped["reconstructed / not a v6.2 sheet"] += 1
            continue
        s, findings = sheet_grader.grade(text, (r / "application.md").exists())
        graded.append(r.name)
        for f in findings:
            by_rule[(f.rule, f.severity)] += 1
            rows.append((r.name, "sheet", f))

    drafts = sorted(r for r in runs if (r / "application.md").exists())
    skipped_format = []
    for r in drafts:
        jd = (r / "jd.md").read_text() if (r / "jd.md").exists() else ""
        text = (r / "application.md").read_text()
        fmt = draft_grader.is_draft_format(text)
        if not fmt:
            skipped_format.append(r.name)
        for f in draft_grader.grade(text, facts, jd, format_checks=fmt, never_claim=never):
            by_rule[(f.rule, f.severity)] += 1
            rows.append((r.name, "draft", f))

    errors = sum(1 for _, _, f in rows if f.severity == "error")
    clean = [g for g in graded if not any(n == g and f.severity == "error" for n, _, f in rows)]
    today = dt.date.today().isoformat()
    out = [f"# Offline eval: existing sheets and drafts, {today}", "",
           f"- Sheets graded (fresh v6.2): **{len(graded)}**; without a rule error: **{len(clean)}**",
           f"- Not graded: " + ", ".join(f"{v} {k}" for k, v in skipped.items()),
           f"- Drafts graded: **{len(drafts)}**" + (f" (hand-written, not /draft format, so content checks only: {', '.join(skipped_format)})" if skipped_format else ""),
           f"- Errors: **{errors}**; warnings: **{sum(1 for _, _, f in rows if f.severity == 'warn')}**; "
           f"names for a human to check: **{sum(1 for _, _, f in rows if f.severity == 'check')}**", "",
           "## By rule", "", "| Rule | Severity | Count |", "|---|---|---:|"]
    for (rule, sev), n in sorted(by_rule.items(), key=lambda x: ({"error": 0, "warn": 1}.get(x[0][1], 2), -x[1])):
        out.append(f"| {rule} | {sev} | {n} |")
    out += ["", "## Findings", ""]
    for name, kind, f in sorted(rows, key=lambda x: ({"error": 0, "warn": 1}.get(x[2].severity, 2), x[0])):
        out.append(f"- **{f.severity}** `{f.rule}` {name} ({kind}): {f.message}")
    report = "\n".join(out) + "\n"

    if "--stdout" in sys.argv:
        print(report)
    else:
        p = HERE / "reports" / f"offline-{today}.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text(report)
        print(f"wrote {p.relative_to(HERE.parent)}: {len(graded)} sheets, {len(drafts)} drafts, {errors} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
