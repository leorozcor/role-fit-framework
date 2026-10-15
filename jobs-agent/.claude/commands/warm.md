---
description: Find the warm path into one role's company from profile/network.md and draft the ask — never sends
argument-hint: <job id>
---

Find the warm path for: $ARGUMENTS

The goal is **advocacy**, not a forwarded CV. A contact forwards a CV; an
advocate tells the hiring team why a non-obvious background fits. Draft so that
a contact can become an advocate with almost no effort.

## 1. Gather

`bin/jobs show <id>`, `runs/<id>/jd.md`, `runs/<id>/sheet.md` if it exists,
and `profile/network.md`.

List everyone in `profile/network.md` at this company, or who the file says
knows someone there. Use the strength written in the file. **Never upgrade it.**
If nobody is listed, say so plainly and suggest who to ask by role only
(e.g. "a former colleague who now knows their CPO"). Never
invent a name.

No people search tools are available or wanted here. Do not browse LinkedIn.

## 2. Draft (never send)

For the best one or two paths:

- **The ask**, three or four sentences, in his own voice (plain and direct,
  no corporate filler). Ask for a specific thing:
  a word with the hiring manager, or 20 minutes on what the seat really needs.
- **The forwardable paragraph**: two or three sentences the contact can paste
  to the hiring team, saying why his background fits *this* role's problem.
  Every claim inside `profile/facts.md`. If the sheet found a
  selection-critical gap, the paragraph names what transfers; it does not hide
  the gap.

Write both to `runs/<id>/outreach.md`. Write in the language the human uses with
this person.

## 3. Record

If the human confirms someone has agreed to advocate, then and only then:
`bin/jobs record <id> --channel Advocate --advocate "Name"`.

Report the drafts and the one-line reason for the path you ranked first.
