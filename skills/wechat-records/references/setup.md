# 安装与初始化

## 首次配置向导（推荐）

```powershell
python "<skill>/scripts/wechat.py" setup
```

向导检查或安装独立 CLI，复用已经验证的账号；新账号会提示选择数据库目录，再优先验证导入与该目录匹配的旧密钥。没有现成密钥时会明确给出下一步，不自动扫描进程。

Agent/脚本使用非交互模式：

```powershell
python "<skill>/scripts/wechat.py" --profile main setup --non-interactive --db-dir "<账号>/db_storage" --keys-file "<现有密钥>/all_keys.json"
```

缺少账号选择返回 `needs_account` 和候选目录、退出码2；缺少密钥返回 `needs_keys`；部分密钥可用返回 `partial`、退出码3。已存在且健康的账号保持原配置。

可选的真实读取验证：添加 `--verify-chat "指定联系人或username"`。最多读取该聊天的一条记录，在本机检查返回格式，不把正文写进报告；`query_verified` 表示这一步是否通过。默认配置过程不查询消息。

`doctor` 提供 state/message/next_steps、密钥健康信息及运行中微信的版本。读取版本使用 Windows 文件元数据，不扫描内存。没有可靠版本信息时标记 unknown；有版本时也只标记现场提取 experimental，不做未经实测的版本兼容承诺。

## 安装 CLI

```powershell
python "<skill>/scripts/wechat.py" install
python "<skill>/scripts/wechat.py" cli-help
```

安装器创建独立 venv，下载并校验固定 GitHub 源码归档，安装数据库查询版 `huohuoer/wechat-cli`。该固定源码自报 0.2.4，不能拿版本号判断与其他同名项目的关系。来源提交与归档 SHA256 固定在 wechat.py；依赖固定为 click 8.1.8、pycryptodome 3.23.0、zstandard 0.25.0。依赖从 PyPI 安装，未宣称整个 Python 构建工具链完全可复现。

不依赖 WorkBuddy；也不修改 WorkBuddy 的 Python、PATH、微信安装或 `~/.wechat-cli`。重复安装校验能力后复用现有环境。升级到另一固定源码时，用新的 CODEX_WECHAT_HOME 安装验证，避免覆盖在用环境。

私有文件默认位置：Windows `%LOCALAPPDATA%/CodexWeChatRecords`；macOS/Linux `~/.local/share/codex-wechat-records`。可用 `CODEX_WECHAT_HOME` 指定其他私有目录，其他电脑不要照抄本机用户名。

## 复用已有密钥（优先）

已有 wechat-cli 或 WorkBuddy 的 `all_keys.json` 时，使用确切账号的数据库路径：

```powershell
python "<skill>/scripts/wechat.py" --profile main import-keys --db-dir "<账号目录>/db_storage" --keys-file "<现有密钥文件路径>/all_keys.json"
python "<skill>/scripts/wechat.py" --profile main check
```

导入会读取目标数据库的首个加密页验证 HMAC，只保存匹配的密钥。没有匹配时保留原配置。不会在终端显示密钥。每次初始化新建不可变密钥文件，并以原子更新 config.json 完成切换；旧密钥文件保留，以便恢复。

## Windows Config.Cipher 只读提取

1. 让用户确认微信已登录目标账号，获取 `doctor` 给出的 Weixin.exe PID 与目标 db_storage 路径。
2. 用户要求初始化该账号时执行：

```powershell
python "<skill>/scripts/wechat.py" --profile main initialize --db-dir "<账号目录>/db_storage" --pid <Weixin进程ID> --timeout 120
python "<skill>/scripts/wechat.py" --profile main check
python "<skill>/scripts/wechat.py" --profile main run -- sessions --limit 5
```

也可通过 `setup --non-interactive --db-dir "<账号>/db_storage" --scan --pid <PID>` 调用同一实验扫描流程。

脚本为 Windows x64 编写，按 `com.Tencent.WCDB.Config.Cipher` 对象布局寻找 blob，只在内存中处理 blob，不生成 dump。扫描设有时间和 4 GiB 总读取上限；只有实际通过数据库 HMAC 的 32 字节 raw encryption key 才保存。不能再用 256000 轮 PBKDF2 把这个 raw key 当 passphrase 派生一次。HMAC 校验本身仍需要 SQLCipher 的两轮 PBKDF2 来派生独立 MAC key，不能把“不要再派生加密密钥”误解为完全不能使用 PBKDF2。

对象偏移来自用户所给 4.1.x 工作流的兼容经验；未在所有 4.1.12+ 版本实测，不保证更高版本一定适用。必要时在用户终端以管理员身份初始化一次；通常查询不需要管理员。不自动提权、不重启微信、不降级、不注入。

## 多账号

为每个账号使用不同别名，例如 main、study。每次查询都显式传 `--profile study`，不要通过覆盖共享的 ~/.wechat-cli/config.json 来切换。已有别名绑定另一数据库目录时会拒绝覆盖，避免沿用另一账号的增量游标；迁移到新目录时请另建别名。密钥、解密缓存、图片输出和增量游标均按 profile 隔离；同一 profile 的运行通过进程锁串行化。不要把同一数据库目录导入多个 profile 后以为它们是不同微信账号。

## macOS / Linux

可安装 CLI、使用合法取得且已验证的本地密钥进行查询。附带的进程扫描仅支持 Windows x64；没有提供跨平台内存提取、重签名或绕过系统保护的自动化。导入正确密钥不保证不同微信数据库 schema 都能被此固定上游版本读取。
