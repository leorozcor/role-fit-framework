#!/usr/bin/env python3
"""Check the tracked public snapshot; cannot validate Git history or NDA obligations."""
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]
issues = []
tracked = [p for p in subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0") if p]

for path in tracked:
    if path.startswith(("jobs-agent/data/", "jobs-agent/runs/")) and path != "jobs-agent/runs/.gitkeep":
        issues.append("Private runtime file tracked: " + path)
    if path.startswith("jobs-agent/profile/") and path.endswith((".md", ".json")):
        if not path.endswith((".template.md", ".template.json")):
            issues.append("Real profile tracked: " + path)
    if path in {"jobs-agent/.env", "jobs-agent/dashboard/overrides.json",
                "jobs-agent/dashboard/process-dates.csv",
                "jobs-agent/dashboard/sample/screenshot.png"}:
        issues.append("Private or historical artifact tracked: " + path)
    if path.endswith((".db", ".sqlite", ".sqlite3")):
        issues.append("Database tracked: " + path)

approved_employers = {
    "Director of Hyperspace Route Strategy": "Claatuvac Guild",
    "VP Platform, Tycho Station": "Tycho Manufacturing and Engineering Concern",
    "Head of LCARS Design Systems": "Starfleet Research and Development",
    "Director of Outer Rim Customer Growth": "Trade Federation",
    "Holodeck Product Operations Lead": "Starfleet Engineering",
    "Epstein Drive Portfolio Lead": "Martian Congressional Republic Navy",
    "Director of Cantina Guest Experience": "Chalmun's Spaceport Cantina",
    "Director of Ferengi Business Systems": "Ferengi Commerce Authority",
    "Head of Digital Services, Rocinante": "Rocinante (independent crew)",
    "Death Star Portfolio Planning Manager": "Galactic Empire — Imperial Navy",
    "Director of Protomolecule Analytics": "Protogen",
    "VP Commerce, Mos Eisley Spaceport": "Hutt Clan",
    "Principal Jedi Product Coach": "Jedi Order",
    "Kessel Run Operations Transformation Lead": "Pyke Syndicate",
    "Director of Subspace Platform Experience": "Starfleet Communications",
    "Starfleet Product Enablement Lead": "Starfleet Command",
    "Director of Replicator Service Design": "Starfleet Engineering",
    "Technology Strategy Lead, Ceres Station": "Outer Planets Alliance (Ceres faction)",
}

try:
    sample = json.loads((root / "jobs-agent/dashboard/sample/roles.sample.json").read_text())
    preview = (root / "jobs-agent/dashboard/sample/preview.html").read_text()
    match = re.search(r'<script id="roles-data" type="application/json">([\s\S]*?)</script>', preview)
    if not match or json.loads(match.group(1)) != sample:
        issues.append("Sample HTML does not contain exactly the independently fictional JSON dataset")
    if len(sample) != len(approved_employers):
        issues.append("Unexpected number of public fictional roles")
    for i, item in enumerate(sample, 1):
        if item.get("company") != approved_employers.get(item.get("role")):
            issues.append(f"Record {i}: role/employer is not in the fictional demonstration allowlist")
        for obj in [item] + item.get("processes", []):
            for field in ("applied", "ended", "last"):
                val = obj.get(field) or ""
                if val and (not re.fullmatch(r"20\d\d-\d\d-\d\d", val) or int(val[:4]) < 2030):
                    issues.append(f"Record {i}: {field} outside fictional 2030+ timeline")
except (OSError, ValueError, TypeError) as ex:
    issues.append("Unable to verify sample/preview: " + str(ex))

patterns = [
    re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{35,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{30,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")
]
for path in tracked:
    if pathlib.Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".webp", ".ico"}:
        continue
    try:
        content = (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    if any(pattern.search(content) for pattern in patterns):
        issues.append("Potential credential in " + path)

for problem in issues:
    print("PRIVACY CHECK FAILED:", problem, file=sys.stderr)
if issues:
    sys.exit(1)
print("Current tracked public snapshot passed structural privacy checks.")
print("Historical commits, caches and NDA-covered assertions still need separate review.")
