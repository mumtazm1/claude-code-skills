# claude-code-skills

Claude Code skills I use day to day: 

**expert-opinion** (direct, research-grounded decision consulting) 

**publicize** (ship a private repo as public without breaking the version you still use).

Distributed as a Claude Code plugin marketplace.

## Install

In Claude Code:

```
/plugin marketplace add mumtazm1/claude-code-skills
/plugin install claude-code-skills@claude-code-skills
```

Update later with:

```
/plugin marketplace update claude-code-skills
```

## Manual install (no plugin machinery)

If you'd rather drop the skills straight into your user config:

```bash
git clone https://github.com/mumtazm1/claude-code-skills.git
cp -r claude-code-skills/skills/expert-opinion ~/.claude/skills/
cp -r claude-code-skills/skills/publicize ~/.claude/skills/
```

Restart Claude Code. Both skills will register automatically.

## Skills

### expert-opinion

Claude's default voice at decision points is too agreeable and relies on training-data priors. This skill makes Claude answer like a specific professional (a principal engineer, a fee-only CFP, an evidence-based PCP, and so on), pull fresh information from the web, and commit to a pick instead of listing tradeoffs.

Trigger it by saying "expert opinion", "second opinion", "what would a [role] say", or "help me decide". The skill enforces a four-step protocol: name the professional, pull current sources (with cross-referencing and date-stamping), synthesize internally, and return a short verdict with inline citations and a data-freshness line.

#### An example

I asked Claude Code how I'd recommend syncing Postgres to Snowflake for a startup with ~100GB of data, as if I were the consultant answering.

First run, no skill, Claude gave me specific numbers. "4-6 hours to stand up the first source, ~1 hour per additional source." "Don't backfill through dlt or Airbyte, dump to Parquet first." It sounded authoritative.

I pushed back and told Claude to actually verify. It admitted the hours were fabricated and the dogma about backfills had no source. It was predicting plausible tokens instead of answering the question.

Second run, with `/expert-opinion`:

> Pick: Airbyte OSS, self-hosted. Long-term optionality decides this. Airbyte has a published Python connector SDK and 300+ pre-built sources. PeerDB has three sources and no custom-connector framework. [PeerDB supported-connectors matrix, as of 2026-04]

Same question. Actual web searches, real connector matrices, inline citations, a data-freshness line. The answer I'd have written myself.

By forcing Claude to look things up instead of guessing, the results are much more grounded in reality.

See [`skills/expert-opinion/SKILL.md`](skills/expert-opinion/SKILL.md).

### publicize

Turns a private repo into a public one without the usual failure modes: committed secrets surviving in history, commit dates getting nuked by `--reset-author`, drift between the private copy and the public snapshot, or README voice that reads like an AI wrote it.

The skill runs a nine-phase workflow (recover originals, sandbox, scan, triage, refactor-first, history rewrite, verify, README review, push private, review rendering, flip public) with hard gates at every destructive step. Uses `gitleaks` and `git-filter-repo` where available; falls back to `ripgrep` patterns when not.

See [`skills/publicize/SKILL.md`](skills/publicize/SKILL.md) and its supporting files (`workflow.md`, `scanner-patterns.md`, `abstraction-recipes.md`, `history-rewrite.md`, `per-repo-archetypes.md`).

## License

MIT. See [`LICENSE`](LICENSE).
