#!/usr/bin/env python3
"""Create isolated, synthetic project material for regressions and blind handoff runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


FILES = {
    "README.md": """# Lantern Tasks

Lantern Tasks helps small volunteer teams manage equipment-return reminders.
The current release is a single-team pilot. People can create tasks, postpone a
reminder, and mark one task done. It does not support inviting other teams.

## Local use
Run `python3 src/api.py`. SQLite stores tasks; a separate worker consumes the
outbox. The worker uses UTC timestamps. A failed message retries at most twice.
Task completion and its outbox message must commit together.

## Project facts
The shipping service still runs commit `fixture-release-a`; the working tree
contains the next delay-rule change. See docs/product.md and ops/deploy.json.
""",
    "docs/product.md": """# Product decisions

Users are volunteer shift leads sharing equipment. A shift lead needs reminders
to reduce manual follow-up, but recipients must not receive late-night messages.
Every task belongs to one team. Team membership is checked before reads/writes.
Archived tasks cannot be postponed. The current default postponement is 24 hours.

## Planned, not implemented
Bulk completion was approved for a future release. It should complete up to 100
selected tasks, returning per-task failures. The current API only accepts one id.
Multiple teams and invitations remain open design questions; do not treat them
as released capabilities. Audit retention has not yet been decided.
""",
    "src/api.py": """from service import postpone, complete


def handle(method, path, payload, actor, db):
    if method == 'POST' and path == '/tasks/complete':
        # Deliberately single-item; batch is only in the product plan.
        return complete(db, payload['task_id'], actor['team_id'])
    if method == 'POST' and path == '/tasks/postpone':
        return postpone(db, payload['task_id'], actor['team_id'])
    return {'status': 404, 'error': 'unknown_route'}
""",
    "src/service.py": """from datetime import timedelta

POSTPONE_HOURS = 24


def owned_task(db, task_id, team_id):
    task = db.get_task(task_id)
    if task is None or task['team_id'] != team_id:
        return None  # Do not reveal another team's task existence.
    return task


def postpone(db, task_id, team_id):
    task = owned_task(db, task_id, team_id)
    if task is None:
        return {'status': 404}
    if task['archived']:
        return {'status': 409, 'error': 'archived'}
    due_at = task['due_at'] + timedelta(hours=POSTPONE_HOURS)
    with db.transaction():
        db.set_due(task_id, due_at)
        db.enqueue('reminder_rescheduled', task_id)
    return {'status': 200, 'due_at': str(due_at)}


def complete(db, task_id, team_id):
    task = owned_task(db, task_id, team_id)
    if task is None:
        return {'status': 404}
    with db.transaction():
        db.set_done(task_id, True)
        db.enqueue('task_completed', task_id)
    return {'status': 200}
""",
    "src/worker.py": """MAX_RETRIES = 2
QUIET_START_UTC = 22
QUIET_END_UTC = 7


def dispatch(job, clock, transport):
    hour = clock.hour
    if hour >= QUIET_START_UTC or hour < QUIET_END_UTC:
        return 'defer_until_07_utc'
    try:
        transport.send(job['body'])
    except TimeoutError:
        return 'retry' if job['attempt'] < MAX_RETRIES else 'dead_letter'
    return 'sent'
""",
    "db/001_init.sql": """CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    due_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE outbox (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0
);
""",
    "tests/test_rules.py": """import unittest
from types import SimpleNamespace
from src.worker import dispatch


class QuietHours(unittest.TestCase):
    def test_utc_quiet_hour(self):
        result = dispatch({}, SimpleNamespace(hour=23), None)
        self.assertEqual('defer_until_07_utc', result)

    def test_third_timeout_dead_letters(self):
        class Transport:
            def send(self, body):
                raise TimeoutError()
        result = dispatch({'body': 'return equipment', 'attempt': 2},
                          SimpleNamespace(hour=9), Transport())
        self.assertEqual('dead_letter', result)
""",
    "ops/deploy.json": json.dumps({"environment": "fixture-production", "commit": "fixture-release-a", "deployed_at": "2026-09-15T08:00:00Z", "verification": "health endpoint only; bulk API unverified", "previous_commit": "fixture-release-previous"}, indent=2) + "\n",
    "exports/shift-notes.md": "# Ignored but in scope\nWeekend reminders are currently the largest user complaint.\nThe next shift starts Monday at 07:00 UTC.\n",
    ".gitignore": "exports/\n.env\n.project-context/\n__pycache__/\n",
}

EXTERNAL = {
    "schema_version": 1,
    "source_id": "team-wiki",
    "run_id": "REPLACE_WITH_CURRENT_RUN",
    "scope_hash": "REPLACE_WITH_SCAN_SCOPE",
    "status": "complete",
    "mode": "full",
    "enumeration_complete": True,
    "permissions_verified": True,
    "next_cursor": None,
    "collected_at": "2026-09-16T10:00:00Z",
    "coverage": {"pages": 2, "scope": "configured public fixture pages; attachments: none"},
    "items": [
        {"id": "feature-plan", "title": "Future bulk operations", "locator": "https://example.org/lantern/feature-plan", "version": "2", "updated_at": "2026-09-16T08:00:00Z", "content": "Approved plan: bulk completion up to 100 tasks with per-task results. This is a plan, not a deployed feature. Multiple-team invitations are still undecided.\n"},
        {"id": "incident-17", "title": "Night reminders incident", "locator": "https://example.org/lantern/incidents/17", "version": "1", "updated_at": "2026-09-15T12:00:00Z", "content": "Observed incident: 4 delayed notifications in fixture-production between 06:55 and 07:10 UTC. The window includes fixture-release-previous and fixture-release-a. No proven causal attribution.\n"},
    ],
    "deleted_ids": [],
    "errors": [],
}


def write_fixture(root: Path, *, git: bool = False, large: bool = False) -> dict:
    project = root / "lantern"
    project.mkdir(parents=True, exist_ok=True)
    for name, content in FILES.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if large:
        # Unique line numbers and a distinct tail make suffix truncation observable.
        text = "".join(f"第 {i:06d} 条历史规则：完整保留该行及其跨行上下文。αβγ\n" for i in range(18000)) + "END_OF_FULL_HISTORY_18000\n"
        (project / "docs/full-history.txt").write_text(text, encoding="utf-8")
    (root / "external-full.json").write_text(json.dumps(EXTERNAL, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if git:
        def cmd(*args):
            subprocess.run(["git", "-C", str(project), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd("init", "-q")
        cmd("config", "user.name", "Fixture Author")
        cmd("config", "user.email", "fixture@example.org")
        cmd("add", ".")
        cmd("commit", "-qm", "synthetic fixture baseline")
        api = project / "src/api.py"
        api.write_text(api.read_text() + "\n# STAGED_FIXTURE_CHANGE\n")
        cmd("add", "src/api.py")
        api.write_text(api.read_text() + "# UNSTAGED_FIXTURE_CHANGE\n")
        (project / "docs/new-work.md").write_text("Untracked proposal: configurable postponement. Not yet approved.\n")
    expected = {
        "project": str(project),
        "files": {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest() for p in project.rglob("*") if p.is_file() and ".git" not in p.parts},
        "expected_facts": [
            "single-team pilot; multiple-team invitations undecided",
            "current API accepts one task id; planned batch limit is 100",
            "cross-team task access returns 404 without revealing existence",
            "archived task postponement returns 409",
            "default postponement 24 hours; update and outbox commit together",
            "quiet hours 22:00 to 07:00 UTC; at most two retries",
            "deployment health-only evidence does not prove feature acceptance",
            "incident crosses two deployment versions; cause unproven",
            "gitignored shift-notes remains project source material",
        ],
    }
    (root / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--git", action="store_true")
    parser.add_argument("--large", action="store_true")
    args = parser.parse_args()
    print(json.dumps(write_fixture(args.output.resolve(), git=args.git, large=args.large), ensure_ascii=False, indent=2))
