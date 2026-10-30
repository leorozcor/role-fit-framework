---
description: Draft application material for a scored Strong/Viable role, from the fact base only, with the gap list
argument-hint: <job id> [anyway]
---

Draft application material for: $ARGUMENTS

## 0. Check it should be drafted

`bin/jobs show <id>` and read `runs/<id>/sheet.md`.

- Status must be `scored` with verdict Strong or Viable. Otherwise stop and say why.
- If the sheet lists an UNRESOLVED gate, stop unless the arguments include
  `anyway` — the human choosing to invest before it resolves.
- If the channel-decision matrix said "advocate/sponsor first" and no Advocate
  or Sponsor is recorded, say so in one line before drafting. Do not suggest a
  stronger cover letter as the fix.

## 1. Draft

Follow `CLAUDE.md` Step 4 and `rules/tailoring.md` exactly. Every claim traces
to a line in `profile/facts.md`. Write `runs/<id>/application.md` with these
sections, in order:

1. `## Title line`
2. `## Intro` (one paragraph, ~90 words)
3. `## Core competencies` (five or six lines)
4. `## Gap paragraph` (only if a gap exists)
5. `## Cover note` (only if the posting asks for one or the human asked)
6. `## Requirements the fact base does not support` — every one, plainly. This
   section is the point; never leave it out, write "none found" if so.
7. `## Trace` — for each competency and each factual sentence in the intro,
   the `facts.md` line it rests on, quoted briefly.

If the posting has application questions, answer them in an extra section,
under the same rules.

## 2. Self-check, then fix

Run the six checks at the end of `rules/tailoring.md` against what you wrote.
Also: grep the draft for the company name and confirm it matches
`bin/jobs show` everywhere; grep for em-dashes and for the banned words list.
Fix anything that fails before reporting. Report which checks you ran.

## 3. Export and record

If `pandoc` is available: `pandoc runs/<id>/application.md -o runs/<id>/application.docx`.

`bin/jobs set <id> drafted`

Ask which CV file he will attach and run `bin/jobs cvcheck <file>`. A date
mismatch with `profile/facts.md` blocks the send: report it first.

Report: the path to the draft, the cvcheck result, the unsupported-requirements list in full, and
the one thing the human should check first. Remind him that applying is his
button: `bin/jobs set <id> applied` after he sends it.
