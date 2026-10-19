"""Bounded, read-only Weixin.exe Config.Cipher scanner for Windows x64.

The offsets are a compatibility heuristic, not a guarantee for every 4.1 release.
Candidates are kept only in memory and are accepted only after page HMAC validation.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import os
from pathlib import Path
import struct
import time

NAME = b'com.Tencent.WCDB.Config.Cipher'
MAX_ADDRESS = 0x0000800000000000
CHUNK = 2 * 1024 * 1024


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('PartitionId', wt.WORD),
                ('RegionSize', ctypes.c_size_t), ('State', wt.DWORD),
                ('Protect', wt.DWORD), ('Type', wt.DWORD)]


def u64(raw, offset):
    return struct.unpack_from('<Q', raw, offset)[0] if len(raw) >= offset + 8 else 0


def api():
    if os.name != 'nt' or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError('Config.Cipher 提取需要64位 Windows 和64位 Python。')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.CloseHandle.restype = wt.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wt.BOOL
    kernel.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
    kernel.VirtualQueryEx.restype = ctypes.c_size_t
    kernel.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel.ReadProcessMemory.restype = wt.BOOL
    return kernel


def scan_blobs(pid, timeout=120):
    kernel = api()
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise RuntimeError('无法读取所选进程，请确认终端与微信的运行权限一致。')
    deadline = time.monotonic() + timeout
    scanned = 0

    def check():
        if time.monotonic() > deadline:
            raise RuntimeError('只读扫描超时，账号配置未改变。')

    def read(address, size):
        check()
        if not 0x10000 <= address < MAX_ADDRESS or not 0 < size <= CHUNK:
            return b''
        data = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        kernel.ReadProcessMemory(handle, ctypes.c_void_p(address), data, size, ctypes.byref(count))
        return data.raw[:count.value]

    try:
        filename = ctypes.create_unicode_buffer(32768)
        count = wt.DWORD(len(filename))
        if not kernel.QueryFullProcessImageNameW(handle, 0, filename, ctypes.byref(count)):
            raise RuntimeError('无法验证所选进程的身份，请重新确认 PID。')
        if Path(filename.value).name.lower() != 'weixin.exe':
            raise ValueError('所选 PID 不属于 Weixin.exe，已停止提取。')
        regions = []
        address = 0
        while address < MAX_ADDRESS:
            check()
            info = MBI()
            if not kernel.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(info), ctypes.sizeof(info)):
                break
            base = info.BaseAddress or 0
            size = info.RegionSize
            if info.State == 0x1000 and not info.Protect & 0x100 and (info.Protect & 0xff) in (2, 4, 8, 32, 64, 128):
                regions.append((base, size))
            next_address = base + size
            if next_address <= address:
                break
            address = next_address

        def chunks(overlap):
            nonlocal scanned
            for base, size in regions:
                tail = b''
                for offset in range(0, size, CHUNK):
                    size_now = min(CHUNK, size - offset)
                    chunk = read(base + offset, size_now)
                    scanned += len(chunk)
                    if scanned > 4 * 1024**3:
                        raise RuntimeError('只读扫描已达到4 GiB读取上限，账号配置未改变。')
                    if not chunk:
                        tail = b''
                        continue
                    yield base + offset - len(tail), tail + chunk
                    tail = chunk[-overlap:] if len(chunk) == size_now else b''

        addresses = set()
        for base, raw in chunks(len(NAME) - 1):
            offset = raw.find(NAME)
            while offset >= 0:
                addresses.add(base + offset)
                if len(addresses) > 256:
                    raise RuntimeError('Config.Cipher 布局不符合预期，当前微信版本可能不兼容，账号配置未改变。')
                offset = raw.find(NAME, offset + 1)
        if not addresses:
            raise RuntimeError('未找到 Config.Cipher，请检查登录状态、进程和微信版本兼容性。')
        patterns = [struct.pack('<QQ', address, len(NAME)) for address in addresses]
        blobs = set()
        for base, raw in chunks(128):
            for pattern in patterns:
                offset = raw.find(pattern)
                while offset >= 0:
                    node = read(base + offset - 16, 80)
                    if u64(node, 16) in addresses and u64(node, 24) == len(NAME):
                        config = u64(node, 40)
                        obj = read(config + 0x88, 40)
                        pointer, length = u64(obj, 8), u64(obj, 16)
                        if 0 < length <= 1024:
                            blob = read(pointer, length)
                            if len(blob) == length:
                                blobs.add(blob)
                                if len(blobs) > 4096:
                                    raise RuntimeError('候选数量异常，账号配置未改变。')
                    offset = raw.find(pattern, offset + 1)
        return list(blobs)
    finally:
        kernel.CloseHandle(handle)
