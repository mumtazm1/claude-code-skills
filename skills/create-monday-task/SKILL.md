---
name: create-monday-task
description: Use when the user wants to create a task on a Monday.com board and says "create monday task", "add to monday", "new monday item", "log this on monday", or similar. Builds a parent item with short title, context notes, and actionable subitems, then shows a preview before creating anything. Writes notes in plain, specific prose (no corporate filler, no AI voice).
---

# Create Monday Task

## Overview

Create a Monday.com item with:
- A short title naming the deliverable
- A context note (single update, HTML) explaining what it is and why it matters
- Subitems that break down the actual work, each with its own one-sentence description

The skill shows a preview before calling any `create_item` tool. Nothing is written to Monday until the user confirms.

## Prerequisites

- A Monday.com MCP server configured for your workspace. The official one (`mondaydotcomorg/monday-api-mcp` or equivalent) exposes `create_item`, `create_update`, `all_monday_api`, and board-query tools. Whichever server you use, it must have write access.
- One config value: the board ID. Get it from the board URL (`https://yourorg.monday.com/boards/<BOARD_ID>`).

Set it once at the top of your project `CLAUDE.md`, or pass it via `$BOARD` on each invocation:

```
MONDAY_BOARD_ID: 1234567890
```

## Arguments

| Arg | Default | Options | Purpose |
|-----|---------|---------|---------|
| `$TASK` | (required) | Natural-language description | What the task is. The skill distills this into a short title. |
| `$BOARD` | from config | Board ID | Override the default board |
| `$GROUP` | inferred | Group name (matched against board's groups) | Which group/workstream the item belongs to |
| `$PRIORITY` | Medium | Matches against Priority column options | e.g. Critical, High, Medium, Low |
| `$STATUS` | Not Started | Matches against Status column options | e.g. Not Started, In Progress, Done, Stuck |

If `$GROUP`, `$PRIORITY`, or `$STATUS` aren't provided, the skill infers them from the task description.

---

## Task Title Format

Titles should name the deliverable, not describe the work. Think about what someone scanning the board should see.

**Good titles (name the deliverable):**
- "Yardi data transformation layer"
- "Employee onboarding data tables"
- "Hardware provisioning automation"
- "Cross-system reporting layer"

**Bad titles (too granular or too descriptive):**
- "Build dim_hardware from silver" (this is a subitem, not a task)
- "Debugged silver layer type casting errors" (past-tense work log, not a deliverable)
- "Fix Yardi join key and re-export" (subitem-level detail)

Rules:
- Keep it under 8 words when possible
- Name the overarching deliverable, not an individual model or step
- No em dashes. Use hyphens or semicolons.
- No filler: "implement", "leverage", "streamline", "facilitate"
- No people's names in titles
- Action verbs are fine but not required

---

## Task Notes (the item update)

After creating the item, add a single update with context about the task.

Monday.com updates use HTML, not markdown. Only these tags work:

`<b>`, `<i>`, `<u>`, `<br>`, `<ul><li>`, `<ol><li>`, `<a href="">`

### What the notes should cover

Write 1-3 paragraphs that answer: What is this? Why does it matter? What's the current state?

Write it as a first-person account. Don't use section headers like "Background" or "Details" unless they genuinely help. Most tasks just need a paragraph or two.

Do NOT include a "What's left" section. Subitems handle that.

### Writing Style

Write like you're leaving notes for yourself or a coworker. Short, factual, specific.

**Good:**
- "Came up in the 3/31 meeting. The vendor's dev needs CSV exports to manually clean and import."
- "459 of 1,531 assets already have the required field populated. That's enough to stand up the initial tables."
- "Both tasks are completely dependent on the upstream connection landing in the lakehouse."

**Bad:**
- "This task was identified during a strategic alignment session with key stakeholders."
- "This initiative aims to streamline the data integration pipeline."
- "Leveraging the gateway architecture to facilitate connectivity."

No em dashes. No corporate filler. No AI voice. Don't reference Claude, AI tooling, or `CLAUDE.md` in the notes. They're for the Monday.com reader, not the author.

These voice rules reflect the skill author's preferences. If your team's norms are different, adjust this section before using the skill at scale.

---

## Subitems

Every task should have subitems that break down the work. Subitems are the actionable steps; the parent is the deliverable they serve.

### Subitem titles

Descriptive enough to stand on their own. Past tense (work done) or present tense (work needed) both fine.

**Good:**
- "Investigated E3Replication gateway timeout; identified network access as root cause"
- "Build dim_employee from bronze layer"
- "Define PII masking and data exposure rules"
- "Reconcile with IT hardware audit results"

**Bad:**
- "Fix the thing"
- "Step 1"
- "Gateway" (too vague)

### Subitem descriptions

Every subitem gets a description via `create_update`. 1-2 sentences explaining the why or the specific ask. Don't just restate the title.

**Good:**
- "One row per employee. Orientation date is the key field, it's the trigger for the entire new-hire onboarding flow."
- "IT is auditing current assignments via Active Directory and Intune. Once that's available, merge it with what we derived from tickets."

**Bad:**
- "Build the dim_employee table." (restates the title)
- (no description at all)

---

## Execution Steps

### Step 1. Resolve board structure

Read the configured board ID. If none is set and `$BOARD` wasn't passed, stop and ask the user for one.

Query the board's structure via the Monday MCP. You need:
- The list of groups (id + title)
- The Status column's ID and its available labels
- The Priority column's ID and its available labels

Most Monday MCP servers expose a `all_monday_api` (GraphQL passthrough) tool. The query looks like:

```graphql
query ($boardId: [ID!]) {
  boards(ids: $boardId) {
    groups { id title }
    columns { id title type settings_str }
  }
}
```

Parse `settings_str` for Status and Priority columns to get the label → index mapping.

Cache the resolved IDs for this run. If the user invokes the skill again in the same session, the structure can be re-used without another query.

### Step 2. Parse the request

From `$TASK`, determine:
- A short title following the title rules above
- Which group it belongs to (match `$GROUP` to board groups case-insensitively; if not given, infer from context keywords)
- Priority (default Medium if not given or not inferrable)
- Status (default Not Started)
- The context for the notes
- Subitem list with descriptions

If inference is uncertain (e.g. group ambiguous), state your best guess in the preview and let the user correct.

### Step 3. Draft everything

Write:
- The parent item's notes in HTML (only the allowed tags)
- Each subitem's title
- Each subitem's description

### Step 4. Show the preview

Before calling any create tool, show exactly what will be created:

```
**Task preview:**

Board: {board_name}
Title: Employee onboarding data tables
Group: HR Hardware Automation
Priority: High
Status: Stuck

Notes:
> These are the gold tables that drive the entire automation workflow. One
> provides orientation dates (the trigger for new hire flows) and another
> has the hardware field that determines provisioning per role. Both depend
> on the upstream data landing in the lakehouse.

Subitems:
1. "Build dim_employee from bronze"
   > One row per employee. Orientation date is the key field, it's the
   > trigger for the entire new-hire onboarding flow.

2. "Build dim_position from bronze"
   > One row per position. The hardware field determines what gets
   > provisioned. Needs the upstream connection working first.
```

Render notes and subitem descriptions as readable prose. Don't show raw HTML.

Then ask: "Create this task?"

### Step 5. Create

Only after the user confirms:

1. Call `create_item` for the parent (board_id, group_id, item_name, column_values for status + priority)
2. Call `create_update` with the HTML notes on the parent
3. For each subitem: call `create_item` with the parent's item ID as `parent_item_id`
4. For each subitem: call `create_update` with its description
5. Return the Monday.com URL of the parent item

If any call fails, print the specific error and stop. Don't partially recover without the user saying so.

---

## Examples

### Example 1: Deliverable with subitems

User: `/create-monday-task $TASK="we need to build the transformation layer for the property system - joining bronze tables, handling PII, deciding silver vs gold"`

Preview:
```
Title: Property data transformation layer
Group: Enterprise Data Warehouse
Priority: Medium
Status: Not Started

Notes:
> The property system has 11 bronze tables. The transformation layer needs
> to join them, apply type casting and cleaning, and decide what gets
> exposed downstream. Silver may just be a PII-stripped version of bronze,
> or skip silver and go straight to gold.

Subitems:
1. "Define PII masking and exposure rules"
   > SSN, DOB, and contact info need clear rules before anything hits
   > silver or gold.

2. "Join bronze tables into unified person and property views"
   > TENANT, FAMILY, PROSPECT, PERSON all have person-level data at
   > different grains.

3. "Decide silver vs. straight-to-gold"
   > If silver is just bronze with PII removed it might be worth having
   > as a safe layer. Otherwise go straight to gold.

4. "Build and run transformation in Fabric"
   > Reads from bronze tables, writes to silver or gold.

5. "Validate output against bronze source counts"
   > Confirm no dropped or duplicated records through the joins.
```

### Example 2: Blocked task

User: `/create-monday-task $TASK="the provisioning automation can't start until the gold tables exist and the upstream system is working"`

Preview:
```
Title: Hardware provisioning automation
Group: HR Hardware Automation
Priority: High
Status: Stuck

Notes:
> This is the end-to-end automation that ties everything together. Watches
> for new rows in the onboarding tickets table, then fires a webhook to
> the automation layer. Specs are written but the build can't start until
> gold tables exist and upstream data is landing.

Subitems:
1. "Configure watcher on onboarding tickets"
   > Watches for new rows and fires a webhook to the automation layer.

2. "Build the automation flows"
   > 5 flows: new hire onboarding, orientation alert, termination, weekly
   > report, survey trigger.

3. "Test end-to-end with sample record"
   > Simulate a new hire and verify the full chain fires.
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Board ID not set | Stop, ask the user for one. Do not guess. |
| Group name doesn't match any board group | List the available groups and ask the user to pick. |
| Status or Priority label doesn't match | List available options, ask user to pick. |
| Monday MCP not available | Tell the user: "Install and configure a Monday.com MCP server first." |
| `create_item` returns an error | Print the exact error. Do not retry silently. |

---

## Context Management

- Board structure queries can be large (hundreds of columns on busy boards). If the main context is already heavy, delegate the board-structure query to a subagent and have it return only the resolved group/column IDs.
- After creating, note the Monday URL and suggest `/clear` if the session is getting long.
