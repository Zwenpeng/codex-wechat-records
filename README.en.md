# Codex WeChat Records

**English** | [简体中文](README.md)

[![Checks](https://github.com/Zwenpeng/codex-wechat-records/actions/workflows/test.yml/badge.svg)](https://github.com/Zwenpeng/codex-wechat-records/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Download](https://github.com/Zwenpeng/codex-wechat-records/releases/latest) · [Changelog](CHANGELOG.md) · [Privacy](PRIVACY.md) · [Issues](https://github.com/Zwenpeng/codex-wechat-records/issues)

A portable Codex skill for reading, searching, exporting and analyzing local WeChat records with the database-query edition of wechat-cli. Invoke it as `$wechat-records`; the UI description is Chinese.

## Install

Requires Codex, Python 3.10+ and network access to GitHub and the Python package index. Windows extraction requires 64-bit Python. You must be authorized to access the target account and have local database files. Installing the skill does not automatically provide decryption keys.

Download `codex-wechat-records.zip` from [Releases](https://github.com/Zwenpeng/codex-wechat-records/releases/latest), extract it, open a terminal in the directory containing `install.py`, and run:

```powershell
python install.py
python "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py" setup
```

If CODEX_HOME is set, use the path printed by install.py. A custom destination is supported with `--skills-dir`. Restart Codex or open a new chat to discover the skill. No WorkBuddy installation or global PATH changes are required.

The setup wizard installs the pinned, SHA256-verified CLI into a private venv when needed, selects an account and prefers importing validated existing keys. It does not query messages by default. Memory extraction requires explicit --scan and --pid. Use --non-interactive for agents; missing choices return a Chinese diagnostic report and exit code 2. The doctor command only inspects environment, version metadata and profile health. Unrelated projects share the wechat-cli name, so entry point and commands are verified.

Alternatively clone the source:

```text
git clone https://github.com/Zwenpeng/codex-wechat-records.git
cd codex-wechat-records
python install.py
```

Friends install their own copy and configure their own account. Never share your private profile or keys. You can ask Codex: "Install wechat-records from https://github.com/Zwenpeng/codex-wechat-records following its README. Diagnose only at first; let me confirm the account directory before reading messages or extracting keys."

## Initialize and use

Prefer importing an existing key file, after identifying the correct account directory:

```powershell
$entry = "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py"
python $entry --profile main import-keys --db-dir "<account>\db_storage" --keys-file "<keys>\all_keys.json"
python $entry --profile main check
python $entry --profile main run -- sessions --limit 5
python $entry --profile main run -- history "Contact or group" --limit 30
python $entry --profile main run -- export "Group" --format markdown --output ".\chat.md" --limit 500
```

On Windows x64, a selected, logged-in Weixin.exe process can be scanned read-only:

```powershell
python $entry --profile main initialize --db-dir "<account>\db_storage" --pid <PID>
```

Candidates are accepted only after a database-page HMAC check. The scanner has a timeout and a byte budget, never injects code, writes the original databases or dumps process memory. Its Config.Cipher offsets are a compatibility heuristic, not a guarantee for every 4.1+ version. macOS/Linux support importing existing keys; this package does not implement native extraction there.

Use different profile names for different accounts. Keys, decrypted caches and incremental cursors are isolated. Exports refuse to overwrite an existing file. `new-messages` tracks session summaries and is not a lossless message queue. Deleted, unsynced or phone-only history cannot be recovered. Use `cli-help <command>` for actual supported flags.

Exports with --output return a JSON integrity report without message bodies. It includes requested/actual count, time range, checked shards, missing databases and failures. success, fewer_available and empty have distinct meanings; partial results are retained with exit code 3 when critical keys are missing, reads fail or source data changes during the query. The file includes the integrity notice. Without --output, the body goes to stdout and the report to stderr.

Setup can optionally validate a named chat with --verify-chat. It reads at most one message locally and returns query_verified rather than the message body. A ready profile is not itself proof of successful message retrieval. Detected WeChat versions do not imply verified scanner compatibility; extraction remains experimental.

## Privacy and storage

Private state defaults to `%LOCALAPPDATA%\CodexWeChatRecords` on Windows and `~/.local/share/codex-wechat-records` elsewhere. CODEX_WECHAT_HOME overrides it. Keys are JSON and decrypted caches are readable databases protected by user-directory permissions, not an encrypted vault. Older keys are retained when reinitializing a profile.

Local queries do not actively upload messages. Passing records to Codex for analysis sends those records to the currently configured model service. Keep keys, caches, real exports and memory data out of Git and public artifacts. Installation never automatically reads real conversations.

## Development and distribution

```text
python -m unittest discover -s tests -v
python tools/build_release.py
```

Tests use synthetic data and temporary directories, never a real WeChat account. Install the managed runtime to include the upstream integration test; otherwise that test explicitly skips. Release packaging includes only an explicit file manifest. The archive is written to dist/codex-wechat-records.zip.

Update with `python install.py --replace`; prior skills are backed up outside the discovery directory. To uninstall, remove the installed skill directory. Private data is retained until explicitly removed. Local build scripts never push or publish automatically.

Published archives include `SHA256SUMS.txt`; compare it with `Get-FileHash .\codex-wechat-records.zip -Algorithm SHA256` in PowerShell. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and issue-report guidance, [SECURITY.md](SECURITY.md) for security reports and [CHANGELOG.md](CHANGELOG.md) for release history.

This repository's original code is MIT licensed. The separately installed database-query CLI is Apache-2.0. See [third-party notices](THIRD_PARTY_NOTICES.md) and the [Chinese documentation](README.md) for detailed troubleshooting.
