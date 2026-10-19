"""Run the pinned upstream CLI with profile-specific cache and cursor locations."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import sys

from key_material import load_profile
from local_state import private_dir

COMMANDS = {'sessions', 'history', 'search', 'contacts', 'members', 'export',
            'stats', 'unread', 'new-messages', 'favorites'}


def load_cli(folder=None):
    # Import config first: modules copy these constants when imported.
    from wechat_cli.core import config
    if folder is not None:
        folder = Path(folder).resolve()
        value, _, _ = load_profile(folder)
        config.STATE_DIR = str(folder)
        config.CONFIG_FILE = str(folder / 'config.json')
        config.KEYS_FILE = value['keys_file']
        from wechat_cli.core.db_cache import DBCache
        cache = Path(value['cache_dir'])
        private_dir(cache)
        DBCache.CACHE_DIR = str(cache)
        DBCache.MTIME_FILE = str(cache / '_mtimes.json')
    from wechat_cli.main import cli
    if not COMMANDS.issubset(cli.commands):
        raise RuntimeError('安装的是另一套同名 wechat-cli，缺少数据库查询命令，请修复独立环境。')
    entries = importlib.metadata.distribution('wechat-cli').entry_points
    if not any(entry.name == 'wechat-cli' and entry.value == 'wechat_cli.main:cli' for entry in entries):
        raise RuntimeError('wechat-cli 的程序入口不匹配，请重新安装独立运行环境。')
    if folder is not None:
        # AppContext uses these module-global paths even with --config set.
        from wechat_cli.commands import new_messages
        new_messages.STATE_FILE = str(folder / 'last_check.json')
    return cli


def validate_destination(value):
    if value is None:
        return None
    target = Path(value).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('输出文件已存在，请使用新文件名。')
    if not target.parent.is_dir():
        raise ValueError('输出目录不存在，请先选择已存在的目录。')
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli-help')
    parser.add_argument('--profile-dir')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.cli_help:
        import click
        cli = load_cli()
        command = cli if args.cli_help == 'root' else cli.commands.get(args.cli_help)
        if command is None:
            raise ValueError('未知查询命令，请查看 cli-help。')
        print(command.get_help(click.Context(command, info_name=args.cli_help)))
        return 0
    if not args.profile_dir:
        raise ValueError('缺少账号配置目录。')
    forwarded = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    if not forwarded or forwarded[0] not in COMMANDS:
        raise ValueError('此入口仅支持已列出的读取和查询命令。')
    # Upstream does not allow abbreviated options; global --config is never forwarded.
    cli = load_cli(args.profile_dir)
    try:
        if forwarded[0] == 'export':
            import click
            import export_chat
            with cli.commands['export'].make_context('export', forwarded[1:], parent=click.Context(cli)) as parsed:
                destination = validate_destination(parsed.params['output_path'])
                return export_chat.execute(parsed.params, args.profile_dir, destination)
        _, _, missing = load_profile(args.profile_dir)
        if missing:
            print(json.dumps({'type': 'warning', 'code': 'missing_databases',
                              'message': '部分数据库缺少密钥，查询结果可能不完整。',
                              'missing_databases': missing}, ensure_ascii=False), file=sys.stderr)
        def invoke():
            return cli.main(args=['--config', str(Path(args.profile_dir) / 'config.json'), *forwarded],
                            prog_name='wechat-records', standalone_mode=False)
        code = invoke()
        if isinstance(code, int):
            return code
    except OSError:
        raise
    except Exception as exc:
        import click
        if isinstance(exc, click.exceptions.Exit):
            return exc.exit_code
        if isinstance(exc, click.ClickException):
            print(json.dumps({'type': 'error', 'code': 'invalid_arguments',
                              'message': '命令参数无效，请运行 cli-help 查看参数。',
                              'detail': exc.format_message()}, ensure_ascii=False), file=sys.stderr)
            return exc.exit_code
        raise
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, ImportError, KeyError, TypeError, sqlite3.Error) as exc:
        from errors import payload
        print(json.dumps(payload(exc), ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
