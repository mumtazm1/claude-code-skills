# Publicize Workflow — Phase Details

Each phase has: goal, commands, pause points, and a "done when" gate. Don't skip gates. They exist because skipping compounds errors.

**Before you start, read `feedback_publicize_hard_rules.md` in memory if you haven't already this session. Those rules override any instinct to move faster.**

---

## Phase 0: Recover original commits from reflog

**Goal:** Make sure we're starting from the user's ORIGINAL commits, not from a previously-rewritten state. Git keeps unreachable objects for ~90 days in `.git/objects/`, so even if force-pushes or resets have orphaned them, they're usually still recoverable.

**Why this is Phase 0, not skipped:** if you start rewriting from the current HEAD of a repo that's already been touched, real commit dates are lost permanently and errors accumulate on top of errors. Always start from a verified original commit.

**Commands:**

```bash
REPO=/home/alice/Projects/<repo-name>
cd "$REPO"

# Check the reflog for commits that were once on the branch
git reflog | head -30

# Also check all dangling commits (things in .git/objects that no ref points to)
git fsck --unreachable --no-reflogs 2>&1 | rg '^unreachable commit'
```

Look for commits that predate any "Prepare for public" / "Rewrite README" / "Cleanup" messages I (or someone else) may have added. These are the originals.

If you find them:
```bash
# Point a temp branch at the real tip of original history
git branch publicize-original-tip <sha-of-most-recent-original-commit>
git log --format='%h %ai %s' publicize-original-tip
```

**If the reflog is clean and there are no rewrites yet** (a virgin publicize run): skip to Phase 1 using current HEAD as the starting point.

**If rewrites have happened and originals are recoverable:** use `publicize-original-tip` as the starting point throughout the rest of the workflow. All filter-repo, cloning, and rebasing operates from there.

**If rewrites have happened and originals are NOT recoverable:** warn the user that real commit dates cannot be preserved. Ask whether they want to proceed anyway or accept the loss.

**Done when:**
- Either: `publicize-original-tip` branch exists at the real tip of original history
- Or: confirmed that current HEAD is the original (no prior rewrites)
- Or: explicitly told the user we can't preserve dates and they accepted

---

## Phase 1: Sandbox

**Goal:** Get an isolated copy of the repo where destructive operations can't hurt the original.

**Commands:**

```bash
REPO=/home/alice/Projects/<repo-name>
SANDBOX=/tmp/publicize-$(basename "$REPO")-$(date +%s)

# Clone from the starting point identified in Phase 0
# If you created publicize-original-tip:
git clone --single-branch --branch publicize-original-tip "$REPO" "$SANDBOX"

# Otherwise clone current state:
git clone "$REPO" "$SANDBOX"

cd "$SANDBOX"
```

**Always full clone, never worktree.** Worktrees share `.git` with the original, so any `git gc` or reflog operation affects the source. A full clone is completely isolated.

**Done when:**
- `$SANDBOX` exists and contains the repo
- `cd $SANDBOX && git status` shows clean working tree
- You've confirmed `$SANDBOX != $REPO`
- Sandbox's HEAD points at the correct starting commit (original tip if recovered, current HEAD otherwise)

---

## Phase 2: Scan

**Goal:** Produce a complete inventory of personal-ness in the sandbox. Don't fix anything yet — just catalog.

Read `scanner-patterns.md` for the full detector list. Run detectors in parallel where possible and write findings to `$SANDBOX/.publicize-findings.md` (gitignore this later or just delete it).

**Minimum detectors to run:**

```bash
# Secrets (current tree)
gitleaks detect --source="$SANDBOX" --no-git --report-path="$SANDBOX/.publicize-gitleaks-current.json" 2>&1 || true

# Secrets (full history) — slower
gitleaks detect --source="$SANDBOX" --report-path="$SANDBOX/.publicize-gitleaks-history.json" 2>&1 || true

# If gitleaks missing, use scanner-patterns.md's ripgrep fallback

# Personal paths
rg -n '/home/alice' "$SANDBOX" > "$SANDBOX/.publicize-paths.txt" || true

# Personal URLs
rg -n 'alice\.workers\.dev' "$SANDBOX" > "$SANDBOX/.publicize-urls.txt" || true

# Committed env/token files
(cd "$SANDBOX" && git ls-files | rg -i '(\.env$|token.*\.json|credential|secret|\.pem$|\.key$)') > "$SANDBOX/.publicize-creds.txt" || true

# Local-only docs
(cd "$SANDBOX" && git ls-files | rg '(\.claude/|\.cursor/|^CLAUDE\.md|DEBUG_SESSION|scratch\.md)') > "$SANDBOX/.publicize-docs.txt" || true

# LICENSE status
ls "$SANDBOX"/LICENSE* 2>/dev/null || echo "NO LICENSE FILE" > "$SANDBOX/.publicize-license.txt"

# Fork provenance
(cd "$SANDBOX" && git remote -v) > "$SANDBOX/.publicize-remotes.txt"

# Commit authors
(cd "$SANDBOX" && git log --format='%ae' | sort -u) > "$SANDBOX/.publicize-authors.txt"
```

**Done when:** all detector outputs exist. Some may be empty — that's fine, empty = clean on that dimension.

---

## Phase 3: Triage

**Goal:** Convert raw findings into a human-readable plan. Show it to the user. Get explicit agreement before any destructive work.

Aggregate the Phase 2 outputs into a triage report organized by the four buckets (MUST FIX, SHOULD ABSTRACT, SHOULD REMOVE, FUNCTIONALITY RISK). Use this format:

```markdown
# Publicize Triage Report — <repo-name>

## 🚨 MUST FIX (blocks publication)
- `src/config.py:42` — API_KEY = "sk-live-..."
- `.env` committed to repo (contains 7 secrets — see gitleaks report)
- History: `7f3a2c1` committed `credentials.json` (later deleted but still in history)

## ♻️ SHOULD ABSTRACT (refactor to config)
- `deploy.py:12` — hardcoded `/home/alice/Projects/.venv`
- `README.md:28` — worker URL `alice.workers.dev`
- `wrangler.toml:5` — KV namespace ID belongs to the user's Cloudflare account

## 🗑️ SHOULD REMOVE (gitignore + git rm --cached)
- `.claude/` directory (3 files)
- `.cursor/DEBUG_SESSION.md`
- `CLAUDE.md`

## ⚠️ FUNCTIONALITY RISK
- Depends on localhost postgres (will break for any other user)
- Requires a private Cloudflare worker with personal OAuth tokens

## META
- LICENSE: MISSING (README claims MIT)
- Remotes: origin → alice/<repo> (PRIVATE)
- Upstream: none
- Commit authors: alice@<personal-email> (all commits)
```

**Then ask the user, explicitly:**

> Here's what I found. For each bucket, here's what I plan to do:
> - MUST FIX: remove from current tree AND rewrite history in Phase 5, then rotate
> - SHOULD ABSTRACT: refactor in the private repo (Phase 4), commit incrementally, test
> - SHOULD REMOVE: add to `.gitignore`, `git rm --cached`, commit
> - FUNCTIONALITY RISK: add a "Setup Required" section to README explaining what users need
>
> Does this plan match what you want? Anything I should skip or handle differently?

**Done when:** user has explicitly approved the plan or told you to adjust it. Don't proceed without this.

---

## Phase 4: Refactor Private (on the REAL repo, not the sandbox)

**Goal:** Push all SHOULD ABSTRACT and SHOULD REMOVE findings into the private repo, verify the private repo still works, commit.

This is the ONE phase that modifies the actual private repo. Everything else stays in sandbox or mirror. Be careful.

**Approach:**

1. Leave the sandbox alone — it's your reference for what needs fixing
2. Work in the real repo: `cd $REPO`
3. Read `abstraction-recipes.md` for language-specific refactor patterns
4. For each SHOULD ABSTRACT finding:
   - Introduce config loading if not present (env vars, `config.local.yaml`, etc.)
   - Replace hardcoded value with config read
   - Add the key to `.env.example` with a placeholder value and comment
   - Add the real config file to `.gitignore` if not already
5. For each SHOULD REMOVE finding:
   - Add pattern to `.gitignore`
   - `git rm --cached <file>` (removes from index, keeps on disk if still needed)
6. For MUST FIX in current tree (history comes later in Phase 5):
   - Same as SHOULD REMOVE — gitignore + `git rm --cached`
   - If the file is still needed (e.g., `.env`), leave it on disk, just untracked
7. Verify the private repo still works end-to-end. This is critical. Run whatever "does it work" command exists:
   - Tests: `pytest` / `npm test` / `cargo test`
   - Manual: actually run the app against real config
   - Dev: `npm run dev` / `python -m <module>` / `wrangler dev`
8. If it broke, FIX IT before moving on. Do not proceed with a broken private repo.
9. Commit incrementally — one refactor = one commit. Makes review easier and bisect useful later.

**Pause point:** before Phase 5, explicitly ask the user:

> I've refactored the private repo. Personal values now come from `.env` / config files. I ran [command] and it still works. Commits are [list]. Ready to rewrite history and publish?

**Done when:**
- Private repo still works
- All commits are on the current branch
- `git status` clean
- `.env.example` committed with all needed keys
- User confirms ready to proceed

---

## Phase 5: History Rewrite (preserve dates!)

**Goal:** Rewrite history to scrub personal details (secrets, emails, paths, files) while **preserving commit dates**. The rewritten history gets pushed to a new public remote, never back to the private origin.

**Critical: preserve commit dates.** Use `filter-repo` which preserves author and committer dates by default. Never use `git commit --amend --reset-author` during this phase — that flag resets the author date to "now" and destroys real timestamps.

### Step 5a: Create a clean sandbox from Phase 0's starting point

If you created `publicize-original-tip` in Phase 0, your Phase 1 sandbox already starts there. Confirm:
```bash
cd "$SANDBOX"
git log --format='%h %ai %s'
```
Every commit should have its real original date.

### Step 5b: Run filter-repo to scrub personal details

```bash
cd "$SANDBOX"

# Rewrite author email to GitHub noreply (preserves dates)
# Get the noreply email via `gh api user --jq .id` + "<id>+<username>@users.noreply.github.com"
cat > /tmp/publicize-mailmap.txt <<EOF
alice <12345678+alice@users.noreply.github.com> <alice-old@example.com>
EOF
git filter-repo --mailmap /tmp/publicize-mailmap.txt

# Scrub personal URLs, paths, and any strings you identified in Phase 2
cat > /tmp/publicize-replacements.txt <<EOF
myapp.alice.workers.dev==>your-worker.your-subdomain.workers.dev
/home/alice==>/home/user
EOF
git filter-repo --force --replace-text /tmp/publicize-replacements.txt

# Remove files that should never be in public history
git filter-repo --force --path CLAUDE.md --invert-paths
git filter-repo --force --path .env --invert-paths
git filter-repo --force --path-glob '.claude/*' --invert-paths
git filter-repo --force --path-glob '.cursor/*' --invert-paths
```

Read `history-rewrite.md` for full recipe details.

### Step 5c: Fold fixups into the initial commit while preserving its date

After filter-repo, the tree has clean history but lacks LICENSE, a humanized README, and other polish that needs to go into the FIRST commit (so it reads as "this repo always had them"). Do this via `git rebase -i --root` with `edit` on the first commit, amending with explicit date env vars:

```bash
# Capture the original author date of the first commit BEFORE editing
ORIG_FIRST_DATE=$(git log --format='%aI' $(git rev-list --max-parents=0 HEAD))

# Configure git identity (used for committer on the amend)
git config user.email "12345678+alice@users.noreply.github.com"
git config user.name "alice"

# Start rebase, mark first commit as "edit", make committer dates follow author dates for others
GIT_SEQUENCE_EDITOR='sed -i "1s/^pick/edit/"' \
  git rebase -i --root --committer-date-is-author-date

# Rebase pauses at first commit. Working tree reflects commit 1's state.
# Inject the public-ready files (LICENSE, approved README, updated config, etc.):
cp /path/to/LICENSE .
cp /path/to/approved-README.md README.md
# ... etc for .gitignore, package.json, wrangler.toml-without-triggers ...

git add -A

# Amend with preserved author + committer date, NEVER use --reset-author
GIT_AUTHOR_DATE="$ORIG_FIRST_DATE" \
GIT_COMMITTER_DATE="$ORIG_FIRST_DATE" \
GIT_AUTHOR_EMAIL="12345678+alice@users.noreply.github.com" \
GIT_AUTHOR_NAME="alice" \
GIT_COMMITTER_EMAIL="12345678+alice@users.noreply.github.com" \
GIT_COMMITTER_NAME="alice" \
git commit --amend --no-edit

# Continue rebase. Handle README conflicts on later commits by taking `--ours` (the approved README)
git -c core.editor=true rebase --continue

# If conflict:
git checkout --ours README.md
git add README.md
git -c core.editor=true rebase --continue
```

**Verify:**
```bash
git log --format='%h %ai %s'
# Every commit should show its original date, not today's date.
```

**Safety rails:**
- NEVER use `git commit --amend --reset-author`. It resets author date.
- NEVER run filter-repo in the original private repo. Sandbox only.
- NEVER force-push the sandbox back to the private origin. Use a new remote for the public copy.
- Use `--committer-date-is-author-date` on `git rebase` to keep committer dates consistent with author dates.
- For amends that need a specific date, set both `GIT_AUTHOR_DATE` AND `GIT_COMMITTER_DATE`.

**Done when:**
- Sandbox has the rewritten history with real dates preserved
- Every commit shows the correct original date via `git log --format='%ai'`
- No personal details in any `git log -p` output
- Fixups (LICENSE, README, etc.) are present from the first commit

---

## Phase 6: Verify

**Goal:** Prove the rewritten mirror is actually clean before publishing.

```bash
cd "$MIRROR"

# Re-run all Phase 2 scanners against the mirror
gitleaks detect --source="$MIRROR" --report-path=/tmp/publicize-verify-gitleaks.json
git log --all -p | rg '/home/alice' && echo "FAIL: still finding personal paths" || echo "OK"
git log --all -p | rg -i '(api[_-]?key|secret|password|token)\s*=\s*["\x27][a-zA-Z0-9]{20,}' && echo "FAIL: possible secret" || echo "OK"

# Spot-check by cloning the mirror to a working copy
VERIFY="/tmp/publicize-verify-$$"
git clone "$MIRROR" "$VERIFY"
cd "$VERIFY"
ls -la
cat README.md
cat LICENSE 2>/dev/null || echo "NO LICENSE"
cat .env.example 2>/dev/null || echo "NO .env.example"
```

**Done when:**
- Scanner finds zero MUST FIX issues
- Manual spot-check shows LICENSE, README, `.env.example` present
- Personal paths absent from log -p output
- A clean clone of the mirror can be cat'd and nothing surprising shows up

If anything fails: go back to Phase 5, adjust the filter-repo commands, redo.

---

## Phase 6.5: README review gate (MANDATORY)

**Before Phase 7, show the user the final README and wait for explicit approval or edits.**

This gate exists because my default writing voice has AI tells that the user catches only on review. Even if the README content "hasn't changed since the last approval" or "is basically the same as the private version", the gate applies. Per-version review, not per-session.

Show the full README content in chat. Ask the user to call out any:
- **Em dashes** (`—` or `–`). The number one AI tell.
- **Punchy AI phrases:** "just works", "seamlessly", "in the background", "transparently", "failing silently", "takes 30 seconds", "that's the whole surface", "with ease"
- **Cute section titles:** "Why this exists", "Things that will trip you up", "The one gotcha", "Using it", "Getting started quickly", "What you need to know"
- **Marketing adjectives:** comprehensive, elegant, seamless, robust, simple, powerful
- **Anything that reads as AI-generated** rather than human-written

**README section titles must be flat nouns.** Setup. Usage. Development. License. Endpoints. Configuration. Token refresh. Deployment. Testing. Not sentences, not descriptive phrases with verbs, not cute conversational titles.

Wait for the user to say "README is fine" (or equivalent) or give edits. Iterate until approval. Only then proceed to Phase 7.

---

## Phase 7: Publish (two separate gates!)

**Goal:** Push the verified sandbox to the public remote AND flip visibility. These are two separate steps with two separate user gates.

### Step 7a: Force-push to the private remote (still private)

```bash
cd "$SANDBOX"
git remote add github https://github.com/alice/<repo-name>.git
git push github master --force
```

**Then sync the local working copy to match the new remote:**
```bash
cd "$REPO"  # the real local repo
git fetch origin
git reset --hard origin/master
```

After this step the rewritten history is on github.com but the repo is STILL PRIVATE. Nothing is publicly visible yet.

### Step 7b: Tell the user to review on github.com

> Reload https://github.com/alice/<repo-name>. The repo is still private, so only you can see it. Verify:
> 1. Commit list shows your avatar and alice profile link on every commit (not generic "the user" with no avatar)
> 2. Commit dates show the real spread from your iterative development (e.g., "2 months ago / 6 weeks ago / 6 days ago"), not all "just now"
> 3. README renders correctly with the flat section titles
> 4. LICENSE is present, no CLAUDE.md, no personal URLs visible in any file

Wait for the user to explicitly confirm the github rendering is correct. If something's wrong (author attribution, dates, README formatting, missing file), go back to Phase 5 and fix.

### Step 7c: The visibility flip (irreversible gate)

**This is the single most irreversible step in the entire workflow.** Only run after:
- User has seen the rendering on github.com
- User has given a NEW explicit "flip public" signal this turn
- Prior approval earlier in the session does NOT carry

```bash
gh repo edit alice/<repo-name> --visibility public --accept-visibility-change-consequences

# Optionally set description and topics if missing
gh repo edit alice/<repo-name> \
  --description "<one-line description>" \
  --add-topic <topic1> --add-topic <topic2>
```

For forks, preserve upstream attribution in README. Example:

> Originally forked from [upstream/repo](https://github.com/upstream/repo). This version adds: [list of augmentations]. Upstream LICENSE preserved.

**Done when:**
- Public repo URL loads in browser with correct rendering
- README, LICENSE, `.env.example` (if applicable) all visible
- Commit list shows correct avatar, profile link, and real dates
- No sensitive content in any visible file or commit

---

## Phase 8: Post-Publish

**Goal:** Clean up loose ends that affect your real-world security and future-you's ability to keep the repos in sync.

**Mandatory:**
- If ANY secrets were ever committed (even if scrubbed from history): rotate them NOW. Filter-repo doesn't un-leak. Anyone who cloned before the scrub still has them. Assume compromise.
- Hit the deployed service's health endpoint (if applicable) to confirm personal usage is unaffected. For workers with `/status` or similar: `curl https://<worker-url>/status`.
- Run `npm run typecheck` / `pytest` / equivalent to confirm the refactored local repo still compiles and runs.
- **Do NOT delete sandboxes immediately.** Wait for explicit user confirmation that the final public state looks right. Keep `/tmp/publicize-*` around as rollback source until the user says "clean up".
- Once approved: `rm -rf /tmp/publicize-*`

**Recommended:**
- Write a short note in a personal journal / `~/.publicize-log.md`:
  ```
  2026-04-10 — published alice/<repo> publicly.
  Refactored values: worker URL, KV ID, venv path
  Secrets rotated: <list>
  Private repo at: /home/alice/Projects/<repo>
  ```
- For future private changes that should flow to public: just commit to private, then push to the public remote normally. The refactor-first approach means you don't need to re-sanitize.

**Done when:**
- Rotated secrets confirmed
- Temp directories cleaned
- User knows how to update the public version going forward

---

## Checkpoint Summary

Before each phase transition, verify the gate:

| Leaving phase | Gate |
|---|---|
| 0 → 1 | Original commits identified (reflog or confirmed virgin state) |
| 1 → 2 | Sandbox isolated from original, starting from correct commit |
| 2 → 3 | All detectors ran, findings captured |
| 3 → 4 | **User signed off on plan** |
| 4 → 5 | Private repo still works, changes committed, user confirms |
| 5 → 6 | filter-repo ran without errors, real commit dates preserved |
| 6 → 6.5 | Scanner finds zero critical issues on sandbox |
| 6.5 → 7 | **User explicitly approved README** |
| 7a → 7b | Force-push succeeded, local synced to new remote, still private |
| 7b → 7c | **User explicitly confirmed github.com rendering + NEW "flip public" signal** |
| 7c → 8 | Public repo loads, LICENSE + README + correct attribution + correct dates |
| 8 → done | Secrets rotated, live service health confirmed, **user said clean up**, temp dirs removed |

## The meta-rule

Destructive operations deserve more gates, not fewer. Prior approval earlier in the session does NOT carry across destructive steps. When in doubt: show state, wait for signal. The user can always tell you to move faster; they cannot undo a public push with wrong attribution or lost dates.
