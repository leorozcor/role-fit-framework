# Role fit framework

A decision tool for senior job searches, and the thinking behind it. It tries to answer three separate questions about any role, and to keep them separate:

1. **Would I thrive there?** Organizational fit: four gates, then nine weighted factors.
2. **Would I create unusual value once hired?** Asymmetric fit: rarity × relevance × deployability.
3. **Will they pick me?** Candidate fit: scored on literal evidence, not on how good the analogy sounds.

Folding these into one number corrupts all three. Most of the framework exists to stop that from happening.

## What's here

| Path | What it is |
|---|---|
| [`framework/framework.md`](framework/framework.md) | The framework (v6.2): principles, gates, the asymmetry lens, candidate fit, nine factors with diagnostics and interview probes, fear diagnostic, evidence rules, verdicts, and an anonymized calibration appendix. |
| [`framework/scoring-sheet.md`](framework/scoring-sheet.md) | One-page sheet for scoring a role. Fill it in before re-reading the framework. |
| [`notebook/leadership-philosophy.md`](notebook/leadership-philosophy.md) | The explanatory side: cognitive ecology, fear and the centralization of judgment, urgency displacement, requisite variety, the profit formula, AI and the moving bottleneck. Ideas live here if they help thinking; they move into the framework only if they improve prediction. |
| [`jobs-agent/`](jobs-agent/) | A Claude Code agent that scores a job description against the framework and, only if it passes, drafts application material from a verified fact base without inventing anything. Profile files are templates. |
| [`tools/job-scorer.jsx`](tools/job-scorer.jsx) | An earlier React scoring widget. Uses older factor weights than v6.2. |
| [`tools/chiva-x-posts/`](tools/chiva-x-posts/) | Unrelated side project: a WordPress plugin that shows recent X posts using the X API v2. |

## Using the agent

1. Copy `jobs-agent/` somewhere private.
2. In `profile/`, copy each template to its real name and fill it in: `facts.md`, `search-profile.md`, `network.md`, `scan.json`. The `.gitignore` keeps all four out of version control.
3. Run `bin/jobs init`. For the optional JobsPipe radar, put `JOBSPIPE_API_KEY=...` in `jobs-agent/.env` (free key at [jobspipe.dev](https://jobspipe.dev/signup)).
4. Open the folder in Claude Code and trust it, so `.claude/settings.json` applies.

| Command | What it does |
|---|---|
| `/score <file, URL or pasted JD>` | Gates, the nine factors, asymmetry, candidate fit and channel. Writes a sheet; never drafts. |
| `/draft <id>` | Application material for a Strong or Viable role, from the fact base only, with a list of every requirement the facts don't support. |
| `/warm <id>` | The warm path from `network.md`, drafted as an ask plus a paragraph the contact can forward. |
| `/outcome <id> <outcome>` | Records what happened and applies the outcome-update rule. |
| `/scan` | A narrow JobsPipe search, screened cheaply. A radar for companies worth a warm approach, not a cold-application funnel. |
| `/board` | The board and what needs attention. |

`bin/jobs` is a small standard-library Python tracker (SQLite) that does the bookkeeping; the model does the judgment and records it there. The agent cannot edit `profile/`, `rules/`, `bin/` or its own settings, and has no tool that applies, sends or contacts anyone. It drafts; you decide.

The pipeline shape (scripts for the mechanical, the model for judgment, a person for every call that matters) follows Mattijs Kersten's [jobs-dashboard](https://github.com/mattijskersten/jobs-dashboard), MIT licensed. This version drops volume collection and auto-tailoring in favour of a scoring framework and network-first channels.

## Status and honesty notes

- The calibration behind this framework is a small sample from one person's search. The selection findings are working heuristics, not laws.
- Organizational fit has not been validated as a predictor of thriving. It has been validated, repeatedly, as *not* a predictor of being hired, which is why candidate fit exists.
- The real calibration appendix names organizations and people, so it stays private. The public appendix keeps the lessons without the cases.

## Licence

The writing (framework, notebook, agent instructions and rules) is [CC BY 4.0](LICENSE): use and adapt it freely, with attribution. The agent's code and commands, `jobs-agent/bin/` and `jobs-agent/.claude/`, are [MIT](LICENSE-CODE). The WordPress plugin in `tools/chiva-x-posts/` is GPL-2.0-or-later.

## Author

Luis Orozco, Helsinki. Writing at [chivacongelado.com](https://chivacongelado.com).
