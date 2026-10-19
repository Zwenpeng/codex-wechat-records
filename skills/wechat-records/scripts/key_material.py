"""Validate raw SQLCipher 4 key candidates against a database's first page.

No process access, output or filesystem writes occur at import time.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import struct

from local_state import atomic_json

PAGE_SIZE = 4096
SQLITE_HEADER = b'SQLite format 3\0'


def verify_key(key, page):
    if len(key) != 32 or len(page) != PAGE_SIZE or page.startswith(SQLITE_HEADER):
        return False
    # The raw encryption key is NOT derived again with 256000 iterations.
    # SQLCipher still derives a separate HMAC key with two PBKDF2 iterations.
    mac_salt = bytes(value ^ 0x3a for value in page[:16])
    mac_key = hashlib.pbkdf2_hmac('sha512', key, mac_salt, 2, dklen=32)
    digest = hmac.new(mac_key, page[16:4032] + struct.pack('<I', 1), hashlib.sha512).digest()
    return hmac.compare_digest(digest, page[4032:4096])


def collect_pages(db_dir):
    db_dir = Path(db_dir).expanduser().resolve(strict=True)
    if not db_dir.is_dir() or db_dir.name != 'db_storage':
        raise ValueError('请选择目标账号的 db_storage 目录。')
    pages = {}
    for path in sorted(db_dir.rglob('*.db')):
        if path.is_symlink() or not path.resolve().is_relative_to(db_dir):
            continue
        with path.open('rb') as stream:
            page = stream.read(PAGE_SIZE)
        if len(page) == PAGE_SIZE and not page.startswith(SQLITE_HEADER):
            pages[path.relative_to(db_dir).as_posix()] = page
    if not pages:
        raise ValueError('目录中未发现符合当前加密页格式的数据库，请检查账号目录。')
    return db_dir, pages


def candidate_keys(blobs):
    seen = set()
    for blob in blobs:
        for match in re.finditer(rb'(?<![0-9a-fA-F])[0-9a-fA-F]{64,192}(?![0-9a-fA-F])', blob):
            text = match.group()
            if len(text) % 2:
                continue
            raw = bytes.fromhex(text.decode('ascii'))
            for offset in (0, 16):
                candidate = raw[offset:offset + 32]
                if len(candidate) == 32 and candidate not in seen:
                    seen.add(candidate)
                    yield candidate


def match_keys(blobs, pages):
    found = {}
    by_salt = {}
    for relative, page in pages.items():
        by_salt.setdefault(page[:16], []).append((relative, page))
    for key in candidate_keys(blobs):
        for salt, group in by_salt.items():
            if all(relative in found for relative, _ in group):
                continue
            for relative, page in group:
                if relative not in found and verify_key(key, page):
                    found[relative] = {'enc_key': key.hex(), 'salt': salt.hex()}
    return found


def validated_keys(raw, db_dir):
    if not isinstance(raw, dict):
        raise ValueError('密钥文件必须是 JSON 对象。')
    db_dir, pages = collect_pages(db_dir)
    found = {}
    for relative, entry in raw.items():
        if not isinstance(relative, str) or relative.startswith('_'):
            continue
        relative = relative.replace('\\', '/')
        if relative not in pages or not isinstance(entry, dict):
            continue
        try:
            key = bytes.fromhex(entry.get('enc_key', ''))
        except (ValueError, TypeError):
            continue
        if verify_key(key, pages[relative]):
            found[relative] = {'enc_key': key.hex(), 'salt': pages[relative][:16].hex()}
    if not found:
        raise ValueError('没有密钥能匹配这个账号的数据库，请确认账号与密钥来源；现有配置未改变。')
    return db_dir, found, sorted(set(pages) - set(found))


def save_profile(folder, db_dir, keys):
    db_dir, found, missing = validated_keys(keys, db_dir)
    folder = Path(folder).resolve()
    prior_path = folder / 'config.json'
    if prior_path.exists():
        prior = json.loads(prior_path.read_text(encoding='utf-8'))
        if Path(prior['db_dir']).resolve() != db_dir:
            raise ValueError('这个别名已绑定另一个账号目录，请使用新的 --profile。')
    # New immutable key filename + atomic config commit avoids mixed-account pairs.
    generation = secrets.token_hex(8)
    key_file = folder / f'keys-{generation}.json'
    cache = folder / f'cache-{generation}'
    atomic_json(key_file, found)
    config = {'db_dir': str(db_dir), 'keys_file': str(key_file),
              'decrypted_dir': str(cache), 'decoded_image_dir': str(folder / 'decoded-images'),
              'cache_dir': str(cache)}
    atomic_json(folder / 'config.json', config)
    return {'matched_databases': len(found), 'missing_databases': missing,
            'session_ready': 'session/session.db' in found,
            'contact_ready': any(name.startswith('contact/') for name in found),
            'message_shards': sum(bool(re.fullmatch(r'message/message_\d+\.db', name)) for name in found)}


def load_profile(folder):
    folder = Path(folder).resolve()
    path = folder / 'config.json'
    if not path.is_file():
        raise ValueError('这个账号尚未初始化，请先运行 setup 或导入现有密钥。')
    config = json.loads(path.read_text(encoding='utf-8'))
    for field in ('keys_file', 'cache_dir', 'decrypted_dir', 'decoded_image_dir'):
        target = Path(config[field]).resolve()
        if not target.is_relative_to(folder) or target == folder:
            raise ValueError('账号的密钥与缓存路径必须位于其独立私有目录中。')
    raw = json.loads(Path(config['keys_file']).read_text(encoding='utf-8'))
    _, valid, missing = validated_keys(raw, config['db_dir'])
    if len(valid) != len(raw):
        raise ValueError('部分已保存的密钥不再匹配该账号，请重新导入或初始化这个账号。')
    return config, valid, missing
