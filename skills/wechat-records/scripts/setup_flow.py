"""First-use workflow. Non-interactive mode reports missing choices instead of guessing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from diagnostics import legacy_metadata, profile_health
from key_material import collect_pages, match_keys, save_profile
from local_state import profile_dir, profile_lock


def choose_database(explicit, candidates, *, interactive, prompt=input):
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    if len(candidates) == 1:
        return candidates[0]
    if not interactive:
        return None
    if candidates:
        for index, path in enumerate(candidates, 1):
            print(f'{index}. {path}', file=sys.stderr)
        reply = prompt('请选择账号目录编号（直接回车取消）：').strip()
        if reply.isdigit() and 1 <= int(reply) <= len(candidates):
            return candidates[int(reply) - 1]
        return None
    reply = prompt('请输入目标账号 db_storage 的完整路径（直接回车取消）：').strip().strip('"')
    return str(Path(reply).expanduser().resolve()) if reply else None


def setup(args, backend):
    steps = []

    def result(state, message, **values):
        return {'type': 'setup_report', 'profile': args.profile, 'state': state,
                'message': message, 'steps': steps, 'query_verified': False, **values}

    def finish(health, **values):
        verified = False
        if args.verify_chat and health['keys_validated']:
            verified = backend.verify(args.profile, args.verify_chat)
            steps.append({'stage': 'query', 'state': 'verified' if verified else 'failed',
                          'message': '指定聊天查询验证通过。' if verified else '指定聊天查询验证未通过，请检查联系人和数据库结构。'})
        state = 'query_failed' if args.verify_chat and not verified else health['state']
        report = result(state, '指定聊天查询未通过。' if state == 'query_failed' else health['message'],
                        health=health, **values)
        report['query_verified'] = verified
        return report, 0 if state == 'ready' else 3

    # The install subcommand is idempotent and does not access WeChat records.
    installed = backend.install_ready()
    if not installed:
        print('正在安装并检查独立 CLI…', file=sys.stderr)
        backend.install_runtime()
    steps.append({'stage': 'runtime', 'state': 'ready', 'message': '独立 CLI 已通过命令能力检查。'})
    health = profile_health(args.profile)
    same_directory = not args.db_dir or (health.get('db_dir') and
                      Path(args.db_dir).expanduser().resolve() == Path(health['db_dir']).resolve())
    if health['state'] == 'ready' and same_directory and not any((args.keys_file, args.scan)):
        steps.append({'stage': 'keys', 'state': 'ready', 'message': '现有账号密钥已通过验证。'})
        return finish(health)
    available = backend.db_candidates(args.search_root)
    target = choose_database(args.db_dir or health.get('db_dir'), available,
                             interactive=not args.non_interactive and sys.stdin.isatty())
    if not target:
        return result('needs_account', '请选择目标账号后，添加 --db-dir 再运行 setup。',
                      db_candidates=available), 2
    db_dir, pages = collect_pages(target)
    folder = profile_dir(args.profile)
    # Reject another account before reading process memory or importing its secrets.
    config_path = folder / 'config.json'
    if config_path.is_file():
        prior = json.loads(config_path.read_text(encoding='utf-8'))
        if Path(prior['db_dir']).resolve() != db_dir:
            return result('profile_conflict', '这个别名已绑定另一账号，请用新的 --profile。'), 2
    steps.append({'stage': 'account', 'state': 'selected', 'message': '已确定目标数据库目录。'})
    key_file = Path(args.keys_file).expanduser() if args.keys_file else None
    legacy = legacy_metadata()
    if key_file is None and not args.scan and legacy['db_dir']:
        legacy_file = Path.home() / '.wechat-cli/all_keys.json'
        if Path(legacy['db_dir']).expanduser().resolve() == db_dir and legacy_file.is_file():
            key_file = legacy_file
    if key_file is None and not args.scan:
        return result('needs_keys', '请用 --keys-file 指定现有密钥；如需实验提取，明确添加 --scan --pid。',
                      db_dir=str(db_dir), existing_profile=health), 2
    if args.scan and key_file is not None:
        raise ValueError('请在导入密钥和现场提取之间选择一种方式。')
    with profile_lock(folder):
        if key_file is not None:
            keys = json.loads(key_file.read_text(encoding='utf-8-sig'))
        else:
            if os.name != 'nt' or not args.pid:
                return result('needs_process', '现场提取需要 Windows x64，并用 --pid 指定已登录目标账号的 Weixin.exe。',
                              wechat_processes=backend.wechat_processes()), 2
            print('正在尝试实验性只读提取；不会输出密钥。', file=sys.stderr)
            keys = match_keys(backend.scan(args.pid, args.timeout), pages)
        saved = save_profile(folder, db_dir, keys)
    health = profile_health(args.profile)
    steps.append({'stage': 'keys', 'state': health['state'], 'message': health['message']})
    return finish(health, imported=saved)
