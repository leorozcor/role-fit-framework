"""Tests for the graders. A grader nobody has tested is just another opinion.

Each rule gets one sheet that should trigger it and the clean baseline that should not.
Run: python3 -m unittest discover -s evals/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "graders"))
import draft  # noqa: E402
import sheet  # noqa: E402

W = sheet.WEIGHTS


def make_sheet(scores=None, ev=None, total=None, verdict="Viable (conditional on salary)", cand="Medium",
               gates=("pass", "unresolved", "pass", "pass"), load_line=None, combined=None,
               selection="1. Marketplace trust and safety leadership. ☒ Met literally",
               level_row="| Level matches | ☒ | |"):
    scores = scores or {1: 6, 2: 6, 3: 6, 4: 6, 5: 6, 6: 6, 7: 6, 8: 6, 9: 6}
    ev = ev or {n: "A" for n in W}
    if total is None:
        total = round(sum(scores[n] * W[n] for n in W) / 100, 2)
    lb = [n for n in (1, 2, 3, 4) if scores[n] <= 4]
    if load_line is None:
        load_line = "**Load-bearing check:** " + (f"factor {lb} → **warning**." if lb else "none ≤4. No warnings.")
    v_word = verdict.split()[0]
    if combined is None:
        action = {("Viable", "Medium"): "low-cost pursuit", ("Strong", "Medium"): "pursue, warm route preferred",
                  ("Pass", "Medium"): "Pass", ("Pass", "Low"): "Pass", ("Strong", "High"): "pursue hard",
                  ("Viable", "High"): "pursue selectively", ("Pass", "High"): "danger zone"}.get((v_word, cand), "")
        combined = f"**Combined reading:** {v_word} × {cand} → **{action}**."
    cols = {"pass": "| ☒ | | |", "unresolved": "| | ☒ | |", "fail": "| | | ☒ |"}
    labels = ["Salary floor €9,000 base cash", "Geography", "Real, authorized, live", "No dealbreakers"]
    gate_rows = "\n".join(f"| {l} {cols[g]} note |" for l, g in zip(labels, gates))
    rows = "\n".join(f"| {n} | {sheet.FACTOR_NAMES[n]} | {W[n]}% | {scores[n]} | {ev[n]} | M | evidence |" for n in W)
    return f"""# Opportunity Scoring Sheet — v6.2

**Role:** Test  **Company:** Testco

## Gates

| | Pass | Unresolved | Fail | Note |
|---|---|---|---|---|
{gate_rows}

## Factors

| # | Factor | W | Score | Ev | Conf | Evidence |
|---|---|---|---|---|---|---|
{rows}

**Weighted total: {total}**

{load_line}

## Asymmetry overlay: 1

## Candidate fit: {cand}

**Selection-critical requirements:**
{selection}

| | Yes | No |
|---|---|---|
{level_row}

**Channel:** None.

{combined}

## Real alternative

Advisory work.

## Verdict

☒ **{verdict}**

## Rationalisation check

- Verdict before the sheet? No.
"""


def rules(text, has_app=False):
    return {f.rule for f in sheet.grade(text, has_app)[1] if f.severity in ("error", "warn")}


class SheetGrader(unittest.TestCase):
    def test_clean_baseline(self):
        self.assertEqual(rules(make_sheet()), set())

    def test_arithmetic(self):
        self.assertIn("F2-arithmetic", rules(make_sheet(total=7.1)))

    def test_weight_drift(self):
        t = make_sheet().replace("| 1 | Epistemic fit | 19% |", "| 1 | Epistemic fit | 20% |")
        self.assertIn("F1-weight", rules(t))

    def test_provenance_cap(self):
        sc = {n: 6 for n in W}; sc[1] = 8
        self.assertIn("F3-provenance-cap", rules(make_sheet(scores=sc)))
        ev = {n: "A" for n in W}; ev[1] = "R"
        self.assertNotIn("F3-provenance-cap", rules(make_sheet(scores=sc, ev=ev)))
        ev[1] = "structural"  # framework §: behavioural OR structural evidence
        self.assertNotIn("F3-provenance-cap", rules(make_sheet(scores=sc, ev=ev)))

    def test_warning_not_fired(self):
        sc = {n: 6 for n in W}; sc[2] = 4
        self.assertIn("F4-warning-not-fired", rules(make_sheet(scores=sc, load_line="**Load-bearing check:** none. No warnings.")))
        self.assertNotIn("F4-warning-not-fired", rules(make_sheet(scores=sc)))

    def test_presumptive_pass(self):
        sc = {n: 6 for n in W}; sc[2] = 3; sc[4] = 3
        self.assertIn("F5-presumptive-pass", rules(make_sheet(scores=sc)))
        self.assertNotIn("F5-presumptive-pass", rules(make_sheet(scores=sc, verdict="Pass", cand="Medium")))

    def test_strong_with_warning(self):
        sc = {n: 7 for n in W}; sc[3] = 4
        ev = {n: "R" for n in W}
        self.assertIn("V1-strong-with-warning", rules(make_sheet(scores=sc, ev=ev, verdict="Strong (conditional on salary)")))

    def test_upgrade_needs_mandate(self):
        ev = {n: "R" for n in W}
        t = make_sheet(ev=ev, verdict="Strong via asymmetry upgrade (conditional on salary)")
        self.assertIn("V1-upgrade-without-mandate", rules(t))

    def test_first_verdict_word_wins(self):
        t = make_sheet(verdict="Viable (conditional on salary), with a clear path to Strong")
        self.assertEqual(sheet.parse(t).verdict, "Viable")

    def test_verdict_ticked_with_check_mark(self):
        # Agent output, 11.11.2026: a ☑ tick on a line that lists every option.
        t = make_sheet(verdict="Viable").split("## Verdict")[0] + (
            "## Verdict\n\n☐ Strong · ☑ **Viable** · ☐ Watchlist · ☐ Pass · ☐ Gig · ☐ Real alternative\n")
        self.assertEqual(sheet.parse(t).verdict, "Viable")
        t = make_sheet(verdict="Viable").split("## Verdict")[0] + (
            "## Verdict\n\n☑ **Viable** — passes gates.\n\nNot Strong: it does not beat the real alternative.\n")
        self.assertEqual(sheet.parse(t).verdict, "Viable")

    def test_candidate_cap_selection_critical(self):
        t = make_sheet(cand="High", selection="1. Ten years of accounting software. ☒ Missing")
        self.assertIn("C1-cap-selection-critical", rules(t))

    def test_candidate_cap_selection_critical_prose(self):
        t = make_sheet(cand="High", selection="1. Seven years of grid software: **missing** (never worked in utilities).")
        self.assertIn("C1-cap-selection-critical", rules(t))
        t = make_sheet(cand="High", selection="1. Consumer marketplaces: **met literally** (Kauppakulma).")
        self.assertNotIn("C1-cap-selection-critical", rules(t))

    def test_agent_variants_from_first_run(self):
        # "LOW" in capitals (literal-domain-missing, 30.10) and ☑ as the tick (pressure-logistics, 30.10).
        self.assertEqual(sheet.parse("**Candidate fit (literal match only): LOW.** x").candidate_fit, "Low")
        t = make_sheet(cand="High", selection="1. Pricing for a new tier — ☑ Analogy only. No owned pricing.")
        self.assertIn("C1-cap-selection-critical", rules(t))
        t = make_sheet(cand="High", selection="1. OKRs and discovery — ☑ Met literally (Kauppakulma).")
        self.assertNotIn("C1-cap-selection-critical", rules(t))

    def test_total_with_parenthetical(self):
        # control-logistics run 2, 30.10: a note between the label and the number.
        self.assertEqual(sheet.parse("**Weighted total (run in Python; weights sum to 100): 5.48**").stated_total, 5.48)

    def test_candidate_cap_level(self):
        t = make_sheet(cand="High", level_row="| Level matches | | ☒ |")
        self.assertIn("C1-cap-level", rules(t))

    def test_combined_must_use_own_rating(self):
        t = make_sheet(cand="Medium", combined="**Combined reading:** Viable × High → pursue selectively.")
        self.assertIn("M1-candidate-mismatch", rules(t))

    def test_danger_zone_named(self):
        t = make_sheet(verdict="Pass", cand="High", combined="**Combined reading:** Pass × High → Pass.")
        self.assertIn("M1-danger-zone", rules(t))

    def test_failed_gate_stops_scoring(self):
        t = make_sheet(gates=("fail", "pass", "pass", "pass"), verdict="Pass")
        self.assertIn("G1-score-after-fail", rules(t))
        self.assertIn("G1-draft-after-fail", rules(t, has_app=True))

    def test_unresolved_gate_needs_conditional(self):
        t = make_sheet(verdict="Viable").replace("conditional", "")
        self.assertIn("G2-unresolved-not-conditional", rules(t))
        self.assertNotIn("G2-unresolved-not-conditional", rules(make_sheet(verdict="Pass", cand="Medium")))


FACTS = """- Kauppakulma Autot grew from around 200 to 700+ dealers
- 20+ years of professional experience
- Languages: German (Mittelstufe, 2009, not current fluency)
"""

GOOD_DRAFT = """## Title line
PRODUCT LEADER | MARKETPLACES

## Intro
I grew a dealer product from around 200 to 700 dealers over 20 years in product.

## Core competencies
- Marketplaces: dealer product past 700 dealers

## Requirements the fact base does not support
- German at C1: not supported.
- Owned an LLM evaluation framework in production: not supported.

## Trace
- intro: "Kauppakulma Autot grew from around 200 to 700+ dealers"
"""


def drules(text, jd=""):
    return {f.rule for f in draft.grade(text, FACTS, jd) if f.severity in ("error", "warn")}


class DraftGrader(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(drules(GOOD_DRAFT), set())

    def test_invented_number(self):
        self.assertIn("D3-number-not-in-facts", drules(GOOD_DRAFT.replace("700 dealers over", "900 dealers over")))

    def test_number_from_jd_is_fine(self):
        t = GOOD_DRAFT.replace("in product.", "in product, ready for your 40 markets.")
        self.assertNotIn("D3-number-not-in-facts", drules(t, jd="We operate in 40 markets."))

    def test_never_claim_outside_gap_section(self):
        t = GOOD_DRAFT.replace("in product.", "in product, and I speak fluent German.")
        self.assertIn("D4-never-claim", drules(t))

    def test_negated_claim_is_fine(self):
        t = GOOD_DRAFT.replace("in product.", "in product. I have not owned an LLM eval framework in production.")
        self.assertNotIn("D4-never-claim", drules(t))

    def test_eval_ownership_claim(self):
        t = GOOD_DRAFT.replace("in product.", "in product, and I designed and owned the LLM evaluation suite.")
        self.assertIn("D4-never-claim", drules(t))

    def test_own_never_claim_list(self):
        # Your real gaps live in a private profile/never-claim.json; the grader loads them.
        import json, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"vertical launch": r"\b(launched|built)\b[^.\n]{0,40}\bQuickDeal\b"}, fh)
        never = draft.load_never_claim(fh.name)
        t = GOOD_DRAFT.replace("in product.", "in product. Launched QuickDeal in eight weeks.")
        self.assertIn("D4-never-claim", {f.rule for f in draft.grade(t, FACTS, never_claim=never)})
        t = GOOD_DRAFT.replace("in product.", "in product. I co-drove the thesis behind QuickDeal.")
        self.assertNotIn("D4-never-claim", {f.rule for f in draft.grade(t, FACTS, never_claim=never)})

    def test_missing_never_claim_file_falls_back_to_persona(self):
        self.assertIs(draft.load_never_claim("/nonexistent/never-claim.json"), draft.NEVER_CLAIM)

    def test_missing_sections_and_empty_list(self):
        t = GOOD_DRAFT.replace("## Trace", "## Notes")
        self.assertIn("D1-missing-section", drules(t))
        t = GOOD_DRAFT.split("## Requirements")[0] + "## Requirements the fact base does not support\n\n## Trace\n- x\n"
        self.assertIn("D2-empty-unsupported", drules(t))

    def test_style(self):
        self.assertIn("D7-em-dash", drules(GOOD_DRAFT.replace("in product.", "in product — mostly.")))
        self.assertIn("D7-banned-word", drules(GOOD_DRAFT.replace("in product.", "in product, passionate about it.")))


class AgentProseFormats(unittest.TestCase):
    """Formats the agent actually produced in the first behavioural run (30.10.2026)."""

    PROSE = """# Opportunity Scoring Sheet — v6.2

## Gates
| | Result | Note |
|---|---|---|
| Salary floor €9,000 base | Pass (conditional) | confirm base cash |
| Geography | Pass | Helsinki |
| Real, authorized, live, open to external | **UNRESOLVED** | cannot be judged |
| No dealbreakers | Pass | none |

## Factors (all A, capped at 6)
| # | Factor | W | Score | Ev | Conf | Evidence |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| {n} | {sheet.FACTOR_NAMES[n]} | {W[n]} | 5 | A | L | x |" for n in W) + """

**Weighted total: 5.0**
**Load-bearing (1–4):** none ≤4, no warnings fired.

**Candidate fit: High, provisional.** Every stated requirement met literally.

## Combined reading
Viable × High → *pursue selectively*.

## Verdict: **Viable (conditional on gate 3)**, held lightly

- Verdict decided before the sheet? No.
"""

    def test_parses_prose_sheet(self):
        s = sheet.parse(self.PROSE)
        self.assertEqual(len(s.factors), 9)          # weights without a % sign
        self.assertEqual(s.verdict, "Viable")         # verdict in the heading, no tick box
        self.assertEqual(s.candidate_fit, "High")
        self.assertEqual(s.gates["Real, authorized, live, open to external"], "unresolved")
        self.assertEqual(s.combined, ("Viable", "High"))  # reading on the line after a heading
        errors = {f.rule for f in sheet.grade(self.PROSE)[1] if f.severity == "error"}
        self.assertEqual(errors, set())


class DraftNumberReferences(unittest.TestCase):
    def test_checklist_reference_is_not_a_claim(self):
        t = GOOD_DRAFT.replace("- Owned an LLM", "- Decision bank (self-check 7): none fits.\n- Owned an LLM")
        self.assertNotIn("D3-number-not-in-facts", drules(t))


if __name__ == "__main__":
    unittest.main()
