#!/usr/bin/env python3
"""Stage existing UTF-8 files, build an offline review, and apply explicit approvals.

Only `apply --execute --authorization ...` writes source files. No third-party deps.
"""
import argparse
import collections
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid


class ReviewError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def text_bytes(path):
    data = Path(path).read_bytes()
    require(b'\0' not in data, f'Not a text file: {path}')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ReviewError(f'Only UTF-8 text is supported: {path}') from exc
    return data


def init_session(session, paths, title='文件修改审阅'):
    session = Path(session).expanduser().resolve()
    require(not session.exists(), f'Session already exists; choose a new directory: {session}')
    entries, seen = [], set()
    for i, raw in enumerate(paths):
        requested = Path(raw).expanduser().absolute()
        target = requested.resolve(strict=True)
        require(target.is_file(), f'Not a regular file: {target}')
        require(target not in seen, f'Duplicate source / symlink alias: {target}')
        require(session not in target.parents, 'Source files cannot be inside the staging session')
        seen.add(target)
        content = text_bytes(target)
        entries.append((dict(id=f'f{i:03}', path=str(target), requested_path=str(requested),
                             before_sha256=digest(content), mode=stat.S_IMODE(target.stat().st_mode),
                             label=target.name, detail=target.parent.name, group='待审文件',
                             reason='', risk=''), content))
    require(entries, 'Provide at least one source file')
    session.mkdir(parents=True)
    (session / 'before').mkdir()
    (session / 'after').mkdir()
    for entry, content in entries:
        for folder in ('before', 'after'):
            (session / folder / (entry['id'] + '.txt')).write_bytes(content)
    manifest = dict(schema=1, session_id=uuid.uuid4().hex, title=title,
                    created_at=now(), files=[entry for entry, _ in entries])
    write_json(session / 'manifest.json', manifest)
    return dict(session=str(session), files=len(entries),
                next='Edit only after/*.txt and reason/risk/labels in manifest.json, then run build.')


def origin_problem(entry, allowed_hashes):
    path = Path(entry['path'])
    try:
        if Path(entry['requested_path']).resolve(strict=True) != path:
            return 'Source symlink target changed'
        if not path.is_file() or path.is_symlink():
            return 'Original target is no longer a regular file'
        if stat.S_IMODE(path.stat().st_mode) != entry['mode']:
            return 'Source permissions changed since staging'
        if digest(path.read_bytes()) not in allowed_hashes:
            return 'Source content changed since staging'
    except OSError as exc:
        return str(exc)
    return None


def heading(lines, pos):
    for line in reversed(lines[:pos + 1]):
        if line.startswith('#'):
            return line.lstrip('# ').strip()
    return '文本差异'


def newline_label(text):
    if not text:
        return '空文件'
    kinds = []
    if '\r\n' in text:
        kinds.append('CRLF')
    if '\n' in text.replace('\r\n', ''):
        kinds.append('LF')
    if '\r' in text.replace('\r\n', ''):
        kinds.append('CR')
    return (' / '.join(kinds) or '单行') + ('' if text.endswith(('\n', '\r')) else ' · 末尾无换行')


def make_file(entry, before, after):
    old, new = before.decode('utf-8'), after.decode('utf-8')
    # Compare raw lines, including terminators, so CRLF and missing-final-newline edits
    # remain reviewable and can be reconstructed without normalizing other content.
    raw_a, raw_b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    a, b = old.splitlines(), new.splitlines()
    hunks, ops = [], []
    for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, raw_a, raw_b, autojunk=False).get_opcodes():
        hi = None
        if tag != 'equal':
            hi = len(hunks)
            hunks.append(dict(id=f"{entry['id']}-h{hi:03}", tag=tag, a0=a0, a1=a1,
                              b0=b0, b1=b1, heading=heading(b, b0) if b0 < b1 else heading(a, a0)))
        ops.append([tag, a0, a1, b0, b1, hi])
    return dict(entry, short=entry['path'], before=old, after=new,
                after_sha256=digest(after), a=a, b=b, hunks=hunks, ops=ops,
                beforeFormat=newline_label(old), afterFormat=newline_label(new))


def build_review(session):
    session = Path(session).resolve()
    require(not (session / 'review.json').exists() and not (session / 'index.html').exists(),
            'This review is frozen. Create a new session for revised candidates.')
    manifest = read_json(session / 'manifest.json')
    files, groups = [], []
    for entry in manifest['files']:
        before = text_bytes(session / 'before' / (entry['id'] + '.txt'))
        require(digest(before) == entry['before_sha256'], f"Original snapshot altered: {entry['path']}")
        problem = origin_problem(entry, {entry['before_sha256']})
        require(not problem, f"{problem}: {entry['path']}")
        after = text_bytes(session / 'after' / (entry['id'] + '.txt'))
        if before == after:
            continue
        require(entry.get('reason', '').strip() and entry.get('risk', '').strip(),
                f"Fill reason and risk (or explicitly say no material tradeoff) for {entry['path']}")
        files.append(make_file(entry, before, after))
        if entry['group'] not in groups:
            groups.append(entry['group'])
    require(files, 'No candidate changes; nothing to review')
    data = dict(schema=1, auditId='staged-file-review-' + manifest['session_id'],
                title=manifest['title'], snapshotDate=manifest['created_at'][:10],
                groups=groups, files=files, totalHunks=sum(len(f['hunks']) for f in files))
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    encoded = encoded.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = (Path(__file__).resolve().parents[1] / 'assets' / 'review.html').read_text(encoding='utf-8')
    require(template.count('/*__AUDIT_DATA__*/') == 1, 'HTML template data slot is invalid')
    write_json(session / 'review.json', data)
    (session / 'index.html').write_text(template.replace('/*__AUDIT_DATA__*/', encoded), encoding='utf-8')
    return dict(html=str(session / 'index.html'), files=len(files), changes=data['totalHunks'],
                originals_unchanged=True, next='Wait for user annotation and explicit instruction to apply.')


def load_review(session, decisions_path):
    session = Path(session)
    data = read_json(session / 'review.json')
    packet_bytes = Path(decisions_path).read_bytes()
    packet = json.loads(packet_bytes)
    require(packet.get('schema') == 1 and packet.get('auditId') == data['auditId'],
            'Decision file belongs to a different review session')
    decisions = packet.get('decisions')
    require(isinstance(decisions, dict), 'Decision file has no decisions object')
    ids = {h['id'] for f in data['files'] for h in f['hunks']}
    require(set(decisions) <= ids, 'Decision file contains unknown change IDs')
    for choice in decisions.values():
        require(isinstance(choice, dict) and choice.get('status') in {'accept', 'keep', 'pending', 'adjust'}
                and isinstance(choice.get('note'), str), 'Invalid decision value')
    exported = packet.get('files', [])
    require(isinstance(exported, list) and len(exported) == len(data['files']), 'File list mismatch')
    by_path = {f['path']: f for f in exported}
    require(len(by_path) == len(exported), 'Duplicate exported file')
    for f in data['files']:
        item = by_path.get(f['path'], {})
        require(item.get('before_sha256') == f['before_sha256'] and
                item.get('after_sha256') == f['after_sha256'], f"Snapshot mismatch: {f['path']}")
        require(digest(f['before'].encode('utf-8')) == f['before_sha256'] and
                digest(f['after'].encode('utf-8')) == f['after_sha256'], 'Frozen review content altered')
        require(digest(text_bytes(session / 'before' / (f['id'] + '.txt'))) == f['before_sha256'] and
                digest(text_bytes(session / 'after' / (f['id'] + '.txt'))) == f['after_sha256'],
                'Staged files changed after review; create a new review session')
        rebuilt = make_file(f, f['before'].encode('utf-8'), f['after'].encode('utf-8'))
        require(rebuilt['hunks'] == f['hunks'] and rebuilt['ops'] == f['ops'], 'Frozen diff metadata altered')
    return data, decisions, packet_bytes


def selected_bytes(file, decisions):
    a = file['before'].splitlines(keepends=True)
    b = file['after'].splitlines(keepends=True)
    result = []
    for tag, a0, a1, b0, b1, hi in file['ops']:
        approved = tag != 'equal' and decisions.get(file['hunks'][hi]['id'], {}).get('status') == 'accept'
        result.extend(b[b0:b1] if approved else a[a0:a1])
    return ''.join(result).encode('utf-8')


def atomic_replace(path, content, mode):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.file-review-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply_review(session, decisions_path, execute=False, authorization=None):
    require(not execute or bool(authorization and authorization.strip()),
            '--execute requires --authorization with the user instruction authorizing this application')
    session = Path(session).resolve()
    data, decisions, packet_bytes = load_review(session, decisions_path)
    plan, totals = [], collections.Counter()
    for f in data['files']:
        counts = collections.Counter(decisions.get(h['id'], {}).get('status', 'pending') for h in f['hunks'])
        totals.update(counts)
        target = selected_bytes(f, decisions)
        target_sha = digest(target)
        problem = origin_problem(f, {f['before_sha256'], target_sha})
        action = 'blocked' if problem else 'unchanged' if target_sha == f['before_sha256'] else 'apply'
        if not problem and action == 'apply' and digest(Path(f['path']).read_bytes()) == target_sha:
            action = 'already_applied'
        plan.append(dict(id=f['id'], path=f['path'], counts=dict(counts), action=action,
                         problem=problem, target_sha256=target_sha, target=target, entry=f))
    report = dict(schema=1, auditId=data['auditId'], at=now(), execute=execute,
                  authorization=authorization if execute else None, decisions_sha256=digest(packet_bytes),
                  counts=dict(totals), needs_revision=[dict(id=h['id'], path=f['path'],
                    note=decisions[h['id']]['note']) for f in data['files'] for h in f['hunks']
                    if decisions.get(h['id'], {}).get('status') == 'adjust'])
    if execute:
        receipts = session / 'receipts'
        receipts.mkdir(exist_ok=True)
        token = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        (receipts / (token + '-decisions.json')).write_bytes(packet_bytes)
        report_path = receipts / (token + '-result.json')
        report['receipt'] = str(report_path)
        # Commit independently per file. Check again immediately before replacement;
        # a blocked file never authorizes overwriting it or undoing other approved files.
        for step in plan:
            if step['action'] != 'apply':
                continue
            entry = step['entry']
            problem = origin_problem(entry, {entry['before_sha256']})
            if problem:
                step.update(action='blocked', problem=problem)
                continue
            try:
                atomic_replace(step['path'], step['target'], entry['mode'])
                require(digest(Path(step['path']).read_bytes()) == step['target_sha256'], 'Write verification failed')
                step['action'] = 'applied'
            except (OSError, ReviewError) as exc:
                step.update(action='blocked', problem=str(exc))
    report['files'] = [{k: v for k, v in p.items() if k not in {'target', 'entry'}} for p in plan]
    report['blocked_files'] = sum(p['action'] == 'blocked' for p in plan)
    if execute:
        write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Snapshot existing source files without modifying them')
    init.add_argument('session'); init.add_argument('--files', nargs='+', required=True)
    init.add_argument('--title', default='文件修改审阅')
    build = commands.add_parser('build', help='Freeze candidates and generate an offline HTML')
    build.add_argument('session')
    apply = commands.add_parser('apply', help='Preview application; writes only with --execute')
    apply.add_argument('session'); apply.add_argument('--decisions', required=True)
    apply.add_argument('--execute', action='store_true'); apply.add_argument('--authorization')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = init_session(args.session, args.files, args.title)
        elif args.command == 'build':
            result = build_review(args.session)
        else:
            result = apply_review(args.session, args.decisions, args.execute, args.authorization)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('blocked_files') else 0
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
