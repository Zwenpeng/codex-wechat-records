"""Private per-user runtime, profile storage and a cross-process profile lock."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


def home():
    override = os.environ.get('CODEX_WECHAT_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'CodexWeChatRecords'
    return Path.home() / '.local/share/codex-wechat-records'


def profile_dir(name):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}', name):
        raise ValueError('账号别名需为1至48位英文字母、数字、下划线或连字符。')
    folder = home() / 'profiles' / name
    if folder.is_symlink() or folder.resolve().parent != (home() / 'profiles').resolve():
        raise ValueError('账号目录必须位于独立私有目录内，不能指向外部路径。')
    return folder


def private_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt':
        # Inherit the current user's LocalAppData ACL. POSIX chmod is not a DACL.
        return
    path.chmod(0o700)


def atomic_json(path, value):
    path = Path(path)
    private_dir(path.parent)
    fd, temp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        if os.name != 'nt':
            path.chmod(0o600)
    finally:
        Path(temp).unlink(missing_ok=True)


@contextlib.contextmanager
def profile_lock(folder, timeout=10):
    private_dir(folder)
    with (Path(folder) / '.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('这个账号正在执行其他任务，请等待当前操作完成。') from None
                time.sleep(.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)


def python_exe():
    env = home() / 'runtime'
    return env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
