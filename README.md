# claude-code-skills

Claude Code skills I use day to day: 

**expert-opinion** (direct, research-grounded decision consulting) 

**publicize** (ship a private repo as public without breaking the version you still use).

Distributed as a Claude Code plugin marketplace. One git repo, one plugin, two skills.

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

See [`skills/expert-opinion/SKILL.md`](skills/expert-opinion/SKILL.md).

### publicize

Turns a private repo into a public one without the usual failure modes: committed secrets surviving in history, commit dates getting nuked by `--reset-author`, drift between the private copy and the public snapshot, or README voice that reads like an AI wrote it.

The skill runs a nine-phase workflow (recover originals, sandbox, scan, triage, refactor-first, history rewrite, verify, README review, push private, review rendering, flip public) with hard gates at every destructive step. Uses `gitleaks` and `git-filter-repo` where available; falls back to `ripgrep` patterns when not.

See [`skills/publicize/SKILL.md`](skills/publicize/SKILL.md) and its supporting files (`workflow.md`, `scanner-patterns.md`, `abstraction-recipes.md`, `history-rewrite.md`, `per-repo-archetypes.md`).

## License

MIT. See [`LICENSE`](LICENSE).
