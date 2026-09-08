#!/usr/bin/env python3
"""Deterministic regression tests; all writes stay under a temporary directory."""
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import review


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='staged-review-test-')
        self.root = Path(self.tmp.name)
        self.session = self.root / 'review-session'

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, before, after, count=1):
        sources = []
        for i in range(count):
            p = self.root / f'source-{i}.txt'
            p.write_bytes(before)
            p.chmod(0o640)
            sources.append(p)
        review.init_session(self.session, sources, '测试审阅')
        manifest = review.read_json(self.session / 'manifest.json')
        for entry in manifest['files']:
            (self.session / 'after' / (entry['id'] + '.txt')).write_bytes(after)
            entry['reason'] = '按要求调整指定行'
            entry['risk'] = '未接受的行需要逐字节保留'
        review.write_json(self.session / 'manifest.json', manifest)
        review.build_review(self.session)
        return sources, review.read_json(self.session / 'review.json')

    def packet(self, data, decisions=None):
        p = self.root / 'opinions.json'
        review.write_json(p, dict(schema=1, auditId=data['auditId'],
                                 decisions=decisions or {}, files=[dict(path=f['path'],
                                 before_sha256=f['before_sha256'], after_sha256=f['after_sha256'])
                                 for f in data['files']]))
        return p

    def all_accept(self, data):
        return {h['id']: dict(status='accept', note='') for f in data['files'] for h in f['hunks']}

    def run_apply(self, packet, execute=True):
        return review.apply_review(self.session, packet, execute, '用户要求：按已标记的内容修改' if execute else None)

    def test_staging_never_writes_source(self):
        sources, data = self.fixture(b'old\n', b'new\n')
        self.assertEqual(sources[0].read_bytes(), b'old\n')
        self.assertEqual((self.session / 'before/f000.txt').read_bytes(), b'old\n')
        self.assertEqual(data['files'][0]['before'], 'old\n')
        self.assertTrue((self.session / 'index.html').is_file())

    def test_default_is_dry_run_and_execute_requires_authorization(self):
        sources, data = self.fixture(b'old\n', b'new\n')
        packet = self.packet(data, self.all_accept(data))
        self.assertEqual(self.run_apply(packet, False)['files'][0]['action'], 'apply')
        self.assertEqual(sources[0].read_bytes(), b'old\n')
        with self.assertRaises(review.ReviewError):
            review.apply_review(self.session, packet, True)
        self.assertEqual(sources[0].read_bytes(), b'old\n')

    def test_mixed_accept_keep_pending_adjust_preserves_crlf(self):
        old = b'A=old\r\ns1\r\ns2\r\nB=old\r\ns3\r\ns4\r\nC=old\r\ns5\r\ns6\r\nD=old'
        new = old.replace(b'=old', b'=new')
        sources, data = self.fixture(old, new)
        hunks = data['files'][0]['hunks']
        self.assertEqual(len(hunks), 4)
        choices = {h['id']: dict(status=s, note='需要另一种写法' if s == 'adjust' else '')
                   for h, s in zip(hunks, ['accept', 'keep', 'pending', 'adjust'])}
        result = self.run_apply(self.packet(data, choices))
        self.assertEqual(sources[0].read_bytes(), old.replace(b'A=old', b'A=new'))
        self.assertEqual(len(result['needs_revision']), 1)
        self.assertEqual(result['counts'], dict(accept=1, keep=1, pending=1, adjust=1))
        self.assertEqual(stat.S_IMODE(sources[0].stat().st_mode), 0o640)

    def test_insertion_applies_without_unapproved_deletion(self):
        old = b'alpha\nkeep1\nkeep2\nkeep3\nremove?\nend\n'
        new = b'added\nalpha\nkeep1\nkeep2\nkeep3\nend\n'
        sources, data = self.fixture(old, new)
        f = data['files'][0]
        self.assertEqual([h['tag'] for h in f['hunks']], ['insert', 'delete'])
        decisions = {f['hunks'][0]['id']: dict(status='accept', note='')}
        self.run_apply(self.packet(data, decisions))
        self.assertEqual(sources[0].read_bytes(), b'added\n' + old)

    def test_deletion_and_no_final_newline_apply_exactly(self):
        sources, data = self.fixture('一\n删除\n末尾\n'.encode(), '一\n末尾'.encode())
        self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertEqual(sources[0].read_bytes(), '一\n末尾'.encode())

    def test_newline_only_change_is_reviewable(self):
        sources, data = self.fixture(b'line\r\n', b'line\n')
        self.assertEqual(len(data['files'][0]['hunks']), 1)
        self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertEqual(sources[0].read_bytes(), b'line\n')

    def test_pending_and_note_only_never_apply(self):
        old = b'\xef\xbb\xbfprivate\r\n'
        sources, data = self.fixture(old, b'candidate\n')
        hid = data['files'][0]['hunks'][0]['id']
        result = self.run_apply(self.packet(data, {hid: dict(status='pending', note='我还没决定')}))
        self.assertEqual(result['files'][0]['action'], 'unchanged')
        self.assertEqual(sources[0].read_bytes(), old)

    def test_source_drift_blocks_only_affected_file(self):
        sources, data = self.fixture(b'old\n', b'new\n', count=2)
        sources[0].write_bytes(b'user edited after staging\n')
        result = self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertEqual(result['blocked_files'], 1)
        self.assertEqual(sources[0].read_bytes(), b'user edited after staging\n')
        self.assertEqual(sources[1].read_bytes(), b'new\n')
        self.assertTrue(Path(result['receipt']).exists())

    def test_reapplying_same_decisions_is_idempotent(self):
        sources, data = self.fixture(b'old\n', b'new\n')
        packet = self.packet(data, self.all_accept(data))
        self.run_apply(packet)
        modified = sources[0].stat().st_mtime_ns
        result = self.run_apply(packet)
        self.assertEqual(result['files'][0]['action'], 'already_applied')
        self.assertEqual(sources[0].stat().st_mtime_ns, modified)

    def test_different_batch_or_unknown_id_cannot_apply(self):
        sources, data = self.fixture(b'old\n', b'new\n')
        p = self.packet(data, {'not-a-real-change': dict(status='accept', note='')})
        with self.assertRaises(review.ReviewError):
            self.run_apply(p)
        obj = review.read_json(self.packet(data, self.all_accept(data)))
        obj['auditId'] = 'another-review'; review.write_json(p, obj)
        with self.assertRaises(review.ReviewError):
            self.run_apply(p)
        self.assertEqual(sources[0].read_bytes(), b'old\n')

    def test_candidate_mutated_after_review_stops_before_all_writes(self):
        sources, data = self.fixture(b'old\n', b'new\n', count=2)
        (self.session / 'after/f001.txt').write_bytes(b'not what the user reviewed\n')
        with self.assertRaises(review.ReviewError):
            self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertTrue(all(p.read_bytes() == b'old\n' for p in sources))

    def test_snapshot_mismatch_cannot_apply(self):
        sources, data = self.fixture(b'old\n', b'new\n', count=2)
        p = self.packet(data, self.all_accept(data)); obj = review.read_json(p)
        obj['files'][1]['after_sha256'] = 'wrong'; review.write_json(p, obj)
        with self.assertRaises(review.ReviewError):
            self.run_apply(p)
        self.assertTrue(all(x.read_bytes() == b'old\n' for x in sources))

    def test_build_detects_accidental_source_edit(self):
        p = self.root / 'file.txt'; p.write_bytes(b'original\n')
        review.init_session(self.session, [p]); p.write_bytes(b'changed directly\n')
        with self.assertRaises(review.ReviewError):
            review.build_review(self.session)
        self.assertEqual(p.read_bytes(), b'changed directly\n')

    def test_freeze_cannot_be_overwritten(self):
        _, data = self.fixture(b'old\n', b'new\n')
        initial = (self.session / 'review.json').read_bytes()
        with self.assertRaises(review.ReviewError):
            review.build_review(self.session)
        self.assertEqual(initial, (self.session / 'review.json').read_bytes())

    def test_symlink_retarget_is_detected(self):
        real = self.root / 'actual.txt'; real.write_bytes(b'old\n')
        alias = self.root / 'alias.txt'; alias.symlink_to(real)
        review.init_session(self.session, [alias])
        manifest = review.read_json(self.session / 'manifest.json')
        manifest['files'][0].update(reason='change', risk='review first')
        review.write_json(self.session / 'manifest.json', manifest)
        (self.session / 'after/f000.txt').write_bytes(b'new\n')
        review.build_review(self.session); data = review.read_json(self.session / 'review.json')
        alt = self.root / 'alternate.txt'; alt.write_bytes(b'old\n')
        alias.unlink(); alias.symlink_to(alt)
        result = self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertEqual(result['blocked_files'], 1)
        self.assertEqual(real.read_bytes(), b'old\n'); self.assertEqual(alt.read_bytes(), b'old\n')

    def test_permission_change_blocks_application(self):
        sources, data = self.fixture(b'old\n', b'new\n')
        sources[0].chmod(0o600)
        result = self.run_apply(self.packet(data, self.all_accept(data)))
        self.assertEqual(result['blocked_files'], 1)
        self.assertEqual(sources[0].read_bytes(), b'old\n')

    def test_duplicate_alias_and_non_utf8_rejected(self):
        p = self.root / 'file.txt'; p.write_bytes(b'original')
        alias = self.root / 'alias.txt'; alias.symlink_to(p)
        with self.assertRaises(review.ReviewError):
            review.init_session(self.session, [p, alias])
        self.assertFalse(self.session.exists())
        p.write_bytes(b'\xff\x00')
        with self.assertRaises(review.ReviewError):
            review.init_session(self.session, [p])
        self.assertFalse(self.session.exists())

    def test_html_embeds_exact_data_without_executing_source_markup(self):
        old = b'<script>window.reviewInjected=true</script>\n'
        _, data = self.fixture(old, old + b'new\n')
        html = (self.session / 'index.html').read_text()
        self.assertNotIn(old.decode().strip(), html)
        self.assertIn('\\u003cscript>', html)
        self.assertEqual(data['files'][0]['before'].encode(), old)

    def test_atomic_replace_failure_leaves_original(self):
        p = self.root / 'file.txt'; p.write_bytes(b'original')
        with patch('review.os.replace', side_effect=OSError('simulated failure')):
            with self.assertRaises(OSError):
                review.atomic_replace(p, b'new', 0o640)
        self.assertEqual(p.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('.file-review-*')), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
