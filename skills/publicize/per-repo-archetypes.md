# Per-Repo Archetypes

Strategies by repo shape. Most of the time, the hard part of publicizing is picking the right approach for the repo you're looking at. The archetypes below help match a repo to a playbook.

---

## Archetype 1: Ship-Ready

**Shape:** Mostly standalone code, `.env` already gitignored, no committed secrets, maybe missing a LICENSE or has a couple of README rough edges.

**Typical work:** 30 minutes.

**Phases:** 1 (sandbox) → 2 (scan) → 3 (triage — should be empty or tiny) → 6 (verify) → 7 (publish). Skip 4 (no refactor needed) and 5 (no history rewrite needed, unless scan surfaces historical issues).

**Watch out for:**
- LICENSE file missing even though README claims one → add the LICENSE file matching what README says
- Hardcoded resource IDs in infra config (wrangler.toml, terraform) that are personal-specific → either abstract or document "change this to your own"
- README assumes you already have context → rewrite the first paragraph for a stranger

**Example shape:** a Cloudflare Worker OAuth proxy. Already does the right thing with secrets (CF secret manager). Just needs wrangler.toml KV ID noted as "replace with yours" and README setup steps for the OAuth provider side.

---

## Archetype 2: Needs Config Abstraction

**Shape:** Code works but hardcodes values that should be config: voice IDs, user names, default directories, chosen model names, file paths. No committed secrets, but the hardcoded values break for any other user.

**Typical work:** half a day to a day.

**Phases:** All 8. Phase 4 (refactor) is the bulk.

**Watch out for:**
- The refactor can cascade: you extract one config value, realize three more should come with it
- After refactor, the private repo MUST still work — don't leave the private copy half-configured
- `.env.example` must list everything the code reads; missing a key means public users hit runtime errors

**Example shape:** a wake-word daemon that hardcodes a specific ElevenLabs voice ID and a specific agent name. Refactor: move both to env vars with sensible defaults, document in README what they mean.

---

## Archetype 3: Fork With Attribution

**Shape:** Originally cloned from someone else's public repo, substantially modified. Has an `upstream` remote (or should). Licensing and credit matter.

**Typical work:** same as whatever archetype applies to the code itself, plus attribution work.

**Rules:**
- **Preserve the upstream LICENSE file verbatim.** Don't replace it. If you want to add your own copyright line, do it in addition.
- **Credit the upstream** in README first paragraph: "Forked from [upstream](url). Adds: [your changes]."
- **Keep the `upstream` remote** configured so you can pull future upstream changes.
- **If you're publishing under a new name**, that's fine — the license allows it (assuming it's MIT/Apache/BSD-ish). Put the rename in context in the README.
- **GPL/AGPL forks** need extra care. Get the user's explicit decision on whether they want to publish (GPL derivatives must stay GPL).

**Example shape:** a transcription app forked from an upstream project. Already went through a public release cycle but has drifted back (CLAUDE.md and editor configs got re-committed). Re-gitignore `.claude/` and `.cursor/`, `git rm --cached` the tracked copies, add the LICENSE the README claims, restore upstream attribution.

---

## Archetype 4: Personal Documentation Archive

**Shape:** Mostly scripts, configs, and docs — not a running application. Things like dotfiles, system-config, fix scripts, personal wikis.

**Typical work:** an hour. Most of the work is README framing, not code.

**Phases:** 1, 2, 3, 7. Skip 4 if there's nothing to abstract. Skip 5 if history is clean.

**Watch out for:**
- Niche audience — market it accurately. "My dotfiles" competes with thousands of other dotfiles repos. "Fix scripts for [specific hardware] on [specific OS] with [specific bugs]" has a real, findable audience.
- Contains personal debug logs, crash reports, machine UUIDs → those go into the SHOULD REMOVE bucket
- If it's actually useful to others, write the README for them, not as a personal journal

**Example shape:** a collection of fix scripts for a specific laptop model on a specific Linux distro. Rebrand from `system-config` to something like `<model>-<distro>-fixkit`. Lead with the hardware model and the specific bugs the scripts fix. List symptoms someone might google. Keep personal crash logs gitignored.

---

## Archetype 5: Heavy Personal Infra

**Shape:** Code depends on services only the user has — personal postgres, personal Cloudflare workers, MCP servers, specific API accounts. A public clone can't run without major replumbing.

**Typical work:** multi-day refactor OR decision to not publicize.

**Decision point:** before starting work, ask: "Can I reasonably decouple this from my personal infra, or would a user need to set up an identical stack?" If the answer is "identical stack," it's probably not worth publicizing as a runnable app — consider publishing a DESIGN/architecture writeup instead, or carving out a standalone piece.

**If you do publicize:**
- Phase 4 becomes the entire project
- Every personal service dependency needs abstraction: config for connection strings, feature flags for optional integrations, documented alternatives for required services
- README's "Setup Required" section is crucial — be honest about the complexity
- Consider whether a public user would get value from the repo even if they can't run it (e.g., they can read the code for patterns)

**Example shape:** a meeting-transcription desktop app that bundles Electron + FastAPI + Whisper + pyannote + Google Calendar. Calendar names are hardcoded to the author's specific accounts. Refactor would need: calendar auto-discovery, credential manager abstraction, removing hardcoded workspace refs. Worth doing long-term for the resume signal, but it's a weekend project, not 30 minutes.

---

## Picking the First Canary

Always start with the **Ship-Ready** archetype that has the highest signal/effort ratio. Don't start with a Needs-Config-Abstraction or Fork repo for the first run — those have more moving parts, and the canary's job is to shake out the skill itself, not the refactor complexity.

Once the first ship-ready repo is live and nothing exploded, confidence goes up and the next ones feel less daunting.
