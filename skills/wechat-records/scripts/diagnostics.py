"""Chinese readiness diagnostics and read-only Windows process version metadata."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import json
import os
from pathlib import Path
import re

from key_material import load_profile
from local_state import profile_dir


def process_metadata(pid):
    if os.name != 'nt':
        return {'path': None, 'version': None}
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wt.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return {'path': None, 'version': None}
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wt.DWORD(len(name))
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            return {'path': None, 'version': None}
        try:
            found_version = file_version(name.value)
        except OSError:
            found_version = None
        return {'path': name.value, 'version': found_version}
    finally:
        kernel.CloseHandle(handle)


def file_version(path):
    version = ctypes.WinDLL('version', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wt.LPCWSTR, ctypes.POINTER(wt.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wt.DWORD
    version.GetFileVersionInfoW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wt.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wt.LPCWSTR,
                                      ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wt.UINT)]
    version.VerQueryValueW.restype = wt.BOOL
    ignored = wt.DWORD()
    size = version.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size or size > 4 * 1024 * 1024:
        return None
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, data):
        return None
    pointer, length = ctypes.c_void_p(), wt.UINT()
    if not version.VerQueryValueW(data, '\\', ctypes.byref(pointer), ctypes.byref(length)) or length.value < 16:
        return None
    fixed = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    if fixed[0] != 0xFEEF04BD:
        return None
    return '.'.join(str(n) for n in (fixed[2] >> 16, fixed[2] & 0xffff,
                                    fixed[3] >> 16, fixed[3] & 0xffff))


def legacy_metadata():
    path = Path.home() / '.wechat-cli/config.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        db_dir = value.get('db_dir')
        return {'db_dir': db_dir if isinstance(db_dir, str) else None}
    except (OSError, ValueError, AttributeError):
        return {'db_dir': None}


def profile_health(name):
    folder = profile_dir(name)
    if not (folder / 'config.json').is_file():
        return {'state': 'not_initialized', 'message': '尚未配置这个账号别名。', 'keys_validated': False}
    try:
        config, keys, missing = load_profile(folder)
        shards = sum(re.fullmatch(r'message/message_\d+\.db', name.replace('\\', '/')) is not None
                     for name in keys)
        contact = any(name.replace('\\', '/') == 'contact/contact.db' for name in keys)
        discovered = {path.relative_to(config['db_dir']).as_posix()
                      for path in Path(config['db_dir']).rglob('*.db') if path.is_file()}
        missing = sorted(set(missing) | (discovered - set(keys)))
        ready = not missing and shards > 0 and contact
        return {'state': 'ready' if ready else 'partial',
                'message': '密钥已验证，可尝试查询。' if ready else '密钥验证通过，但部分数据库或查询所需分片缺失。',
                'keys_validated': True, 'db_dir': config['db_dir'], 'matched_databases': len(keys),
                'message_shards': shards, 'contact_ready': contact, 'missing_databases': missing,
                'query_verified': False}
    except (OSError, ValueError, KeyError, TypeError):
        return {'state': 'invalid_keys', 'message': '配置或密钥验证失败，请确认账号目录并重新导入正确密钥。',
                'keys_validated': False, 'query_verified': False}


def classify(value, health):
    if not value['runtime_installed']:
        return 'needs_install', '尚未安装独立 CLI。', ['运行 setup 自动安装，或运行 install。']
    if not value.get('runtime_capabilities_ok'):
        return 'runtime_error', '独立 CLI 无法运行或命令能力不匹配。', ['运行 install 检查或修复独立环境。']
    if health['state'] == 'ready':
        return 'ready', health['message'], ['可查询指定聊天；密钥验证通过不等于已经读取聊天。']
    if health['state'] in ('partial', 'invalid_keys'):
        return health['state'], health['message'], ['运行 check 查看缺失情况，优先导入正确的现有密钥。']
    if value['legacy_keys_exist']:
        return 'legacy_keys_available', '发现现有密钥文件，可以先验证并导入。', ['运行 setup；多个账号时选择目标账号目录。']
    return 'needs_keys', '尚无可复用的密钥配置。', ['先指定账号目录并导入密钥；现场提取属于实验适配，需明确选择进程。']


def extraction_status(processes):
    versions = sorted({item['version'] for item in processes if item.get('version')})
    return {'versions': versions, 'status': 'experimental' if versions else 'unknown',
            'message': ('已读取微信版本；Config.Cipher 提取尚无本项目真实版本兼容性保证，优先复用密钥。'
                        if versions else '未能读取运行中微信的版本，请在微信“关于”中确认；不据此自动扫描。')}
