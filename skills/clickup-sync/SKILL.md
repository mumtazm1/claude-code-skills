---
name: clickup-sync
description: Use when the user asks about their ClickUp tasks, pending items, recent task activity, or says "clickup sync", "what am I tagged in on clickup", "what's on my clickup", "check my clickup", or similar. Fetches everything the user is assigned to across all their ClickUp workspaces and returns a compact summary with statuses, due dates, priorities, and recent comments. Read-only.
---

# ClickUp Sync

## Overview

Show the user every ClickUp task assigned to them, across every workspace their API token has access to. Auto-discovers their user ID and workspaces from the token. The only thing the user has to configure is the token itself.

**Read-only.** The skill never creates, updates, deletes, or comments on anything in ClickUp. Only local output.

## Prerequisites

One environment variable:

```
export CLICKUP_API_TOKEN=pk_your_token_here
```

How to get a token: ClickUp → Settings → Apps → API Token → Generate. Paste it into your shell profile, a project `.env`, or a `direnv` file.

The skill ships with a helper script `clickup.py` in the same directory. It uses only the Python standard library, no pip install needed.

Reference to the helper in the instructions below is `<skill_dir>/clickup.py`. When invoking the skill, resolve `<skill_dir>` to the actual path the skill is installed at (usually `~/.claude/skills/clickup-sync/`).

## Arguments

| Arg | Default | Options | Purpose |
|-----|---------|---------|---------|
| `$SINCE` | `14d` | `7d`, `14d`, `30d`, `all`, `none` | Comment recency window. `none` = skip comments entirely for a faster run. |
| `$INCLUDE_CLOSED` | `false` | `true`, `false` | Include completed/closed tasks in the output |
| `$WORKSPACE` | `all` | `all`, or a specific workspace name/ID | Limit scan to one workspace |

---

## Execution Steps

### Step 1. Resolve the user

Run:

```bash
python3 <skill_dir>/clickup.py whoami
```

Prints a single integer (the user's ClickUp ID). Store as `USER_ID`.

If this command exits non-zero with an auth error, stop and tell the user: `CLICKUP_API_TOKEN is unset or invalid. Get a personal token from ClickUp → Settings → Apps → API Token.`

### Step 2. List workspaces

```bash
python3 <skill_dir>/clickup.py workspaces
```

Prints one line per workspace: `<id>\t<name>`. Store as `WORKSPACES`.

If the user passed `$WORKSPACE`, filter `WORKSPACES` to just that one (match by name substring or exact ID).

### Step 3. Fetch assigned tasks (subagent)

Delegate the task fetch to a subagent so raw API output stays out of main context.

**Subagent prompt template:**

```
You are a ClickUp data fetcher. Run the commands below, parse the output, and return only compact markdown. Do NOT return raw JSON.

READ-ONLY. Do not create, update, delete, or comment on anything.

For each of these workspaces:
{WORKSPACES_TSV}

Run in parallel (one Bash call per workspace):
python3 {SKILL_DIR}/clickup.py mytasks {workspace_id} --user-id {USER_ID}{INCLUDE_CLOSED_FLAG}

The command prints one task per line in the format:
<task_id> | <status> | <due_date> | <priority> | <list_name> | <task_name>

Return for each workspace that had tasks:

### {workspace_name}: {N} tasks
| task_id | status | due | priority | list | name |
|---------|--------|-----|----------|------|------|
| ... |

Omit workspaces with zero tasks.
```

`{INCLUDE_CLOSED_FLAG}` is `--include-closed` if `$INCLUDE_CLOSED=true`, else empty.

### Step 4. Fetch recent comments (optional)

Skip this step entirely if `$SINCE=none`.

Compute the cutoff date from `$SINCE`:
- `7d` → today minus 7 days
- `14d` → today minus 14 days
- `30d` → today minus 30 days
- `all` → no cutoff

Collect all `task_id` values from Step 3's tables. Spawn a second subagent:

**Subagent prompt template:**

```
For each task ID below, run in parallel:
python3 {SKILL_DIR}/clickup.py task {task_id} --no-fields

Task IDs:
{TASK_ID_LIST}

Parse the output. The comments section starts after a "-- Comments --" marker. Each comment has a date header like `[Feb 24, 2026] username:` followed by indented text.

Filter to comments on or after {CUTOFF_DATE}.

Return for each task that has qualifying comments:

#### {task_id}: {task_name}
- **{author}** ({date}): "{text, up to 500 chars}"
  - **{author}** ({date}) [reply]: "{text, up to 500 chars}"

Omit tasks with no recent comments. Do not include task metadata, just the comments.
```

### Step 5. Build the summary

Render to the user:

```
## ClickUp Sync ({today's date})

{Step 3 tables, one per workspace}

### Pending attention
{tasks where status is not complete AND (due_date is in the past OR due_date is within the next 7 days)}
- Format overdue dates with strikethrough: ~~Feb 12~~ overdue
- Format upcoming dates plain: Mar 6

### Recent activity
{Step 4 comment blocks, grouped by task}

### Totals
- {N} tasks assigned across {W} workspaces
- {M} overdue, {K} due within 7 days
- {C} tasks with comments since {cutoff}
```

Keep the output dense and scannable. No marketing filler. No "comprehensive summary" framing.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| `whoami` returns 401/403 | Token invalid. Print the setup instructions. Stop. |
| `workspaces` returns empty list | Print "No workspaces accessible with this token." Stop. |
| Any single workspace fetch fails | Note the failure in the summary ("workspace X: fetch failed"), continue with the rest. |
| Rate limit (429) | Wait 2 seconds, retry once. If still failing, note in the summary and continue. |
| Subagent returns garbled output | Fall back to running the relevant `clickup.py` command directly via Bash. |

---

## Context Management

- All ClickUp API calls happen inside subagents. Raw API responses never enter the main conversation.
- The main agent sees only: compact per-workspace tables and per-task comment blocks.
- After the summary, note the current context weight. If it's heavy, suggest `/clear`.

---

## Known Limitations

- **@mentions without assignment.** If someone tags you in a comment on a task you're not assigned to, this skill won't detect it. ClickUp's API has no search-by-mention endpoint. Workaround: maintain your own list of task IDs to watch and pass them to the helper script manually.
- **Closed tasks.** The filter `$INCLUDE_CLOSED=false` relies on ClickUp's API filter. Some closed tasks may still appear depending on how the status was configured on the workspace.
- **Huge assignment lists.** If you're assigned to 500+ tasks, the output will be long. Run with `$SINCE=none` and a specific `$WORKSPACE` filter to trim it down.

---

## Examples

```bash
# Default: all workspaces, comments from last 14 days
/clickup-sync

# Just a status check, no comments
/clickup-sync $SINCE="none"

# Focused on one workspace, last 7 days of comments
/clickup-sync $WORKSPACE="Acme" $SINCE="7d"

# Include closed tasks too
/clickup-sync $INCLUDE_CLOSED="true"
```
