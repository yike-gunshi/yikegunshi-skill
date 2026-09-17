#!/usr/bin/env python3
"""Score full-body evidence, not mentions. Unobservable criteria remain unscored.

Input: --fixture DIR --document handoff.md [--ledger coverage.json]
Optional --topic-document / --plain-document verifies additive, non-sticky brief.
Accepts items/materials/sources lists or mappings, identity via source_id/key/path/
locator, complete/status fields and fingerprints/versions. Explicit SHA fields
must match the source body. This is only the objective portion of rubric.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def ledger_records(content, bodies, external):
    """Normalize meaningful material identities without assuming a required JSON schema."""
    local_paths = {key[6:]: key for key in bodies if key.startswith("local:")}
    external_locators = {item["locator"]: external["source_id"] + ":" + item["id"] for item in external["items"]}
    root = content.get("project_root") or content.get("workspace", {}).get("repository_root")

    def identify(value):
        if not isinstance(value, str):
            return None
        if value in bodies:
            return value
        if value in external_locators:
            return external_locators[value]
        relative = value.removeprefix("./")
        if relative in local_paths:
            return local_paths[relative]
        # Different authors use local:, project:, file: for the same relative path.
        prefix, colon, suffix = relative.partition(":")
        if colon and prefix in ("local", "project", "file") and suffix in local_paths:
            return local_paths[suffix]
        if root:
            try:
                relative = Path(value).relative_to(root).as_posix()
                if relative in local_paths:
                    return local_paths[relative]
            except ValueError:
                pass
        return None

    normalized = {}
    for field in ("items", "materials", "sources"):
        collection = content.get(field, [])
        records = collection.items() if isinstance(collection, dict) else ((None, record) for record in collection) if isinstance(collection, list) else []
        for mapping_key, record in records:
            if not isinstance(record, dict):
                continue
            candidates = [mapping_key] + [record.get(name) for name in ("key", "source_id", "path", "locator")]
            source_id, item_id = record.get("source_id"), record.get("id")
            if source_id and item_id:
                candidates.append(str(source_id) + ":" + str(item_id))
            identified = {key for candidate in candidates if (key := identify(candidate)) is not None}
            if len(identified) == 1:
                normalized.setdefault(identified.pop(), []).append(record)
    return normalized


def ledger_evidence(record, key, body, document_has_body, ledger, external):
    expected_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    hash_fields = {name: record[name] for name in ("sha256", "content_sha256", "raw_fingerprint") if name in record and record[name] is not None}
    hashes_match = all(isinstance(value, str) and value.lower().removeprefix("sha256:") == expected_hash for value in hash_fields.values())
    declared_content_matches = "content" not in record or record["content"] == body
    fingerprint = record.get("fingerprint") or record.get("snapshot_fingerprint")
    version = record.get("version")
    if not key.startswith("local:") and version is not None:
        source_item = next(item for item in external["items"] if external["source_id"] + ":" + item["id"] == key)
        version_valid = str(version) == str(source_item.get("version"))
    else:
        version_valid = isinstance(version, str) and bool(version.strip())
    provenance = hashes_match and bool(hash_fields or fingerprint or version_valid)
    state = any(name in record and record[name] is not None for name in ("status", "complete", "collected_at", "captured_at"))
    state = state or any(ledger.get(name) for name in ("started_at", "created_at", "collected_at"))
    listed = document_has_body and declared_content_matches
    return {"listed": bool(listed), "provenance": bool(listed and provenance), "state": bool(listed and state),
            "hash_fields_checked": list(hash_fields), "hashes_match": hashes_match if hash_fields else None,
            "declared_content_matches": declared_content_matches}


def evaluate(fixture: Path, document: Path, ledger: Path | None = None,
             topic_document: Path | None = None, plain_document: Path | None = None,
             brief_marker: str = "BRIEF_ONLY_COLLAB_729", phase: str = "initial") -> dict:
    expected = json.loads((fixture / "expected.json").read_text())
    # Prefer the immutable initial artifact snapshot over the later-mutated worktree.
    project = fixture / "source" if (fixture / "source").is_dir() else Path(expected["project"])
    external = json.loads((fixture / "external-full.json").read_text())
    text = document.read_text(encoding="utf-8")
    bodies = {}
    for rel, fingerprint in expected["files"].items():
        payload = (project / rel).read_bytes()
        if hashlib.sha256(payload).hexdigest() != fingerprint:
            raise ValueError("Initial fixture source changed: " + rel + "; score against the immutable initial/source snapshot")
        bodies["local:" + rel] = payload.decode("utf-8")
    if phase == "incremental":
        bodies["local:src/notification_worker.py"] = bodies.pop("local:src/worker.py")
        bodies["local:src/service.py"] = bodies["local:src/service.py"].replace("POSTPONE_HOURS = 24", "POSTPONE_HOURS = 48")
        del bodies["local:docs/new-work.md"]
    bodies.update({external["source_id"] + ":" + item["id"]: item["content"] for item in external["items"]})
    found = {key: body in text for key, body in bodies.items()}
    criteria = [{"id": "raw_material", "score": round(20 * sum(found.values()) / len(found), 2), "max": 20,
                 "evidence": {"whole_bodies_found": sum(found.values()), "whole_bodies_expected": len(found),
                              "missing": [key for key, ok in found.items() if not ok]}}]
    if ledger:
        content = json.loads(ledger.read_text())
        items = ledger_records(content, bodies, external)
        records = {}
        for key, body in bodies.items():
            candidates = [ledger_evidence(record, key, body, found[key], content, external) for record in items.get(key, [])]
            records[key] = max(candidates, key=lambda evidence: sum(evidence[name] for name in ("listed", "provenance", "state"))) if candidates else {"listed": False, "provenance": False, "state": False}
        numerator = sum(sum(record[name] for name in ("listed", "provenance", "state")) for record in records.values())
        criteria.append({"id": "coverage_ledger", "score": round(10 * numerator / (3 * len(bodies)), 2), "max": 10,
                         "evidence": records})
    else:
        criteria.append({"id": "coverage_ledger", "score": None, "max": 10, "reason": "No machine-readable ledger supplied; not inferred from prose."})
    if topic_document and plain_document and phase == "initial":
        topic = topic_document.read_text(encoding="utf-8")
        plain = plain_document.read_text(encoding="utf-8")
        retained = all(body in topic and body in plain for body in bodies.values())
        isolated = brief_marker in topic and brief_marker not in plain
        criteria.append({"id": "brief_isolation", "score": (5 if retained else 0) + (5 if isolated else 0), "max": 10,
                         "evidence": {"all_bodies_in_both": retained, "brief_only_in_topic": isolated}})
    else:
        reason = ("Incremental source content changed. Compare topic removal with the subjective judge; source-body equality across versions is not a valid criterion."
                  if phase == "incremental" else "Paired topic/plain exports with an exclusive brief marker not supplied.")
        criteria.append({"id": "brief_isolation", "score": None, "max": 10, "reason": reason})
    executed = [c for c in criteria if c["score"] is not None]
    return {"schema_version": 1, "method": "Exact whole material body containment and enumerated provenance records.",
            "phase": phase, "oracle": "Immutable initial source snapshot, expected SHA-256 validation, and the published deterministic incremental mutations.",
            "criteria": criteria, "observed_score": sum(c["score"] for c in executed),
            "observed_max": sum(c["max"] for c in executed), "subjective_points_unscored": 60,
            "human_review": "not performed", "limitations": "Does not judge explanation correctness or prove 99 percent understanding. Incremental retained external bodies are checked; their stale/permission-failure labeling needs judge review."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--topic-document", type=Path)
    parser.add_argument("--plain-document", type=Path)
    parser.add_argument("--brief-marker", default="BRIEF_ONLY_COLLAB_729")
    parser.add_argument("--phase", choices=["initial", "incremental"], default="initial")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.fixture, args.document, args.ledger, args.topic_document, args.plain_document, args.brief_marker, args.phase)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
