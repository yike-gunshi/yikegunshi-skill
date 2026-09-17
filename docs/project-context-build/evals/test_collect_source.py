#!/usr/bin/env python3
"""Deterministic provider simulations; no real provider, account or network access.

These tests assess adapter behavior, not live GitHub/Lark/production readiness.
"""
from __future__ import annotations

from copy import deepcopy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


REPOSITORY = Path(__file__).resolve().parents[3]
SCRIPTS = REPOSITORY / "skills/project-context/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("project_context_collect_test", SCRIPTS / "collect_source.py")
collect_source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_source)


class Response:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.data[:size]


class CollectorRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="project-context-collect-")
        self.root = Path(self.temp.name)
        # Any accidental uncaptured network call is a test failure.
        self.network_guard = patch("socket.socket", side_effect=AssertionError("Live network is prohibited in adapter regressions"))
        self.network_guard.start()

    def tearDown(self):
        self.network_guard.stop()
        self.temp.cleanup()

    def github_source(self, include=None, max_requests=500):
        return {"id": "github-fixture", "kind": "github", "label": "Synthetic repository",
                "scope": {"repo": "fixture/project", "include": include or ["issues"]},
                "budget": {"max_requests": max_requests, "timeout_seconds": 5, "max_response_bytes": 1024 * 1024}}

    def production_source(self):
        return {"id": "production-fixture", "kind": "production", "label": "Synthetic metric records", "scope": {"dataset": "counts"},
                "transport": "http-json", "environment": "fixture-production",
                "approval": {"confirmed": True, "confirmed_at": "2026-09-15T09:00:00Z"},
                "window": {"start": "2026-09-16T00:00:00+08:00", "end": "2026-09-17T00:00:00+08:00", "timezone": "Asia/Shanghai"},
                "fields": ["id", "at", "count"], "read_only": {"verified": True, "mechanism": "Fixture immutable reporting GET endpoint"},
                "budget": {"max_requests": 10, "timeout_seconds": 5, "max_response_bytes": 100000},
                "request": {"url": "https://metrics.example.invalid/records", "start_param": "from", "end_param": "until",
                            "timestamp_field": "at", "id_field": "id", "fields_param": "fields"},
                "pagination": {"items_path": "rows", "next_cursor_path": "next", "cursor_param": "cursor"}}

    def collector(self, source, **kwargs):
        return collect_source.Collector(source, "fixture-run", "fixture-scope", **kwargs)

    def issue(self, number):
        return {"number": number, "title": f"Issue {number}", "body": f"Issue {number} full description", "html_url": f"https://example.invalid/issues/{number}",
                "updated_at": "2026-09-16T09:00:00Z"}

    def gh_mock(self, responses, commands):
        def execute(argv, **kwargs):
            commands.append(list(argv))
            self.assertEqual(argv[:4], ["gh", "api", "--method", "GET"])
            self.assertNotIn("shell", kwargs)
            self.assertNotIn("--input", argv)
            self.assertNotIn("-f", argv)
            endpoint = argv[4]
            self.assertIn(endpoint, responses, f"Unplanned provider request: {endpoint}")
            value = responses[endpoint]
            if isinstance(value, Exception):
                raise value
            if value is None:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"SENSITIVE_PROVIDER_STDERR_MUST_NOT_PERSIST")
            return SimpleNamespace(returncode=0, stdout=json.dumps(value).encode(), stderr=b"")
        return execute

    def http_mock(self, payloads, requests):
        def open_request(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertGreater(timeout, 0)
            requests.append(request)
            self.assertLessEqual(len(requests), len(payloads), "Unexpected extra HTTP request")
            return Response(payloads[len(requests) - 1])
        return SimpleNamespace(open=open_request)

    def test_github_follows_comment_pages_and_preserves_final_comment(self):
        commands = []
        responses = {"repos/fixture/project": {"id": 1},
                     "repos/fixture/project/issues?state=all&per_page=100&page=1": [self.issue(1)],
                     "repos/fixture/project/issues/1/comments?per_page=100&page=1": [{"id": n, "body": f"Comment {n}"} for n in range(100)],
                     "repos/fixture/project/issues/1/comments?per_page=100&page=2": [{"id": 100, "body": "LAST_COMMENT_FULL_BODY"}]}
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            envelope = self.collector(self.github_source()).collect()
        self.assertEqual(envelope["status"], "complete")
        body = json.loads(envelope["items"][0]["content"])
        self.assertEqual(len(body["comments"]), 101)
        self.assertEqual(body["comments"][-1]["body"], "LAST_COMMENT_FULL_BODY")
        self.assertEqual(envelope["coverage"]["requests_this_run"], 4)
        self.assertEqual(len(commands), 4)

    def test_github_pr_includes_discussion_reviews_comments_files_and_commits(self):
        commands = []
        base = "repos/fixture/project"
        pull = {"number": 4, "title": "PR four", "html_url": "https://example.invalid/pull/4"}
        responses = {base: {"id": 1}, base + "/pulls?state=all&per_page=100&page=1": [pull],
                     base + "/pulls/4": {**pull, "changed_files": 1, "commits": 1, "updated_at": "2026-09-16T09:00:00Z"},
                     base + "/issues/4/comments?per_page=100&page=1": [{"body": "PR discussion"}],
                     base + "/pulls/4/reviews?per_page=100&page=1": [{"body": "Review explanation"}],
                     base + "/pulls/4/comments?per_page=100&page=1": [{"body": "Line review"}],
                     base + "/pulls/4/files?per_page=100&page=1": [{"filename": "source.py", "changes": 1, "patch": "+new_behavior()"}],
                     base + "/pulls/4/commits?per_page=100&page=1": [{"sha": "f" * 40}]}
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            envelope = self.collector(self.github_source(["pulls"])).collect()
        self.assertEqual(envelope["status"], "complete")
        material = json.loads(envelope["items"][0]["content"])
        self.assertEqual(set(material), {"pull", "discussion", "reviews", "review_comments", "files", "commits"})
        self.assertIn("Review explanation", envelope["items"][0]["content"])
        self.assertIn("+new_behavior()", envelope["items"][0]["content"])

    def test_github_later_failure_keeps_completed_material_and_hides_stderr(self):
        commands = []
        responses = {"repos/fixture/project": {"id": 1},
                     "repos/fixture/project/issues?state=all&per_page=100&page=1": [self.issue(1), self.issue(2)],
                     "repos/fixture/project/issues/1/comments?per_page=100&page=1": [{"body": "Saved first issue comment"}],
                     "repos/fixture/project/issues/2/comments?per_page=100&page=1": None}
        collector = self.collector(self.github_source())
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            envelope = collector.collect()
        self.assertEqual(envelope["status"], "partial")
        self.assertFalse(envelope["enumeration_complete"])
        self.assertEqual([item["id"] for item in envelope["items"]], ["issue-1"])
        self.assertNotIn("SENSITIVE_PROVIDER_STDERR", json.dumps({"envelope": envelope, "cache": collector.cache}))

    def test_budget_and_resume_cannot_reset_consumed_request_count(self):
        commands = []
        source = self.github_source(max_requests=2)
        responses = {"repos/fixture/project": {"id": 1},
                     "repos/fixture/project/issues?state=all&per_page=100&page=1": [self.issue(1)]}
        collector = self.collector(source)
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            first = collector.collect()
        resumed = self.collector(source, cache=deepcopy(collector.cache), request_count=collector.total_requests)
        with patch.object(collect_source.subprocess, "run", side_effect=AssertionError("Resume must honor exhausted run budget")):
            second = resumed.collect()
        self.assertEqual(first["status"], "partial")
        self.assertEqual(second["status"], "partial")
        self.assertEqual(second["coverage"]["requests_this_run"], 2)
        self.assertEqual(second["coverage"]["requests_this_invocation"], 0)

    def test_resume_reuses_successful_responses_with_original_times(self):
        source = self.github_source(max_requests=4)
        commands = []
        responses = {"repos/fixture/project": {"id": 1},
                     "repos/fixture/project/issues?state=all&per_page=100&page=1": [self.issue(1)],
                     "repos/fixture/project/issues/1/comments?per_page=100&page=1": None}
        original = self.collector(source)
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            self.assertEqual(original.collect()["status"], "partial")
        checkpoint = deepcopy(original.cache)
        self.assertEqual(original.total_requests, 3)
        self.assertTrue(all(isinstance(entry, dict) and "fetched_at" in entry and "value" in entry for entry in checkpoint.values()))
        responses = {"repos/fixture/project/issues/1/comments?per_page=100&page=1": [{"body": "Recovered comment"}]}
        commands = []
        resumed = self.collector(source, cache=checkpoint, request_count=3)
        with patch.object(collect_source.subprocess, "run", side_effect=self.gh_mock(responses, commands)):
            envelope = resumed.collect()
        self.assertEqual(envelope["status"], "complete")
        self.assertEqual(len(commands), 1)
        self.assertEqual(envelope["coverage"]["requests_this_run"], 4)
        self.assertEqual(envelope["coverage"]["requests_this_invocation"], 1)
        for key, entry in original.cache.items():
            self.assertEqual(resumed.cache[key]["fetched_at"], entry["fetched_at"])
        observed_times = [entry["fetched_at"] for entry in resumed.cache.values()]
        self.assertEqual(envelope["coverage"]["earliest_response_at"], min(observed_times))
        self.assertEqual(envelope["coverage"]["latest_response_at"], max(observed_times))
        self.assertEqual(envelope["coverage"]["reused_responses"], 2)
        start = dt.datetime.fromisoformat(envelope["coverage"]["collection_started_at"])
        finish = dt.datetime.fromisoformat(envelope["coverage"]["collection_finished_at"])
        self.assertIsNotNone(start.tzinfo)
        self.assertLessEqual(start, finish)

    def test_lark_missing_revision_uses_content_fingerprint(self):
        source = {"id": "lark-fixture", "kind": "lark", "label": "Fixture doc", "scope": {"documents": ["fixture-document"], "comments": False}}
        payload = {"ok": True, "data": {"document": {"document_id": "fixture-document", "content": "<doc><p>Full body</p></doc>"}, "reference_map": {"one": "reference"}}}
        calls = []
        def execute(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[:3], ["lark-cli", "docs", "+fetch"])
            self.assertIn("--scope", argv)
            self.assertEqual(argv[argv.index("--scope") + 1], "full")
            self.assertEqual(argv[argv.index("--detail") + 1], "full")
            self.assertEqual(argv[argv.index("--doc-format") + 1], "xml")
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode(), stderr=b"")
        with patch.object(collect_source.subprocess, "run", side_effect=execute):
            first = self.collector(source).collect()
            second = self.collector(source).collect()
        self.assertEqual(first["status"], "complete")
        self.assertRegex(first["items"][0]["version"], r"^sha256:[a-f0-9]{64}$")
        self.assertEqual(first["items"][0]["version"], second["items"][0]["version"])
        self.assertIn("reference_map", first["items"][0]["content"])

    def test_lark_media_and_unfetched_comments_remain_partial(self):
        source = {"id": "lark-fixture", "kind": "lark", "label": "Fixture doc", "scope": {"documents": ["fixture-document"], "comments": True}}
        payload = {"ok": True, "data": {"document": {"document_id": "fixture-document", "revision_id": "v1", "content": '<doc><img token="media-fixture"/><sheet/></doc>'}}}
        with patch.object(collect_source.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode(), stderr=b"")):
            result = self.collector(source).collect()
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["permissions_verified"])
        self.assertIn("<sheet/>", result["items"][0]["content"])
        self.assertTrue(any("media" in error for error in result["errors"]))
        self.assertTrue(any("comments" in error for error in result["errors"]))

    def test_production_prerequisites_are_checked_before_get(self):
        mutations = [lambda s: s["approval"].pop("confirmed_at"), lambda s: s["approval"].update(confirmed=False),
                     lambda s: s["read_only"].update(verified=False), lambda s: s.update(fields=[]),
                     lambda s: s.update(budget={}), lambda s: s["request"].update(timestamp_field="private_field"),
                     lambda s: s["request"].update(url="http://metrics.example.invalid/records")]
        for mutate in mutations:
            with self.subTest(change=mutations.index(mutate)):
                source = self.production_source()
                mutate(source)
                with patch.object(collect_source.urllib.request, "build_opener", side_effect=AssertionError("Invalid config must not call network")):
                    envelope = self.collector(source).collect()
                self.assertEqual(envelope["status"], "partial")
                self.assertEqual(envelope["coverage"]["requests_this_run"], 0)

    def test_production_get_preserves_fields_window_timezone_and_finishes_cursor(self):
        source = self.production_source()
        rows = [{"rows": [{"id": "a", "at": "2026-09-16T01:00:00+08:00", "count": 3}], "next": "page-2"},
                {"rows": [{"id": "b", "at": "2026-09-16T03:00:00Z", "count": 4}], "next": None}]
        requests = []
        with patch.object(collect_source.urllib.request, "build_opener", return_value=self.http_mock(rows, requests)):
            envelope = self.collector(source).collect()
        self.assertEqual(envelope["status"], "complete")
        self.assertEqual([item["id"] for item in envelope["items"]], ["a", "b"])
        first_query = parse_qs(urlsplit(requests[0].full_url).query)
        next_query = parse_qs(urlsplit(requests[1].full_url).query)
        self.assertEqual(first_query["from"], [source["window"]["start"]])
        self.assertEqual(first_query["until"], [source["window"]["end"]])
        self.assertEqual(first_query["fields"], ["id,at,count"])
        self.assertNotIn("cursor", first_query)
        self.assertEqual(next_query["cursor"], ["page-2"])
        self.assertEqual(envelope["coverage"]["window"]["timezone"], "Asia/Shanghai")
        self.assertIsNone(envelope["coverage"]["next_cursor"])

    def test_production_extra_fields_never_enter_checkpoint_or_envelope(self):
        source = self.production_source()
        checkpoint = self.root / "checkpoint.json"
        collector = self.collector(source, checkpoint=lambda data: collect_source.atomic_json(checkpoint, data))
        payload = {"rows": [{"id": "a", "at": "2026-09-16T03:00:00Z", "count": 2,
                              "email": "UNAPPROVED_FIELD_SENTINEL@example.invalid", "private_profile": {"nested": "UNAPPROVED_NESTED_SENTINEL"}}],
                   "next": None, "unrequested_metadata": "UNAPPROVED_METADATA_SENTINEL"}
        requests = []
        with patch.object(collect_source.urllib.request, "build_opener", return_value=self.http_mock([payload], requests)):
            envelope = collector.collect()
        self.assertEqual(envelope["status"], "complete")
        output = self.root / "envelope.json"
        collect_source.atomic_json(output, envelope)
        persisted = checkpoint.read_text() + output.read_text()
        self.assertNotIn("UNAPPROVED_", persisted)
        self.assertEqual(set(json.loads(envelope["items"][0]["content"])), {"id", "at", "count"})

    def test_production_outside_window_or_naive_timestamp_is_partial(self):
        for stamp in ("2026-09-17T00:00:00+08:00", "2026-09-15T23:59:59+08:00", "2026-09-16T03:00:00"):
            with self.subTest(timestamp=stamp):
                payload = {"rows": [{"id": "a", "at": stamp, "count": 1}], "next": None}
                collector = self.collector(self.production_source())
                with patch.object(collect_source.urllib.request, "build_opener", return_value=self.http_mock([payload], [])):
                    result = collector.collect()
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["items"], [])
                self.assertFalse(collector.cache)

    def test_production_duplicate_id_across_pages_is_partial(self):
        payloads = [{"rows": [{"id": "a", "at": "2026-09-16T03:00:00Z", "count": 1}], "next": "second"},
                    {"rows": [{"id": "a", "at": "2026-09-16T04:00:00Z", "count": 2}], "next": None}]
        with patch.object(collect_source.urllib.request, "build_opener", return_value=self.http_mock(payloads, [])):
            result = self.collector(self.production_source()).collect()
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["enumeration_complete"])
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(any("duplicate" in error for error in result["errors"]))

    def test_production_repeated_cursor_stops_without_extra_requests(self):
        payloads = [{"rows": [{"id": "a", "at": "2026-09-16T03:00:00Z", "count": 1}], "next": "same"},
                    {"rows": [{"id": "b", "at": "2026-09-16T04:00:00Z", "count": 2}], "next": "same"}]
        requests = []
        with patch.object(collect_source.urllib.request, "build_opener", return_value=self.http_mock(payloads, requests)):
            result = self.collector(self.production_source()).collect()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["coverage"]["next_cursor"], "same")

    def test_redirect_cannot_send_credentials_to_unconfigured_destination(self):
        with self.assertRaises(collect_source.CollectionError):
            collect_source.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.example.invalid/data")

    def test_public_reference_tokens_survive_clean_serialization_and_capture(self):
        import context
        payload = {"reference_map": {"attachment": {"obj_token": "obj-fixture-123", "node_token": "node-fixture-123",
                                                    "file_token": "file-fixture-123", "image_token": "image-fixture-123"}},
                   "api_token_env": "PROJECT_ACCESS_TOKEN", "secret_ref": "fixture-vault/path",
                   "API_KEY_ENV": "PROJECT_API_KEY", "access_token": "AUTH_CREDENTIAL_MUST_DISAPPEAR"}
        collector = self.collector(self.github_source())
        collector.item("ref", "Source references", "fixture://refs", collect_source.scrub(payload))
        state = self.root / "state"
        item = context.capture(state, collector.items[0]["content"].encode(), {"id": "ref"})
        text = (state / item["object"]).read_text()
        recorded = json.loads(text)
        self.assertEqual(recorded["reference_map"], payload["reference_map"])
        for key in ("api_token_env", "secret_ref", "API_KEY_ENV"):
            self.assertEqual(recorded[key], payload[key])
        self.assertNotIn("AUTH_CREDENTIAL_MUST_DISAPPEAR", text)

    def test_text_reference_allowlist_still_redacts_real_auth_values(self):
        import context
        raw = ('node_token="node-reference"\nAPI_TOKEN_ENV=PROJECT_AUTH_TOKEN\n'
               'api_token="AUTH_TOKEN_MUST_DISAPPEAR"\n'
               'password=PASSWORD_MUST_DISAPPEAR\n'
               '{"Authorization": "AUTH_HEADER_MUST_DISAPPEAR", "file_token": "file-reference"}\n'
               'https://example.invalid/?node_token=node-ref&access_token=QUERY_TOKEN_MUST_DISAPPEAR\n')
        screened, count = context.redact(raw)
        self.assertIn('node_token="node-reference"', screened)
        self.assertIn('API_TOKEN_ENV=PROJECT_AUTH_TOKEN', screened)
        self.assertIn('"file_token": "file-reference"', screened)
        self.assertIn('?node_token=node-ref', screened)
        for credential in ("AUTH_TOKEN_MUST_DISAPPEAR", "PASSWORD_MUST_DISAPPEAR", "AUTH_HEADER_MUST_DISAPPEAR", "QUERY_TOKEN_MUST_DISAPPEAR"):
            self.assertNotIn(credential, screened)
        self.assertGreaterEqual(count, 4)


if __name__ == "__main__":
    unittest.main()
