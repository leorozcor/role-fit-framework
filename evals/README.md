# Evals for the jobs agent

The agent in `jobs-agent/` scores job postings against a written framework and drafts applications from a fact base. Both jobs have rules that are easy to state and easy to break: arithmetic, evidence caps, gates that must stop the process, ratings that must not go above a ceiling, claims that must trace to `facts.md`. This folder checks whether the agent keeps them.

It does not check whether a score is *right*. Nobody can, for one posting. It checks whether the agent obeys its own rules, whether it behaves the same way when someone leans on it, and, over months, whether its ratings predicted anything.

## Four layers

| Layer | What it answers | Script | Cost |
|---|---|---|---|
| 1. Rule graders on existing output | Do the sheets and drafts in `jobs-agent/runs/` obey their rules? | `run_offline.py` | Free, seconds |
| 2. Behavioural cases | Given postings built to trip one rule each, does the live agent do the right thing? The same posting with a prompt injection, or with the human pressing for a better score: does the result move? | `run_cases.py` | A full agent session per case |
| 3. Calibration | Did candidate fit predict who got interviews, and did organizational fit (correctly) not? | `calibration.py` | Free |
| 3b. Forecasts | Did the agent's probabilities, and yours, predict who reached interview or offer? Brier score, head to head, from `jobs-agent/journal/predictions.csv`. | `predictions.py` | Free |
| 4. Human review of the graders | When a grader flags something, is it right? | `human_review.py` | Your time |

```
python3 -m unittest discover -s evals/tests      # the graders' own tests, first
python3 evals/run_offline.py                     # layer 1 -> evals/reports/offline-<date>.md
python3 evals/run_cases.py --jobs 4              # layer 2 -> evals/reports/behaviour-<stamp>.md
python3 evals/run_cases.py control-logistics positive-marketplace --repeat 3   # variance
python3 evals/run_cases.py --regrade evals/results/<stamp>   # new graders, old outputs, no agent calls
python3 evals/calibration.py                     # layer 3, from your tracker database
python3 evals/predictions.py                     # layer 3b, forecasts
python3 evals/human_review.py sample             # layer 4: a CSV to label y / n / ?
python3 evals/human_review.py score evals/human-review/labels-<date>.csv
```

Layer 2 needs the [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) CLI (`claude`) on your path and uses your plan or API usage.

## The eval persona

The cases are written for one candidate, so they need one. `persona/` holds an invented one, Alex Esimerkki: a Helsinki-based director of product with a consumer-marketplace and trust background, a salary floor of €9,000 a month, payroll software on the avoid list, no German beyond school level and no LLM-evaluation ownership. `run_cases.py` installs it as the agent's `profile/` in every sandbox, so:

- the cases are reproducible: anyone gets the same candidate;
- your own fact base never enters a case run, and never leaves your machine in a transcript.

Layers 1, 3, 3b and 4 run on *your* data (`jobs-agent/runs/`, the tracker, your forecasts) and stay on your machine.

## Your own never-claim list

The draft grader's D4 rule flags any sentence that asserts something on the fact base's "NEVER claim these" list. The patterns in `graders/draft.py` are the persona's. For your own drafts, put yours in `jobs-agent/profile/never-claim.json`, a JSON object of short names and case-insensitive regular expressions:

```json
{
  "LLM eval ownership": "\\b(owned|led|built)\\b[^.\\n]{0,60}\\beval(uation)?s?\\b",
  "launch I didn't lead": "\\blaunched\\b[^.\\n]{0,40}\\bProduct X\\b"
}
```

Layers 1 and 4 load it when it exists. It describes your real gaps, so the `.gitignore` and `scripts/check_public_snapshot.py` keep it out of the repository. Add a pattern whenever a draft claims something it shouldn't: the grader then catches that claim every time after.

## Design decisions

- **The agent never sees the evals.** Each case runs in a fresh copy of `jobs-agent/` with no runs, no database, no `evals/` and the persona as its profile. Expectations and graders are out of its reach, so it can't optimise for the test.
- **Same permissions as in real use.** Headless runs ignore an untrusted folder's project settings, so the harness passes the agent's own `.claude/settings.json`: the same allow and deny lists, nothing added.
- **Generation and grading are separate.** Outputs are saved; `--regrade` re-runs the graders over them. A grader bug costs a regrade, not another round of agent sessions.
- **Graders are tested.** Each rule has a test that should trigger it and a clean sheet that shouldn't. In the original project the tests were mutation-checked: breaking a rule in the grader made a test fail. Formats the agent actually produced are kept as regression tests.
- **A positive control.** One case (`positive-marketplace`) is a literal match at a clearing salary. A suite of traps alone would reward an agent that says no to everything.
- **Paired cases instead of absolute answers.** There is no correct total for a posting, but there is a correct *difference*: adding a prompt injection or a plea to the same posting should change nothing. `injection-logistics` and `pressure-logistics` are compared with `control-logistics`.
- **Proxies are labelled as proxies.** The draft grader can't judge a claim; it checks that every number appears in `facts.md` or the posting, that no never-claim item is asserted, and lists unknown names for a human. Layer 4 measures how often those flags are right.
- **Calibration refuses to overclaim.** It reports counts, prints every row, and says when the sample is too small to mean anything.

## Mistakes feed the tests

Keep a short log of each mistake the agent actually makes and the rule it taught, and give each entry a test: a grader rule, a case, or a stated reason it can't have one. A rule without a test is a hope; a test fails if the mistake comes back. Several cases here started that way: the prompt-injection case also checks that the agent *tells* you the posting tried to instruct it, because an early run ignored the instruction correctly but said nothing.

## What this is, said plainly

An evaluation suite for an LLM agent I designed: rule-based graders with their own tests, adversarial and paired behavioural cases run against the live agent, run-to-run variance, calibration against real outcomes, and a human-review loop to measure the graders. It is a personal project on my own agent, not a production evaluation with users, traffic or a team. The rules and the cases are mine; Claude Code wrote the code.

## Files

- `graders/sheet.py`, `graders/draft.py`: deterministic graders, standard library only.
- `cases/<id>/`: `jd.md` (fictional posting; companies are invented), `case.json` (why the case exists and what is expected), fixture sheets for the `/draft` cases.
- `persona/`: the fictional candidate the cases are written for.
- `tests/`: the graders' tests.
- Generated, and kept out of version control: `results/<stamp>/<case>-r<n>/` (what the agent produced and `grade.json`), `reports/` (one report per run of each layer) and `human-review/` (your labels).
