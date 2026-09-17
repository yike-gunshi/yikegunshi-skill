#!/usr/bin/env python3
"""Bounded, read-only source collection. Produces an ingest envelope; never publishes it.

Provider commands are fixed argument arrays, without a shell. No credentials in config.
The generic production adapter supports explicitly approved JSON GET endpoints only.
Other production tools are orchestrated by the host agent using the same envelope.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


class CollectionError(ValueError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def at(value, path):
    for key in path.split(".") if path else []:
        if not isinstance(value, dict) or key not in value:
            raise CollectionError("response lacks configured field: " + path)
        value = value[key]
    return value


def scrub(value):
    # Reuse the core's persistence filter. Importing it performs no collection.
    import context
    return context.clean(value)


def atomic_json(path, value):
    import context
    context.atomic_json(Path(path), scrub(value))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("redirect refused; configure and authorize the destination explicitly")


class Collector:
    def __init__(self, source, run_id, scope_hash, cache=None, checkpoint=None, request_count=0):
        self.source = source
        self.scope = source.get("scope", {})
        self.run_id, self.scope_hash = run_id, scope_hash
        budget = source.get("budget", {})
        self.limit = int(budget.get("max_requests", 100))
        self.timeout = int(budget.get("timeout_seconds", 30))
        self.max_bytes = int(budget.get("max_response_bytes", 20 * 1024 * 1024))
        if not (0 < self.limit <= 10000 and 0 < self.timeout <= 300 and self.max_bytes > 0):
            raise CollectionError("invalid request budget")
        self.requests = 0
        self.total_requests = request_count
        self.items = []
        self.errors = []
        self.coverage = {"environment": source.get("environment"), "next_cursor": None}
        self.cache = cache or {}
        self.checkpoint = checkpoint
        self.started_at = now()
        self.response_times = []
        self.reused_responses = 0

    def cached(self, key, operation):
        key = digest(key)
        if key in self.cache:
            entry = self.cache[key]
            if not isinstance(entry, dict) or "fetched_at" not in entry or "value" not in entry:
                raise CollectionError("checkpoint lacks response time; collect again without --resume")
            self.response_times.append(entry["fetched_at"])
            self.reused_responses += 1
            return entry["value"]
        if self.total_requests >= self.limit:
            raise CollectionError("run request budget reached; change the approved budget before starting another collection run")
        self.requests += 1
        self.total_requests += 1
        if self.checkpoint:
            self.checkpoint({"cache": self.cache, "request_count": self.total_requests})
        value = scrub(operation())
        fetched_at = now()
        self.cache[key] = {"value": value, "fetched_at": fetched_at}
        self.response_times.append(fetched_at)
        if self.checkpoint:
            self.checkpoint({"cache": self.cache, "request_count": self.total_requests})
        return value

    def command(self, argv):
        def execute():
            try:
                result = subprocess.run(argv, capture_output=True, timeout=self.timeout, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise CollectionError("provider command unavailable or timed out") from None
            if result.returncode:
                # Provider stderr may contain URLs or credentials. Keep it out of artifacts.
                raise CollectionError("provider command failed; inspect authentication/permissions separately")
            if len(result.stdout) > self.max_bytes:
                raise CollectionError("provider response exceeds configured byte budget")
            try:
                return json.loads(result.stdout)
            except (ValueError, UnicodeError):
                raise CollectionError("provider did not return valid JSON") from None
        return self.cached(argv, execute)

    def gh(self, endpoint):
        argv = ["gh", "api", "--method", "GET", endpoint]
        if self.source.get("hostname"):
            host = self.source["hostname"]
            if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
                raise CollectionError("invalid GitHub hostname")
            argv += ["--hostname", host]
        return self.command(argv)

    def pages(self, endpoint):
        items, page = [], 1
        while True:
            separator = "&" if "?" in endpoint else "?"
            part = self.gh(f"{endpoint}{separator}per_page=100&page={page}")
            if not isinstance(part, list):
                raise CollectionError("GitHub list response is not an array")
            items.extend(part)
            if len(part) < 100:
                return items
            page += 1

    def item(self, identifier, title, locator, content, version=None):
        content = scrub(content)
        self.items.append({"id": str(identifier), "title": title, "locator": locator,
                           "version": str(version) if version is not None and str(version) else "sha256:" + digest(content),
                           "content": json.dumps(content, ensure_ascii=False, indent=2)})

    def github(self):
        repo = self.scope.get("repo", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise CollectionError("scope.repo must be owner/repository")
        include = self.scope.get("include", ["issues", "pulls", "releases", "deployments"])
        if not isinstance(include, list) or not include or set(include) - {"issues", "pulls", "releases", "deployments"}:
            raise CollectionError("unsupported GitHub collection scope")
        base = "repos/" + repo
        self.gh(base)  # Verify repository access, not the existence of the gh executable.
        if "issues" in include:
            for issue in self.pages(base + "/issues?state=all"):
                if "pull_request" in issue:
                    continue
                number = issue["number"]
                full = {"issue": issue, "comments": self.pages(f"{base}/issues/{number}/comments")}
                self.item(f"issue-{number}", issue["title"], issue["html_url"], full, issue.get("updated_at"))
        if "pulls" in include:
            for pull in self.pages(base + "/pulls?state=all"):
                number = pull["number"]
                detail = self.gh(f"{base}/pulls/{number}")
                full = {"pull": detail,
                        "discussion": self.pages(f"{base}/issues/{number}/comments"),
                        "reviews": self.pages(f"{base}/pulls/{number}/reviews"),
                        "review_comments": self.pages(f"{base}/pulls/{number}/comments"),
                        "files": self.pages(f"{base}/pulls/{number}/files"),
                        "commits": self.pages(f"{base}/pulls/{number}/commits")}
                if detail.get("changed_files", len(full["files"])) != len(full["files"]):
                    self.errors.append(f"PR {number}: changed-file enumeration incomplete")
                if detail.get("commits", len(full["commits"])) != len(full["commits"]):
                    self.errors.append(f"PR {number}: commit enumeration incomplete")
                if any("patch" not in f and f.get("changes", 0) > 0 for f in full["files"]):
                    self.errors.append(f"PR {number}: binary/omitted patch requires supplementary artifact")
                self.item(f"pull-{number}", pull["title"], pull["html_url"], full, detail.get("updated_at"))
        for category in [name for name in ["releases", "deployments"] if name in include]:
            for entry in self.pages(f"{base}/{category}"):
                full = {category: entry}
                if category == "deployments":
                    full["statuses"] = self.pages(f"{base}/deployments/{entry['id']}/statuses")
                if category == "releases" and entry.get("assets"):
                    self.errors.append(f"release {entry['id']}: assets require separately collected attachments")
                self.item(f"{category}-{entry['id']}", entry.get("name") or category,
                          entry.get("html_url") or entry.get("url", ""), full,
                          entry.get("updated_at") or entry.get("created_at"))
        self.coverage["repository"] = repo

    def lark(self):
        documents = self.scope.get("documents")
        if not isinstance(documents, list) or not documents:
            raise CollectionError("lark adapter requires an explicit scope.documents list; use host tools for wiki traversal")
        for document in documents:
            if not isinstance(document, str) or not document or document.startswith("-"):
                raise CollectionError("invalid Lark document identifier")
            if "#" in document:
                raise CollectionError("section anchors are not permitted in full-document scope")
            data = self.command(["lark-cli", "docs", "+fetch", "--doc", document,
                                 "--scope", "full", "--detail", "full", "--doc-format", "xml", "--format", "json"])
            if data.get("ok") is not True:
                raise CollectionError("Lark document unavailable or permission denied")
            body = at(data, "data.document")
            content = body.get("content", "")
            if not isinstance(content, str):
                raise CollectionError("Lark document has invalid content")
            if re.search(r"<(?:excerpt|fragment)\b", content):
                self.errors.append("Lark returned partial content: " + document)
            if re.search(r"<(?:img|image|source|whiteboard|sheet|bitable|file|cite)\b", content):
                self.errors.append("Lark embedded media/data/reference requires host collection: " + document)
            # Keep XML, reference_map and tips together; do not collapse to plain text.
            self.item(body.get("document_id", document), document, document, data, body.get("revision_id"))
        if self.scope.get("comments", True):
            self.errors.append("Lark comments require host collection; document fetch alone does not prove discussion completeness")

    def http_json(self):
        s = self.source
        import context
        if s.get("kind") != "production" or not context.production_valid(s):
            raise CollectionError("production source requires dated approval, fields, window, budget and verified read-only mechanism")
        read_only = s.get("read_only", {})
        if not isinstance(read_only, dict) or read_only.get("verified") is not True or not read_only.get("mechanism"):
            raise CollectionError("read_only must identify a verified read-only endpoint mechanism")
        fields, window, request = s.get("fields"), s.get("window", {}), s.get("request", {})
        if not isinstance(fields, list) or not fields or any(not isinstance(f, str) or not f for f in fields):
            raise CollectionError("production fields must be an explicit nonempty list")
        if not all(k in s.get("budget", {}) for k in ["max_requests", "timeout_seconds", "max_response_bytes"]):
            raise CollectionError("production collection requires an explicit budget")
        start, end = window.get("start"), window.get("end")
        try:
            lo, hi = [dt.datetime.fromisoformat(v.replace("Z", "+00:00")) for v in (start, end)]
            if lo.tzinfo is None or hi.tzinfo is None or lo >= hi:
                raise ValueError()
        except (TypeError, ValueError, AttributeError):
            raise CollectionError("window requires ordered timezone-aware start/end timestamps") from None
        url = request.get("url", "")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise CollectionError("production URL must be HTTPS without embedded credentials or fragment")
        if re.search(r"(?i)(token|secret|password|api.?key|authorization)=", parsed.query):
            raise CollectionError("use credential environment references instead of URL secrets")
        if not all(request.get(k) for k in ["start_param", "end_param", "timestamp_field"]):
            raise CollectionError("request must map window start/end and a timestamp_field")
        if request["timestamp_field"] not in fields or (request.get("id_field") and request["id_field"] not in fields):
            raise CollectionError("timestamp_field and id_field must be included in the approved fields")
        if not request.get("fields_param") and request.get("fixed_response_fields") is not True:
            raise CollectionError("configure a fields_param or verify fixed_response_fields for this endpoint")
        headers = {}
        for name, env in request.get("headers_env", {}).items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", env):
                raise CollectionError("invalid credential environment reference")
            if not os.environ.get(env):
                raise CollectionError("required credential environment variable is unavailable")
            headers[name] = os.environ[env]
        pagination = s.get("pagination", {})
        if not pagination.get("single_page") and not all(pagination.get(k) for k in ["next_cursor_path", "cursor_param"]):
            raise CollectionError("declare single_page or explicit cursor pagination")
        params = dict(urllib.parse.parse_qsl(parsed.query))
        params.update(request.get("params", {}))
        if any(re.search(r"(?i)(token|secret|password|api.?key|authorization)", str(k)) for k in params):
            raise CollectionError("credentials must use headers_env, not URL/query parameters")
        params[request["start_param"]], params[request["end_param"]] = start, end
        if request.get("fields_param"):
            params[request["fields_param"]] = ",".join(fields)
        base_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        cursor, seen, row_ids = None, set(), set()
        self.coverage.update({"window": window, "fields": fields, "endpoint": base_url,
                              "query_params": params, "environment": s.get("environment")})
        while True:
            query = dict(params)
            if cursor is not None:
                query[pagination["cursor_param"]] = cursor
            target = base_url + "?" + urllib.parse.urlencode(query)
            def fetch():
                try:
                    req = urllib.request.Request(target, headers=headers, method="GET")
                    with urllib.request.build_opener(NoRedirect()).open(req, timeout=self.timeout) as response:
                        raw = response.read(self.max_bytes + 1)
                except (OSError, urllib.error.URLError):
                    raise CollectionError("production GET failed; inspect access/network without logging credentials") from None
                if len(raw) > self.max_bytes:
                    raise CollectionError("production response exceeds byte budget")
                try:
                    response_data = json.loads(raw)
                except ValueError:
                    raise CollectionError("production response is not JSON") from None
                rows = at(response_data, pagination.get("items_path", ""))
                if not isinstance(rows, list):
                    raise CollectionError("configured items_path must yield an array")
                records = []
                for row in rows:
                    stamp = at(row, request["timestamp_field"])
                    try:
                        observed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                        valid = observed.tzinfo is not None and lo <= observed < hi
                    except (TypeError, ValueError, AttributeError):
                        valid = False
                    if not valid:
                        raise CollectionError("provider returned a timestamp outside the approved window or invalid timestamp")
                    selected = {field: at(row, field) for field in fields}
                    identifier = str(at(row, request["id_field"])) if request.get("id_field") else digest(selected)
                    records.append({"id": identifier, "timestamp": stamp, "selected": selected})
                next_cursor = None if pagination.get("single_page") else at(response_data, pagination["next_cursor_path"])
                # Persist only approved fields, never the provider's extra columns.
                return {"records": records, "next_cursor": next_cursor}
            data = self.cached(["GET", target], fetch)
            for record in data["records"]:
                identifier = record["id"]
                if identifier in row_ids:
                    raise CollectionError("duplicate record id across pages; disambiguate scope or use a stable unique id")
                row_ids.add(identifier)
                self.item(identifier, "production record " + identifier, base_url, record["selected"], record["timestamp"])
            cursor = data["next_cursor"]
            self.coverage["next_cursor"] = cursor
            if cursor is None or cursor == "":
                break
            if not isinstance(cursor, (str, int)) or str(cursor) in seen:
                raise CollectionError("invalid or repeated pagination cursor")
            seen.add(str(cursor))

    def collect(self):
        try:
            kind = self.source.get("kind")
            if kind == "github":
                self.github()
            elif kind == "lark":
                self.lark()
            elif kind == "production" and self.source.get("transport") == "http-json":
                self.http_json()
            else:
                raise CollectionError("use host read-only tools and an ingest envelope for this source kind")
        except (CollectionError, KeyError, TypeError, ValueError) as exc:
            self.errors.append(str(exc))
        complete = not self.errors
        self.coverage.update({"requests_this_invocation": self.requests,
                              "requests_this_run": self.total_requests,
                              "responses_in_checkpoint": len(self.cache), "records": len(self.items),
                              "reused_responses": self.reused_responses,
                              "collection_started_at": self.started_at, "collection_finished_at": now(),
                              "earliest_response_at": min(self.response_times) if self.response_times else None,
                              "latest_response_at": max(self.response_times) if self.response_times else None})
        return {"schema_version": 1, "source_id": self.source["id"], "run_id": self.run_id,
                "scope_hash": self.scope_hash, "status": "complete" if complete else "partial",
                "mode": "full", "enumeration_complete": complete, "permissions_verified": complete,
                "collected_at": now(), "coverage": self.coverage, "items": self.items,
                "deleted_ids": [], "errors": self.errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true", help="reuse this run's successful response checkpoints")
    args = parser.parse_args()
    try:
        state = Path(args.state).expanduser().resolve()
        import context
        with context.locked(state):
            config = context.config_read(state)
            source = next(s for s in config["sources"] if s["id"] == args.source)
            manifest = context.current_read(state, config)
            run_id = manifest["run_id"]
            scope_hash = manifest["sources"][args.source]["scope_hash"]
            if context.source_hash(source) != scope_hash:
                raise CollectionError("source configuration changed after scan; create a new scan before collection")
            checkpoint_file = context.inside(state, "collector-checkpoints/" + digest([run_id, args.source, scope_hash]) + ".json")
            prior = json.loads(checkpoint_file.read_text()) if checkpoint_file.exists() else {}
            cache = prior.get("cache", {}) if args.resume else {}
            collector = Collector(source, run_id, scope_hash, cache,
                                  lambda data: atomic_json(checkpoint_file, data), prior.get("request_count", 0))
            envelope = collector.collect()
            atomic_json(args.output, envelope)
        print(json.dumps({"source_id": args.source, "status": envelope["status"],
                          "items": len(envelope["items"]), "errors": envelope["errors"],
                          "output": str(Path(args.output).resolve())}, ensure_ascii=False))
        return 0 if envelope["status"] == "complete" else 2
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        print(json.dumps({"error": "invalid source configuration or run state", "type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
