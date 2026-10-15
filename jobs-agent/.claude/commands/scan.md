---
description: Pull new postings from JobsPipe, RSS feeds and the company watchlist, and screen them cheaply (gates, avoid list, network) — no full scoring
argument-hint: [days]
---

Run the radar, then screen what landed. This is a **screen**, not a score: it
decides only whether a role is worth a full `/score`. Spend tokens accordingly.

The scan is a radar for companies worth a warm approach, not a cold-application
funnel. Six months of evidence: every process that reached a real conversation
came through a person.

## 1. Collect

Run `bin/jobs scan` (add `--days $ARGUMENTS` if a number was given). If it fails
for a missing key, tell the human to put `JOBSPIPE_API_KEY=...` in
`jobs-agent/.env`. Report the counts line verbatim, including errors.

**Whether or not collection succeeded, go on to step 2.** Rows left `new` by an
earlier scan still need screening; a failed collection is reported, not a
reason to stop.

## 2. Screen each `new` row

Read `profile/search-profile.md` (gates, avoid list, recent career identity)
and `profile/network.md` once. Then for each row from
`bin/jobs list --status new --json`, read `runs/<id>/jd.md` and judge only:

1. **Gates 1, 2 and 4** from the search profile. Gate 3 can't be judged from a
   posting; skip it here. A salary stated in USD/year from the source is a
   conversion of the original: treat it as approximate.
2. **Avoid list.** The scanner pre-flags keyword hits in `flags`; a keyword hit
   is a prompt to look, not a verdict (a marketplace that *mentions* invoicing
   is not accounting software).
3. **Level and functional center of gravity** from the title and JD: an
   IC-level or Engineering-centred seat is a screen-out unless the JD
   clearly says otherwise.
4. **Company unknown** (`flags.company_unknown`, from feeds that don't name it):
   read the JD. If it names the employer, fix it with
   `bin/jobs record <id> --company "<name>"` before anything else. If it
   doesn't (a recruiter posting for an unnamed client), leave it unknown and
   say so in the gate note. Never guess an employer.
5. **Network:** does `profile/network.md` list anyone at this company? Copy
   the strength exactly as written there. Never upgrade a Contact to an
   Advocate.

Then record one of:

- `bin/jobs record <id> --status screened_out --gate-note "<one line: which gate or rule, and the evidence>"`
- `bin/jobs record <id> --status to_score --gate-note "<one line: why it is worth scoring; any unresolved gate>" [--channel X --advocate "Name"]`

If the JD body is missing (`has_jd` = 0) and the title looks plausible, move it
to `to_score` with the note "JD missing, paste before scoring".

When unsure, prefer `to_score` with the doubt written in the note. Screening is
cheap to reverse; a wrongly dropped role is invisible.

**Search-firm roles** (`flags.via_search_firm`): the employer is the client
named in the title; the channel is the recruiter. Say so in the gate note: the
next step is a call with the recruiter, not a cold application.

**Watchlist rows** (source greenhouse, lever, ashby, recruitee, personio or
teamtailor) come from companies he chose to watch. Their title filter is looser
("product" anywhere), so judge level carefully: an IC Senior PM seat is a
level-cap question for `/score`, not an automatic screen-out, if the company is
on the watchlist.

Sources: `jobspipe` rows carry `flags.boards` (e.g. linkedin, teamtailor,
greenhouse), the boards JobsPipe found the posting on. RSS rows carry the feed
name as their source. Duunitori and LinkedIn are never scraped: their terms
forbid it, and the account at risk would be his.

## 3. Report

A short table of the roles moved to `to_score`, network hits first, each with
its one-line note and the next command (`/score <id>` or `/warm <id>`). Then
one line with the number screened out and the most common reason. Do not list
every screen-out unless asked.
