# v0.1.0 - Codex WeChat Records

[English](#english) | [简体中文](#简体中文)

## 简体中文

首次公开发布，包含便携式 `wechat-records` Skill、独立 CLI 安装器、中文诊断、首次配置向导和带完整性报告的 Markdown/文本导出。

### 安装

1. 下载 `codex-wechat-records.zip`，与 `SHA256SUMS.txt` 核对 SHA256 后解压。
2. 在包含 `install.py` 的目录运行 `python install.py`。需要 Python 3.10+。
3. 运行 `python "$env:USERPROFILE\.codex\skills\wechat-records\scripts\wechat.py" setup`（自定义 CODEX_HOME 时使用安装器打印的路径）。
4. 新建 Codex 对话，输入“使用 $wechat-records 检查微信读取环境，先只诊断”。

已有安装用 `python install.py --replace` 更新；已有账号数据不会随 Skill 更新被删除。朋友必须配置自己的账号和密钥，不要共享你的私有目录。

### 验证与限制

- 本机 32 项合成测试通过；CI 另在 Windows/Linux、Python 3.10/3.12 运行。
- 发布包只包含源码、文档和测试，不包含运行环境、密钥、聊天记录或缓存。
- 需要已有可用密钥，或显式尝试实验性 Windows x64 只读提取；不能保证新版本微信提取成功。
- `ready` 不等于已经实际读取聊天；实际查询验证需显式指定 `--verify-chat`。
- 完整性只针对本机现有数据，不恢复手机独有、已删除或未同步记录。
- 把聊天交给 Codex 分析会向当前模型服务发送相关内容。请阅读隐私说明。

## English

Initial public release: portable `wechat-records` skill, isolated pinned CLI installation, first-use setup, Chinese diagnostics, Markdown/text export and integrity reports.

Download the ZIP, check `SHA256SUMS.txt`, extract and run `python install.py` with Python 3.10+. Run the installed `wechat.py setup`, then start a new Codex chat. Use the installer's printed path when CODEX_HOME is customized. Update an existing skill with `python install.py --replace`.

32 synthetic tests passed locally. CI separately checks Windows/Linux on Python 3.10/3.12. Assets contain source/docs/tests only. Users configure their own keys; live extraction is experimental and Windows x64 only. A ready profile is not proof of successful message retrieval. Reports cover available local data, not deleted or unsynced history. Sending records to Codex for analysis sends relevant data to the configured model provider.
