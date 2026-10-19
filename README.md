# Codex WeChat Records

[English](README.en.md) | **简体中文**

[![Checks](https://github.com/Zwenpeng/codex-wechat-records/actions/workflows/test.yml/badge.svg)](https://github.com/Zwenpeng/codex-wechat-records/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[下载发布包](https://github.com/Zwenpeng/codex-wechat-records/releases/latest) · [更新记录](CHANGELOG.md) · [隐私说明](PRIVACY.md) · [问题反馈](https://github.com/Zwenpeng/codex-wechat-records/issues)

把本机微信聊天记录的查询、搜索、导出与分析能力接入 Codex。技能中文名为“微信记录助手”，调用名是 `$wechat-records`。

它包含两部分：可安装的 Codex Skill，以及自动安装到独立 Python 环境的数据库查询版 wechat-cli。不依赖 WorkBuddy，不修改系统 PATH。

## 能做什么

- 浏览会话和未读摘要、查联系人与群成员。
- 按聊天对象、关键词、日期和消息类型查询记录。
- 导出 Markdown/纯文本，统计消息活跃度，查询收藏。
- 在 Codex 中提取待办、整理通知、总结讨论。
- 复用已有的 all_keys.json；Windows x64 可按指定 PID 尝试 Config.Cipher 只读提取。
- 为多个账号分别保存配置、密钥、解密缓存和增量游标。
- 导出自带条数、时间范围、缺失分片和读取异常校验；诊断提供中文状态、微信版本和下一步。

不包含发消息、朋友圈操作、删除记录，也不恢复电脑上不存在的历史。新版微信提取和数据库结构兼容性随版本变化，不保证所有 4.1+ 都成功。

## 安装

需要 Codex、Python 3.10+、可访问 GitHub 和 Python 包索引的网络；Windows 提取需要 64 位 Python。微信账号必须是你有权访问的账号，并且电脑上已有相应数据；安装 Skill 本身不会自动获得解密密钥。

不会 Git 也能安装：打开上面的“下载发布包”，下载 `codex-wechat-records.zip`，解压，在包含 `install.py` 的文件夹空白处右键“在终端中打开”，运行：

```powershell
python install.py
python "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py" setup
```

如果设置了 CODEX_HOME，使用 install.py 实际打印的安装目录，不能仍然照抄默认路径。安装器也支持 `python install.py --skills-dir "<自定义 skills 目录>"`。

第二步进入首次配置向导：按需安装固定提交及 SHA256 的 CLI 和依赖，提示选择账号，优先验证并导入现有密钥。没有密钥时给出下一步；只有明确添加 --scan --pid 才会尝试实验提取。默认不查询消息。朋友在自己的电脑上重复这些步骤即可，不需要你的 Python 路径或账号配置。

也可以使用 Git 下载：

```powershell
git clone https://github.com/Zwenpeng/codex-wechat-records.git
cd codex-wechat-records
python install.py
```

愿意让 Codex 帮忙安装的朋友，可以直接发送：

```text
请从 https://github.com/Zwenpeng/codex-wechat-records 安装 wechat-records skill，
按照 README 配置独立运行环境。先只诊断；账号目录由我确认，不要自动读取真实聊天或提取密钥。
```

无人值守或由 Agent 调用时添加 `--non-interactive`，缺少选择会返回候选目录和中文提示。还可用 `doctor` 单独做只读诊断，或用 `install` 只安装 CLI。

重新打开 Codex 或新建对话后，可说：

```text
使用 $wechat-records 检查我的微信读取环境，先只诊断。
使用 $wechat-records 初始化我指定的微信账号，优先复用已有密钥。
使用 $wechat-records 找出“某项目群”本周关于材料提交的消息，列出截止时间和依据。
使用 $wechat-records 把“某项目群”10月1日至10月7日的聊天导出成 Markdown，放到我指定目录。
```

## 初始化自己的账号

向导也支持一次性提供参数：

```powershell
python "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py" --profile main setup --non-interactive --db-dir "<账号目录>\db_storage" --keys-file "<密钥目录>\all_keys.json"
```

如需验证实际读取，可加 `--verify-chat "指定联系人或username"`，只在本机查询最多一条记录并报告验证结果，正文不进入报告。`ready` 表示配置和密钥就绪，`query_verified` 单独记录真实读取验证。

已有 WorkBuddy/其他数据库查询工具生成的密钥时，先明确账号目录，再导入：

```powershell
$entry = "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py"
python $entry --profile main import-keys --db-dir "<账号目录>\db_storage" --keys-file "<密钥文件>\all_keys.json"
python $entry --profile main check
python $entry --profile main run -- sessions --limit 5
```

没有密钥且使用 Windows x64 时，登录目标账号，读取 doctor 输出中的 Weixin.exe PID 后执行：

```powershell
python $entry --profile main initialize --db-dir "<账号目录>\db_storage" --pid <实际PID>
```

脚本只读取指定 Weixin.exe 进程内存，按 HMAC 校验目标库，不注入、不写原库、不保存内存 dump。失败时查看 [排错](skills/wechat-records/references/troubleshooting.md)。账号选择不能只凭目录修改时间推断；密钥零匹配时不会覆盖现有 profile。管理员权限不一致时，由用户在自己的管理员终端运行该命令。

## 查询例子

```powershell
python $entry --profile main run -- history "联系人或群名" --limit 30
python $entry --profile main run -- search "提交" --chat "项目群" --limit 50
python $entry --profile main run -- export "项目群" --format markdown --output ".\项目群记录.md" --limit 500
python $entry --profile main cli-help history
```

默认数量有限；搜索最多每次500条。日期和分页详见 [命令参考](skills/wechat-records/references/commands.md)。同名联系人需确认唯一 username。导出目标已存在时会拒绝覆盖。`new-messages` 是会话最新摘要的增量观察，不是完整逐条消息同步，也不会代替微信备份。

带输出路径的导出会返回 JSON 报告，包含实际条数、时间范围、检查的消息分片和缺失/错误信息。`success` 表示达到请求条数且未发现异常，`fewer_available` 表示当前范围不足请求条数，`empty` 表示没有消息。`partial` 表示关键数据库缺失、读取失败或查询中数据变化，此时保留可读结果并返回退出码3，文件也附有说明。它不保证恢复未同步或已删除的记录。

## 数据位置与隐私

默认独立环境和私有 profile 位于 Windows `%LOCALAPPDATA%\CodexWeChatRecords`；其他系统位于 `~/.local/share/codex-wechat-records`。设置 `CODEX_WECHAT_HOME` 可更改位置。macOS/Linux 目前支持安装和导入已有密钥，附带的现场扫描仅支持 Windows x64。

密钥以本地 JSON 保存，解密缓存为可读数据库，依赖当前用户目录权限保护，**并非加密保险箱**。初始化更新保留旧密钥文件，备份同样敏感。不要把该目录、密钥、数据库、内存片段和真实导出加入 Git 或同步到公开网盘。

CLI 本地查询不会主动上传聊天，但将记录交给 Codex 分析会把内容发送到你当前使用的模型服务。只想本地导出时，明确要求“仅导出，不把全文加入对话”。首次部署本项目不会自动读取真实会话。

## 更新、卸载与发布

更新技能：下载新源码后 `python install.py --replace`；旧技能备份到 skills 同级的 skill-backups，避免出现两个可发现的技能。独立运行环境版本不一致时使用新的 CODEX_WECHAT_HOME 测试，勿在 WorkBuddy 环境 pip 升级。

卸载技能：删除自己的 skills/wechat-records 文件夹即可，私有数据不会跟着被删除。需要清除私有缓存和密钥时先确认路径再手动处理，不能删除微信原始 db_storage。

发布前运行：

```powershell
python -m unittest discover -s tests -v
python tools/build_release.py
```

测试使用合成页、临时文件和模拟 CLI，不读取真实微信进程或真实聊天。构建脚本使用明确的发布文件列表并做个人路径检查，产出 `dist/codex-wechat-records.zip`。打包前应安装运行环境，以执行带真实上游 CLI 的合成集成测试；缺失依赖时测试会明确 skip，不能称为全量验证。

正式发布包和 SHA256 校验文件见 [Releases](https://github.com/Zwenpeng/codex-wechat-records/releases)。下载后可在 PowerShell 用 `Get-FileHash .\codex-wechat-records.zip -Algorithm SHA256` 与 `SHA256SUMS.txt` 对照。本地构建脚本不会自动推送或发布。

版本记录见 [CHANGELOG.md](CHANGELOG.md)。贡献和问题报告见 [CONTRIBUTING.md](CONTRIBUTING.md)；安全问题请参阅 [SECURITY.md](SECURITY.md)，不要在公开 Issue 粘贴密钥、账号目录或聊天内容。

## 来源和授权

Skill、入口脚本和文档使用 MIT；运行依赖 [huohuoer/wechat-cli](https://github.com/huohuoer/wechat-cli) 为 Apache-2.0，通过安装器单独下载。详见 [第三方说明](THIRD_PARTY_NOTICES.md)。本项目不附带微信安装包或 WorkBuddy 原始技能脚本。
