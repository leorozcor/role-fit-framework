#!/usr/bin/env python3
"""Layer 3: did the ratings predict anything?

The framework makes two separate claims, and this script tests each one against
what actually happened:

  1. Candidate fit (will they pick me?) should predict selection outcomes.
  2. Organizational fit (would I thrive there?) should NOT predict selection.
     It is a judgment about the environment, not about being chosen. If the
     organizational verdict predicted rejections as well as candidate fit did,
     the two axes would not be measuring different things.

It reads the tracker database: the live one on your laptop by default
(jobs-agent/data/jobs.db), or, with --seed, a fresh database built from a seed
script at jobs-agent/seed/board.sh, if you keep one (a shell script of bin/jobs calls
that rebuilds a reconstructed board; keep it private).

Usage: python3 evals/calibration.py [--seed] [--db PATH] [--stdout]
"""
import argparse
import datetime as dt
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent / "jobs-agent"
REACHED = ("interviewing", "offer")
OUTCOME_STATES = ("interviewing", "offer", "rejected")


def seeded_db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="calib-"))
    sb = tmp / "agent"
    shutil.copytree(AGENT, sb, ignore=shutil.ignore_patterns("data", ".env"))
    subprocess.run([sys.executable, "bin/jobs", "init"], cwd=sb, check=True, capture_output=True)
    if not (sb / "seed" / "board.sh").exists():
        sys.exit("no seed script at jobs-agent/seed/board.sh; use --db or the live database")
    subprocess.run(["bash", "seed/board.sh"], cwd=sb, check=True, capture_output=True)
    return sb / "data" / "jobs.db"


def was_interviewing(con, job_id) -> bool:
    """True if the tracker history ever moved this job to interviewing."""
    return con.execute("select 1 from events where job_id=? and to_status='interviewing' limit 1", (job_id,)).fetchone() is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="build from the committed seed instead of the live database")
    ap.add_argument("--db")
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    db = Path(a.db) if a.db else (seeded_db() if a.seed else AGENT / "data" / "jobs.db")
    if not db.exists():
        print(f"no database at {db}; pass --db PATH, or --seed if you keep a seed script", file=sys.stderr)
        return 2
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("select * from jobs")]

    def stage(r):
        if r["status"] in REACHED:
            return "reached interview"
        if r["status"] == "rejected":
            return "rejected after interview" if was_interviewing(con, r["id"]) else "rejected (stage unrecorded or at application)"
        return None

    out = [f"# Calibration: did the ratings predict selection? ({dt.date.today().isoformat()})", "",
           f"Source: `{'seed (reconstructed board)' if a.seed else db}`. {len(rows)} opportunities.", ""]

    # 1. Candidate fit against outcomes.
    cand = [r for r in rows if r.get("candidate_fit") and r["status"] in OUTCOME_STATES]
    no_cand = [r for r in rows if not r.get("candidate_fit") and r["status"] in OUTCOME_STATES]
    table = defaultdict(Counter)
    for r in cand:
        table[r["candidate_fit"]][stage(r)] += 1
    cols = ["reached interview", "rejected after interview", "rejected (stage unrecorded or at application)"]
    out += ["## 1. Candidate fit against what happened", "",
            f"Roles with a candidate-fit rating **and** a selection outcome: **{len(cand)}**. "
            f"Roles with an outcome but no rating (scored before the axis existed, or never scored): {len(no_cand)}.", "",
            "| Candidate fit | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for level in ("High", "Medium", "Low"):
        out.append(f"| {level} | " + " | ".join(str(table[level][c]) for c in cols) + " |")
    out += ["", "Each row, so the stage can be checked by hand (stage = the tracker history ever reached `interviewing`):", ""]
    for r in sorted(cand, key=lambda r: (r["candidate_fit"], r["company"])):
        out.append(f"- {r['candidate_fit']}: {r['company']}, {r['title']}: {stage(r)}"
                   + (f" (reason: {r['outcome_reason']})" if r.get("outcome_reason") else ""))

    # 2. Organizational verdict against outcomes (should be unrelated).
    org = defaultdict(Counter)
    for r in rows:
        if r.get("verdict") and r["status"] in OUTCOME_STATES:
            org[r["verdict"]][stage(r)] += 1
    out += ["", "## 2. Organizational verdict against what happened (expected: no relationship)", "",
            "| Verdict | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for v in ("Strong", "Viable", "Gig", "Pass"):
        if org[v]:
            out.append(f"| {v} | " + " | ".join(str(org[v][c]) for c in cols) + " |")

    # 3. Reasons.
    reasons = Counter(r["outcome_reason"] for r in rows if r.get("outcome_reason"))
    tagged_selection = sum(n for k, n in reasons.items() if k not in ("his-call", "no-reply", "no-buyer"))
    out += ["", "## 3. Why processes ended", "",
            ", ".join(f"{k}: {n}" for k, n in reasons.most_common()), "",
            f"Ended by the employer with a tag: {tagged_selection}, of which `unknown`: {reasons.get('unknown', 0)}."]

    # Verdict on the evidence.
    n = len(cand)
    out += ["", "## What this can and cannot say", ""]
    if n < 20:
        out.append(f"- **Not enough data to test the claim.** {n} rated outcomes cannot separate a useful rating from "
                   "chance: with this few, one more rejection moves any rate by more than ten points. "
                   "Read the table as a list of cases, not as evidence.")
    out.append("- The candidate-fit axis is weeks old; most outcomes predate it and carry no rating. "
               "Ratings were not back-filled on purpose: rating an outcome you already know is hindsight, not prediction.")
    out.append("- What would count as evidence: by the framework review (31.1.2027 or ten more tagged outcomes), "
               "High and Medium reach interview clearly more often than Low, **and** the organizational verdict does not.")
    text = "\n".join(out) + "\n"
    if a.stdout:
        print(text)
    else:
        p = HERE / "reports" / f"calibration-{dt.date.today().isoformat()}.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text(text)
        print(f"wrote {p.relative_to(HERE.parent)}: {n} rated outcomes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
