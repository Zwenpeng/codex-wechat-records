"""Build a source-only release from an explicit, reviewed manifest."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    '.gitignore', 'LICENSE', 'README.md', 'README.en.md', 'THIRD_PARTY_NOTICES.md', 'install.py',
    'VERSION', 'CHANGELOG.md', 'PRIVACY.md', 'SECURITY.md', 'CONTRIBUTING.md', 'RELEASE_NOTES.md',
    'skills/wechat-records/SKILL.md', 'skills/wechat-records/agents/openai.yaml',
    'skills/wechat-records/scripts/wechat.py', 'skills/wechat-records/scripts/run_cli.py',
    'skills/wechat-records/scripts/local_state.py', 'skills/wechat-records/scripts/key_material.py',
    'skills/wechat-records/scripts/windows_scan.py',
    'skills/wechat-records/scripts/export_chat.py', 'skills/wechat-records/scripts/diagnostics.py',
    'skills/wechat-records/scripts/setup_flow.py', 'skills/wechat-records/scripts/errors.py',
    'skills/wechat-records/references/setup.md', 'skills/wechat-records/references/commands.md',
    'skills/wechat-records/references/analysis.md', 'skills/wechat-records/references/troubleshooting.md',
    'tests/test_skill.py', 'tests/test_readiness_export.py', 'tools/build_release.py', '.github/workflows/test.yml',
)


def main():
    entries = []
    for relative in FILES:
        path = ROOT / relative
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Release source must stay inside the project: ' + relative)
        raw = path.read_bytes()
        text = raw.decode('utf-8')
        if re.search(r'[A-Za-z]:[/\\]Users[/\\](?:50584|27249|Administrator)|wxid_[a-zA-Z0-9]{5,}', text):
            raise ValueError('Machine-specific identity found in: ' + relative)
        entries.append((relative, raw))
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    target = dist / 'codex-wechat-records.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative, raw in entries:
            archive.writestr('codex-wechat-records/' + relative, raw)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (dist / 'SHA256SUMS.txt').write_text(digest + '  ' + target.name + '\n', encoding='ascii')
    print(f'{len(entries)} source files packaged: {target}')
    print('SHA256:', digest)


if __name__ == '__main__':
    main()
