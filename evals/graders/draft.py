"""Deterministic grader for application drafts (runs/<id>/application.md).

The hard rule (rules/tailoring.md): every biographical or experiential claim traces to
profile/facts.md. A script cannot judge a claim, so this grader uses proxies and says so:

  D3 numbers     every number in the draft must appear in facts.md or in the JD.
  D4 never-claim no sentence may assert an item from facts.md "NEVER claim these"
                 unless the sentence negates it or sits in the gap / unsupported sections.
  D5 names       capitalised names absent from facts.md and the JD are listed for a human.

D3 and D4 are flagged as errors; D5 only as "check". Their precision is measured, not
assumed: see evals/human-review/.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REQUIRED_SECTIONS = [
    "Title line", "Intro", "Core competencies",
    "Requirements the fact base does not support", "Trace",
]
# Sections where naming a gap is the point, so never-claim phrases are expected there.
GAP_SECTIONS = re.compile(r"gap|does not support|unsupported|trace", re.I)

BANNED = ["passionate", "results-driven", "proven track record", "synergy", "synergies"]
BANNED_RE = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in BANNED] + [
    re.compile(r"\bleverag(e|es|ed|ing)\b(?=\s+(?:my|our|his|their|the|a|an)\b)", re.I)]

NEGATION = re.compile(r"\b(not|never|no|haven't|hasn't|hadn't|don't|didn't|without|yet to|gap|lack|rather than)\b|n't\b", re.I)

# Positive assertions of items on the never-claim list (facts.md, "Gaps — NEVER claim these").
# These defaults match the fictional eval persona (evals/persona/facts.md). Your own list
# belongs in jobs-agent/profile/never-claim.json, which stays private (see load_never_claim).
NEVER_CLAIM = {
    "LLM eval ownership": re.compile(r"\b(owned|own|led|built|designed|ran|run)\b[^.\n]{0,60}\b(LLM|AI|model)\b[^.\n]{0,30}\beval(uation)?s?\b(?![^.\n]{0,20}\b(of|for) (roles|jobs|opportunit))", re.I),
    "eval framework in production": re.compile(r"\beval(uation)?\b[^.\n]{0,40}\bin production\b", re.I),
    "solo shipped product": re.compile(r"\b(shipped|built|launched)\b[^.\n]{0,40}\b(alone|single-handed|solo|by myself|on my own)\b", re.I),
    "hands-on engineering career": re.compile(r"\b(hands-on|professional|senior)\s+(software\s+)?(engineer|developer|programmer)\b|\bengineering career\b", re.I),
    "P&L ownership": re.compile(r"\b(owned|own|ran|run|held|accountable for)\b[^.\n]{0,40}\bP&L\b", re.I),
    "commercial forecasting accountability": re.compile(r"\b(owned|own|accountable for|responsible for|delivered)\b[^.\n]{0,40}\b(revenue|retention|commercial) forecast", re.I),
    "German proficiency": re.compile(r"\b(fluent|proficient|professional|business|working|C1|C2)\b[^.\n]{0,30}\bGerman\b|\bGerman\b[^.\n]{0,30}\b(fluent|proficient|C1|C2|professional|business|working)\b", re.I),
    "domain not worked in": re.compile(r"\bexperience (in|with|across)\b[^.\n]{0,40}\b(grid|utilit\w*|energy networks|iGaming|healthcare)\b", re.I),
    "AI prototyping proficiency": re.compile(r"\b(proficient|expert|experienced|hands-on)\b[^.\n]{0,30}\b(prototyp\w+|Claude Code|Cursor|vibe-?coding)\b", re.I),
}


def load_never_claim(path) -> dict:
    """Your own never-claim patterns: a JSON object {"short name": "regex", ...}.

    Keep it next to your fact base (jobs-agent/profile/never-claim.json) and out of any
    public repository: the list describes your real gaps. Patterns are case-insensitive.
    Returns the persona defaults when the file does not exist.
    """
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return NEVER_CLAIM
    return {k: re.compile(v, re.I) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str


def _sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"^##\s+(.+)$", text, flags=re.M)
    out = [("_preamble", parts[0])]
    for i in range(1, len(parts), 2):
        out.append((parts[i].strip(), parts[i + 1] if i + 1 < len(parts) else ""))
    return out


def _norm_num(s: str) -> str:
    return re.sub(r"[,\s  ]", "", s)


def numbers(text: str) -> set[str]:
    # 100,000 / 1,000+ / 45 / 2019 / 259.5 ; skip list markers like "1." at line start.
    found = set()
    for m in re.finditer(r"(?<![\w.])(\d{1,3}(?:[,   ]\d{3})+|\d+(?:\.\d+)?)(?![\w])", text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if re.fullmatch(r"\s*", text[line_start:m.start()]) and text[m.end():m.end() + 1] == ".":
            continue
        if re.match(r"\.?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\b",
                    text[m.end():m.end() + 12]):
            continue  # a day of the month
        if re.match(r"\.\d{1,2}\.\d{4}", text[m.end():m.end() + 9]):
            continue  # Finnish date 27.10.2026
        if re.search(r"(?i)\b(check|step|item|section|question|gate|factor|rule)\s*$", text[max(0, m.start() - 12):m.start()]):
            continue  # a reference to a checklist item, not a claim
        found.add(_norm_num(m.group(1)))
    return found


def is_draft_format(draft: str) -> bool:
    """True if this looks like /draft output; hand-written documents get content checks only."""
    return bool(re.search(r"^##\s+(Trace|Title line)\b", draft, re.M))


def grade(draft: str, facts: str, jd: str = "", company: str | None = None,
          format_checks: bool = True, never_claim: dict | None = None) -> list[Finding]:
    f: list[Finding] = []
    never_claim = NEVER_CLAIM if never_claim is None else never_claim
    add = lambda r, sev, msg: f.append(Finding(r, sev, msg))
    secs = _sections(draft)
    names = [n.lower() for n, _ in secs]

    for req in (REQUIRED_SECTIONS if format_checks else []):
        if not any(req.lower() in n for n in names):
            add("D1-missing-section", "error", f"no '## {req}' section")

    unsup = [body for n, body in secs if "does not support" in n.lower()]
    if unsup and not unsup[0].strip():
        add("D2-empty-unsupported", "error", "unsupported-requirements section is empty (write 'none found' if so)")

    # D3 — numbers must come from facts.md or the JD.
    allowed = {_norm_num(x) for x in numbers(facts) | numbers(jd)}
    for n, body in secs:
        if n == "_preamble" or "trace" in n.lower():
            continue  # the preamble is a note to the candidate; the trace quotes facts.md
        for num in sorted(numbers(body)):
            if num not in allowed:
                add("D3-number-not-in-facts", "error", f"'{num}' in section '{n}' appears in neither facts.md nor the JD")

    # D4 — never-claim items asserted outside the gap sections.
    for n, body in secs:
        if GAP_SECTIONS.search(n):
            continue
        for sent in re.split(r"(?<=[.!?])\s+|\n", body):
            if NEGATION.search(sent):
                continue
            for label, rx in never_claim.items():
                if rx.search(sent):
                    add("D4-never-claim", "error", f"{label}: \"{sent.strip()[:140]}\"")

    # D5 — capitalised names not grounded anywhere (for a human to check).
    ground = facts + "\n" + jd
    stop = {"I", "My", "The", "A", "An", "In", "At", "On", "For", "With", "And", "But", "What", "When", "This",
            "That", "Product", "Products", "Data", "Sales", "Engineering", "Design", "AI", "CEO", "CPO", "CTO",
            "VP", "Head", "Director", "Lead", "Team", "Nordics", "Europe", "European", "English", "Finnish",
            "Spanish", "Dear", "Best", "Regards", "Title", "Intro", "Core", "Trace", "Gap", "Cover", "Requirements"}
    seen = set()
    for n, body in secs:
        if n == "_preamble" or "trace" in n.lower():
            continue
        for m in re.finditer(r"(?<=[a-z,;:(] )([A-Z][\w&-]*(?: [A-Z][\w&-]*)*)", body):
            name = m.group(1)
            if name in stop or name in seen or name.split()[0] in stop:
                continue
            seen.add(name)
            if name.lower() not in ground.lower():
                add("D5-name-check", "check", f"'{name}' is not in facts.md or the JD")

    # D6 — company name, if known, appears; style rules.
    if company and company.lower() not in draft.lower():
        add("D6-company-absent", "warn", f"company name '{company}' does not appear in the draft")
    dashes = draft.count("—")
    if dashes:
        add("D7-em-dash", "warn", f"{dashes} em-dash(es) (style rule: none)")
    for rx in BANNED_RE:
        for m in rx.finditer(draft):
            add("D7-banned-word", "warn", f"banned phrase '{m.group(0)}'")
    return f


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    draft_p, facts_p = Path(sys.argv[1]), Path(sys.argv[2])
    jd_p = draft_p.parent / "jd.md"
    out = grade(draft_p.read_text(), facts_p.read_text(), jd_p.read_text() if jd_p.exists() else "")
    print(json.dumps([x.__dict__ for x in out], ensure_ascii=False, indent=1))
