"""Readiness/wizard/export regression tests with synthetic metadata and no live account."""
import contextlib
import io
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_skill as fixtures

fake_page, SCRIPTS, ROOT = fixtures.fake_page, fixtures.SCRIPTS, fixtures.ROOT

sys.path.insert(0, str(SCRIPTS))
import diagnostics
import errors
import export_chat
import key_material
import local_state
import setup_flow
import wechat


class ReportTests(unittest.TestCase):
    def report(self, count, **updates):
        options = dict(shard_count=2, checked_shards=2, missing=[], failures=[])
        options.update(updates)
        lines = [f'[2026-10-01 09:{index:02d}] synthetic message' for index in range(count)]
        return export_chat.make_report('Synthetic friend', 5, lines, **options)

    def test_success_short_empty_and_partial_are_distinct(self):
        self.assertEqual(self.report(5)['status'], 'success')
        self.assertEqual(self.report(2)['status'], 'fewer_available')
        self.assertEqual(self.report(0)['status'], 'empty')
        self.assertEqual(self.report(5, missing=['message/message_2.db'])['status'], 'partial')
        self.assertEqual(self.report(5, failures=[{'code': 'shard_read_failed'}])['status'], 'partial')
        self.assertEqual(self.report(5, source_changed=True)['status'], 'partial')

    def test_non_message_missing_library_does_not_claim_chat_data_lost(self):
        result = self.report(5, missing=['solitaire/solitaire.db'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['missing_databases'], ['solitaire/solitaire.db'])

    def test_report_does_not_contain_message_body(self):
        self.assertNotIn('synthetic message', json.dumps(self.report(5)))

    def test_no_message_shards_is_partial_not_empty(self):
        self.assertEqual(self.report(0, shard_count=0, checked_shards=0)['status'], 'partial')

    def test_chinese_diagnosis_distinguishes_runtime_and_keys(self):
        value = {'runtime_installed': False, 'runtime_capabilities_ok': False, 'legacy_keys_exist': False}
        state = {'state': 'not_initialized'}
        self.assertEqual(diagnostics.classify(value, state)[0], 'needs_install')
        value.update(runtime_installed=True)
        self.assertEqual(diagnostics.classify(value, state)[0], 'runtime_error')
        value.update(runtime_capabilities_ok=True, legacy_keys_exist=True)
        self.assertEqual(diagnostics.classify(value, state)[0], 'legacy_keys_available')
        self.assertEqual(diagnostics.classify(value, {'state': 'partial', 'message': '缺分片'})[0], 'partial')

    def test_unknown_and_known_versions_do_not_claim_scanner_verified(self):
        self.assertEqual(diagnostics.extraction_status([])['status'], 'unknown')
        self.assertEqual(diagnostics.extraction_status([{'version': '4.1.12.1'}])['status'], 'experimental')

    def test_json_error_never_echoes_bad_secret_input(self):
        try:
            json.loads('secret-not-json')
        except ValueError as exc:
            public = errors.payload(exc)
        self.assertEqual(public['code'], 'invalid_json')
        self.assertNotIn('secret-not-json', json.dumps(public))


class WizardTests(unittest.TestCase):
    def setUp(self):
        fixtures.SkillTests.setUp(self)
        self.legacy = patch.object(setup_flow, 'legacy_metadata', return_value={'db_dir': None})
        self.legacy.start()
        self.backend = SimpleNamespace(install_ready=Mock(return_value=True), install_runtime=Mock(),
                                       db_candidates=Mock(return_value=[str(self.db)]),
                                       wechat_processes=Mock(return_value=[]), scan=Mock(),
                                       verify=Mock(return_value=True))

    def tearDown(self):
        self.legacy.stop()
        fixtures.SkillTests.tearDown(self)

    def complete_keys(self):
        for name in ('contact/contact.db', 'message/message_0.db'):
            target = self.db / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(fake_page(self.key))
            self.keys[name] = {'enc_key': self.key.hex()}
        path = self.root / 'existing-keys.json'
        path.write_text(json.dumps(self.keys), encoding='utf-8')
        return path

    def test_setup_installs_and_imports_without_exposing_records(self):
        keys = self.complete_keys()
        self.backend.install_ready.return_value = False
        args = wechat.parser().parse_args(['setup', '--non-interactive', '--db-dir', str(self.db), '--keys-file', str(keys)])
        with contextlib.redirect_stderr(io.StringIO()):
            report, code = setup_flow.setup(args, self.backend)
        self.assertEqual(code, 0)
        self.assertEqual(report['state'], 'ready')
        self.assertFalse(report['query_verified'])
        self.assertNotIn(self.key.hex(), json.dumps(report))
        self.backend.install_runtime.assert_called_once()
        self.backend.scan.assert_not_called()
        self.backend.verify.assert_not_called()

    def test_setup_multiple_accounts_requires_choice_without_mutation(self):
        self.backend.db_candidates.return_value = [str(self.db), str(self.root / 'other/db_storage')]
        args = wechat.parser().parse_args(['setup', '--non-interactive'])
        report, code = setup_flow.setup(args, self.backend)
        self.assertEqual((report['state'], code), ('needs_account', 2))
        self.assertFalse((local_state.profile_dir('main') / 'config.json').exists())

    def test_setup_no_keys_does_not_implicitly_scan(self):
        report, code = setup_flow.setup(wechat.parser().parse_args(['setup', '--non-interactive']), self.backend)
        self.assertEqual((report['state'], code), ('needs_keys', 2))
        self.backend.scan.assert_not_called()

    def test_ready_profile_is_reused_and_named_chat_verification_is_explicit(self):
        self.complete_keys()
        folder = local_state.profile_dir('main')
        key_material.save_profile(folder, self.db, self.keys)
        before = (folder / 'config.json').read_bytes()
        report, code = setup_flow.setup(wechat.parser().parse_args(['setup', '--non-interactive',
                                                                 '--verify-chat', 'Synthetic friend']), self.backend)
        self.assertEqual(code, 0)
        self.assertTrue(report['query_verified'])
        self.backend.verify.assert_called_once_with('main', 'Synthetic friend')
        self.assertEqual(before, (folder / 'config.json').read_bytes())

    def test_named_chat_verification_failure_is_not_reported_as_ready(self):
        self.complete_keys()
        key_material.save_profile(local_state.profile_dir('main'), self.db, self.keys)
        self.backend.verify.return_value = False
        report, code = setup_flow.setup(wechat.parser().parse_args(['setup', '--non-interactive',
                                                                 '--verify-chat', 'Missing synthetic friend']), self.backend)
        self.assertEqual((report['state'], code), ('query_failed', 3))
        self.assertFalse(report['query_verified'])

    def test_partial_import_does_not_report_ready(self):
        path = self.root / 'keys.json'; path.write_text(json.dumps(self.keys), encoding='utf-8')
        report, code = setup_flow.setup(wechat.parser().parse_args(['setup', '--non-interactive', '--keys-file', str(path)]), self.backend)
        self.assertEqual((report['state'], code), ('partial', 3))

    def test_resource_and_search_libraries_do_not_satisfy_query_readiness(self):
        for name in ('contact/contact_fts.db', 'message/message_resource.db'):
            target = self.db / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(fake_page(self.key))
            self.keys[name] = {'enc_key': self.key.hex()}
        key_material.save_profile(local_state.profile_dir('main'), self.db, self.keys)
        health = diagnostics.profile_health('main')
        self.assertEqual(health['state'], 'partial')
        self.assertEqual(health['message_shards'], 0)
        self.assertFalse(health['contact_ready'])


class ExportIntegrationTests(unittest.TestCase):
    def test_actual_pinned_engine_exports_synthetic_messages_and_reports_partial_shard(self):
        import subprocess
        managed = local_state.python_exe()
        if not managed.exists():
            self.skipTest('Install the managed CLI for synthetic integration.')
        code = r'''
import contextlib, hashlib, io, json, os, sqlite3, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
from test_skill import fake_page
import key_material,local_state,run_cli,export_chat
with tempfile.TemporaryDirectory(prefix='verified-export-') as temp:
 root=Path(temp);os.environ['CODEX_WECHAT_HOME']=str(root/'private')
 db=root/'account/db_storage';keys={};key=bytes(range(32))
 for name in ('contact/contact.db','session/session.db','message/message_0.db'):
  path=db/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(fake_page(key));keys[name]={'enc_key':key.hex()}
 profile=local_state.profile_dir('main');key_material.save_profile(profile,db,keys)
 plain=root/'synthetic.sqlite3';username='synthetic_friend';table='Msg_'+hashlib.md5(username.encode()).hexdigest()
 with contextlib.closing(sqlite3.connect(plain)) as con,con:
  con.execute('CREATE TABLE contact(username,nick_name,remark)')
  con.execute('INSERT INTO contact VALUES(?,?,?)',(username,'Synthetic friend',''))
  con.execute(f'CREATE TABLE [{table}](local_id,local_type,create_time,real_sender_id,message_content,WCDB_CT_message_content)')
  con.executemany(f'INSERT INTO [{table}] VALUES(?,?,?,?,?,?)',[(i,1,1700000000+i,0,'Synthetic text '+str(i),0) for i in range(5)])
 cli=run_cli.load_cli(profile)
 from wechat_cli.core.db_cache import DBCache
 from wechat_cli.core import contacts
 def cache_get(self,relative):return str(plain)
 options={'chat_name':username,'limit':3,'start_time':'','end_time':'','fmt':'markdown'}
 for mode in ('complete','missing','truncated','decode','contact'):
  extra=db/'message/message_1.db'
  if extra.exists():extra.unlink()
  if mode in ('missing','truncated'):extra.write_bytes(fake_page(key) if mode=='missing' else b'truncated')
  if mode=='decode':
   with contextlib.closing(sqlite3.connect(plain)) as con,con:
    con.execute(f'UPDATE [{table}] SET message_content=?,WCDB_CT_message_content=4 WHERE local_id=4',(b'not-valid-zstd',))
  damaged=root/'damaged.db';damaged.write_bytes(b'invalid sqlite')
  def cache_get(self,relative):
   return str(damaged) if mode=='contact' and relative.replace('\\','/')=='contact/contact.db' else str(plain)
  output=io.StringIO();destination=root/(mode+'.md')
  with patch.object(DBCache,'get',cache_get),patch.object(contacts,'resolve_username',return_value=username),patch.object(contacts,'get_contact_names',return_value={username:'Synthetic friend'}),contextlib.redirect_stdout(output):
   exit_code=export_chat.execute(options,profile,destination)
  report=json.loads(output.getvalue());assert report['exported_count']==3,report
  assert report['status']==('success' if mode=='complete' else 'partial'),report
  assert exit_code==(0 if mode=='complete' else 3)
  if mode=='decode':assert any(f['code']=='message_decode_failed' for f in report['failures']),report
  if mode=='contact':assert any(f['code']=='contact_read_failed' for f in report['failures']),report
  assert 'Synthetic text' not in output.getvalue()
  assert 'Synthetic text' in destination.read_text(encoding='utf-8')
 with patch.object(sys,'argv',['run_cli.py','--profile-dir',str(profile),'--','export','--help']),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
  assert run_cli.main()==0
 with patch.object(sys,'argv',['run_cli.py','--profile-dir',str(profile),'--','export','--','--output=synthetic-chat-name']),patch.object(export_chat,'execute',return_value=0) as execute:
  assert run_cli.main()==0
  assert execute.call_args.args[0]['chat_name']=='--output=synthetic-chat-name'
  assert execute.call_args.args[2] is None
 print('verified export integration passed')
'''
        completed = subprocess.run([str(managed), '-X', 'utf8', '-c', code, str(SCRIPTS), str(ROOT / 'tests')],
                                   capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('integration passed', completed.stdout)


if __name__ == '__main__':
    unittest.main()
