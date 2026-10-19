# 查询与导出

以下 `<entry>` 表示 `python "<skill>/scripts/wechat.py" --profile main`。PowerShell 里应使用完整命令和实际目录；`<entry>` 仅表示可替换的公共前缀。

| 需求 | 参数 |
| --- | --- |
| 最近会话 | `run -- sessions --limit 10 --format json` |
| 未读会话 | `run -- unread --limit 20 --format json` |
| 找联系人 | `run -- contacts --query "名字" --limit 20` |
| 最近消息 | `run -- history "名字或username" --limit 50 --offset 0 --format json` |
| 分页 | `run -- history "名字" --limit 50 --offset 50` |
| 某天的消息 | `run -- history "群名" --start-time "2026-10-01" --end-time "2026-10-01" --limit 100` |
| 搜索 | `run -- search "截止" --chat "群名" --start-time "2026-10-01" --limit 100` |
| 消息类型 | `run -- history "群名" --type file --limit 50` |
| 群成员 | `run -- members "群名" --format json` |
| 统计 | `run -- stats "群名" --start-time "2026-10-01" --format json` |
| 收藏 | `run -- favorites --query "论文" --limit 20` |
| 导出 Markdown | `run -- export "群名" --format markdown --output "<目录>/群记录.md" --limit 1000` |
| 导出纯文本 | `run -- export "群名" --format txt --output "<目录>/群记录.txt" --limit 1000` |
| 增量摘要 | `run -- new-messages --format json` |

不确定参数时先运行 `cli-help history` 等，帮助来自安装中的真实命令且不需要密钥或聊天访问。查询通常默认 JSON；export 仅支持 markdown/txt，不要虚构 JSON 导出选项。JSON 查询可以由本地脚本处理或保存；不要让 shell 的不同编码默认值破坏中文。

history 默认 50 条，sessions 默认 20 个，export 默认 500 条。search 的每次 limit 上限为 500，更多需求应缩小日期范围，不能简单把参数设为 100000。时间为本机本地时间，日期形式的结束日包含当日 23:59:59。先声明时间范围，解释返回条数和读取限制。

export 输出文件名必须不存在；需要重做时用另一个文件名，不能默默覆盖用户文件。为了可迁移，输出到用户指定的工作目录，不要写入技能目录或私有密钥目录。

指定 --output 时 stdout 是 JSON 校验报告（不含正文）：`status`、`requested_count`、`exported_count`、`oldest/newest`、`message_shards_with_keys`、`checked_message_shards`、`missing_databases`、`failures`、`warnings` 和输出路径。正文保存在指定文件，并附校验说明。达到条数也可能因缺分片或查询期间源数据变化而返回 partial，退出码为3；不足请求条数但没有读取异常为 fewer_available，不自动推断丢失了记录。无 --output 时 stdout 仍是正文，报告输出到 stderr。

`new-messages` 只基于会话最新时间和摘要追踪变化，首次返回未读会话并建立游标。它不是完整的逐条新消息队列，也不会在微信中把消息标成已读。需要完整增量记录时，结合明确时间区间的 history 分页并按记录来源去重。

品牌占位会话和系统占位符可能没有可导出的消息；不把这种情况归为所有聊天都失效。
