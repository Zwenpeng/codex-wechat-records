# Privacy / 隐私说明

## 简体中文

- 仅用于你自己的账号或已获得合法授权的本地数据，不用于隐蔽监控或绕过他人授权。
- 安装不会自动扫描微信内存或读取聊天。`doctor` 读取环境与版本元数据，并可验证已有密钥对应的数据库加密页；它不是聊天内容查询。
- Windows 私有状态默认在 `%LOCALAPPDATA%\CodexWeChatRecords`，其他系统在 `~/.local/share/codex-wechat-records`；`CODEX_WECHAT_HOME` 可修改位置。
- 密钥为本地 JSON，解密缓存为可读 SQLite，均不是加密保险箱。初始化保留的旧密钥也需要保护。
- 导出文件含真实聊天；JSON 完整性报告不含消息正文，但可能含联系人名、路径和时间范围，也应按敏感数据处理。
- CLI 不主动上传聊天；安装会连接 GitHub 和包索引下载依赖。如果让 Codex 总结记录，相关内容会进入你当前模型服务的请求，不保证仅在本机处理。
- 不要把密钥、数据库、真实导出、账号目录、配置、内存片段或未脱敏截图上传到仓库/Issue/公共网盘。`.gitignore` 只是额外防线，不能代替人工检查。
- 卸载 Skill 不删除私有状态或导出。清理前确认目标路径，不要误删微信原始 `db_storage`。
- 不能恢复未同步、已删除或仅存在手机上的聊天；不应当作完整备份工具。

## English

Use only your own account or explicitly authorized local data. Installation never automatically scans process memory or reads conversations. Diagnostics inspect environment/version metadata and may validate encrypted pages against existing keys, without querying message bodies.

State defaults to `%LOCALAPPDATA%\CodexWeChatRecords` on Windows and `~/.local/share/codex-wechat-records` elsewhere. `CODEX_WECHAT_HOME` overrides it. JSON keys, retained old keys and readable decrypted SQLite caches are sensitive local files, not an encrypted vault.

Exports contain conversation content. Integrity reports omit message bodies but may contain names, paths and date ranges. Do not publish these files or unredacted screenshots. The CLI does not actively upload messages; installation downloads dependencies, and asking Codex to analyze messages sends relevant data to your configured model provider.

Removing the skill retains private state and exports. Verify paths before cleanup and preserve original WeChat databases. This is not a complete backup or deleted-message recovery tool.
