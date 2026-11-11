"""Deterministic grader for a filled v6.2 scoring sheet (runs/<id>/sheet.md).

Each check maps to a rule written in jobs-agent/CLAUDE.md or rules/framework-v6.2.md.
The grader only checks what can be checked mechanically. It cannot tell whether a
score is *right*; it can tell whether the sheet obeys its own rules.

Severity:
  error  a stated hard rule is broken
  warn   probably a problem, or the spec itself is ambiguous here
  info   noted, not counted

Standard library only, like bin/jobs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

WEIGHTS = {1: 19, 2: 17, 3: 14, 4: 12, 5: 11, 6: 9, 7: 5, 8: 5, 9: 8}
FACTOR_NAMES = {
    1: "Epistemic fit", 2: "Translation tax", 3: "Political safety", 4: "Sustainability",
    5: "Mandate", 6: "Learning loops", 7: "Work interest", 8: "Culture", 9: "Growth",
}
VERDICTS = ["Strong", "Viable", "Watchlist", "Pass", "Gig"]
TOTAL_TOLERANCE = 0.05

# Combined-reading action that each matrix cell must name (lower-case substrings; any one is enough).
MATRIX = {
    ("Strong", "High"): ["pursue hard"],
    ("Strong", "Medium"): ["warm route", "pursue"],
    ("Strong", "Low"): ["advocate", "sponsor"],
    ("Viable", "High"): ["selective"],
    ("Viable", "Medium"): ["low-cost", "low cost"],
    ("Viable", "Low"): ["advocate", "pass"],
    ("Pass", "High"): ["danger"],
    ("Pass", "Medium"): ["pass"],
    ("Pass", "Low"): ["pass"],
}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str


@dataclass
class Sheet:
    text: str
    is_v62: bool = False
    reconstructed: bool = False
    factors: dict = field(default_factory=dict)  # n -> {"weight", "score", "ev", "conf"}
    stated_total: float | None = None
    load_bearing_line: str = ""
    verdict: str | None = None
    verdict_line: str = ""
    candidate_fit: str | None = None
    asymmetry: int | None = None
    gates: dict = field(default_factory=dict)  # label -> "pass" | "unresolved" | "fail" | "?"
    combined: tuple | None = None
    combined_line: str = ""
    selection_unmet: list = field(default_factory=list)
    level_mismatch: bool = False
    template_drift: list = field(default_factory=list)


def _section(text: str, heading_regex: str) -> str:
    """Text from a markdown heading matching heading_regex to the next heading of the same or higher level."""
    m = re.search(r"^(#{1,6})\s*" + heading_regex + r".*$", text, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(r"^#{1,%d}\s" % level, rest, re.M)
    return m.group(0) + "\n" + (rest[: nxt.start()] if nxt else rest)


def parse(text: str) -> Sheet:
    s = Sheet(text=text)
    s.is_v62 = bool(re.search(r"Scoring Sheet\s*[—-]\s*v6\.2", text))
    s.reconstructed = bool(re.search(r"Reconstructed", text[:1500], re.I))

    row = re.compile(r"^\|\s*([1-9])\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*%?\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", re.M)
    for m in row.finditer(text):
        n = int(m.group(1))
        if n in s.factors:
            continue
        s.factors[n] = {"name": m.group(2), "weight": int(m.group(3)), "score": float(m.group(4)),
                        "ev": m.group(5), "conf": m.group(6)}

    m = re.search(r"Weighted total(?:\s*\([^)\n]*\))?:?\**:?\s*\**\s*(\d+(?:\.\d+)?)", text)
    if m:
        s.stated_total = float(m.group(1))

    m = re.search(r"^.*Load-bearing.*$", text, re.M | re.I)
    s.load_bearing_line = m.group(0) if m else ""
    # The load-bearing verdict is sometimes on the same line as the weighted total.
    m2 = re.search(r"^.*Weighted total.*$", text, re.M)
    if m2 and "warning" in m2.group(0).lower():
        s.load_bearing_line += " " + m2.group(0)

    vsec = _section(text, r"Verdict")
    vword = re.compile(r"\b(" + "|".join(VERDICTS) + r")\b")
    for line in vsec.splitlines():
        if "☒" in line:
            # The first verdict word on the ticked line ("Viable, with a path to Strong" is Viable).
            hits = [(m.start(), m.group(1)) for m in vword.finditer(line)]
            if hits:
                s.verdict, s.verdict_line = min(hits)[1], line.strip()
                break
    if not s.verdict and vsec:
        # Prose form: "## Verdict: **Viable (conditional)**" or the first bold line under the heading.
        for line in vsec.splitlines()[:4]:
            if line.strip().startswith("- Verdict"):
                continue
            hits = [(m.start(), m.group(1)) for m in vword.finditer(line.split("Verdict", 1)[-1])]
            if hits:
                s.verdict, s.verdict_line = min(hits)[1], line.strip()
                s.template_drift.append("verdict written as prose, not a ticked box")
                break

    m = re.search(r"Candidate fit(?:\s*\(literal match only\))?\s*:\s*\**\s*(High|Medium|Low)\b(?!\s*/)", text, re.I)
    if m:
        s.candidate_fit = m.group(1).capitalize()

    m = re.search(r"Asymmetry(?: overlay)?:?\**:?\s*\**\s*([0-2])\b(?!\s*/)", text)
    if m:
        s.asymmetry = int(m.group(1))

    gsec = _section(text, r"Gates")
    result_col = None
    for line in gsec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Result" in cells:
            result_col = cells.index("Result")
            s.template_drift.append("gates written as a Result column, not ticked boxes")
            continue
        if not cells or not cells[0] or set(cells[0]) <= set("-: ") or cells[0] == "Pass":
            continue
        if result_col is not None and len(cells) > result_col:
            r = cells[result_col].lower()
            state = "unresolved" if "unresolved" in r else "fail" if "fail" in r else "pass" if "pass" in r else "?"
            s.gates[cells[0]] = state
        elif len(cells) >= 4:
            marks = cells[1:4]
            if any("☒" in c for c in marks):
                state = ["pass", "unresolved", "fail"][[("☒" in c) for c in marks].index(True)]
                s.gates[cells[0]] = state

    m = re.search(r"^.*Combined reading.*$", text, re.M | re.I)
    if m:
        s.combined_line = m.group(0)
        if "×" not in s.combined_line:  # heading form: the reading is in the next lines
            s.combined_line += " " + " ".join(text[m.end():].strip().splitlines()[:3])
        c = re.search(r"\b(Strong|Viable|Pass|Watchlist|Gig)\s*[×x]\s*(High|Medium|Low)\b", s.combined_line)
        if c:
            s.combined = (c.group(1), c.group(2))

    # Selection-critical requirements: the numbered list after the heading, marked met / missing / analogy.
    sc = re.search(r"Selection-critical requirement.*?(?:\n\s*\n(?=\S)(?!\d\.)|\Z)", text, re.S | re.I)
    if sc:
        for line in sc.group(0).splitlines():
            if not re.match(r"\s*\d\.", line):
                continue
            low = line.lower()
            ticked = re.search(r"[☒☑✓✔]\s*\**\s*(met|analogy|missing)", low)
            if ticked:  # the template's tick boxes decide
                unmet = ticked.group(1) != "met"
            elif re.search(r"\bnot met\b|\bnot literally\b", low):
                unmet = True
            elif "met literally" in low:
                unmet = False
            else:
                unmet = bool(re.search(r"\bmissing\b|\banalogy\b|\bpartial(ly)?\b|\bgap\b", low))
            if unmet:
                s.selection_unmet.append(line.strip())

    for line in text.splitlines():
        low = line.lower()
        if "level match" in low and "|" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and "☒" in cells[2]:
                s.level_mismatch = True
        if re.search(r"level (cap|mismatch)", low) and "candidate fit" in low:
            s.level_mismatch = True
    return s


def grade(text: str, has_application: bool = False) -> tuple[Sheet, list[Finding]]:
    s = parse(text)
    f: list[Finding] = []
    add = lambda r, sev, msg: f.append(Finding(r, sev, msg))

    gate_failed = [g for g, st in s.gates.items() if st == "fail"]
    gate_unresolved = [g for g, st in s.gates.items() if st == "unresolved"]

    # G1 — a failed gate stops the process: no factor scores, no draft.
    if gate_failed:
        if s.factors:
            add("G1-score-after-fail", "error", f"gate failed ({gate_failed[0]}) but {len(s.factors)} factors were scored")
        if has_application:
            add("G1-draft-after-fail", "error", "gate failed but application.md exists")
        if s.verdict and s.verdict != "Pass":
            add("G1-verdict", "error", f"gate failed but verdict is {s.verdict}")
        return s, f

    # G2 — an unresolved gate makes the verdict conditional.
    # A Pass does not depend on the gate, so it need not be called conditional.
    if gate_unresolved and s.verdict != "Pass":
        if "conditional" not in text.lower():
            add("G2-unresolved-not-conditional", "error", f"unresolved gate ({gate_unresolved[0]}) but the sheet never says the verdict is conditional")
        if has_application:
            add("G2-draft-before-resolution", "warn", "application.md exists while a gate is unresolved (allowed only if he said 'anyway')")

    if not s.factors:
        add("F0-no-factors", "error" if s.is_v62 else "info", "no factor table found")
        return s, f

    # F1 — all nine factors, canonical weights.
    missing = [n for n in WEIGHTS if n not in s.factors]
    if missing:
        add("F1-missing-factors", "error", f"factors missing: {missing}")
    for n, d in s.factors.items():
        if d["weight"] != WEIGHTS[n]:
            add("F1-weight", "error", f"factor {n} weight {d['weight']}% (should be {WEIGHTS[n]}%)")
        if not 0 <= d["score"] <= 10:
            add("F1-range", "error", f"factor {n} score {d['score']} out of 0–10")

    # F2 — arithmetic: the stated total must equal the weighted sum.
    if not missing:
        recomputed = round(sum(s.factors[n]["score"] * WEIGHTS[n] for n in WEIGHTS) / 100, 3)
        if s.stated_total is None:
            add("F2-no-total", "error", f"no weighted total stated (recomputed {recomputed:.2f})")
        elif abs(recomputed - s.stated_total) > TOTAL_TOLERANCE:
            add("F2-arithmetic", "error", f"stated total {s.stated_total} but weights give {recomputed:.2f}")

    # F3 — evidence provenance: advertised language alone caps a factor at 6.
    for n, d in s.factors.items():
        ev = d["ev"].strip()
        if d["score"] > 6 and re.fullmatch(r"A\.?", ev):
            add("F3-provenance-cap", "error", f"factor {n} ({FACTOR_NAMES[n]}) scored {d['score']:g} on advertised evidence only")
        if ev and not re.search(r"\b(A|R|D)\b|structural", ev, re.I):
            add("F3-evidence-code", "warn", f"factor {n} evidence code '{ev}' is not A/R/D/structural")
        if not ev:
            add("F3-evidence-code", "warn", f"factor {n} has no evidence code")

    # F4 — load-bearing warnings (factors 1–4 at or below 4).
    lb = [n for n in (1, 2, 3, 4) if n in s.factors and s.factors[n]["score"] <= 4]
    line = s.load_bearing_line.lower()
    says_none = bool(re.search(r"\bnone\b|no warnings", line)) and "warning" not in line.replace("no warnings", "")
    if lb and (not line or says_none):
        add("F4-warning-not-fired", "error", f"load-bearing factor(s) {lb} ≤4 but no warning recorded")
    if not lb and line and re.search(r"→\s*\*\*warning|\bwarning\b(?!s?\s*fired:\s*none)", line) and not says_none:
        add("F4-phantom-warning", "warn", "a load-bearing warning is recorded but no factor 1–4 is ≤4")

    # F5 — two or more load-bearing factors at or below 3: presumptive Pass.
    lb3 = [n for n in (1, 2, 3, 4) if n in s.factors and s.factors[n]["score"] <= 3]
    if len(lb3) >= 2 and s.verdict and s.verdict != "Pass":
        add("F5-presumptive-pass", "error", f"factors {lb3} ≤3 (presumptive Pass) but verdict is {s.verdict}")

    # V1 — Strong requires no load-bearing warning; asymmetry upgrade requires Mandate ≥7.
    if s.verdict == "Strong" and lb:
        add("V1-strong-with-warning", "error", f"verdict Strong with load-bearing warning(s) on {lb}")
    mandate = s.factors.get(5, {}).get("score")
    if s.verdict == "Strong" and re.search(r"upgrade", s.verdict_line, re.I) and mandate is not None and mandate < 7:
        add("V1-upgrade-without-mandate", "error", f"asymmetry upgrade to Strong with Mandate {mandate:g} (<7)")
    if s.verdict is None:
        add("V0-no-verdict", "error", "no ticked verdict found")

    # C1 — candidate fit: selection-critical requirement not met literally, or level mismatch, caps below High.
    if s.candidate_fit is None:
        add("C0-no-candidate-fit", "error" if s.is_v62 else "info", "no candidate-fit rating found")
    elif s.candidate_fit == "High":
        if s.selection_unmet:
            add("C1-cap-selection-critical", "error", f"candidate fit High with an unmet selection-critical requirement: {s.selection_unmet[0][:100]}")
        if s.level_mismatch:
            add("C1-cap-level", "error", "candidate fit High with a level mismatch")

    # M1 — the combined reading must use the sheet's own ratings and name the matrix action.
    if s.combined:
        cv, cc = s.combined
        if s.candidate_fit and cc != s.candidate_fit:
            add("M1-candidate-mismatch", "error", f"combined reading uses {cc}, candidate-fit rating is {s.candidate_fit}")
        if s.verdict and cv != s.verdict:
            add("M1-verdict-mismatch", "warn", f"combined reading row is {cv}, ticked verdict is {s.verdict} "
                "(the verdict box may be holding the pursuit decision, not the organizational verdict)")
        want = MATRIX.get((cv, cc))
        if want and not any(w in s.combined_line.lower() for w in want):
            add("M1-action", "warn", f"combined reading for {cv} × {cc} does not name the matrix action ({' / '.join(want)})")
        if (cv, cc) == ("Pass", "High") and "danger" not in s.combined_line.lower():
            add("M1-danger-zone", "error", "Pass × High must be named as the danger zone")
    elif s.is_v62 and s.verdict in ("Strong", "Viable", "Pass"):
        add("M0-no-combined", "warn", "no combined reading (verdict × candidate fit) found")

    # T1 — the template is a form; a sheet that drifts from it is harder to read by script and by eye.
    for d in s.template_drift:
        add("T1-template-drift", "info", d)

    # R1 — required sections of the template.
    for name, pat in [("asymmetry", r"Asymmetry"), ("channel strength", r"\bChannel\b"),
                      ("rationalisation check", r"Rationali[sz]ation|Verdict before the sheet"),
                      ("real alternative", r"Real alternative")]:
        if s.is_v62 and not re.search(pat, text, re.I):
            add("R1-missing-section", "warn", f"no {name} section")

    return s, f


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    for p in sys.argv[1:]:
        path = Path(p)
        sheet, findings = grade(path.read_text(), (path.parent / "application.md").exists())
        print(json.dumps({"file": p, "verdict": sheet.verdict, "candidate_fit": sheet.candidate_fit,
                          "findings": [f.__dict__ for f in findings]}, ensure_ascii=False, indent=1))
