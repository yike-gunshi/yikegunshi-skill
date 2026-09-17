#!/usr/bin/env python3
"""Black-box regressions for the documented project-context CLI contract.

Every project, git repository, external page and credential here is synthetic.
Run: python3 -m unittest discover -s docs/project-context-build/evals -p test_context.py -v
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from make_fixture import EXTERNAL, write_fixture


REPOSITORY = Path(__file__).resolve().parents[3]
CLI = REPOSITORY / "skills/project-context/scripts/context.py"


class ContextRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="project-context-regression-")
        self.root = Path(self.temp.name)
        self.expected = write_fixture(self.root, git=True)
        self.project = Path(self.expected["project"])
        self.state = self.project / ".project-context"
        self.cli("init", "--project", self.project, "--state", self.state, "--name", "Lantern fixture")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, command, *args, success=True):
        invocation = [sys.executable, str(CLI), command]
        if command != "init":
            invocation += ["--state", str(self.state)]
        invocation += [str(arg) for arg in args]
        result = subprocess.run(invocation, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if success:
            self.assertEqual(result.returncode, 0, f"{invocation}\n{result.stdout}\n{result.stderr}")
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                self.fail(f"CLI did not return JSON: {result.stdout}\n{result.stderr}")
        self.assertNotEqual(result.returncode, 0, f"invalid input unexpectedly accepted: {invocation}\n{result.stdout}")
        return result

    def scan(self):
        self.scan_result = self.cli("scan")
        self.manifest_path = Path(self.scan_result["manifest_path"])
        self.manifest = json.loads(self.manifest_path.read_text())
        return self.manifest

    def current(self):
        self.manifest = json.loads(self.manifest_path.read_text())
        return self.manifest

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def configure_external(self):
        path = self.state / "config.json"
        config = json.loads(path.read_text())
        config["sources"] = [{"id": "team-wiki", "kind": "feishu", "label": "Synthetic public wiki", "scope": {"root": "fixture-root", "attachments": True}}]
        path.write_text(json.dumps(config, indent=2) + "\n")

    def envelope(self, **overrides):
        value = deepcopy(EXTERNAL)
        value["run_id"] = self.scan_result["run_id"]
        value["scope_hash"] = self.scan_result["source_scopes"]["team-wiki"]
        value.update(overrides)
        return value

    def ingest(self, value, success=True):
        result = self.cli("ingest", "--input", self.write_json("envelope.json", value), success=success)
        self.current()
        return result

    def cover(self):
        current = self.current()
        covers = {key: value["fingerprint"] for key, value in current["items"].items()}
        # These minimal synthetic explanations exercise coverage mechanics only;
        # semantic explanation quality is independently scored in behavior evals.
        notes = {"schema_version": 1, "run_id": current["run_id"], "sections": [
            {"id": "product", "title": "Product", "category": "product", "content": "Fixture product explanation; see source materials.", "covers": covers},
            {"id": "technical", "title": "Technical", "category": "technical", "content": "Fixture technical flow; source references are version-bound.", "covers": covers},
            {"id": "state", "title": "State", "category": "state", "content": "Local changes are distinct from deployment evidence.", "covers": covers},
            {"id": "runtime", "title": "Runtime", "category": "runtime", "content": "Only supplied fixture deployment evidence is available.", "covers": {}},
        ], "deleted_ids": []}
        self.cli("note", "--input", self.write_json("notes.json", notes))
        return self.current()

    def object_text(self, key):
        item = self.current()["items"][key]
        return (self.state / item["object"]).read_text(encoding="utf-8")

    def imported_core(self):
        spec = importlib.util.spec_from_file_location("fixture_context_core", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def accept_scan_result(self, result):
        self.scan_result = result
        self.manifest_path = Path(result["manifest_path"])
        return self.current()

    def test_large_full_text_gitignored_and_no_recursive_state(self):
        large = "".join(f"Rule {i:06d}: 完整内容 αβγ\n" for i in range(60000)) + "UNIQUE_LAST_LINE_60000\n"
        (self.project / "docs/huge.txt").write_text(large, encoding="utf-8")
        manifest = self.scan()
        self.assertIn("local:exports/shift-notes.md", manifest["items"])
        self.assertFalse(any(".project-context/" in key or "/.git/" in key for key in manifest["items"]))
        self.assertEqual(self.object_text("local:docs/huge.txt"), large)
        self.cover()
        result = self.cli("build")
        output = Path(result["document"]).read_text(encoding="utf-8")
        self.assertIn(large, output)
        self.assertIn((self.project / "exports/shift-notes.md").read_text(), output)

    def test_actual_staged_unstaged_and_untracked_working_tree(self):
        manifest = self.scan()
        api = self.object_text("local:src/api.py")
        self.assertIn("STAGED_FIXTURE_CHANGE", api)
        self.assertIn("UNSTAGED_FIXTURE_CHANGE", api)
        self.assertIn("local:docs/new-work.md", manifest["items"])
        workspace = json.dumps(manifest["workspace"])
        self.assertIn("src/api.py", workspace)
        self.assertIn("docs/new-work.md", workspace)
        self.assertTrue("MM" in workspace or ("staged" in workspace and "unstaged" in workspace), workspace)

    def test_rename_delete_and_invalidated_notes(self):
        self.scan()
        self.cover()
        self.assertEqual(self.cli("build")["status"], "complete")
        (self.project / "src/api.py").rename(self.project / "src/routes.py")
        (self.project / "docs/new-work.md").unlink()
        manifest = self.scan()
        self.assertNotIn("local:src/api.py", manifest["items"])
        self.assertNotIn("local:docs/new-work.md", manifest["items"])
        self.assertIn("local:src/routes.py", manifest["items"])
        self.assertIn("local:src/api.py", manifest["changes"]["deleted"])
        self.assertIn("local:src/routes.py", manifest["changes"]["added"])
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_modified_file_invalidates_old_note(self):
        self.scan()
        self.cover()
        self.assertEqual(self.cli("build")["status"], "complete")
        with (self.project / "src/worker.py").open("a") as stream:
            stream.write("\nNEW_WORKER_POLICY = 'pending'\n")
        self.scan()
        result = self.cli("build")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["gaps"])

    def test_added_source_requires_new_explanation(self):
        self.scan()
        self.cover()
        self.assertEqual(self.cli("build")["status"], "complete")
        (self.project / "docs/brand-new.md").write_text("New source requires explanation, not silent carry-over.\n")
        self.scan()
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_note_deletion_invalidates_required_category(self):
        self.scan()
        self.cover()
        self.assertEqual(self.cli("build")["status"], "complete")
        payload = {"schema_version": 1, "run_id": self.manifest["run_id"], "sections": [], "deleted_ids": ["technical"]}
        self.cli("note", "--input", self.write_json("delete-note.json", payload))
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_old_run_note_rejected_without_changing_current(self):
        self.scan()
        old = self.manifest["run_id"]
        self.scan()
        payload = {"schema_version": 1, "run_id": old, "sections": [], "deleted_ids": ["technical"]}
        before = self.manifest_path.read_bytes()
        self.cli("note", "--input", self.write_json("old-note.json", payload), success=False)
        self.assertEqual(before, self.manifest_path.read_bytes())

    def test_brief_additive_and_does_not_persist_to_plain_export(self):
        self.scan()
        self.cover()
        brief = self.root / "brief.md"
        brief.write_text("BRIEF_ONLY_COLLAB_729: Discuss invitations; this is not an implemented capability.\n")
        with_brief = self.cli("build", "--brief", brief)
        topic = Path(with_brief["document"]).read_text()
        plain = self.cli("build")
        plain_text = Path(plain["document"]).read_text()
        self.assertIn("BRIEF_ONLY_COLLAB_729", topic)
        self.assertNotIn("BRIEF_ONLY_COLLAB_729", plain_text)
        self.assertNotEqual(with_brief["document"], plain["document"])
        for key in self.manifest["items"]:
            body = self.object_text(key)
            self.assertIn(body, topic, key)
            self.assertIn(body, plain_text, key)

    def test_partial_source_keeps_unseen_old_objects(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.scan()
        one = deepcopy(EXTERNAL["items"][0])
        one["content"] += "New revision from page one.\n"
        self.ingest(self.envelope(status="partial", enumeration_complete=False, items=[one], next_cursor="page-2", errors=["fixture page 2 timeout"]))
        self.assertIn("team-wiki:incident-17", self.current()["items"])
        self.assertIn("New revision", self.object_text("team-wiki:feature-plan"))
        self.cover()
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_permission_failure_does_not_delete_old_objects(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        previous = self.object_text("team-wiki:incident-17")
        self.scan()
        self.ingest(self.envelope(status="unavailable", enumeration_complete=False, permissions_verified=False, items=[], errors=["permission denied"]))
        self.assertEqual(previous, self.object_text("team-wiki:incident-17"))
        self.cover()
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_authoritative_full_snapshot_removes_missing_object(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.scan()
        self.ingest(self.envelope(items=EXTERNAL["items"][:1]))
        self.assertNotIn("team-wiki:incident-17", self.current()["items"])
        self.assertIn("team-wiki:feature-plan", self.current()["items"])

    def test_explicit_delta_delete_preserves_other_objects(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.scan()
        self.ingest(self.envelope(mode="delta", items=[], deleted_ids=["incident-17"]))
        self.assertNotIn("team-wiki:incident-17", self.current()["items"])
        self.assertIn("team-wiki:feature-plan", self.current()["items"])

    def test_ingest_wrong_run_or_scope_rejected_atomically(self):
        self.configure_external()
        self.scan()
        for override in ({"run_id": "wrong-run"}, {"scope_hash": "0" * 64}):
            with self.subTest(override=override):
                before = self.manifest_path.read_bytes()
                self.ingest(self.envelope(**override), success=False)
                self.assertEqual(before, self.manifest_path.read_bytes())

    def test_complete_claim_cannot_hide_remaining_pages_or_permission_gap(self):
        self.configure_external()
        self.scan()
        for override in ({"next_cursor": "another-page"}, {"permissions_verified": False}, {"enumeration_complete": False}, {"errors": ["page failed"]}):
            with self.subTest(override=override):
                # Safe downgrade retains useful data without pretending it is complete.
                result = self.ingest(self.envelope(**override))
                self.assertEqual(result["status"], "partial")
                self.cover()
                self.assertEqual(self.cli("build")["status"], "partial")

    def test_attachment_and_content_file_paths_cannot_escape_envelope(self):
        self.configure_external()
        self.scan()
        secret = self.root.parent / (self.root.name + "-outside.txt")
        secret.write_text("OUTSIDE_SOURCE_MUST_NOT_BE_COPIED\n")
        self.addCleanup(lambda: secret.unlink(missing_ok=True))
        (self.root / "linked.txt").symlink_to(secret)
        for field in ("content_file", "attachments"):
            for unsafe in (str(secret), "../" + secret.name, "linked.txt"):
                with self.subTest(field=field, path=unsafe):
                    item = {"id": "unsafe", "title": "Bad path", "locator": "https://example.org/unsafe", "version": "1"}
                    if field == "content_file":
                        item["content_file"] = unsafe
                    else:
                        item["content"] = "Attachment path must be validated.\n"
                        item["attachments"] = [{"path": unsafe, "name": "attachment.txt"}]
                    self.ingest(self.envelope(items=[item]), success=False)
                    self.assertNotIn("team-wiki:unsafe", self.current()["items"])

    def test_secrets_redacted_before_any_state_cache_write(self):
        secret = "sk-proj-" + "SyntheticFixtureOnlyNeverValid0123456789" * 2
        password = "SYNTHETIC_PASSWORD_38f5e84c"
        (self.project / ".env").write_text(f"API_KEY={secret}\nDATABASE_PASSWORD={password}\nMODE=fixture\n")
        self.scan()
        self.assertIn("local:.env", self.current()["items"])
        self.cover()
        result = self.cli("build")
        self.assertIn("[REDACTED]", Path(result["document"]).read_text())
        self.assertIn("MODE=fixture", self.object_text("local:.env"))
        for path in self.state.rglob("*"):
            if path.is_file():
                payload = path.read_bytes()
                self.assertNotIn(secret.encode(), payload, str(path))
                self.assertNotIn(password.encode(), payload, str(path))

    def test_binary_attachment_packaged_as_portable_file(self):
        self.configure_external()
        self.scan()
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4hoAAAAASUVORK5CYII=")
        (self.root / "pixel.png").write_bytes(png)
        item = deepcopy(EXTERNAL["items"][0])
        item["attachments"] = [{"path": "pixel.png", "name": "pixel.png"}]
        self.ingest(self.envelope(items=[item]))
        self.cover()
        result = self.cli("build")
        doc = Path(result["document"])
        # Export must carry actual attachment bytes; an absolute source path is not enough.
        exported = [p for p in doc.parent.rglob("*") if p.is_file() and p.read_bytes() == png]
        self.assertTrue(exported, result)
        self.assertNotIn(str(self.root / "pixel.png"), doc.read_text())

    def test_partial_build_keeps_latest_complete_document(self):
        self.scan()
        self.cover()
        complete = self.cli("build")
        self.assertEqual(complete["status"], "complete")
        previous = Path(complete["document"]).read_bytes()
        before_pointer = (self.state / "latest-complete.json").read_bytes()
        (self.project / "docs/missing-explanation.md").write_text("New material without an explanation.\n")
        self.scan()
        partial = self.cli("build")
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(Path(complete["document"]).read_bytes(), previous)
        self.assertEqual(before_pointer, (self.state / "latest-complete.json").read_bytes())
        self.assertEqual(partial["latest_complete"], complete["document"])

    def test_chunked_document_reconstructs_without_loss(self):
        self.scan()
        self.cover()
        result = self.cli("build", "--max-part-chars", "1200")
        document = Path(result["document"]).read_bytes()
        self.assertGreater(len(result["parts"]), 1)
        parts = [Path(part).read_bytes() for part in result["parts"]]
        self.assertEqual(b"".join(parts), document)

    def test_checkpoint_reuses_unchanged_objects_and_refreshes_changed(self):
        first = self.scan()
        objects = {key: (item["object"], (self.state / item["object"]).stat().st_mtime_ns) for key, item in first["items"].items()}
        # No build: this is an interrupted first run with material capture complete.
        changed = self.project / "src/worker.py"
        changed.write_text(changed.read_text() + "\nRESUMED_CHANGE = True\n")
        second = self.scan()
        for key, (obj, mtime) in objects.items():
            if key == "local:src/worker.py":
                self.assertNotEqual(second["items"][key]["object"], obj)
            else:
                self.assertEqual(second["items"][key]["object"], obj, key)
                self.assertEqual((self.state / obj).stat().st_mtime_ns, mtime, key)
        self.cover()
        self.assertEqual(self.cli("build")["status"], "complete")

    def test_business_history_is_not_ai_conversation(self):
        history = '{"event":"task_completed","task_id":"fixture-task-7","at":"2026-09-16T10:00:00Z"}\n'
        (self.project / "docs/history.jsonl").write_text(history)
        self.scan()
        self.assertIn("local:docs/history.jsonl", self.manifest["items"])
        self.assertEqual(self.object_text("local:docs/history.jsonl"), history)

    def test_unapproved_production_snapshot_cannot_be_imported(self):
        path = self.state / "config.json"
        config = json.loads(path.read_text())
        config["sources"] = [{"id": "team-wiki", "kind": "production", "label": "Synthetic metrics", "scope": {"environment": "fixture", "source": "metrics"}}]
        path.write_text(json.dumps(config))
        self.scan()
        before = self.manifest_path.read_bytes()
        self.ingest(self.envelope(), success=False)
        self.assertEqual(before, self.manifest_path.read_bytes())
        self.cover()
        self.assertEqual(self.cli("build")["status"], "partial")

    def test_scope_change_cannot_reuse_old_source_as_current(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        old_envelope = self.envelope()
        path = self.state / "config.json"
        config = json.loads(path.read_text())
        config["sources"][0]["scope"]["root"] = "different-fixture-root"
        path.write_text(json.dumps(config))
        self.cli("build", success=False)
        self.scan()
        self.assertNotIn("team-wiki:feature-plan", self.manifest["items"])
        old_envelope["run_id"] = self.scan_result["run_id"]
        self.ingest(old_envelope, success=False)

    def test_corrupt_checkpoint_is_detected_before_export(self):
        self.scan()
        self.cover()
        finished = self.cli("build")
        original = Path(finished["document"]).read_bytes()
        pointer = (self.state / "latest-complete.json").read_bytes()
        cached = self.state / self.manifest["items"]["local:src/worker.py"]["object"]
        cached.write_text("CORRUPTED_OBJECT\n")
        self.cli("build", success=False)
        self.assertEqual(Path(finished["document"]).read_bytes(), original)
        self.assertEqual((self.state / "latest-complete.json").read_bytes(), pointer)

    def test_file_read_failure_retains_old_snapshot_and_reports_partial(self):
        self.scan()
        self.cover()
        finished = self.cli("build")
        key = "local:src/worker.py"
        old = deepcopy(self.current()["items"][key])
        core = self.imported_core()
        original_read = core.read_stable
        target = (self.project / "src/worker.py").resolve()

        def unreadable(path):
            if Path(path).resolve() == target:
                raise PermissionError(13, "Synthetic denied file", str(path))
            return original_read(path)

        with mock.patch.object(core, "read_stable", side_effect=unreadable):
            self.accept_scan_result(core.cmd_scan(SimpleNamespace(state=str(self.state))))
        current = self.current()
        self.assertEqual(current["items"][key], old)
        self.assertNotIn(key, current["changes"]["deleted"])
        self.assertTrue(any(error.get("path") == "src/worker.py" and error.get("retained_old_snapshot") for error in current["errors"]))
        candidate = self.cli("build")
        self.assertEqual(candidate["status"], "partial")
        self.assertEqual(candidate["latest_complete"], finished["document"])
        self.assertIn(self.object_text(key), Path(candidate["document"]).read_text())

    def test_directory_read_failure_retains_old_subtree_and_reports_partial(self):
        self.scan()
        self.cover()
        finished = self.cli("build")
        old = {key: deepcopy(item) for key, item in self.current()["items"].items() if key.startswith("local:src/")}
        core = self.imported_core()
        original_scandir = os.scandir
        target = (self.project / "src").resolve()

        def unreadable(path):
            if not isinstance(path, int) and Path(path).resolve() == target:
                raise PermissionError(13, "Synthetic denied directory", str(path))
            return original_scandir(path)

        with mock.patch.object(core.os, "scandir", side_effect=unreadable):
            self.accept_scan_result(core.cmd_scan(SimpleNamespace(state=str(self.state))))
        current = self.current()
        for key, item in old.items():
            self.assertEqual(current["items"][key], item)
            self.assertNotIn(key, current["changes"]["deleted"])
        error = next(error for error in current["errors"] if error.get("path") == "src")
        self.assertEqual(set(error["retained_old_items"]), set(old))
        candidate = self.cli("build")
        self.assertEqual(candidate["status"], "partial")
        self.assertEqual(candidate["latest_complete"], finished["document"])

    def test_tracked_ai_conversation_does_not_leak_via_git_changes(self):
        marker = "EXCLUDED_CHAT_CONTENT_984a92c7"
        chat = self.project / "docs/conversation.json"
        chat.write_text(json.dumps({"messages": [{"role": "user", "content": marker + "_OLD"}]}))
        subprocess.run(["git", "-C", str(self.project), "add", "docs/conversation.json"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.project), "commit", "-qm", "add synthetic excluded conversation"], check=True, capture_output=True)
        chat.write_text(json.dumps({"messages": [{"role": "user", "content": marker + "_NEW"}]}))
        self.scan()
        self.assertNotIn("local:docs/conversation.json", self.current()["items"])
        self.cover()
        self.cli("build")
        for path in self.state.rglob("*"):
            if path.is_file():
                self.assertNotIn(marker.encode(), path.read_bytes(), str(path))

    def runtime_note(self, key, marker):
        current = self.current()
        payload = {"schema_version": 1, "run_id": current["run_id"], "sections": [
            {"id": "runtime", "title": "Current runtime evidence", "category": "runtime", "content": marker,
             "covers": {key: current["items"][key]["fingerprint"]}},
        ], "deleted_ids": []}
        self.cli("note", "--input", self.write_json("runtime-note.json", payload))

    def assert_runtime_stale(self, result, marker):
        self.assertTrue(any(gap.get("kind") == "stale_explanations" and "runtime" in gap.get("sections", [])
                            for gap in result["gaps"]), result)
        self.assertNotIn(marker, Path(result["document"]).read_text())

    def test_nonempty_runtime_note_invalidates_when_source_becomes_unavailable(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.cover()
        marker = "RUNTIME_FRESH_COMPLETE_CLAIM_31dd09"
        self.runtime_note("team-wiki:incident-17", marker)
        self.assertEqual(self.cli("build")["status"], "complete")
        old_fingerprint = self.current()["items"]["team-wiki:incident-17"]["fingerprint"]
        self.ingest(self.envelope(status="unavailable", enumeration_complete=False,
                                  permissions_verified=False, items=[], errors=["permission denied"]))
        self.assertEqual(self.current()["items"]["team-wiki:incident-17"]["fingerprint"], old_fingerprint)
        self.assert_runtime_stale(self.cli("build"), marker)

    def test_nonempty_runtime_note_invalidates_on_source_window_config_change(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.cover()
        marker = "RUNTIME_OLD_WINDOW_CLAIM_719aa3"
        self.runtime_note("local:ops/deploy.json", marker)
        self.assertEqual(self.cli("build")["status"], "complete")
        path = self.state / "config.json"
        config = json.loads(path.read_text())
        config["sources"][0]["window"] = {"start": "2026-09-16T00:00:00Z", "end": "2026-09-17T00:00:00Z"}
        path.write_text(json.dumps(config))
        self.scan()
        self.assert_runtime_stale(self.cli("build"), marker)

    def test_partial_delta_tombstone_survives_until_complete_final_page(self):
        self.configure_external()
        self.scan()
        for restart in (False, True):
            with self.subTest(resume_after_scan=restart):
                self.ingest(self.envelope())
                self.ingest(self.envelope(mode="delta", status="partial", enumeration_complete=False,
                                          items=[], deleted_ids=["incident-17"], next_cursor="page-2"))
                self.assertIn("team-wiki:incident-17", self.current()["items"])
                if restart:
                    self.scan()
                result = self.ingest(self.envelope(mode="delta", items=[], deleted_ids=[]))
                self.assertEqual(result["status"], "complete")
                self.assertNotIn("team-wiki:incident-17", self.current()["items"])
                self.assertIn("team-wiki:feature-plan", self.current()["items"])

    def test_later_delta_item_restoration_cancels_deferred_tombstone(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.ingest(self.envelope(mode="delta", status="partial", enumeration_complete=False,
                                  items=[], deleted_ids=["incident-17"], next_cursor="page-2"))
        restored = deepcopy(EXTERNAL["items"][1])
        restored["content"] += "RESTORED_ITEM_REVISION_42\n"
        result = self.ingest(self.envelope(mode="delta", items=[restored], deleted_ids=[]))
        self.assertEqual(result["status"], "complete")
        self.assertIn("RESTORED_ITEM_REVISION_42", self.object_text("team-wiki:incident-17"))

    def test_authoritative_full_snapshot_overrides_deferred_delta_tombstone(self):
        self.configure_external()
        self.scan()
        self.ingest(self.envelope())
        self.ingest(self.envelope(mode="delta", status="partial", enumeration_complete=False,
                                  items=[], deleted_ids=["incident-17"], next_cursor="page-2"))
        result = self.ingest(self.envelope(mode="full", items=EXTERNAL["items"], deleted_ids=[]))
        self.assertEqual(result["status"], "complete")
        self.assertIn("team-wiki:incident-17", self.current()["items"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
