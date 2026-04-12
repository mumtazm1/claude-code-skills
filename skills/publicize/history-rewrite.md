# History Rewrite — git-filter-repo Recipes

Phase 5 commands for scrubbing secrets and personal data from git history. These operate on a bare mirror — NEVER the original private repo.

## Install (if missing)

```bash
# Via pipx (recommended, userspace)
pipx install git-filter-repo

# Via apt
sudo apt install git-filter-repo  # user must run this — don't run sudo yourself

# Via pip
pip install --user git-filter-repo
```

Verify: `git filter-repo --version`

## Why not git filter-branch?

The git project itself recommends against `filter-branch` — it's slow, has subtle bugs around encoding and renames, and has unclear semantics for subtree operations. `git-filter-repo` is the official replacement. Don't even consider `filter-branch`; it'll bite you.

## Always Work on a Mirror

```bash
REPO=/home/alice/Projects/<repo-name>
MIRROR="/tmp/publicize-$(basename "$REPO")-mirror-$(date +%s).git"
git clone --mirror "$REPO" "$MIRROR"
cd "$MIRROR"
```

The `--mirror` flag creates a bare repo with all refs. All following commands run in `$MIRROR`.

---

## Recipe 1: Replace text across all history

Scrub a known string (e.g., a personal path prefix) from all files in all commits:

```bash
# Create a replacement file
cat > /tmp/replacements.txt <<'EOF'
/home/alice==>/home/user
alice.workers.dev==>your-worker.workers.dev
alice==>your-username
EOF

git filter-repo --replace-text /tmp/replacements.txt
```

Format: `old==>new`, one per line. Lines starting with `literal:` or `regex:` are supported — see `git filter-repo --help`.

**Caveat:** `--replace-text` operates on blob content, not file paths. For file paths, use `--path-rename`.

---

## Recipe 2: Delete files from all history

Remove files that should never appear in public history:

```bash
git filter-repo --path .env --invert-paths
git filter-repo --path credentials.json --invert-paths
git filter-repo --path-glob '.claude/*' --invert-paths
git filter-repo --path-glob '.cursor/*' --invert-paths
git filter-repo --path-glob '*.pem' --invert-paths
```

`--invert-paths` means "keep everything EXCEPT these paths." Without it, filter-repo would keep ONLY those paths.

You can combine in one command:

```bash
git filter-repo \
  --path .env \
  --path credentials.json \
  --path-glob '.claude/*' \
  --path-glob '.cursor/*' \
  --path-glob '*.pem' \
  --invert-paths
```

---

## Recipe 3: Remove a specific committed secret

If a secret is committed in history, scrub it via `--replace-text`. The file format is `literal==>replacement`, one pair per line. Use clearly-fake replacement text so reviewers can tell at a glance that the scrubbed version is a placeholder, not a new real secret:

```bash
cat > /tmp/secrets.txt <<'EOF'
sk-live-abc123==>REDACTED
ghp_EXAMPLE_TOKEN_DO_NOT_USE==>REDACTED
postgresql://user:hunter2@db:5432/app==>postgresql://user:REDACTED@db:5432/app
EOF

git filter-repo --replace-text /tmp/secrets.txt
```

For pattern-based replacement (e.g. all strings matching a token shape rather than one specific literal), use the `regex:` prefix:

```bash
cat > /tmp/patterns.txt <<'EOF'
regex:sk-[A-Za-z0-9]{20,}==>REDACTED
regex:ghp_[A-Za-z0-9]{36}==>REDACTED
EOF

git filter-repo --replace-text /tmp/patterns.txt
```

**IMPORTANT:** rotation is still mandatory. Replacing the string in YOUR history doesn't un-leak it from backups, forks, cloned copies, or the wayback machine.

---

## Recipe 4: Rewrite commit authors

If you want to publish under a different email than what's in your commits:

```bash
# Option A: mailmap file
cat > /tmp/mailmap.txt <<'EOF'
Public Name <public@example.com> <alice-personal@example.com>
Public Name <public@example.com> Alice <alice-old@example.com>
EOF

git filter-repo --mailmap /tmp/mailmap.txt
```

Format: `NewName <newemail> OldName <oldemail>` or `NewName <newemail> <oldemail>` (match by email only).

---

## Recipe 5: Combine everything

For a typical publicize run, you usually need text replacement + file deletion + maybe mailmap. Do them in order:

```bash
cd "$MIRROR"

# Step 1: delete files that should never be in history
git filter-repo \
  --path .env \
  --path credentials.json \
  --path-glob '.claude/*' \
  --path-glob '.cursor/*' \
  --invert-paths

# Step 2: scrub text (paths + secrets)
git filter-repo --replace-text /tmp/replacements.txt

# Step 3: (optional) rewrite authors
git filter-repo --mailmap /tmp/mailmap.txt
```

Each `git filter-repo` invocation requires a clean state (no previous failed rewrites). If one step errors out, you may need to re-clone from the original repo and start over. Keep `/tmp/replacements.txt` and `/tmp/mailmap.txt` around so you can replay.

---

## The Freshness Check

`git-filter-repo` by default refuses to run on a repo that's not a fresh clone (to prevent accidental rewrites of your working repo). If you see:

```
Aborting: Refusing to destructively overwrite repo history since
this does not look like a fresh clone.
```

That's the safety check. If you're truly on a fresh mirror and it's misfiring, use `--force`. But FIRST confirm you're in `$MIRROR` and not the original repo. This is the error that saves you from disaster — don't cavalierly bypass it.

```bash
pwd                          # should be $MIRROR
git config remote.origin.url # should NOT be your private repo's real origin
git filter-repo --force ...  # only after confirming the above
```

---

## Verification After Rewrite

Before pushing, verify the rewrite worked:

```bash
cd "$MIRROR"

# No more personal paths in any commit content
git log --all -p | rg '/home/alice' && echo "FAIL" || echo "OK: no alice paths"

# Deleted files really gone from all history
git log --all --full-history -- .env
# ^ should return nothing

# Secrets gone
git log --all -p | rg -i 'api[_-]?key.*=.*[a-zA-Z0-9]{16,}' && echo "FAIL" || echo "OK"

# Re-run gitleaks
gitleaks detect --source="$MIRROR" --exit-code 0
```

If any check fails: don't push. Go back and fix the filter-repo commands, possibly re-clone from original and restart.

---

## Pushing the Rewritten Mirror

For a NEW public repo:

```bash
# Create the empty public repo
gh repo create alice/<repo-name> --public --description "..."

# Add public remote (call it "public" to avoid confusion with origin)
cd "$MIRROR"
git remote add public https://github.com/alice/<repo-name>.git

# Push all refs
git push public --mirror
```

For flipping an EXISTING private repo public (rewrites its history):

```bash
# This force-pushes the rewritten history over the existing remote
# ⚠️ Anyone with existing clones will need to re-clone (tell them)
cd "$MIRROR"
git push --mirror --force origin

# Then flip visibility
gh repo edit alice/<repo-name> --visibility public
```

**For the second case, confirm with the user before running.** Force-pushing over the origin is safe ONLY when you're certain no one else has clones that matter. For personal repos this is usually fine, but make it an explicit user decision.

---

## What to Do If You Mess Up

- **Filter-repo run on wrong repo:** if you ran it on `$REPO` instead of `$MIRROR`, STOP. Don't commit or push anything. If you have a backup or the private remote still has the original history, you can restore from that. This is why you always work on a mirror.
- **Pushed secrets publicly:** rotate immediately, consider deleting the public repo and starting over, assume the secrets are compromised. Filter-repo cannot fix this after-the-fact because GitHub's cached data and any clones still have the secrets.
- **Broke history you needed:** if you have the original `$REPO` intact, re-clone from it and redo with corrected commands.

The safety net is: **original repo untouched, all destructive ops on a clearly-labeled temp mirror.** If you maintain that invariant, mistakes are always recoverable.
