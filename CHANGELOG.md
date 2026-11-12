# 更新日志

## 未发布（8）

新增 1 条。

- **#38** 会话日志是一份凭据仓库 —— 对话里贴过的 token 明文存在 `session.v4.jsonl.zstd` 里
  （本次实测：`github_pat_` 614 次、`cfut_` 403 次、`ghp_` 107 次，去重 16 + 8 个）。
  关键方法：验证令牌别只看 401，要看错误正文（`Requires authentication` vs `Bad credentials`）；
  Cloudflare 的 `9109` 才是「无效令牌」。备份上传到私有仓库时，凭据跟着走。

## 未发布（7）

新增 2 条 + 更正 1 条。

- **#36** 在 Electron 宿主里测 Electron 程序，它变成了 node —— 宿主（如 DSH、Slack）给子进程设了
  `ELECTRON_RUN_AS_NODE=1`，于是 `Code.exe --version` 打印的是 Node 的 `v24.22.1`，
  GUI 静默退出、「崩溃」全是假的。原生 exe 不受影响，正好当对照组。
- **#37** 程序装在 U 盘上：崩溃码天天不一样，签名却完全有效 —— 卷状态 `Warning` 时随机读出错误字节，
  哈希校验那次读对了所以签名 `Valid`，加载进内存那次读错了所以 `0xC0000005`。
  最快的二分：**把安装目录复制到内置盘跑一次**。
- **#32 更正**：当时把 VS Code 崩溃循环归因到 GPU 加速，实际根因是装在 U 盘上。
  「关掉某个功能后不崩了」只能证明路径被绕过，不能证明根因。

## 未发布（6）

新增 2 条。

- **#34** 一个 emoji 让整个脚本崩在错误处理里 —— 中文版 Windows 下 `sys.stdout` 是 GBK，
  `print(f"⏸ …")` 抛 `UnicodeEncodeError`，位置正好在**限流分支**里，
  于是「采集中断」看起来像网络问题。修法：`reconfigure(encoding="utf-8", errors="replace")` + 日志不用 emoji。
- **#35** `python` 命令在，但执行返回 9009 —— `WindowsApps\python.exe` 是商店的应用执行别名，
  `where` 找得到、`Get-Command` 找得到，**执行等于「命令不存在」**；最贵的后果是计划任务显示「成功」。

## 未发布（5）

新增 3 条。

- **#31** PowerShell 脚本不带 BOM，中文注释把解析搞崩 —— 5.1 按 GBK 解码无 BOM 文件，
  中文字节被切成引号字符；`pwsh` 正常、`powershell.exe` 报错，且**报错行号是假的**。
- **#32** 应用崩溃了，但事件日志干净得像没事发生 —— 安全软件把 WER 组策略写成 `Disabled=1`；
  另外 Electron 应用根本不会进事件日志（自带 Crashpad），只能靠二分法定位。
- **#33** 教程里的 `.\脚本.ps1` 在这台机器上直接跑不了 —— Windows 默认 `Restricted`；
  文档作者早改过策略，所以"文档没错、脚本没错、就是跑不了"。别用 Bypass，用 `RemoteSigned`。

## 未发布（3）

新增 1 条。

- **#30** 私有资源读不到时，返回的是 404 不是 403 —— GitHub 故意把「无权」伪装成「不存在」；
  顺带记两条同源坑：令牌前缀不代表权限、GitHub App 令牌 1 小时过期。

## 未发布（2）

新增 4 条 + 一个检查脚本。

- **#26** 改了代码、部署成功，用户看到的还是旧的 —— 三层缓存标识（URL `?v=` / SW `CACHE` / 预构建 CSS）
- **#27** `cmd | tail` 让退出码永远是 0 —— 把失败当成功，症状和 #26 一样
- **#28** 数据看起来是空的，其实是外面包了一层 —— `{ok,data}` 信封
- **#29** 改了配置没生效：它是编译期常量 —— 源码常量和数据库是两回事

脚本：`scripts/check-links.py` —— 按 GitHub slug 规则校验 README 索引里的锚点，
改标题/改编号/拆文档之后不会静默失效。退出码 0 = 全部对得上。

## 未发布

新增 6 条：

- filesystem：备份体积突然三倍（附件存两份，不是备份逻辑变了）
- platform-quirks：发版成功但安装链接 404（附件没上传）
- tooling：`wc -l` 数的是换行符、`zstd` CLI 缺失但库在、
  Node 只解第一帧不报错、搜不到错误码就以为不是这份代码

**编号重排**：全部条目按分类顺序重新编为 1–25，索引重新生成。
（此前是 1–13 顺序、14–16 插在中途、20–25 追加在末尾。）

---

## 未发布（会话存储）

新增「会话存储」分类，收录 3 条：

- session-integrity：首帧不是一行导致会话静默消失、改目录名让工作区挂掉、备份能备份不能恢复

工具类补 3 条：

- tooling：`grep -c` 给两个 0、`awk` 引号不配对、硬编码白名单

新脚本：`scripts/frame-check.py`（只读，已实测）

---

## 未发布（初版）

初始化框架，收录 13 条。

- network：IPv6 黑洞、DNS 固定 5 秒
- filesystem：硬链接被摊平、`/sdcard` 不支持 hardlink
- data-hygiene：轮次当天数、累计值当首日、时区错位
- platform-quirks：静默变慢、搜索非全量、改名误判、同质折叠
- tooling：`pkill -f` 打中自己、apt 源慢

脚本：`net-probe.sh` / `dup-scan.sh` / `timezone-check.sh`（全部只读，已实测）
