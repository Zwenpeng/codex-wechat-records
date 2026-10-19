# Contributing / 贡献与反馈

## 简体中文

欢迎改进平台适配、中文诊断、导出可靠性和文档。提交前：

1. 使用 Python 3.10+，安装独立 CLI：`python skills/wechat-records/scripts/wechat.py install`。
2. 运行 `python -m unittest discover -s tests -v` 和 `python tools/build_release.py`。
3. 测试只用合成数据和临时目录，不自动读取真实账号、进程或聊天。检查是否有跳过项，不能把跳过的集成检查称为已验证。
4. 新增发布文件须更新 `tools/build_release.py` 的明确文件清单。
5. 保持中英文 README、隐私边界与实际命令一致。不要加入自动扫描、自动发消息或隐式账号选择。

普通问题请在 [Issues](https://github.com/Zwenpeng/codex-wechat-records/issues) 描述系统/Python/微信版本、脱敏命令、预期和实际结果。不要粘贴完整 doctor 输出、真实用户目录或联系人；先脱敏。安全漏洞请走 [SECURITY.md](SECURITY.md)。

上游代码与原始 Skill 包装器许可不同；不要直接复制无明确许可的第三方脚本。贡献采用本仓库 MIT 许可，保留适用的第三方署名。

## English

Use Python 3.10+, install the pinned runtime, run the synthetic test suite and build the release with the commands above. Note any skipped integration checks. Add new distributable files to the explicit release manifest. Keep both README languages synchronized and preserve explicit account selection and read-only behavior.

Report ordinary issues with redacted versions, commands, expected/actual results and synthetic fixtures. Never post unredacted diagnostic output, keys or conversations. Follow SECURITY.md for vulnerabilities. Contributions are MIT licensed; respect third-party attribution and do not copy unlicensed scripts.
