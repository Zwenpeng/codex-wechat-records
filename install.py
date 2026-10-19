"""Install the portable skill into this user's Codex skills directory."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat


def reject_links(directory):
    """Never traverse a destination junction or symlink during backup/update."""
    directory = Path(directory)
    if not directory.exists() and not directory.is_symlink():
        return
    for current, directories, files in os.walk(directory, followlinks=False):
        for path in [Path(current), *(Path(current) / name for name in directories + files)]:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Install/update refuses symlinks or Windows reparse points inside: ' + str(directory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, help='Override the destination skills directory')
    parser.add_argument('--replace', action='store_true', help='Back up an existing skill and replace it')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / 'skills/wechat-records'
    codex = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser()
    root = (args.skills_dir or codex / 'skills').expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'wechat-records'
    if target.is_symlink():
        raise SystemExit('Refusing to overwrite a symlinked skill.')
    reject_links(source)
    reject_links(target)
    backup = None
    if target.exists():
        if not args.replace:
            raise SystemExit('Skill already exists. Use --replace to back it up and update.')
        # Backup outside skills so Codex does not discover a duplicate SKILL.md.
        backup_root = root.parent / 'skill-backups'
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / ('wechat-records-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copytree(target, backup)
    try:
        shutil.copytree(source, target, dirs_exist_ok=args.replace,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    except Exception:
        print('Install incomplete; original backup is at:', backup)
        raise
    print('Installed skill:', target)
    print('Next: python "' + str(target / 'scripts/wechat.py') + '" install')
    print('Restart Codex or open a new chat to discover $wechat-records.')


if __name__ == '__main__':
    main()
