# Changelog / 更新记录

## 0.1.0

Initial public release / 首次公开发布。

- Portable Codex skill with a separately installed, pinned database-query CLI.
  可迁移的微信记录 Skill，独立安装固定版本 CLI，不依赖 WorkBuddy。
- First-use setup with explicit account selection, existing-key reuse and optional named-chat verification.
  首次配置向导、账号选择、已有密钥复用和可选指定聊天验证。
- Chinese diagnostics with process version metadata, key checks and actionable next steps.
  中文诊断，区分环境就绪、密钥有效和实际查询成功。
- Markdown/text export with counts, time range, source-change detection and partial-result reporting.
  导出条数、时间范围和完整性报告；损坏分片、联系人读取失败或解压失败不再误报成功。
- Per-account private state, no-overwrite export, synthetic tests and Windows/Linux CI.
  多账号隔离、导出防覆盖、合成数据测试及跨平台持续检查。
- Experimental bounded Windows x64 read-only extraction; no universal compatibility guarantee.
  Windows x64 有界只读提取仍为实验功能，不承诺任意微信版本均可用。
