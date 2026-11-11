#!/usr/bin/env python3
"""Score the forecasts in jobs-agent/journal/predictions.csv against what happened.

Each row says: on this date, this forecaster (agent or human) gave this probability that
this process reaches `interview` or `offer`. The outcome comes from the tracker, never
from the CSV:

  interview  yes  the tracker history ever reached interviewing (or offer)
             no   rejected or closed without ever reaching interviewing
  offer      yes  the tracker reached offer
             no   rejected or closed without an offer
  either     void if the candidate withdrew (passed); unresolved while the process is live

Scores: the Brier score (mean squared error of the probability; 0 is perfect, 0.25 is
what always saying 0.5 earns) per forecaster, and head-to-head on the rows where both
forecast the same event. The earliest forecast per (job, forecaster, event) is scored;
later rows are listed as updates.

Usage: python3 evals/predictions.py [--seed] [--db PATH] [--csv PATH] [--stdout]
"""
import argparse
import csv
import datetime as dt
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent / "jobs-agent"
sys.path.insert(0, str(HERE))
from calibration import seeded_db  # noqa: E402

EVENTS = ("interview", "offer")
FORECASTERS = ("agent", "human")
# The stage the process was at when the forecast was made: P(offer | applied) and
# P(offer | interviewing) are different questions and are never pooled.
STAGES = ("applied", "interviewing")


def load_forecasts(path: Path) -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            try:
                dt.date.fromisoformat(r["made_on"])
                p = float(r["p"])
                assert 0 <= p <= 1, "p outside 0–1"
                assert r["forecaster"] in FORECASTERS, f"forecaster must be one of {FORECASTERS}"
                assert r["event"] in EVENTS, f"event must be one of {EVENTS}"
                assert r.get("stage") in STAGES, f"stage must be one of {STAGES}"
            except (ValueError, KeyError, AssertionError) as e:
                problems.append(f"line {i}: {e}")
                continue
            r["p"] = p
            rows.append(r)
    return rows, problems


def resolve(con, job_id: str, event: str) -> str | None:
    """'yes', 'no', 'void', or None while unresolved; 'unknown-id' if not in the tracker."""
    row = con.execute("select status from jobs where id=?", (job_id,)).fetchone()
    if row is None:
        return "unknown-id"
    status = row[0]
    reached = {r[0] for r in con.execute("select to_status from events where job_id=?", (job_id,))}
    reached.add(status)
    if event == "interview" and ({"interviewing", "offer"} & reached):
        return "yes"
    if event == "offer" and "offer" in reached:
        return "yes"
    if status == "passed":
        return "void"
    if status in ("rejected", "closed"):
        return "no"
    return None


def brier(pairs) -> float | None:
    pairs = list(pairs)
    return round(sum((p - o) ** 2 for p, o in pairs) / len(pairs), 3) if pairs else None


def report(forecasts, con, problems) -> str:
    first, updates = {}, []
    for r in sorted(forecasts, key=lambda r: r["made_on"]):
        k = (r["job_id"], r["forecaster"], r["event"])
        if k in first:
            updates.append(r)
        else:
            first[k] = r
    for r in first.values():
        r["outcome"] = resolve(con, r["job_id"], r["event"])

    scored = [r for r in first.values() if r["outcome"] in ("yes", "no")]
    out = [f"# Forecasts against outcomes ({dt.date.today().isoformat()})", "",
           f"{len(forecasts)} forecast rows, {len(first)} first forecasts, {len(scored)} resolved.", ""]
    if problems:
        out += ["**Rows skipped:** " + "; ".join(problems), ""]

    out += ["## Brier score (lower is better; always saying 0.5 scores 0.250)", "",
            "| Forecaster | Stage → event | Resolved | Brier | Mean p | Hit rate |", "|---|---|---:|---:|---:|---:|"]
    for who in FORECASTERS:
        for st, ev in [(st, ev) for st in STAGES for ev in EVENTS]:
            s = [r for r in scored if r["forecaster"] == who and r["event"] == ev and r["stage"] == st]
            if not s:
                continue
            ys = [1 if r["outcome"] == "yes" else 0 for r in s]
            out.append(f"| {who} | {st} → {ev} | {len(s)} | {brier((r['p'], y) for r, y in zip(s, ys)):.3f} | "
                       f"{sum(r['p'] for r in s) / len(s):.2f} | {sum(ys) / len(ys):.2f} |")

    both = {}
    for (job, who, ev), r in first.items():
        if r["outcome"] in ("yes", "no"):
            both.setdefault((job, ev), {})[who] = r
    pairs = [v for v in both.values() if len(v) == 2]
    out += ["", "## Head to head (same process, same event, both forecast)", ""]
    if pairs:
        a = brier((v["agent"]["p"], v["agent"]["outcome"] == "yes") for v in pairs)
        l_ = brier((v["human"]["p"], v["human"]["outcome"] == "yes") for v in pairs)
        out.append(f"{len(pairs)} pairs. Agent {a:.3f}, human {l_:.3f}.")
    else:
        out.append("No resolved pairs yet.")

    out += ["", "## Every first forecast", "", "| Made | Job | Who | Stage → event | p | Outcome |", "|---|---|---|---|---:|---|"]
    for r in sorted(first.values(), key=lambda r: (r["job_id"], r["event"], r["forecaster"])):
        out.append(f"| {r['made_on']} | {r['job_id']} | {r['forecaster']} | {r['stage']} → {r['event']} | {r['p']:.2f} | {r['outcome'] or 'open'} |")
    if updates:
        out += ["", "Later updates (not scored): " + "; ".join(
            f"{u['job_id']} {u['forecaster']} {u['event']} {u['p']:.2f} on {u['made_on']}" for u in updates)]

    out += ["", "## What this can and cannot say", ""]
    if len(scored) < 20:
        out.append(f"- **Too few resolved forecasts ({len(scored)}) to tell skill from luck.** "
                   "Read the rows, not the averages, until there are at least twenty per forecaster.")
    out.append("- Forecasts are only honest if made before the outcome was known; the date column is the check.")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="build the tracker from jobs-agent/seed/board.sh, if you keep one")
    ap.add_argument("--db")
    ap.add_argument("--csv", default=str(AGENT / "journal" / "predictions.csv"))
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    db = Path(a.db) if a.db else (seeded_db() if a.seed else AGENT / "data" / "jobs.db")
    if not db.exists():
        print(f"no database at {db}; pass --db PATH, or --seed if you keep a seed script", file=sys.stderr)
        return 2
    forecasts, problems = load_forecasts(Path(a.csv))
    text = report(forecasts, sqlite3.connect(db), problems)
    if a.stdout:
        print(text)
    else:
        p = HERE / "reports" / f"predictions-{dt.date.today().isoformat()}.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text(text)
        print(f"wrote {p.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
