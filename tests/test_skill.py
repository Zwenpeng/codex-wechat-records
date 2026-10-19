"""Synthetic-only regression tests. No real processes, accounts or messages."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/wechat-records/scripts'
sys.path.insert(0, str(SCRIPTS))
import key_material as material
import local_state
import run_cli
import export_chat
import wechat


def fake_page(key, salt=b'synthetic-salt!!'):
    salt = salt.ljust(16, b'0')[:16]
    page = bytearray(salt + bytes((index % 251 for index in range(4080))))
    mac_key = hashlib.pbkdf2_hmac('sha512', key, bytes(value ^ 0x3a for value in salt), 2, dklen=32)
    page[4032:] = hmac.digest(mac_key, bytes(page[16:4032]) + struct.pack('<I', 1), 'sha512')
    return bytes(page)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wechat-synthetic-')
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'CODEX_WECHAT_HOME': str(self.root / 'private')})
        self.env.start()
        self.db = self.root / 'account/db_storage'
        (self.db / 'session').mkdir(parents=True)
        self.key = bytes(range(32))
        self.page = fake_page(self.key)
        (self.db / 'session/session.db').write_bytes(self.page)
        self.keys = {'session/session.db': {'enc_key': self.key.hex(), 'salt': self.page[:16].hex()}}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_key_validation_detects_wrong_key_tampering_and_short_pages(self):
        self.assertTrue(material.verify_key(self.key, self.page))
        self.assertFalse(material.verify_key(bytes(32), self.page))
        tampered = bytearray(self.page); tampered[20] ^= 1
        self.assertFalse(material.verify_key(self.key, tampered))
        self.assertFalse(material.verify_key(self.key, self.page[:100]))

    def test_raw_key_and_salt_candidates_match_without_passphrase_derivation(self):
        blob = b"name:x'" + self.key.hex().encode() + self.page[:16].hex().encode() + b"'"
        found = material.match_keys([blob, b'not a candidate'], {'session/session.db': self.page})
        self.assertEqual(found['session/session.db']['enc_key'], self.key.hex())

    def test_odd_hex_and_boundary_fragments_do_not_crash_or_match(self):
        self.assertEqual(list(material.candidate_keys([b'x' + b'a' * 65 + b'x'])), [])
        self.assertEqual(list(material.candidate_keys([b'x' + b'a' * 200 + b'x'])), [])

    def test_profile_commit_keeps_prior_generation_on_failed_import(self):
        folder = local_state.profile_dir('main')
        result = material.save_profile(folder, self.db, self.keys)
        self.assertTrue(result['session_ready'])
        before = (folder / 'config.json').read_bytes()
        with self.assertRaises(ValueError):
            material.save_profile(folder, self.db, {'session/session.db': {'enc_key': bytes(32).hex()}})
        self.assertEqual(before, (folder / 'config.json').read_bytes())
        material.save_profile(folder, self.db, self.keys)
        self.assertEqual(len(list(folder.glob('keys-*.json'))), 2)

    def test_profile_rejects_another_account_and_retains_incremental_cursor(self):
        folder = local_state.profile_dir('main')
        material.save_profile(folder, self.db, self.keys)
        local_state.atomic_json(folder / 'last_check.json', {'synthetic_friend': 42})
        old_config = (folder / 'config.json').read_bytes()
        other = self.root / 'other-account/db_storage'
        (other / 'session').mkdir(parents=True)
        (other / 'session/session.db').write_bytes(self.page)
        with self.assertRaises(ValueError):
            material.save_profile(folder, other, self.keys)
        self.assertEqual((folder / 'config.json').read_bytes(), old_config)
        self.assertEqual(json.loads((folder / 'last_check.json').read_text())['synthetic_friend'], 42)

    def test_malicious_key_paths_cannot_escape_db_directory(self):
        raw = {**self.keys, '../outside.db': {'enc_key': self.key.hex()},
               '/absolute.db': {'enc_key': self.key.hex()}}
        _, keys, _ = material.validated_keys(raw, self.db)
        self.assertEqual(list(keys), ['session/session.db'])

    def test_profile_names_and_config_paths_cannot_escape(self):
        for name in ('../outside', '/tmp/escape', 'a/b', ''):
            with self.assertRaises(ValueError):
                local_state.profile_dir(name)
        folder = local_state.profile_dir('main')
        material.save_profile(folder, self.db, self.keys)
        config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
        config['keys_file'] = str(self.root / 'outside.json')
        local_state.atomic_json(folder / 'config.json', config)
        with self.assertRaises(ValueError):
            material.load_profile(folder)

    def test_import_command_emits_counts_never_keys(self):
        source = self.root / 'input.json'
        source.write_text(json.dumps(self.keys), encoding='utf-8')
        output = io.StringIO()
        args = wechat.parser().parse_args(['import-keys', '--db-dir', str(self.db), '--keys-file', str(source)])
        with contextlib.redirect_stdout(output):
            wechat.initialize(args)
        result = json.loads(output.getvalue())
        self.assertEqual(result['matched_databases'], 1)
        self.assertNotIn(self.key.hex(), output.getvalue())
        self.assertNotIn(self.page[:16].hex(), output.getvalue())

    def test_source_database_bytes_never_change(self):
        original = (self.db / 'session/session.db').read_bytes()
        folder = local_state.profile_dir('main')
        material.save_profile(folder, self.db, self.keys)
        material.load_profile(folder)
        self.assertEqual(original, (self.db / 'session/session.db').read_bytes())

    def test_export_refuses_existing_target_and_accepts_new_path(self):
        existing = self.root / 'existing.md'; existing.write_text('keep', encoding='utf-8')
        with self.assertRaises(ValueError):
            run_cli.validate_destination(str(existing))
        run_cli.validate_destination(str(self.root / 'new.md'))
        self.assertEqual(existing.read_text(encoding='utf-8'), 'keep')

    def test_export_race_cannot_truncate_another_accounts_file(self):
        target = self.root / 'new.md'
        run_cli.validate_destination(str(target))
        target.write_text('another export', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            export_chat.publish('current export', {}, target)
        self.assertEqual(target.read_text(encoding='utf-8'), 'another export')

    def test_query_allowlist_rejects_send_and_upstream_init(self):
        for command in ('send', 'setup', 'init', '--config'):
            args = wechat.parser().parse_args(['run', '--', command])
            with self.assertRaises(ValueError), patch.object(wechat, 'child') as child:
                wechat.run(args)
            child.assert_not_called()

    def test_installer_can_install_into_another_users_location(self):
        target = self.root / 'friend account/skills'
        result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'install.py'), '--skills-dir', str(target)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / 'wechat-records/SKILL.md').is_file())
        duplicate = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'install.py'), '--skills-dir', str(target)],
                                   capture_output=True, text=True)
        self.assertNotEqual(duplicate.returncode, 0)
        update = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'install.py'), '--skills-dir', str(target), '--replace'],
                                capture_output=True, text=True)
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertEqual(len(list((target.parent / 'skill-backups').glob('*/SKILL.md'))), 1)

    def test_installer_rejects_nested_junction_or_symlink(self):
        skill = self.root / 'friend/skills/wechat-records'
        skill.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'wechat.py'
        sentinel.write_text('preserve', encoding='utf-8')
        link = skill / 'scripts'
        if os.name == 'nt':
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
            if result.returncode:
                self.skipTest('Cannot create a synthetic junction on this host.')
        else:
            link.symlink_to(outside, target_is_directory=True)
        updated = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'install.py'), '--skills-dir', str(skill.parent), '--replace'],
                                 capture_output=True, text=True)
        self.assertNotEqual(updated.returncode, 0)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'preserve')

    def test_win64_memory_layout_and_wrong_process_fail_closed(self):
        import ctypes
        import windows_scan
        if os.name == 'nt' and ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(windows_scan.MBI), 48)
            with self.assertRaises(ValueError):
                windows_scan.scan_blobs(os.getpid(), timeout=10)


class UpstreamIntegrationTests(unittest.TestCase):
    def test_wrapper_forwards_help_output_from_hidden_windows_child(self):
        if not local_state.python_exe().is_file():
            self.skipTest('Install the managed CLI to run the wrapper transport test.')
        result = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'wechat.py'), 'cli-help', 'history'],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--start-time', result.stdout)
        self.assertIn('--limit', result.stdout)

    def test_real_cli_isolates_cursors_caches_and_queries_synthetic_sessions(self):
        # Execute in the managed venv to test exactly the dependency used in production.
        managed = local_state.python_exe()
        if not managed.is_file():
            self.skipTest('Install the managed CLI to run the upstream integration test.')
        code = r'''
import contextlib, hashlib, hmac, io, json, os, sqlite3, struct, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from unittest.mock import patch
import key_material, local_state, run_cli
with tempfile.TemporaryDirectory(prefix='wechat-integration-') as temp:
    root=Path(temp); os.environ['CODEX_WECHAT_HOME']=str(root/'private')
    db=root/'account/db_storage'; (db/'session').mkdir(parents=True)
    key=bytes(range(32)); salt=b'fixture-salt!!!!'
    page=bytearray(salt+bytes(4080))
    mac=hashlib.pbkdf2_hmac('sha512',key,bytes(x^0x3a for x in salt),2,dklen=32)
    page[4032:]=hmac.digest(mac,bytes(page[16:4032])+struct.pack('<I',1),'sha512')
    (db/'session/session.db').write_bytes(page)
    keys={'session/session.db':{'enc_key':key.hex()}}
    first=local_state.profile_dir('first'); second=local_state.profile_dir('second')
    key_material.save_profile(first,db,keys); key_material.save_profile(second,db,keys)
    plain=root/'synthetic.sqlite3'
    with contextlib.closing(sqlite3.connect(plain)) as connection, connection:
        connection.execute('CREATE TABLE SessionTable(username,unread_count,summary,last_timestamp,last_msg_type,last_msg_sender,last_sender_display_name)')
        connection.execute('INSERT INTO SessionTable VALUES(?,?,?,?,?,?,?)',('synthetic_friend',1,'Synthetic deadline',1700000000,1,'',''))
    cli=run_cli.load_cli(first)
    from wechat_cli.core.db_cache import DBCache
    from wechat_cli.core import config
    from wechat_cli.commands import new_messages
    assert Path(config.STATE_DIR)==first
    assert Path(new_messages.STATE_FILE)==first/'last_check.json'
    assert Path(DBCache.CACHE_DIR).is_relative_to(first)
    old_cache=DBCache.CACHE_DIR
    output=io.StringIO()
    def cache_get(self,relative):
        return str(plain) if relative.replace('\\','/')=='session/session.db' else None
    with patch.object(DBCache,'get',cache_get), contextlib.redirect_stdout(output):
        cli.main(args=['--config',str(first/'config.json'),'sessions','--limit','1'],standalone_mode=False)
    assert json.loads(output.getvalue())[0]['last_message']=='Synthetic deadline'
    run_cli.load_cli(second)
    assert Path(new_messages.STATE_FILE)==second/'last_check.json'
    assert DBCache.CACHE_DIR!=old_cache
    assert Path(DBCache.CACHE_DIR).is_relative_to(second)
    print('synthetic upstream integration passed')
'''
        result = subprocess.run([str(managed), '-X', 'utf8', '-c', code, str(SCRIPTS)],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('integration passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
