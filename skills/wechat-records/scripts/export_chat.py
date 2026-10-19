"""Verified export using the pinned upstream query engine and local metadata."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

from key_material import collect_pages, load_profile


def is_shard(name):
    return re.fullmatch(r'message/message_\d+\.db', name.replace('\\', '/')) is not None


def source_stamp(directory):
    """Track database and WAL changes during this query, without reading bodies."""
    result = {}
    for path in Path(directory).rglob('*'):
        if path.is_file() and path.name.endswith(('.db', '.db-wal')):
            try:
                stat = path.stat()
                result[path.relative_to(directory).as_posix()] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                result[path.relative_to(directory).as_posix()] = None
    return result


def make_report(chat, requested, lines, *, shard_count, checked_shards, missing, failures,
                source_changed=False, query_start='', query_end=''):
    warnings = []
    if not shard_count:
        warnings.append('没有可用密钥的消息分片，不能据此认定聊天没有消息。')
    relevant_missing = [name for name in missing if is_shard(name) or name.startswith('contact/')]
    if relevant_missing:
        warnings.append('部分消息或联系人数据库缺少密钥，结果可能不完整。')
    if failures:
        warnings.append('部分数据库或消息读取失败，已保留可读取内容。')
    if source_changed:
        warnings.append('查询期间本地数据库发生变化，结果不是同一时间点的完整快照。')
    if warnings:
        status, message = 'partial', '部分导出：存在缺失或读取变化，请查看报告。'
    elif not lines:
        status, message = 'empty', '当前本地数据和指定时间范围内没有消息。'
    elif len(lines) < requested:
        status, message = 'fewer_available', '已导出当前范围内可读取的消息，数量不足请求条数。'
    else:
        status, message = 'success', '已导出请求条数；当前可用本地数据未发现读取异常。'
    dates = [match.group(1) for line in lines
             if (match := re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]', line))]
    return {'type': 'export_report', 'status': status, 'message': message, 'chat': chat,
            'requested_count': requested, 'exported_count': len(lines),
            'oldest': min(dates) if dates else None, 'newest': max(dates) if dates else None,
            'query_start': query_start or None, 'query_end': query_end or None,
            'message_shards_with_keys': shard_count, 'checked_message_shards': checked_shards,
            'missing_databases': sorted(missing), 'failures': failures, 'warnings': warnings,
            'source_changed': source_changed,
            'scope': '仅校验当前电脑已有数据，不包含未同步、已删除或手机端独有消息。'}


def collect(app, options):
    from wechat_cli.core.contacts import get_contact_names, resolve_username
    from wechat_cli.core import messages
    from wechat_cli.core.messages import collect_chat_history, parse_time_range, validate_pagination
    validate_pagination(options['limit'], 0, limit_max=None)
    start, end = parse_time_range(options['start_time'], options['end_time'])
    failures = []
    contact_paths = [Path(app.decrypted_dir) / 'contact/contact.db']
    cached_contact = app.cache.get('contact/contact.db')
    if cached_contact:
        contact_paths.append(Path(cached_contact))
    contact_ok = False
    for path in contact_paths:
        if not path.is_file():
            continue
        try:
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
                connection.execute('SELECT username,nick_name,remark FROM contact').fetchall()
            contact_ok = True
            break
        except (OSError, sqlite3.Error):
            continue
    if not contact_ok:
        failures.append({'database': 'contact/contact.db', 'code': 'contact_read_failed',
                         'message': '联系人库无法读取，名称或发送者解析可能不完整。'})
    username = resolve_username(options['chat_name'], app.cache, app.decrypted_dir)
    if not username:
        raise ValueError('未匹配到聊天对象，请先查询联系人并使用唯一 username。')
    names = get_contact_names(app.cache, app.decrypted_dir)
    display = names.get(username, username)
    table_name = 'Msg_' + hashlib.md5(username.encode('utf-8')).hexdigest()
    tables = []
    checked = 0
    for relative in app.msg_db_keys:
        try:
            path = app.cache.get(relative)
            if not path:
                raise ValueError('missing_cache')
            with closing(sqlite3.connect(path)) as connection:
                checked += 1
                exists = connection.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',
                                            ('table', table_name)).fetchone()
                if exists:
                    # Check columns even for empty tables; discovery must not hide schema errors.
                    connection.execute(f'SELECT local_id,local_type,create_time,real_sender_id,'
                                       f'message_content,WCDB_CT_message_content FROM [{table_name}] LIMIT 0')
                    tables.append({'db_path': path, 'table_name': table_name})
        except (OSError, ValueError, sqlite3.Error):
            failures.append({'database': relative.replace('\\', '/'), 'code': 'shard_read_failed',
                             'message': '消息分片无法读取或数据库结构不兼容。'})
    context = {'query': options['chat_name'], 'username': username, 'display_name': display,
               'is_group': '@chatroom' in username, 'message_tables': tables}
    # The pinned engine swallows decoding errors. Observe the structured result
    # during this single-process query, not the rendered placeholder text.
    original_decode = messages.decompress_content
    decode_failures = 0

    def checked_decode(content, kind):
        nonlocal decode_failures
        value = original_decode(content, kind)
        if value is None and isinstance(content, bytes):
            decode_failures += 1
        return value

    messages.decompress_content = checked_decode
    try:
        lines, row_failures = collect_chat_history(context, names, app.display_name_fn,
                                                  start_ts=start, end_ts=end, limit=options['limit'])
    finally:
        messages.decompress_content = original_decode
    if decode_failures:
        failures.append({'code': 'message_decode_failed', 'count': decode_failures,
                         'message': '部分候选消息无法解压，导出保留占位提示。'})
    if row_failures:
        # The upstream exception text can include payload fragments. Report only count/code.
        failures.append({'code': 'message_read_failed', 'count': len(row_failures),
                         'message': '部分消息未能解析或读取。'})
    return context, lines, failures, checked


def render(context, lines, options, report):
    from wechat_cli.commands.export import _format_markdown, _format_txt
    formatter = _format_markdown if options['fmt'] == 'markdown' else _format_txt
    text = formatter(context['display_name'], '群聊' if context['is_group'] else '私聊',
                     f"{options['start_time'] or '最早'} ~ {options['end_time'] or '最新'}",
                     datetime.now().astimezone().strftime('%Y-%m-%d %H:%M'), lines)
    notice = '\n'.join([report['message'], *report['warnings'], report['scope']])
    # Keep the native export header intact while making partial results visible in the file.
    return text.rstrip() + '\n\n---\n导出校验\n' + notice + '\n'


def execute(options, folder, destination):
    from wechat_cli.core.context import AppContext
    config, keys, missing_before = load_profile(folder)
    stamp = source_stamp(config['db_dir'])
    app = AppContext(str(Path(folder) / 'config.json'))
    try:
        context, lines, failures, checked = collect(app, options)
        _, pages = collect_pages(config['db_dir'])
        after = source_stamp(config['db_dir'])
        discovered = {name for name in set(stamp) | set(after) if name.endswith('.db')}
        missing = sorted(set(missing_before) | ((set(pages) | discovered) - set(keys)))
        report = make_report(context['display_name'], options['limit'], lines,
                             shard_count=sum(is_shard(name) for name in keys), checked_shards=checked,
                             missing=missing, failures=failures,
                             source_changed=stamp != after,
                             query_start=options['start_time'], query_end=options['end_time'])
        report['profile'] = Path(folder).name
        report['output'] = str(destination) if destination else None
        content = render(context, lines, options, report)
        publish(content, report, destination)
        return 3 if report['status'] == 'partial' else 0
    finally:
        app.cache.cleanup()


def publish(content, report, destination):
    if destination is not None:
        with Path(destination).open('x', encoding='utf-8') as stream:
            stream.write(content)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(content)
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
