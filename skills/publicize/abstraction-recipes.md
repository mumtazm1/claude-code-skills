# Abstraction Recipes

Phase 4 patterns for pushing hardcoded personal values into gitignored config. Organized by language.

## The Pattern (language-agnostic)

1. Identify the hardcoded value (`.publicize-findings.md` from Phase 2 has them)
2. Introduce a config source (env var, local config file, whatever's idiomatic)
3. Replace the hardcoded literal with a read from that source
4. Add the source's real file to `.gitignore`
5. Commit a `.example` template showing the shape without real values
6. Document the setup in README

**The `.example` file is the key artifact.** It's what public users clone; it tells them "here's what you need to provide."

---

## Python

### Recipe: `.env` + python-dotenv

```python
# config.py (new file, or extend existing)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

POSTGRES_URL = os.environ["POSTGRES_URL"]
API_KEY = os.environ["OPENAI_API_KEY"]
WORKER_URL = os.getenv("WORKER_URL", "https://example.workers.dev")  # with default
```

Before:
```python
db = psycopg2.connect("postgresql://dbuser:hunter2@localhost:5432/myapp_dev")
```

After:
```python
from config import POSTGRES_URL
db = psycopg2.connect(POSTGRES_URL)
```

`.env.example`:
```
# Required
POSTGRES_URL=postgresql://user:password@host:5432/dbname
OPENAI_API_KEY=sk-...

# Optional (with defaults)
# WORKER_URL=https://your-worker.workers.dev
```

`.gitignore`:
```
.env
```

### Recipe: paths via env var

Before:
```python
TOOL_BIN = "/home/alice/projects/myapp/.venv/bin/mytool"
```

After:
```python
import os
TOOL_BIN = os.environ.get("TOOL_BIN", "mytool")  # default: assume it's in PATH
```

Document in README: "Set `TOOL_BIN` if your executable isn't in PATH."

---

## JavaScript / TypeScript

### Recipe: `.env` + dotenv / process.env

```ts
// config.ts
import 'dotenv/config';

export const WORKER_URL = process.env.WORKER_URL!;
export const KV_NAMESPACE_ID = process.env.KV_NAMESPACE_ID!;
```

For Cloudflare Workers, use `wrangler.toml` variables and secrets:

```toml
# wrangler.toml
name = "your-worker-name"
main = "src/index.ts"

[[kv_namespaces]]
binding = "TOKENS"
id = "REPLACE_WITH_YOUR_KV_ID"

[vars]
CALLBACK_URL = "https://your-worker.workers.dev/callback"
```

Commit `wrangler.toml.example` with placeholders, gitignore the real `wrangler.toml` if it contains personal IDs — OR commit it with placeholder IDs and document what to change.

For secrets, use `wrangler secret put KEY` — never commit secrets to `wrangler.toml`.

---

## Shell Scripts

### Recipe: source a local config file

Before:
```bash
#!/bin/bash
DEPLOY_DIR="/home/alice/Projects/myapp"
S3_BUCKET="alice-backups"
```

After:
```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.local.sh" 2>/dev/null || {
  echo "error: config.local.sh not found. Copy config.example.sh and fill it in."
  exit 1
}

# Now DEPLOY_DIR and S3_BUCKET are set from config.local.sh
```

`config.example.sh`:
```bash
#!/bin/bash
DEPLOY_DIR="/path/to/your/app"
S3_BUCKET="your-backup-bucket"
```

`.gitignore`:
```
config.local.sh
```

---

## Rust

### Recipe: env vars via std::env or figment/config crate

```rust
// src/config.rs
use std::env;

pub struct Config {
    pub api_key: String,
    pub worker_url: String,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            api_key: env::var("API_KEY").expect("API_KEY must be set"),
            worker_url: env::var("WORKER_URL").unwrap_or_else(|_| "https://example.com".into()),
        }
    }
}
```

For more structured config, use the `config` crate with `config.toml` + `config.local.toml` override.

---

## Terraform / Wrangler / Infra-as-code

**Don't commit real resource IDs, account numbers, or bucket names.** Use variables:

```hcl
variable "aws_account_id" {
  type        = string
  description = "Your AWS account ID"
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.aws_account_id}-backups"
}
```

Commit `terraform.tfvars.example`, gitignore the real `terraform.tfvars`.

---

## The README "Setup Required" Section

Every public repo should document what the user needs to provide. Use this template:

```markdown
## Setup

1. Clone this repo
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Fill in the values:
   - `POSTGRES_URL` — your postgres connection string
   - `API_KEY` — get one at [provider URL]
   - `WORKER_URL` — (optional) defaults to [default]
4. Install dependencies: `<command>`
5. Run: `<command>`

## What you need

- <prerequisite 1>
- <prerequisite 2>
```

For heavy-infra repos (multiple services, private APIs, specific databases), add a "Not a plug-and-play setup" note up front so readers know what they're signing up for.

---

## Refactor Verification Checklist

After each refactor commit:

- [ ] Did the private repo still build/run with the refactor? (Run it, don't just trust it.)
- [ ] Does `.env` / config file exist locally with real values?
- [ ] Is `.env` in `.gitignore`?
- [ ] Is `.env.example` committed with placeholder values?
- [ ] Does `.env.example` have ALL keys the code reads?
- [ ] If a public user followed the README setup, could they fill in `.env` without needing to read your code?

If any answer is "no" or "not sure," you're not done with that refactor. Don't move on.
