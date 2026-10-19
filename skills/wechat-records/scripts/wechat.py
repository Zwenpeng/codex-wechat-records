"""Portable entry point: install, diagnose, initialize and query local WeChat data."""
from __future__ import annotations

import argparse
import csv
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import venv

from key_material import collect_pages, load_profile, match_keys, save_profile
from local_state import atomic_json, home, private_dir, profile_dir, profile_lock, python_exe
import diagnostics

COMMIT = 'a3789232d4f79bf0b30634d9dadbce71e4acd601'
SOURCE_URL = f'https://codeload.github.com/huohuoer/wechat-cli/zip/{COMMIT}'
SOURCE_SHA256 = '3f3e858d957669528b3f4769296847853d3945ac2ab90a92f2ad6064d0faf4cb'
COMMANDS = ('sessions', 'history', 'search', 'contacts', 'members', 'export',
            'stats', 'unread', 'new-messages', 'favorites')


def flags():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def install():
    if sys.version_info < (3, 10):
        raise RuntimeError('需要 Python 3.10 或以上版本。')
    private_dir(home())
    runtime = home() / 'runtime'
    with profile_lock(home() / 'install-lock', timeout=1):
        receipt = home() / 'runtime.json'
        if receipt.exists() and python_exe().exists():
            prior = json.loads(receipt.read_text(encoding='utf-8'))
            if prior.get('commit') != COMMIT or prior.get('sha256') != SOURCE_SHA256:
                raise RuntimeError('已有其他版本的独立运行环境，请指定新的 CODEX_WECHAT_HOME 安装验证。')
            result = cli_help(None, capture=True)
            if result.returncode == 0 and all(name in result.stdout for name in COMMANDS):
                emit({'installed': True, 'already_installed': True, 'runtime': str(runtime)})
                return
        if not python_exe().exists():
            venv.EnvBuilder(with_pip=True).create(runtime)
        with tempfile.TemporaryDirectory(prefix='wechat-install-', dir=home()) as temp:
            archive = Path(temp) / 'wechat-cli.zip'
            with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
                raw = response.read(20 * 1024 * 1024 + 1)
            if len(raw) > 20 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
                raise RuntimeError('上游源码压缩包校验失败，安装已停止。')
            archive.write_bytes(raw)
            environment = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
            command = [str(python_exe()), '-m', 'pip', '--isolated', 'install',
                       '--index-url', 'https://pypi.org/simple',
                       'click==8.1.8', 'pycryptodome==3.23.0', 'zstandard==0.25.0', str(archive)]
            subprocess.run(command, check=True, env=environment, **flags())
        result = cli_help(None, capture=True)
        if result.returncode or not all(name in result.stdout for name in COMMANDS):
            raise RuntimeError('独立 CLI 未通过命令能力检查，请检查安装。')
        atomic_json(receipt, {'commit': COMMIT, 'sha256': SOURCE_SHA256, 'source': SOURCE_URL,
                              'entry_point': 'wechat_cli.main:cli', 'version': '0.2.4'})
    emit({'installed': True, 'runtime': str(runtime), 'source_commit': COMMIT,
          'commands': list(COMMANDS)})


def child(arguments, capture=False, timeout=None):
    if not python_exe().is_file():
        raise RuntimeError('尚未安装独立运行环境，请先运行 install 或 setup。')
    command = [str(python_exe()), '-X', 'utf8', str(Path(__file__).with_name('run_cli.py')), *arguments]
    # CREATE_NO_WINDOW can detach inherited stdout on Windows. Always pipe it
    # explicitly so successful queries cannot silently lose their records.
    result = subprocess.run(command, capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'),
                            timeout=timeout, **flags())
    if not capture:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    return result


def cli_help(command=None, capture=False):
    return child(['--cli-help', command or 'root'], capture=capture, timeout=20)


def processes():
    if os.name != 'nt':
        return []
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Weixin.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, **flags())
    rows = csv.reader(io.StringIO(result.stdout.decode('mbcs', errors='replace')))
    return [{'name': row[0], 'pid': int(row[1]), **diagnostics.process_metadata(int(row[1]))} for row in rows
            if len(row) >= 2 and row[0].lower() == 'weixin.exe' and row[1].isdigit()]


def candidates(roots=()):
    roots = [Path(value).expanduser() for value in roots]
    roots.append(Path.home() / 'Documents/xwechat_files')
    if os.name == 'nt':
        roots.append(Path.home() / 'xwechat_files')
        directory = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'Tencent/xwechat/config'
        if directory.is_dir():
            for path in directory.glob('*.ini'):
                try:
                    with path.open('rb') as stream:
                        raw = stream.read(4096)
                except OSError:
                    continue
                for encoding in ('utf-8-sig', 'gbk'):
                    try:
                        text = raw.decode(encoding).strip()
                    except UnicodeError:
                        continue
                    if text and not any(value in text for value in '\r\n\0'):
                        roots.append(Path(text) / 'xwechat_files')
                        roots.append(Path(text))
                    break
    else:
        roots.append(Path.home() / 'Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files')
    found = set()
    for root in roots:
        if not root.is_dir():
            continue
        if root.name == 'db_storage':
            found.add(str(root.resolve()))
        for match in root.glob('*/db_storage'):
            if match.is_dir():
                found.add(str(match.resolve()))
        for match in root.glob('xwechat_files/*/db_storage'):
            if match.is_dir():
                found.add(str(match.resolve()))
    return sorted(found)


def diagnosis(args):
    selected = profile_dir(args.profile)
    result = {'runtime_installed': python_exe().is_file(), 'private_home': str(home()),
              'profile': args.profile, 'profile_initialized': (selected / 'config.json').is_file(),
              'wechat_processes': processes(), 'db_candidates': candidates(args.search_root),
              'legacy_config_exists': (Path.home() / '.wechat-cli/config.json').is_file(),
              'legacy_keys_exist': (Path.home() / '.wechat-cli/all_keys.json').is_file()}
    if result['runtime_installed']:
        try:
            check = cli_help(None, capture=True)
            result['runtime_capabilities_ok'] = check.returncode == 0
        except (OSError, RuntimeError, subprocess.SubprocessError):
            result['runtime_capabilities_ok'] = False
    health = diagnostics.profile_health(args.profile)
    state, message, next_steps = diagnostics.classify(result, health)
    result.update(state=state, message=message, next_steps=next_steps, profile_health=health,
                  extraction=diagnostics.extraction_status(result['wechat_processes']),
                  legacy=diagnostics.legacy_metadata())
    return result


def doctor(args):
    emit(diagnosis(args))


class SetupBackend:
    @staticmethod
    def install_ready():
        try:
            return python_exe().is_file() and cli_help(None, capture=True).returncode == 0
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return False

    @staticmethod
    def install_runtime():
        with contextlib.redirect_stdout(sys.stderr):
            install()

    db_candidates = staticmethod(candidates)
    wechat_processes = staticmethod(processes)

    @staticmethod
    def scan(pid, timeout):
        from windows_scan import scan_blobs
        return scan_blobs(pid, timeout)

    @staticmethod
    def verify(profile, chat):
        with profile_lock(profile_dir(profile)):
            result = child(['--profile-dir', str(profile_dir(profile)), '--', 'history', chat,
                            '--limit', '1', '--format', 'json'], capture=True)
        if result.returncode:
            return False
        try:
            value = json.loads(result.stdout)
            return (isinstance(value, dict) and not value.get('failures')
                    and isinstance(value.get('count'), int) and value['count'] > 0
                    and isinstance(value.get('messages'), list) and bool(value['messages']))
        except ValueError:
            return False


def check_profile(args):
    folder = profile_dir(args.profile)
    with profile_lock(folder):
        _, keys, missing = load_profile(folder)
    emit({'profile': args.profile, 'matched_databases': len(keys), 'missing_databases': missing,
          'session_ready': 'session/session.db' in keys,
          'message_shards': sum(name.startswith('message/message_') for name in keys)})


def initialize(args):
    folder = profile_dir(args.profile)
    db_dir, pages = collect_pages(args.db_dir)
    with profile_lock(folder):
        if args.action == 'import-keys':
            keys = json.loads(Path(args.keys_file).expanduser().read_text(encoding='utf-8-sig'))
        else:
            from windows_scan import scan_blobs
            blobs = scan_blobs(args.pid, args.timeout)
            keys = match_keys(blobs, pages)
            del blobs
        result = save_profile(folder, db_dir, keys)
    emit({'profile': args.profile, **result})


def run(args):
    forwarded = args.cli_args
    if forwarded and forwarded[0] == '--':
        forwarded = forwarded[1:]
    if not forwarded or forwarded[0] not in COMMANDS:
        raise ValueError('请选择支持的查询命令：' + ', '.join(COMMANDS))
    folder = profile_dir(args.profile)
    with profile_lock(folder):
        load_profile(folder)
        return child(['--profile-dir', str(folder), '--', *forwarded]).returncode


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument('--profile', default='main', help='Local account profile name (default: main)')
    sub = root.add_subparsers(dest='action', required=True)
    sub.add_parser('install', help='Install the pinned database-query CLI into a private venv')
    wizard = sub.add_parser('setup', help='首次配置向导：安装、选择账号并优先复用现有密钥')
    wizard.add_argument('--non-interactive', action='store_true', help='不提示输入；缺少选择时输出下一步')
    wizard.add_argument('--db-dir', help='目标账号 db_storage 路径')
    wizard.add_argument('--keys-file', help='现有 all_keys.json 路径')
    wizard.add_argument('--search-root', action='append', default=[])
    wizard.add_argument('--scan', action='store_true', help='明确选择实验性只读提取')
    wizard.add_argument('--verify-chat', help='额外查询指定联系人的最多一条消息，只报告验证状态')
    wizard.add_argument('--pid', type=int)
    wizard.add_argument('--timeout', type=int, default=120, choices=range(10, 301), metavar='10..300')
    diagnostic = sub.add_parser('doctor', help='Inspect paths/processes; never read messages or extract keys')
    diagnostic.add_argument('--search-root', action='append', default=[], help='Known xwechat_files root to inspect')
    sub.add_parser('check', help='Verify saved keys against database first pages without showing keys')
    sub.add_parser('profiles', help='List local profile names without reading messages')
    imported = sub.add_parser('import-keys', help='Validate and privately copy an existing key file')
    imported.add_argument('--db-dir', required=True)
    imported.add_argument('--keys-file', required=True)
    scanned = sub.add_parser('initialize', help='Read-only Windows x64 Config.Cipher scan of a selected Weixin.exe PID')
    scanned.add_argument('--db-dir', required=True)
    scanned.add_argument('--pid', required=True, type=int)
    scanned.add_argument('--timeout', type=int, default=120, choices=range(10, 301), metavar='10..300')
    help_command = sub.add_parser('cli-help', help='Show actual upstream command options without initializing a profile')
    help_command.add_argument('command', nargs='?', choices=COMMANDS)
    query = sub.add_parser('run', help='Execute a query command using this account profile')
    query.add_argument('cli_args', nargs=argparse.REMAINDER)
    return root


def main():
    args = parser().parse_args()
    try:
        if args.action == 'install':
            install()
        elif args.action == 'setup':
            from setup_flow import setup
            report, code = setup(args, SetupBackend())
            emit(report)
            return code
        elif args.action == 'doctor':
            doctor(args)
        elif args.action == 'profiles':
            directory = home() / 'profiles'
            emit({'profiles': sorted(p.name for p in directory.iterdir()
                                     if p.is_dir() and (p / 'config.json').is_file()) if directory.exists() else []})
        elif args.action == 'check':
            check_profile(args)
        elif args.action in ('initialize', 'import-keys'):
            initialize(args)
        elif args.action == 'cli-help':
            return cli_help(args.command).returncode
        elif args.action == 'run':
            return run(args)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        from errors import payload
        print(json.dumps(payload(exc), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
