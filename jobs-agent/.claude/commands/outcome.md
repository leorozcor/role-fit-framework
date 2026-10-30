---
description: Record an outcome (applied, interviewing, rejected, offer, closed, passed) and apply the outcome-update rule
argument-hint: <job id> <outcome> [what happened, feedback]
---

Record this outcome: $ARGUMENTS

## 1. Update the tracker

`bin/jobs set <id> <outcome> --note "<one line of what happened>"`.
If the transition is refused, show the allowed ones and ask.

For `rejected`, `closed` or `passed`, also tag the reason:
`bin/jobs record <id> --reason <no-buyer|literal|archetype|level|compensation|mandate|veto|competitor|his-call|no-reply|unknown>`.
`literal` only if the employer named the requirement or the evidence is
recorded; otherwise `unknown`. Never guess a reason that wasn't given.

## 2. If the outcome is `rejected` or `interviewing` with new information

Apply the **outcome-update rule** from `CLAUDE.md`:

- A rejection updates **candidate-fit calibration only**. Do not lower the
  organizational total or asymmetry because of it.
- The exception is **new organizational evidence** revealed by the process
  (owner overriding the hiring manager, role dissolved, mandate described
  differently, the eventual hire showing a different function). Name it if
  present; otherwise say "no new organizational evidence".
- Check it against the known pattern: was the deciding factor a literal stated
  requirement already on the gap list, or a level / functional-archetype
  mismatch? Say which, or say the reason is unknown. Do not guess a reason
  that wasn't given.

If a person delivered the rejection, suggest one question for him to ask:
*"What did the person you chose have that I didn't, and would it have mattered
if I'd had it?"* The answer separates non-recognition (evidence and advocacy can
change it) from a different risk reduction (only a different buyer can).

Write `runs/<id>/outcome.md` with: outcome, date, reason tag, stated reason (verbatim if
given), what it says about how he is read, any new organizational evidence, and
**a proposed one-line entry for the calibration appendix**. The agent does not
edit `rules/` or `profile/`; the human pastes the line if he agrees.

## 3. If the outcome is `interviewing` at a late stage, or `offer`

Ask for his **minimum acceptable terms** before any offer, and write them to
`runs/<id>/offer-acceptance.md` from `rules/offer-acceptance-template.md`. When an
offer arrives, test it against those terms and the cost of saying yes. Never
compare offers by organizational totals.

## 4. If the outcome is `applied`

Note the date. Suggest one follow-up date, 10 working days out, and say who to
nudge if a contact or advocate is recorded.

Keep the report short. If the rejection stings, acknowledge it in one sentence
and move on to what it teaches.
