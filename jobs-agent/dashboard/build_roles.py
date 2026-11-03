"""Build the dashboard's roles file from the tracker (data/jobs.db).

Usage, from jobs-agent/:
    python3 dashboard/build_roles.py [OUT.json] [--dates FILE.csv] [--overrides FILE.json]

Defaults: OUT data/dashboard-roles.json, --dates data/process-dates.csv,
--overrides dashboard/overrides.json. Both inputs are optional and both are
gitignored, because they hold real companies and dates. See dashboard/README.md.
"""
import argparse, csv, datetime, json, os, re, sqlite3

p = argparse.ArgumentParser()
p.add_argument('out', nargs='?', default='data/dashboard-roles.json')
p.add_argument('--db', default='data/jobs.db')
p.add_argument('--dates', default='data/process-dates.csv')
p.add_argument('--overrides', default='dashboard/overrides.json')
a = p.parse_args()

TODAY = datetime.date.today().timetuple()[:3]
MON = {m: i + 1 for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july',
                                       'august', 'september', 'october', 'november', 'december'])}


def dates(t):
    """Dates written in free-text notes: 3.11.2026, 3.11. (this year), November 2026, 2026-11-03."""
    out = []
    if not t:
        return out
    for d, m, y in re.findall(r'\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b', t):
        out.append((int(y), int(m), int(d)))
    for d, m in re.findall(r'\b(\d{1,2})\.(\d{1,2})\.(?!\d)', t):
        if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
            out.append((TODAY[0], int(m), int(d)))
    for mon, y in re.findall(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)', t, re.I):
        out.append((int(y), MON[mon.lower()], 15))
    for y, m, d in re.findall(r'\b(20\d\d)-(\d\d)-(\d\d)\b', t):
        out.append((int(y), int(m), int(d)))
    return out


def iso(d):
    """'YYYY-MM-DD' exact; 'YYYY-MM' -> mid-month, approximate; 'YYYY' -> mid-year, approximate."""
    if not d:
        return '', False
    if len(d) == 10:
        return d, False
    if len(d) == 7:
        return d + '-15', True
    return d + '-07-01', True


# Optional per-role overrides, keyed by tracker id:
#   reached  {id: stage} or {id: [stage, "?"]} (estimated), used when the id has no row in the dates file
#   company / title  display names (e.g. hide a confidential client)
#   detail   one line shown under a live role ("Round 2 done; next: CEO")
#   skip     ids to leave out entirely
O = json.load(open(a.overrides)) if os.path.exists(a.overrides) else {}
REACHED, COMPANY, TITLE, DETAIL = (O.get(k, {}) for k in ('reached', 'company', 'title', 'detail'))
SKIP = set(O.get('skip', []))

# One row per recruitment cycle: id, cycle, applied, ended, reached, reached_estimated, source, note.
PROC = {}
if os.path.exists(a.dates):
    for r in csv.DictReader(open(a.dates)):
        PROC.setdefault(r['id'], []).append(r)
for v in PROC.values():
    v.sort(key=lambda r: int(r.get('cycle') or 1))
PD = {k: v[-1] for k, v in PROC.items()}  # the latest cycle describes the role now

CLOSED = {'no-reply': 'No reply', 'no-buyer': 'Role paused or pulled', 'his-call': 'My call'}

c = sqlite3.connect(a.db)
rows = []
for jid, co, ti, st, reason, notes, gate, verdict, loc in c.execute(
        "select id, company, title, status, outcome_reason, notes, gate_note, verdict, location from jobs"):
    if jid in SKIP:
        continue
    ev = list(c.execute("select to_status, note from events where job_id = ? order by id", (jid,)))
    tos = [e[0] for e in ev]
    ds = [d for d in dates(' '.join(filter(None, [notes, gate] + [e[1] for e in ev]))) if d <= TODAY]
    last = max(ds) if ds else None
    # Status -> dashboard group and stage
    if st in ('interviewing', 'applied', 'offer'):
        group, stage = 'pipeline', ('Interviewing' if st in ('interviewing', 'offer') else 'Applied')
    elif st in ('scored', 'drafted') and verdict == 'Pass':
        group, stage = 'screened', 'After a closer look'
    elif st in ('scored', 'drafted', 'to_score', 'new'):
        group, stage = 'pipeline', 'Exploring'
    elif st == 'rejected':
        group, stage = 'rejected', ('After interviews' if 'interviewing' in tos else 'At application')
    elif st == 'screened_out':
        group, stage = 'screened', 'At first look'
    elif st == 'passed':
        group, stage = 'screened', 'After a closer look'
    else:  # closed
        group, stage = 'closed', CLOSED.get(reason, 'Outcome unknown')
    applied = any(t in ('applied', 'interviewing', 'rejected') for t in tos) or st in ('applied', 'interviewing', 'offer', 'rejected')
    r = REACHED.get(jid, 1 if applied else 0)
    guess = isinstance(r, list)
    reached = r[0] if guess else r
    appliedDate, endedDate, approx = '', '', False
    if jid in PD:
        p = PD[jid]
        reached, guess = int(p['reached']), p['reached_estimated'] == 'yes'
        appliedDate, _ = iso(p['applied'])
        endedDate, a2 = iso(p['ended'])
        if endedDate:
            last, approx = tuple(int(x) for x in endedDate.split('-')), a2
        elif group != 'pipeline':
            last, approx = None, False  # never use the application date as an invented end date
    elif group in ('rejected', 'closed') and applied:
        last = None  # no reliable end date: undated, not the date the note was written
    if jid in PROC:
        processes = [dict(cycle=int(q.get('cycle') or 1), reached=int(q['reached']), estimated=q['reached_estimated'] == 'yes',
                          applied=iso(q['applied'])[0], ended=iso(q['ended'])[0], endedApprox=iso(q['ended'])[1]) for q in PROC[jid]]
    elif reached >= 1:
        processes = [dict(cycle=1, reached=reached, estimated=guess, applied='', ended='')]
    else:
        processes = []
    rows.append(dict(company=COMPANY.get(jid, co), role=TITLE.get(jid, ti), group=group, stage=stage,
                     detail=DETAIL.get(jid, '') if group == 'pipeline' else '', location=loc or '',
                     last=('%04d-%02d-%02d' % last) if last else '', reached=reached, reachedEstimated=guess,
                     applied=appliedDate, ended=endedDate, dateApprox=approx, processes=processes))
rows.sort(key=lambda r: (r['last'] or '0'), reverse=True)
os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
json.dump(rows, open(a.out, 'w'), ensure_ascii=False, indent=0)
print(len(rows), 'roles ->', a.out)
