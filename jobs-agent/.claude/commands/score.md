---
description: Score one role against the v6.2 framework (gates, nine factors, asymmetry, candidate fit, channel) — no drafting
argument-hint: <job id | path to JD file | URL | pasted JD>
---

Score one opportunity: $ARGUMENTS

## 0. Resolve the job

- **A job id or company fragment:** `bin/jobs show <ref>`. If `has_jd` is 0,
  ask the human to paste the JD into `runs/<id>/jd.md` and stop.
- **A file path:** read it, infer company and title (ask if genuinely unclear;
  never guess a company name), then
  `bin/jobs add --file <path> --company "<c>" --title "<t>" [--url ...] [--source network|search-firm|inbound]`.
- **A URL:** fetch it, save the JD text to a temporary file, then add as above
  with `--url`. If the page needs a login or won't render, ask for a paste.
- **Pasted text:** write it to a temporary file and add as above.

Note the job id. Everything for this role goes in `runs/<id>/`.

## 1. Score

Follow `CLAUDE.md` Steps 1, 2, 2b, 2c, 2d, 3 and 5 exactly, using
`rules/framework-v6.2.md`, `rules/scoring-sheet-template.md`,
`profile/search-profile.md`, `profile/facts.md` and `profile/network.md`.

- **A gate fails:** write `runs/<id>/sheet.md` with the failed gate and one
  sentence, then `bin/jobs record <id> --verdict Pass --gate-note "<gate: reason>" --status screened_out`. Stop.
- Otherwise write the filled sheet to `runs/<id>/sheet.md`. Compute the
  weighted total with arithmetic you actually run (Bash `python3 -c`), not in
  your head. Weights must sum to 100.
- Record it:
  `bin/jobs record <id> --verdict <V> --org-total <x.x> --asymmetry <0|1|2> --candidate <H/M/L> --channel <C> [--advocate "Name"] [--gate-note "<unresolved gate and its question>"] --status scored`

## 2. Report

Lead with any UNRESOLVED gate and its question. Then: verdict, total, warnings
fired, asymmetry, candidate fit with the selection-critical requirement, channel
strength, and the action from the channel-decision matrix in one line.

Then the rationalisation check, answered honestly, and the interview questions.

End with the next step: `/draft <id>` if Strong or Viable, `/warm <id>` if the
matrix says an advocate is needed first, or nothing if Pass. **Do not draft in
this command.** The human decides between scoring and drafting.
