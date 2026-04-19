#!/usr/bin/env python3
"""Compact ClickUp CLI for the clickup-sync skill.

Reads the token from CLICKUP_API_TOKEN. Uses only the Python standard library.

Subcommands:
  whoami             Print the authenticated user's ClickUp ID.
  workspaces         Print each workspace (team) the token can access.
  mytasks <team_id>  Print one row per task assigned to a given user in a workspace.
  task <task_id>     Print full details for one task, including custom fields and comments.
  list <list_id>     Print a compact row per task in a specific list.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.clickup.com/api/v2"
DESC_TRUNCATE = 500


def get_token():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        print("Error: CLICKUP_API_TOKEN env var not set.", file=sys.stderr)
        print("Get a personal token at ClickUp -> Settings -> Apps -> API Token.", file=sys.stderr)
        print("Then: export CLICKUP_API_TOKEN=pk_your_token_here", file=sys.stderr)
        sys.exit(1)
    return token


def api_get(path, params=None):
    token = get_token()
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"Authorization": token, "Content-Type": "application/json"})
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code} on {path}: {body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def get_user():
    return api_get("/user").get("user", {})


def get_teams():
    return api_get("/team").get("teams", [])


def get_task(task_id):
    return api_get(f"/task/{task_id}", {"custom_fields": "true"})


def get_comments(task_id):
    return api_get(f"/task/{task_id}/comment").get("comments", [])


def get_thread_replies(comment_id):
    return api_get(f"/comment/{comment_id}/reply").get("comments", [])


def get_list_tasks(list_id, page=0, include_closed=False, assignee=None):
    params = {"page": page, "include_closed": "true" if include_closed else "false"}
    if assignee:
        params["assignees[]"] = assignee
    return api_get(f"/list/{list_id}/task", params)


def get_team_tasks(team_id, page=0, include_closed=False, assignee=None):
    """Get Filtered Team Tasks: workspace-wide task query with optional assignee filter."""
    params = {"page": page, "include_closed": "true" if include_closed else "false"}
    if assignee:
        params["assignees[]"] = str(assignee)
    return api_get(f"/team/{team_id}/task", params)


def fmt_date(ts_ms):
    if not ts_ms:
        return "(none)"
    try:
        dt = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError, OSError):
        return str(ts_ms)


def fmt_custom_field(field):
    name = field.get("name", "?")
    ftype = field.get("type", "")
    value = field.get("value")

    if value is None or value == "" or value == []:
        return None

    if ftype in ("text", "short_text", "url", "email", "phone"):
        display = str(value)
    elif ftype == "date":
        display = fmt_date(value)
    elif ftype == "dropdown":
        options = field.get("type_config", {}).get("options", [])
        id_map = {o.get("id", ""): o.get("name", "?") for o in options}
        if str(value) in id_map:
            display = id_map[str(value)]
        else:
            try:
                display = options[int(value)].get("name", str(value))
            except (IndexError, ValueError, TypeError):
                display = str(value)
    elif ftype == "labels":
        if isinstance(value, list):
            options = field.get("type_config", {}).get("options", [])
            opt_map = {o.get("id", ""): o.get("label", o.get("name", "?")) for o in options}
            display = ", ".join(opt_map.get(str(v), str(v)) for v in value)
        else:
            display = str(value)
    elif ftype == "users":
        if isinstance(value, list):
            display = ", ".join(u.get("username") or u.get("email", "?") for u in value)
        else:
            display = str(value)
    elif ftype in ("number", "rating"):
        display = str(value)
    elif ftype == "currency":
        display = f"${value}"
    elif ftype == "checkbox":
        display = "Yes" if value else "No"
    elif isinstance(value, (dict, list)):
        display = json.dumps(value)[:120]
    else:
        display = str(value)[:200]

    return f"{name}: {display}"


def fmt_comment_text(comment):
    text = comment.get("comment_text", "")
    if text:
        return text.strip()
    blocks = comment.get("comment", [])
    parts = [b.get("text", "") for b in blocks if b.get("text")]
    return " ".join(parts).strip()


def fmt_task(task, include_fields=True, full_desc=False):
    lines = []
    name = task.get("name", "?")
    task_id = task.get("id", "?")
    url = task.get("url", f"https://app.clickup.com/t/{task_id}")
    status = task.get("status", {}).get("status", "(none)")
    assignees = task.get("assignees", [])
    assignee_names = ", ".join(a.get("username") or a.get("email", "?") for a in assignees) or "(none)"
    priority = (task.get("priority") or {}).get("priority", "(none)")
    due = fmt_date(task.get("due_date"))
    tags = ", ".join(t.get("name", "") for t in task.get("tags", [])) or "(none)"
    created = fmt_date(task.get("date_created"))
    updated = fmt_date(task.get("date_updated"))
    list_name = task.get("list", {}).get("name", "?")

    lines += [
        f"== {name} ({task_id}) ==",
        f"URL:        {url}",
        f"List:       {list_name}",
        f"Status:     {status}",
        f"Assignees:  {assignee_names}",
        f"Priority:   {priority}",
        f"Due:        {due}",
        f"Tags:       {tags}",
        f"Created:    {created}",
        f"Updated:    {updated}",
    ]

    desc = (task.get("description") or "").strip()
    if desc:
        lines += ["", "-- Description --"]
        if not full_desc and len(desc) > DESC_TRUNCATE:
            lines.append(desc[:DESC_TRUNCATE] + f"... [{len(desc) - DESC_TRUNCATE} chars truncated, use --full-desc]")
        else:
            lines.append(desc)

    if include_fields:
        custom_fields = task.get("custom_fields", [])
        rendered = [r for r in (fmt_custom_field(f) for f in custom_fields) if r is not None]
        if rendered:
            lines += ["", f"-- Custom Fields ({len(rendered)}) --"]
            lines += rendered

    return "\n".join(lines)


def fmt_task_row(task):
    task_id = task.get("id", "?")
    status = task.get("status", {}).get("status", "")
    name = task.get("name", "?")
    due = fmt_date(task.get("due_date")) if task.get("due_date") else "-"
    if len(name) > 50:
        name = name[:47] + "..."
    return f"{task_id:<12} | {status:<20} | {name:<50} | {due}"


def fmt_mytask_row(task):
    """Row format for the `mytasks` command. Pipe-delimited, easy for a subagent to parse."""
    task_id = task.get("id", "?")
    status = task.get("status", {}).get("status", "")
    priority = (task.get("priority") or {}).get("priority", "none")
    due = fmt_date(task.get("due_date")) if task.get("due_date") else "none"
    list_name = task.get("list", {}).get("name", "?")
    name = task.get("name", "?").replace("|", "/")
    return f"{task_id} | {status} | {due} | {priority} | {list_name} | {name}"


def print_comments(comments):
    print(f"\n-- Comments ({len(comments)}) --")
    for c in comments:
        author = (c.get("user") or {}).get("username") or (c.get("user") or {}).get("email", "?")
        date = fmt_date(c.get("date"))
        text = fmt_comment_text(c)
        print(f"\n[{date}] {author}:")
        for line in text.split("\n"):
            print(f"  {line}")

        # Always fetch replies -- ClickUp often reports replies_count=0
        # even when threaded replies exist (known API quirk).
        replies = get_thread_replies(c["id"])
        if replies:
            for r in replies:
                r_author = (r.get("user") or {}).get("username") or (r.get("user") or {}).get("email", "?")
                r_date = fmt_date(r.get("date"))
                r_text = fmt_comment_text(r)
                print(f"    [{r_date}] {r_author}:")
                for line in r_text.split("\n"):
                    print(f"      {line}")


def cmd_whoami(args):
    user = get_user()
    user_id = user.get("id")
    if not user_id:
        print("Error: could not resolve user ID from /user response.", file=sys.stderr)
        sys.exit(1)
    if args.verbose:
        username = user.get("username", "?")
        email = user.get("email", "?")
        print(f"{user_id}\t{username}\t{email}")
    else:
        print(user_id)


def cmd_workspaces(args):
    teams = get_teams()
    if not teams:
        print("No workspaces accessible with this token.", file=sys.stderr)
        sys.exit(1)
    for t in teams:
        tid = t.get("id", "?")
        name = t.get("name", "?")
        print(f"{tid}\t{name}")


def cmd_mytasks(args):
    team_id = args.team_id
    user_id = args.user_id
    include_closed = args.include_closed
    limit = args.limit

    all_tasks = []
    page = 0
    while len(all_tasks) < limit:
        data = get_team_tasks(team_id, page=page, include_closed=include_closed, assignee=user_id)
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        if len(tasks) < 100:
            break
        page += 1

    all_tasks = all_tasks[:limit]

    for t in all_tasks:
        print(fmt_mytask_row(t))


def cmd_task(args):
    task_id = args.task_id
    m = re.search(r"/t/([a-z0-9]+)", task_id)
    if m:
        task_id = m.group(1)

    task = get_task(task_id)
    print(fmt_task(task, include_fields=not args.no_fields, full_desc=args.full_desc))

    if not args.no_comments:
        comments = get_comments(task_id)
        if comments:
            print_comments(comments)
        else:
            print("\n-- Comments (0) --")


def cmd_list(args):
    list_id = args.list_id
    limit = args.limit
    status_filter = args.status.lower() if args.status else None
    assignee = args.assignee if hasattr(args, "assignee") else None

    all_tasks = []
    page = 0
    while len(all_tasks) < limit:
        data = get_list_tasks(list_id, page=page, include_closed=args.include_closed, assignee=assignee)
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        if len(tasks) < 100:
            break
        page += 1

    all_tasks = all_tasks[:limit]

    if status_filter:
        all_tasks = [t for t in all_tasks if status_filter in t.get("status", {}).get("status", "").lower()]

    list_name = all_tasks[0].get("list", {}).get("name", list_id) if all_tasks else list_id
    print(f"== {list_name} ({list_id}) - {len(all_tasks)} tasks ==\n")
    print(f"{'ID':<12} | {'STATUS':<20} | {'NAME':<50} | DUE")
    print("-" * 93)
    for t in all_tasks:
        print(fmt_task_row(t))


def main():
    parser = argparse.ArgumentParser(description="Compact ClickUp CLI for the clickup-sync skill")
    sub = parser.add_subparsers(dest="command")

    p_whoami = sub.add_parser("whoami", help="Print authenticated user's ClickUp ID")
    p_whoami.add_argument("--verbose", action="store_true", help="Also print username and email")

    sub.add_parser("workspaces", help="Print workspaces (teams) accessible with this token")

    p_my = sub.add_parser("mytasks", help="Print tasks assigned to a user in a workspace")
    p_my.add_argument("team_id", help="Workspace (team) ID")
    p_my.add_argument("--user-id", required=True, help="ClickUp user ID to filter assignees by")
    p_my.add_argument("--include-closed", action="store_true", help="Include closed tasks")
    p_my.add_argument("--limit", type=int, default=500, help="Max tasks to return (default: 500)")

    p_task = sub.add_parser("task", help="Show full details for one task")
    p_task.add_argument("task_id", help="Task ID or full URL")
    p_task.add_argument("--no-comments", action="store_true", help="Skip comments")
    p_task.add_argument("--no-fields", action="store_true", help="Skip custom fields")
    p_task.add_argument("--full-desc", action="store_true", help="Show full description (not truncated)")

    p_list = sub.add_parser("list", help="Show tasks in a specific list")
    p_list.add_argument("list_id", help="ClickUp list ID")
    p_list.add_argument("--status", help="Filter by status (partial match, case-insensitive)")
    p_list.add_argument("--limit", type=int, default=50, help="Max tasks to return (default: 50)")
    p_list.add_argument("--include-closed", action="store_true", help="Include closed/completed tasks")
    p_list.add_argument("--assignee", help="Filter by ClickUp user ID")

    args = parser.parse_args()

    if args.command == "whoami":
        cmd_whoami(args)
    elif args.command == "workspaces":
        cmd_workspaces(args)
    elif args.command == "mytasks":
        cmd_mytasks(args)
    elif args.command == "task":
        cmd_task(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
