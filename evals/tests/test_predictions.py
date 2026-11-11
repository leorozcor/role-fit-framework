"""Tests for evals/predictions.py: resolution from the tracker, and the Brier arithmetic."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import predictions as P  # noqa: E402


def tracker(jobs):
    """jobs: {id: (status, [statuses reached via events])}"""
    con = sqlite3.connect(":memory:")
    con.execute("create table jobs (id text, status text)")
    con.execute("create table events (job_id text, to_status text)")
    for jid, (status, path) in jobs.items():
        con.execute("insert into jobs values (?,?)", (jid, status))
        for s in path:
            con.execute("insert into events values (?,?)", (jid, s))
    return con


class Resolve(unittest.TestCase):
    def setUp(self):
        self.con = tracker({
            "a": ("rejected", ["applied", "interviewing", "rejected"]),
            "b": ("rejected", ["applied", "rejected"]),
            "c": ("interviewing", ["applied", "interviewing"]),
            "d": ("passed", ["applied", "passed"]),
            "e": ("offer", ["applied", "interviewing", "offer"]),
            "f": ("closed", ["applied", "closed"]),
        })

    def test_interview(self):
        r = {j: P.resolve(self.con, j, "interview") for j in "abcdef"}
        self.assertEqual(r, {"a": "yes", "b": "no", "c": "yes", "d": "void", "e": "yes", "f": "no"})

    def test_offer(self):
        r = {j: P.resolve(self.con, j, "offer") for j in "abcdef"}
        self.assertEqual(r, {"a": "no", "b": "no", "c": None, "d": "void", "e": "yes", "f": "no"})

    def test_unknown_id(self):
        self.assertEqual(P.resolve(self.con, "zzz", "interview"), "unknown-id")


class Scoring(unittest.TestCase):
    def test_brier(self):
        self.assertEqual(P.brier([(0.5, 1), (0.5, 0)]), 0.25)
        self.assertEqual(P.brier([(1.0, 1), (0.0, 0)]), 0.0)
        self.assertIsNone(P.brier([]))

    def test_report_scores_first_forecast_and_pairs(self):
        con = tracker({"a": ("rejected", ["interviewing", "rejected"]), "b": ("rejected", ["rejected"])})
        csv_text = ("made_on,job_id,forecaster,stage,event,p,basis\n"
                    "2026-11-01,a,agent,applied,interview,0.2,x\n"
                    "2026-11-01,a,human,applied,interview,0.8,x\n"
                    "2026-11-05,a,human,applied,interview,0.1,update\n"
                    "2026-11-01,b,agent,applied,interview,0.3,x\n"
                    "2026-11-01,b,agent,applied,interview,2,bad\n")
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(csv_text)
        rows, problems = P.load_forecasts(Path(f.name))
        self.assertEqual(len(problems), 1)
        text = P.report(rows, con, problems)
        self.assertIn("1 pairs. Agent 0.640, human 0.040.", text)  # (0.2-1)^2 vs (0.8-1)^2
        self.assertIn("Later updates", text)


if __name__ == "__main__":
    unittest.main()
