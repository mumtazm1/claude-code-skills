# Scanner Patterns

Detector commands and regex patterns for Phase 2. Organized by what they find.

## Tool Preference

- **`gitleaks`** — industry-standard secret detection. Handles many entropy-based checks and known token formats. Use first if installed.
- **`ripgrep` (`rg`)** — fallback for everything. Always available on the user's system.
- **`git ls-files`** — inventory what's tracked.

---

## Secret Detection

### With gitleaks (preferred)

```bash
# Current tree only (fast)
gitleaks detect --source=. --no-git --report-path=gitleaks-current.json

# Full history (slower, catches secrets in old commits)
gitleaks detect --source=. --report-path=gitleaks-history.json
```

`gitleaks` returns non-zero exit code when it finds secrets. Capture stderr or use `--exit-code 0` to keep your script running:

```bash
gitleaks detect --source=. --exit-code 0 --report-path=gl.json
```

### Ripgrep fallback (when gitleaks is missing)

None of these are as good as gitleaks, but they catch the common cases. Combine multiple patterns:

```bash
# Known token prefixes
rg -n 'sk-[a-zA-Z0-9]{20,}' .              # OpenAI keys
rg -n 'sk-ant-[a-zA-Z0-9-_]{20,}' .        # Anthropic keys
rg -n 'ghp_[a-zA-Z0-9]{36}' .              # GitHub personal access tokens
rg -n 'ghs_[a-zA-Z0-9]{36}' .              # GitHub server tokens
rg -n 'github_pat_[a-zA-Z0-9_]{80,}' .     # GitHub fine-grained PATs
rg -n 'glpat-[a-zA-Z0-9_-]{20,}' .         # GitLab PATs
rg -n 'xox[baprs]-[a-zA-Z0-9-]{20,}' .     # Slack tokens
rg -n 'AIza[0-9A-Za-z_-]{35}' .            # Google API keys
rg -n 'apify_api_[a-zA-Z0-9]{30,}' .       # Apify tokens
rg -n '\b[0-9]{9,10}:AA[a-zA-Z0-9_-]{30,}\b' .  # Telegram bot tokens

# Key=value secret patterns (broad — expect false positives)
rg -n -i '(api[_-]?key|secret|password|passwd|token|access[_-]?token|refresh[_-]?token|private[_-]?key|client[_-]?secret)\s*[=:]\s*["\x27][a-zA-Z0-9_\-+/=]{16,}' .

# AWS keys
rg -n 'AKIA[0-9A-Z]{16}' .                 # AWS access key ID
rg -n 'aws_secret_access_key\s*=\s*[a-zA-Z0-9/+=]{40}' .

# Private key headers
rg -n '-----BEGIN (RSA|DSA|EC|OPENSSH|PRIVATE) KEY-----' .

# High-entropy strings (too noisy for general use, skip unless targeted)
```

### Committed credential FILES

These should never be in a public repo regardless of content:

```bash
git ls-files | rg -i '(\.env$|\.env\.|token.*\.json$|credentials?.*\.json$|\.pem$|\.key$|id_rsa|service[_-]account.*\.json$)'
```

If any of these are tracked, they go into the MUST FIX bucket. Also check historical versions — files deleted from current tree may still exist in old commits:

```bash
git log --all --full-history --diff-filter=A --name-only | rg -i '(\.env$|credentials|\.pem$|token.*\.json)' | sort -u
```

---

## Personal Path Detection

```bash
# the user's home directory anywhere
rg -n '/home/alice' .

# Generic home directory references
rg -n '/home/[a-zA-Z]+/' .

# Tilde expansions that reference specific users
rg -n '~/Projects/' .
rg -n '~/\.config/' .  # often fine, flag for review
```

**Noise reduction:** paths in `node_modules/`, `.venv/`, `vendor/`, `target/`, `dist/` are usually build artifacts — exclude them:

```bash
rg -n '/home/alice' . \
  --glob '!node_modules' \
  --glob '!.venv' \
  --glob '!venv' \
  --glob '!vendor' \
  --glob '!target' \
  --glob '!dist' \
  --glob '!build'
```

---

## Personal URL / Infra Detection

```bash
# Cloudflare workers with personal subdomain
rg -n 'alice\.workers\.dev' .
rg -n '[a-z0-9-]+\.workers\.dev' .  # all CF worker URLs for review

# Personal identifiers — customize this list with your own names/handles
rg -n -i '(alice|<your-handle>)' .

# Localhost / personal infra
rg -n '127\.0\.0\.1' .
rg -n 'localhost:[0-9]+' .
rg -n ':5432' .  # postgres default port, often indicates hardcoded DB

# Private IP ranges (RFC 1918)
rg -n '\b192\.168\.[0-9]+\.[0-9]+\b' .
rg -n '\b10\.[0-9]+\.[0-9]+\.[0-9]+\b' .
rg -n '\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+\b' .
```

---

## Personal Identifier Detection

```bash
# Name + known variations
rg -n -i 'alice' .

# Email patterns — extract and review
rg -n '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' . | head -100

# GitHub usernames in code comments / URLs
rg -n 'github\.com/alice' .
```

**Judgment call:** the user's own github username in a URL is usually fine to keep (e.g., `github.com/alice/this-repo` in README). It's hardcoded personal references in code that matter (e.g., `user = "alice"` hardcoded in an auth check).

---

## Local-Only Docs Detection

```bash
git ls-files | rg '^\.claude/'
git ls-files | rg '^\.cursor/'
git ls-files | rg '^CLAUDE\.md$'
git ls-files | rg -i '(DEBUG_SESSION|SCRATCH|TODO|PLANNING|NOTES_LOCAL)\.md$'
git ls-files | rg '^\.aider\.'
```

These should be added to `.gitignore` AND removed from the index with `git rm --cached`.

---

## LICENSE Status

```bash
# Is there a LICENSE file?
ls LICENSE LICENSE.md LICENSE.txt COPYING 2>/dev/null

# What does README claim?
rg -n -i 'licen(s|c)e' README.md 2>/dev/null

# Mismatch check: README says MIT but no file
if ! ls LICENSE* COPYING 2>/dev/null; then
  if rg -q -i 'mit licen' README.md 2>/dev/null; then
    echo "FAIL: README claims MIT but no LICENSE file"
  fi
fi
```

If a LICENSE is missing on a fork: check the upstream's LICENSE and inherit it with proper attribution.

---

## Fork Provenance

```bash
# All remotes
git remote -v

# Look for an "upstream" remote
git remote -v | rg upstream

# Earliest commit — if it mentions "initial commit" but there's a bunch of history before your first commit, it's likely a fork
git log --reverse --format='%h %an %s' | head -5

# Check if current origin differs from your typical github user
git remote get-url origin
```

If upstream exists: preserve their LICENSE file verbatim, add attribution line to README, keep the `upstream` remote so you can pull future changes.

---

## Commit Author Inventory

```bash
git log --format='%ae' | sort -u
git log --format='%ce' | sort -u  # committer emails
```

If you find a personal email and want to publish under a different identity, use `git-filter-repo --mailmap` in Phase 5.

---

## Putting It Together

The triage report in Phase 3 should synthesize all of the above. Here's a one-shot script that runs everything and dumps results:

```bash
#!/bin/bash
set -e
OUT="${1:-./.publicize-scan}"
mkdir -p "$OUT"

# Secrets
if command -v gitleaks >/dev/null; then
  gitleaks detect --source=. --no-git --exit-code 0 --report-path="$OUT/gitleaks-current.json" 2>/dev/null
  gitleaks detect --source=. --exit-code 0 --report-path="$OUT/gitleaks-history.json" 2>/dev/null
else
  echo "gitleaks not installed — using regex fallback" > "$OUT/gitleaks-skipped.txt"
fi

# Credential files
git ls-files | rg -i '(\.env$|token.*\.json$|credential|\.pem$|\.key$)' > "$OUT/credential-files.txt" || true

# Paths
rg -n '/home/alice' . \
  --glob '!node_modules' --glob '!.venv' --glob '!venv' --glob '!vendor' \
  --glob '!target' --glob '!dist' --glob '!build' \
  > "$OUT/personal-paths.txt" 2>/dev/null || true

# URLs / infra
rg -n '(alice|\.workers\.dev|127\.0\.0\.1|localhost|:5432)' . \
  --glob '!node_modules' --glob '!.venv' --glob '!vendor' \
  > "$OUT/personal-urls.txt" 2>/dev/null || true

# Identifiers
rg -n -i 'alice' . \
  --glob '!node_modules' --glob '!.venv' --glob '!vendor' \
  > "$OUT/identifiers.txt" 2>/dev/null || true

# Local docs
git ls-files | rg '(\.claude/|\.cursor/|^CLAUDE\.md$|DEBUG_SESSION|\.aider)' > "$OUT/local-docs.txt" || true

# License & remotes
ls LICENSE* COPYING 2>/dev/null > "$OUT/license.txt" || echo "MISSING" > "$OUT/license.txt"
git remote -v > "$OUT/remotes.txt"
git log --format='%ae' | sort -u > "$OUT/authors.txt"

echo "Scan complete. Results in $OUT/"
ls -la "$OUT/"
```

Save that to `/tmp/publicize-scan.sh` and run it from the sandbox. It produces a directory of findings the triage step can read.
