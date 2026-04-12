---
name: publicize
description: Use when turning a private repo into a public one without breaking the private version you still use every day, or when the user says "publicize", "open source this", "make this public", "share this on my resume", or mentions cleaning personal data / secrets / hardcoded paths out of a repo before sharing
---

# Publicize

## Overview

Private repos get private for a reason — personal paths, secrets, hardcoded infra, embarrassing notes. But many of those repos are real work that would strengthen a resume or help other people. The hard part isn't deciding to share; it's doing it without (a) leaking secrets, (b) breaking the version you still use, or (c) drifting into a dead fork that never gets updates.

**Core principle:** Refactor the PRIVATE repo to push personal-ness into gitignored config, then publish. One canonical codebase, not a snapshot that rots.

**Why refactor-first beats sanitize-and-fork:** A one-shot "scrub and push" produces a public repo that immediately starts drifting from the private one. Every future change to the private version needs a manual re-scrub. Instead, if you move personal values into `.env` / `config.local.*` (gitignored) with `.example` templates committed, the private repo IS the public repo minus local config. Both versions stay in sync forever.

## When to Use

**Use when:**
- The user wants to publish an existing private repo — for resume, for others, or just to not have an empty GitHub
- You're about to push a repo public and need to verify it's safe
- A repo has committed secrets, hardcoded personal paths (`/home/<user>/...`, `~/Projects/...`), or personal identifiers that need to come out
- Existing public fork has drifted from private version and needs re-sync

**Don't use when:**
- Creating a brand new repo that's public from day one (just write it clean the first time)
- The repo is too personal to ever share (recognize this early — some things shouldn't be public no matter how clean they are)
- User is just asking about git history questions unrelated to publication

## The Refactor-First Mental Model

Most "make this public" guides assume you want a one-way export: private → public snapshot. That's wrong for a repo you still use. You want this instead:

```
Before:                       After:
  private repo                  private repo (still yours, still used)
    hardcoded values     →        reads from .env (gitignored)
    secrets in code                .env.example committed as template
    personal config                LICENSE + README for public audience
                                public mirror on GitHub (same code, public)
```

The private repo gets BETTER along the way — cleaner config separation, documented setup, tested LICENSE status. These are improvements you'd want anyway.

## The Nine Phases

You MUST complete each phase before proceeding. Phases are gated because mistakes compound. Publishing secrets that weren't scrubbed means rotation + possibly taking the repo down; losing commit dates means they can't be recovered; attribution errors mean forever-wrong-looking history.

| Phase | What you do | Destructive? | Gate before next |
|---|---|---|---|
| **0. Recover originals** | Find original commits in reflog before any rewriting | No | Starting point identified |
| **1. Sandbox** | Clone to a throwaway location starting from original commits | No | Sandbox isolated, correct starting commit |
| **2. Scan** | Run detectors in parallel, produce inventory | No | All detectors completed |
| **3. Triage** | Categorize findings, show user, agree on plan | No | **User signs off** |
| **4. Refactor private** | Push personal values into gitignored config in REAL private repo | Yes — edits private repo | Private repo still works |
| **5. History rewrite** | filter-repo to scrub + rebase-amend fixups into commit 1, preserving dates | Yes — in sandbox only | Real dates preserved, scrubbed clean |
| **6. Verify** | Re-run scanner, spot-check history | No | Zero critical findings |
| **6.5. README review** | Show README in chat, wait for user edits or approval | No | **User explicitly approved README** |
| **7a. Push private** | Force-push sandbox to private remote, sync local | Yes — creates rewritten remote | Force-push succeeded, still private |
| **7b. GitHub review** | User reviews github.com rendering while still private | No | **User explicitly confirmed rendering** |
| **7c. Public flip** | `gh repo edit --visibility public` | Yes — irreversible public action | **NEW "flip public" signal this turn** |
| **8. Post-publish** | Rotate secrets, verify live service, keep sandbox until user says cleanup | Yes — rotates credentials | User confirms cleanup |

Details of each phase are in `workflow.md`. Read it before executing. **The skill's core lesson: destructive operations need more gates, not fewer. Prior approval does not carry across destructive steps.**

## Tool Prerequisites

Check which tools are installed, then fall back gracefully if missing:

```bash
command -v rg || echo "ripgrep missing (required)"
command -v gitleaks || echo "gitleaks missing (recommended, fallback: rg-based regex)"
command -v git-filter-repo || echo "git-filter-repo missing (required for Phase 5)"
```

**If `gitleaks` missing:** `sudo apt install gitleaks` or download from https://github.com/gitleaks/gitleaks/releases. Fallback: the `scanner-patterns.md` file has ripgrep-based regex alternatives that catch ~80% of common secrets. Offer the install command to the user rather than running `sudo` yourself.

**If `git-filter-repo` missing:** `pipx install git-filter-repo` or `sudo apt install git-filter-repo`. No fallback — Phase 5 is blocked until this is installed. Don't attempt `git filter-branch`; it's officially discouraged and has edge cases that eat data.

## The Four Triage Buckets

Every finding from Phase 2 lands in one of these:

**🚨 MUST FIX — blocks publication:**
- Committed secrets (API keys, tokens, passwords, OAuth credentials)
- Committed credential files (`.env`, `*token*.json`, `credentials*.json`)
- Private keys (`*.pem`, `*.key`, `id_rsa*`)
- PII or data that identifies real people (including the user's own email if they don't want it public)

**♻️ SHOULD ABSTRACT — refactor into gitignored config:**
- Hardcoded personal paths (`/home/<user>/...`, `~/Projects/...`)
- Personal URLs (Cloudflare worker subdomains, internal hostnames)
- Machine-specific identifiers (mic indices, MAC addresses, device names)
- Database connection strings pointing at localhost/personal postgres
- Personal calendar names, workspace names, account IDs

**🗑️ SHOULD REMOVE — add to .gitignore and delete from tree:**
- `.claude/`, `.cursor/`, `CLAUDE.md`, `.aider*`
- Debug session docs (`DEBUG_SESSION.md`, `scratch.md`)
- Personal TODO files, planning docs not meant for public
- Build artifacts that shouldn't have been committed
- IDE-specific config that leaks personal workflow details

**⚠️ FUNCTIONALITY RISK — public users can't run it:**
- Dependencies on personal infra (your postgres, your MCP servers, your Cloudflare workers)
- Hardcoded account IDs that only work for you
- Environment assumptions (specific kernel version, GPU, audio device)

The first three are fixable by the skill. The fourth often needs a "Required Setup" README section explaining what the user needs to provide, OR a decision to not publicize this repo yet.

## Red Flags — STOP

If you catch yourself thinking any of these, stop and return to an earlier phase:

| Thought | Reality |
|---|---|
| "I'll use `--reset-author` to fix the commit emails" | **NEVER.** `--reset-author` resets the author DATE too. Real commit dates are lost forever. Use `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/`GIT_AUTHOR_DATE` env vars instead. |
| "The originals are gone, I'll just start from the current state" | **CHECK THE REFLOG FIRST.** Git keeps unreachable objects ~90 days. Run `git reflog` and `git fsck --unreachable --no-reflogs` before concluding originals are lost. If you start from a previously-rewritten state, dates cannot be recovered. |
| "I'll use the user's personal Gmail as the commit author" | **USE GITHUB NOREPLY INSTEAD.** Personal Gmail won't be verified on the target GitHub account, so commits render as a generic name with no avatar and no profile link. Format: `<userid>+<username>@users.noreply.github.com`. Get id via `gh api user --jq .id`. |
| "I'll write the README and commit it in one step" | **NEVER.** README is draft → show user → wait for approval → only then commit. Every version, every iteration. My default voice has AI tells (em dashes, punchy phrases, cute section titles) that the user catches only on review. |
| "'Why this exists' is a good section title" | **NO.** Section titles should be flat nouns: Setup, Usage, Development, License. Not sentences, not cute conversational phrases. If a title reads like a content marketer wrote it in 2024, rewrite. |
| "User said 'ship it' earlier, I'll flip to public" | **NO.** Prior approval does not carry across destructive steps. The visibility flip needs a NEW explicit signal this turn, AFTER the user has seen github.com rendering. |
| "I'll just operate on the original repo directly" | **NEVER.** Destructive history operations (filter-repo, rebase, reset --hard) happen in sandboxes. The real repo is only synced via fetch + reset --hard AFTER the sandbox work is verified. |
| "I'll clean up the sandbox right after force-pushing" | **KEEP IT.** The sandbox is your rollback source. Only delete after the user has seen the final public state and said "cleanup". |
| "Skip Phase 4, just scrub and push" | The drift trap. The private repo keeps its hardcoded values; every future change needs re-scrubbing. Phase 4 is the whole point. |
| "git-filter-repo will un-leak the historical secrets" | **NO.** filter-repo rewrites YOUR copy of history. Anyone who already cloned still has the original. Secrets ever committed must be rotated. |
| "I'll test the refactor after publishing" | Test the refactored PRIVATE repo BEFORE touching history. If the refactor broke it, you want to know now. |
| "This scanner passed, we're clean" | Scanners miss things. Dry-run + spot check + re-scan are layered defenses. |
| "Just one quick fix commit after publishing" | Post-publish fix commits touching secrets add another entry to the history. Do Phase 2-6 properly the first time. |
| "The secrets are only in old commits, that's fine" | Git history is part of the public repo. "Old commits" are equally public. |

## Common Rationalizations

| Excuse | Reality |
|---|---|
| "It's just a small personal project, scanner is overkill" | Small projects have committed `.env` files more often than large ones. Scan anyway. |
| "I know my code, I know what's in there" | Every engineer who leaked secrets "knew their code." Run the scanner. |
| "I'll rotate the secrets later" | Secrets published publicly are scraped by bots within minutes. Rotate BEFORE the public push, or don't push. |
| "It's a public fork, upstream license doesn't matter" | Forks must preserve the upstream LICENSE and attribution. Check `git remote -v` for upstream. |
| "I don't need history rewrite, nothing sensitive was ever committed" | Verify with `gitleaks detect --source=.` (full history) before skipping Phase 5. |
| "My repo is tiny, filter-repo is overkill" | Even tiny repos have commit histories. Filter-repo on a 10-file repo takes 2 seconds. |

## Archetype-Based Strategy

Different repos need different amounts of work. Before starting Phase 1, classify the repo and read the matching section of `per-repo-archetypes.md`:

- **Ship-ready** — Few personal deps, `.env` already gitignored, LICENSE present. Phases 1-3, 6, 7. Total: ~30 min.
- **Needs config abstraction** — Some hardcoded values but no committed secrets. All 8 phases but Phase 4 is small.
- **Fork with attribution** — Originally forked from someone else's repo. All 8 phases + extra care with LICENSE/attribution/upstream remote.
- **Personal doc archive** — Mostly scripts + docs, not an app. Phases 1-3, 7. Skip refactor if there's nothing to abstract; focus on README framing for the public audience.
- **Heavy personal infra** — Code depends on user's private services. Phase 4 becomes a multi-day refactor. Often better to hold.

Each archetype has an example shape and typical gotchas in `per-repo-archetypes.md`.

## Quick Reference

**Start a publicize session:**
1. Ask user which repo, classify archetype
2. Read `per-repo-archetypes.md` for the matching strategy
3. Read `workflow.md` for phase details
4. Execute Phase 1 (sandbox) → Phase 2 (scan) → Phase 3 (triage + user signoff)
5. If user approves → Phase 4-8

**Supporting files (read when phase says to):**
- `workflow.md` — Phase-by-phase commands, pause points, verification
- `scanner-patterns.md` — Detector regexes, gitleaks usage, ripgrep fallbacks
- `abstraction-recipes.md` — Config refactor patterns by language
- `history-rewrite.md` — git-filter-repo recipes with safety rails
- `per-repo-archetypes.md` — Strategies per archetype with example shapes

**Related skills** (invoke when relevant):
- `superpowers:verification-before-completion` — invoke at end of Phase 4, 6, 7 to enforce "evidence before claim"
- `superpowers:using-git-worktrees` — Phase 1 sandbox creation
- `superpowers:systematic-debugging` — if Phase 4 refactor breaks the private repo

## The Goal

Most private repos stay private out of shyness, not strategy. This skill exists to make each publicize a 30-minute job so momentum builds and the psychological barrier drops. Ship the easy ones first. Don't gatekeep mediocre-but-honest repos.

## Hard Rules (non-negotiable)

These are the expensive lessons. Every one of them came from a real mistake that had to be backed out. Treat them as hard rules, not suggestions.

1. **Use GitHub noreply email for commit attribution, never a personal Gmail.** Personal emails often aren't verified on the target GitHub account, so commits render as a generic name with no avatar and no profile link. Format: `<userid>+<username>@users.noreply.github.com`. Get the ID via `gh api user --jq .id`.
2. **Never use `git commit --amend --reset-author`.** It resets the author DATE as well as the email, silently overwriting real commit dates. Use `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` / `GIT_AUTHOR_DATE` env vars on a rebase-exec instead.
3. **Recover original commits from reflog BEFORE rewriting anything.** Git keeps unreachable objects for ~90 days. Run `git reflog` and `git fsck --unreachable --no-reflogs` first. If you start from a previously-rewritten state, real dates cannot be recovered.
4. **README is draft → show user → wait for approval → only then commit.** Every version, every iteration. Claude's default prose has AI tells (em dashes, punchy phrases, cute section titles) that the user catches only on review.
5. **README section titles are flat nouns.** `Setup`, `Usage`, `Development`, `License`. Not sentences. Not cute conversational phrases. If a title reads like a content marketer wrote it, rewrite.
6. **Public visibility flip is its own gate.** Prior approval does not carry. The `gh repo edit --visibility public` step needs a NEW explicit signal in the current turn, AFTER the user has seen github.com rendering.
7. **Destructive git operations happen in sandboxes, not the real repo.** filter-repo, rebase, reset --hard all run in a throwaway clone. The real repo is only synced via fetch + reset --hard AFTER the sandbox work is verified.
8. **Keep the sandbox until the user explicitly says cleanup.** The sandbox is the rollback source if anything goes wrong post-publish.
