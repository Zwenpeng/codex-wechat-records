# Security / 安全

## 简体中文

当前仅维护最新发布版本。项目还处于初始公开阶段，未接受外部安全审计；不保证所有微信版本兼容。

安全边界：不发消息、不修改微信原库、不注入代码；现场读取仅针对明确选择的 `Weixin.exe`，受超时和字节预算限制。密钥需与目标数据库加密页 HMAC 匹配。以上约束不消除本地恶意软件、其他管理员或明文导出泄漏的风险。

发现密钥泄漏、越界读写或账号误绑定等漏洞时，请优先使用仓库 **Security → Advisories → Report a vulnerability** 私密报告（若此入口不可用，先发一个只说明“希望建立私密报告渠道”的 Issue）。不要公开利用详情或真实数据；等待维护者提供私密渠道。不承诺固定响应时间。

只提供脱敏版本信息、最小合成复现和预期/实际结果。绝不要提交真实密钥、完整数据库、聊天、内存 dump、认证令牌或账号标识。

## English

Only the latest release is maintained. This initial project has not received an independent security audit. Compatibility is not guaranteed across all WeChat versions.

The tool does not send messages, modify original databases or inject code. Explicit process selection, scan budgets and HMAC checks reduce but do not eliminate risks. Local keys, caches and exports remain sensitive.

Prefer a private **Security → Advisories → Report a vulnerability** report. If unavailable, open only a minimal issue requesting a private reporting channel, without exploit details or private data. There is no guaranteed response SLA. Submit synthetic reproductions and redacted metadata, never real keys, chat databases, dumps or tokens.
