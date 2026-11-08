# 平台行为

平台不会告诉你它做了什么。**只能从数据的形状反推。**

---

## 12. 接口看着正常但脚本没有任何输出

**现象**

手动 `curl` 一切正常，脚本跑十分钟一行日志都没有。

**判断信号**

```bash
# 手动测一次耗时
time curl -s -o /dev/null 'https://api.example.com/endpoint'

# 同样的请求换成 Python
time python3 -c "import urllib.request;urllib.request.urlopen('https://api.example.com/endpoint',timeout=20)"
```

**curl 快、Python 慢几十倍** → 不是接口问题，见 [network #1](network.md#1-无-ipv6-出口时-python-每个请求卡-3040-秒)。

**根因**

「接口挂了」是一个太容易接受的解释。
但接口层的问题通常会**报错**，不会只是慢 —— **静默变慢几乎总是本地环境问题**。

**解法**

见 network #1。

**代价**

会误判成「被风控」「接口限流」，然后去换 UA、加 cookie、改 Referer —— 全错方向。

**适用边界**

反过来也成立：如果 curl 也慢，才是真的服务端或链路问题。

---

## 13. 搜索结果不是全量

**现象**

用搜索接口枚举「某账号的全部内容」，得到的数量每次都是 20、40、100 这种整数。

**判断信号**

- 结果数正好是 `每页条数 × 页数`
- 翻到后面几页，结果与本主题无关
- 总数每天都按固定步长跳

**根因**

搜索是**相关度排序**，不是「按作者枚举」。
它会给到上限（常见 1000 条 / 50 页）就截断，而且排序不等于全量。

**解法**

- 用搜索结果时**明确标注「这是下界，不是全量」**
- 需要全量时用官方列表接口（如果有），或者按作者维度枚举
- **给判断标准**：如果这个数字继续按上限增长，先怀疑方法；开始下降才是真信号

**代价**

拿一个「下界」当「全量」写进结论，误差方向未知。

**适用边界**

所有「搜索 → 统计」的链路。**搜索结果天然有偏，且偏向热门。**

---

## 14. 改名被误判成新账号出现

**现象**

「A 账号查不到了，同时出现了一个 B 账号」——看起来像一个消失、一个新增。

**判断信号**

```bash
curl -s '.../card?mid=<同一个 mid>' | grep -o '"name":"[^"]*"'
```

**新旧名字的 `mid` 完全相同** → 是同一个账号改名。

**根因**

账号的唯一标识是 `mid`，**不是名字**。改名后旧名字搜不到，很容易当成「账号没了」。

**解法**

- 所有跨时间的关联**只用 `mid`**
- 名字只作为展示，不参与匹配
- 记录里同时保存 `mid` 和「当时的名字」

**代价**

一个「克隆账号出现」的结论是错的 —— 实际是同一个账号改名。
连带一处「差 3,758 倍」的对比也失效（那是它自己和自己在比）。

**适用边界**

所有以「名称」为标识的平台：账号、仓库、频道、店铺。

---

## 15. 同质内容被直接折叠

**现象**

同一作者、同一题材，前两条拿到 100+ 播放，第三条只有 **7**。

**判断信号**

对比三条的「结构性相似度」：

| 维度 | 是否相同 |
| --- | --- |
| 账号 | ✅ |
| 封面版式（配色/字体/构图） | ✅ |
| 叙事结构（开场/节奏/结尾） | ✅ |
| 标题关键词 | ✅ |
| 发布时间间隔 | 31 小时、31 小时 |

**全中 → 基本可以判定为「同质内容折叠」。**

**根因**

平台的去重**不是逐条判断**，而是按「同一作者的这一批内容」判断。
一旦归到同一批，连「粉丝级的基础推荐」都不给 —— **不是打折，是清零**。

**解法**

- 同一账号短期内**不要发结构相同的内容**（哪怕内容本身是新的）
- 想验证「形态差异」，**换账号或隔足够久**
- 被折叠的损失不是线性的：**7 播放和 109 播放之间没有中间态**

**代价**

一条内容直接报废；更糟的是**破坏了对照实验** —— 三条连发互相挤占，结论不成立。

**适用边界**

所有有推荐系统的平台。**发布策略本身是变量**，做实验时必须控制。

---

## 16. 发版成功，但一键安装一直 404

**现象**

```console
$ curl -fsSL .../install.sh | sh
下载失败
```

release 页面看起来正常，tag 也在，附件区却是空的。

**判断信号**

```bash
curl -s https://api.github.com/repos/OWNER/REPO/releases/latest \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['tag_name'], [a['name'] for a in d['assets']])"
```

输出里 `assets` 是空列表 `[]` → 就是这个坑。

**根因**

**创建 release 和上传附件是两次独立的 API 调用。**

只做前者时：

- release 正常出现在页面上
- tag 正常创建
- 网页没有明显异常

但所有 `releases/download/<tag>/<file>` 链接**全是 404**。

所以用户看到的现象是「下载失败」，而不是「附件不存在」，
排查方向容易跑到网络或脚本上。

**解法**

发版脚本把「创建 release」和「上传附件」放在同一步，
并且**发版后强制验证**：

```bash
assets=$(curl -s .../releases/latest | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('assets') or []))")
[ "$assets" -gt 0 ] || { echo "附件没传，发版不完整"; exit 1; }
```

**代价**

用户那边只看到「下载失败」。我以为是脚本拼 URL 拼错了，查了一轮。

**适用边界**

所有「元数据 + 制品分离」的发布系统都这样：
npm 的 `dist-tags`、Docker 的 manifest、apt 的 Packages 索引。
创建索引和上传内容分开时，都会出现「看着发布成功、实际拿不到」。


---

## 26. 改了代码、部署成功，用户看到的还是旧的

**现象**

本地文件明明改了，`wrangler` / `vercel` / `gh-pages` 都报「部署成功」，
刷新页面还是旧行为。**服务端确实换了，浏览器拿的是缓存。**

**判断信号**

比大小，最快：

```bash
curl -s https://站点/app.js | wc -c      # 线上实际字节数
wc -c frontend/app.js                    # 本地字节数
```

**对不上** → 是缓存，不是部署失败。再确认是哪一层：

```bash
curl -s https://站点/ | grep -o 'app.js?v=[a-z0-9]*'   # ① URL 上的版本号
curl -s https://站点/sw.js | grep -o "CACHE = '[^']*'" # ② Service Worker 缓存名
```

**根因**

静态站通常有**三层缓存标识**，改文件时必须一起动：

| 层 | 内容 | 漏了会怎样 |
| --- | --- | --- |
| ① URL 查询串 | `app.js?v=<内容哈希>` | 旧 JS 在同一 URL 下被缓存 4 小时 |
| ② Service Worker | `const CACHE = 'site-<哈希>'` | SW 从预缓存里回旧文件（cache-first） |
| ③ 预构建产物 | `tailwind.css` 等 | 新加的类不存在，样式静默失效 |

**解法**

发版脚本一次性对齐（内容哈希而不是手写版本号）：

```bash
node build/release.mjs      # 重写 HTML 里的 ?v=、sw.js 的 CACHE 和 SHELL
npx tailwindcss -i input.css -o ../frontend/tailwind.css --minify   # 改了 class 才需要
```

改完用上面两条 `curl` 复核。

**代价**

会怀疑「部署没生效」「CDN 坏了」「代码有 bug」，甚至去回滚——
而真相是新 HTML 配旧 JS，两边都没错。

**适用边界**

只对「有静态缓存层的站点」成立。纯 SSR（每次回源）没有这个问题。

---

## 29. 改了配置没生效：它是编译期常量

**现象**

改了数据库 / 改了环境变量 / 改了 JSON 文件，页面数据没变。

**判断信号**

```bash
grep -rn "PROFILE\|projects:" src/ worker.js deploy/ 2>/dev/null | head
```

如果配置出现在**源码常量**里（`const PROFILE = {...}`），而不是读库/读文件：

```js
const PROFILE = { projects: [ /* 写死在这里 */ ] };
export default { async fetch(req, env) { return json(PROFILE); } }
```

→ 改数据库当然没用。**必须重新构建/部署，它才会变。**

**根因**

同一份配置可能有三个来源，优先级还不同：

```
① 源码常量     → 编译进产物，改源码才生效
② 数据库/文件  → 运行时读取，改了就生效
③ 缓存         → 读得快，但可能滞后
```

「改了没反应」要先分清是哪种。**看代码里有没有 `const` 直接定义那份数据**，一眼就能排除。

**解法**

- 短期：改源码 → 重新部署
- 长期：把需要运维改的数据挪到数据库或配置文件，别硬编码

**代价**

会去翻部署日志、怀疑缓存、怀疑权限——而实际只差一次 `deploy`。

**适用边界**

只对「配置真的被编译进产物」成立。读环境变量的 Worker 属于 ②，改完要重新 deploy 但不用改源码。

---

## 30. 私有资源读不到时，返回的是 404 不是 403

**现象**

换了新 token 之后，读私有仓库返回 404，但仓库明明存在；同一个 token 读公开仓库一切正常。

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $T" \
  https://api.github.com/repos/owner/private-repo
# 404
```

**判断信号**

**拿同一个 token 打一个同名公开仓库**：

```bash
/repos/owner/public-repo    → 200
/repos/owner/private-repo   → 404     ← 权限问题，不是拼写问题
```

两个都 404 才可能是仓库名写错或 token 无效（后者其实是 401）。

**根因**

GitHub 对**无权访问**的私有资源返回 404，而不是 403 —— 故意把「你不能看」伪装成「它不存在」，避免泄露仓库的存在性。

所以 404 有两种完全不同的含义：

```
404 = 不存在
404 = 存在，但你看不见
```

**解法**

查权限，不要查拼写：

- **fine-grained token**：Repository access 要选中该仓库（或选 "All repositories"），权限至少 `Contents: Read` + `Metadata: Read`
- **classic token**：勾 `repo`
- 验证一条命令就够：

```bash
curl -s -H "Authorization: Bearer $T" https://api.github.com/user | jq -r .login   # 令牌是否有效
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $T" \
  https://api.github.com/repos/<owner>/<repo>                                      # 200 才算有权限
```

**代价**

会去反复核对仓库名、分支名、网络、大小写，甚至怀疑 GitHub 挂了 —— 而实际只是权限没给。

**适用边界**

GitHub 的 REST / GraphQL 都这样；但**不是所有接口**都这样：Actions、Packages 这类在部分场景下会返回 403。所以「404 一定是权限」这句只在**仓库/内容读取**这类接口上成立。

**顺带两条同源的坑**

1. **令牌前缀不代表权限**：`ghp_`（classic）、`github_pat_`（fine-grained）、`gho_`（OAuth）都能读私有仓库，只看它有没有对应权限。前缀只决定「用哪套规则校验」。
2. **GitHub App 令牌只有 1 小时有效期**：拿它当长期服务的凭据（比如塞进 Worker secret）会在某天静默失效，且错误表现可能是「数据少了一截」而不是报错。

## 31. PowerShell 脚本不带 BOM，中文注释把解析搞崩

**现象**

同一个 `.ps1`，用 `pwsh`（PowerShell 7）跑一切正常，用 `powershell.exe`（Windows PowerShell 5.1，计划任务默认调的就是它）跑却直接报语法错误：

```text
字符串缺少终止符: '。
    + CategoryInfo : ParserError
```

报的行号还指在一个**看起来完全没问题**的行上（比如一句 `Write-Host "..."`）。

**判断信号**

先看文件开头三个字节：

```powershell
Format-Hex -Path .\setup-task.ps1 -Count 3
#  EF BB BF  → 有 BOM
#  23 20 64  → 没有 BOM（这里是 "# d"）
```

再用 Python 或 `Get-Content -Encoding UTF8` 读一遍：**内容明明是好的**。

最后对比两个解释器：

```powershell
pwsh -File .\setup-task.ps1        # 正常
powershell -File .\setup-task.ps1  # 报错
```

**根因**

**Windows PowerShell 5.1 对「没有 BOM 的文件」按系统 ANSI 代码页（简中环境是 GBK/CP936）解码。**

UTF-8 的中文是 3 字节一组，GBK 按 2 字节一组去切，切出来的字符里会出现 `’` `“` `”` 这类**在 PowerShell 里也算引号/终止符的字符**。

于是解析器以为字符串在中文注释中间就结束了 —— 报错行号自然飘到后面去。

**解法**

保存成 **UTF-8 with BOM**：

- VS Code：右下角编码 → `Save with Encoding` → `UTF-8 with BOM`
- PowerShell：`[IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($true)))`

改完立刻就好，代码一个字都不用动。

**代价**

会去怀疑括号配对、反引号续行、引号转义、PowerShell 版本差异……
最坑的是：**报错信息是真的，但它指的位置是假的**。

**适用边界**

- 只影响 **Windows PowerShell 5.1** 读 **无 BOM 的 `.ps1` / `.psm1`**
- PowerShell 7（`pwsh`）默认按 UTF-8 读，**不受影响** —— 所以会出现"我这台机器上是好的"
- 反过来也成立：**给记事本看的 `.txt` 要 UTF-8 + BOM + CRLF**，否则记事本显示乱码
- 已经踩过两次：`dsh-tools.ps1` 和 `setup-task.ps1`

**顺带一条**

用编辑器工具（包括 AI 写文件）生成 `.ps1` 时，**默认几乎都是无 BOM UTF-8**。
所以「脚本里只要有中文，就显式确认 BOM」应该当成一条固定检查项。

## 32. 应用崩溃了，但事件日志干净得像没事发生

**现象**

VS Code 窗口反复崩溃，提示：

```text
窗口意外终止（原因:"crashed"，代码:"-1073741819"）
```

**一天崩 28 次，每 2–6 分钟一次**，根本没法用。

去「事件查看器 → Windows 日志 → 应用程序」找 `Application Error`：**一条都没有。**

**判断信号**

三件事同时成立，就该怀疑日志本身被掐了：

1. 应用**确实**在崩（有自己的崩溃转储）
2. 事件日志里**完全没有** `Application Error` / `Windows Error Reporting` 条目
3. 机器上装了安全软件 / "优化"工具

查一下错误上报有没有被策略关掉：

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting' |
  Select-Object Disabled, DontShowUI
#  Disabled = 1      ← 就是它
```

**根因**

**安全软件（本例是 360 安全卫士）把 WER 的组策略写成了 `Disabled=1`**，
美其名曰"关闭错误报告，节省磁盘空间"。

结果是：程序崩溃 → Windows 想记录 → 策略说别记 → **事件日志里什么都没有**。

**顺带还有一个坑**：即使恢复了 WER，**Electron 类应用也不会进事件日志** ——
它们用自带的 Crashpad 抓 minidump（在 `%APPDATA%\<App>\Crashpad\reports`），
进程异常被自己接住了，压根走不到 Windows 的错误上报。

所以对这种应用，「事件日志」这条路本身就不通，得靠二分法定位。

**解法**

**① 恢复错误上报（能救大部分原生应用）**

```powershell
$k = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting'
Remove-ItemProperty -Path $k -Name 'Disabled' -ErrorAction SilentlyContinue
New-ItemProperty -Path $k -Name 'DontShowUI' -Value 1 -PropertyType DWord -Force | Out-Null
```

> `DontShowUI=1` = 只记录不弹窗，排查时够用。

**② Electron 类应用：直接二分关闭可疑特性**

本例最后靠这个办法解决：

```json
"disable-hardware-acceleration": true,   // 关 GPU 渲染
"editor.inlineSuggest.enabled": false    // 关 AI 内联建议
```

再清掉渲染缓存（`GPUCache`、`DawnGraphiteCache`、`Code Cache` 等），
**13 分钟不再崩**，确认元凶是 GPU 加速路径。

**代价**

- 会去怀疑扩展、内存、硬盘、系统更新、驱动……**唯独想不到"日志被关了"**
- 每次失败都留下一个 1 MB 的 minidump，但没有符号，**看不出是哪个模块**

**适用边界**

- `Disabled=1` 这种组策略**只有安全软件或域控会写**，普通用户权限改不到
- 安全软件的"优化"会被再次执行 —— 恢复后要验证它有没有写回去
- **不是所有应用都走 WER**：Electron（VS Code、Slack）、Chromium 系都自带 crasher
- 退出码 `-1073741819` = `0xC0000005` = ACCESS_VIOLATION，是原生内存越界，不是配置错误

**一句话**

> **"日志里没有错误"不等于"没有发生错误"。**
> 排查之前，先确认记录日志的开关还开着。

**后续（2026-11-08）：这条的结论只对了一半**

「关掉 GPU 加速 + 清缓存」之后撑了 4 天。11-08 晚上同一台机器上 VS Code 彻底打不开，
退出码变成 `0xC0000409`（fail-fast），这次连日志都不写了。

真正的根因是：**VS Code 装在一块 USB U 盘上，而那块盘的卷状态已经是 `Warning`。**

- `Code.exe` 签名 `Valid`，字节和官方完全一致
- 同一个文件复制到内置盘就能跑
- 换回 U 盘路径就崩

所以当时那些 `0xC0000005` 是**U 盘读取不稳定**造成的，关 GPU 只是让它暂时不走到那条会崩的路径。

> **教训：「关掉某个功能后不崩了」只能证明那条路径被绕过去了，不能证明根因是那个功能。**

（完整判断方法见 #37）

## 33. 教程里的 `.\脚本.ps1` 在这台机器上直接跑不了

**现象**

照着文档敲：

```powershell
.\setup.ps1
```

报错：

```text
无法加载文件 .\setup.ps1，因为在此系统上禁止运行脚本。
有关详细信息，请参阅 about_Execution_Policies。
    + CategoryInfo    : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
```

**但同样的脚本，加个开关又能跑：**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # 成功
```

**判断信号**

查所有范围的执行策略：

```powershell
Get-ExecutionPolicy -List
```

**关键是看 CurrentUser 这一行：**

```text
        Scope ExecutionPolicy
        ----- ---------------
MachinePolicy       Undefined
   UserPolicy       Undefined
      Process       Undefined
  CurrentUser       Undefined      ← 等于 Restricted（默认禁止）
 LocalMachine       Undefined
```

**根因**

**Windows 客户端默认就是 `Restricted`（禁止所有脚本）** —— 而 Cloudflare、GitHub、各种工具的中文文档里，
清一色写成 `.\xxx.ps1`，因为作者自己的机器早就改过了。

于是「文档没错、脚本没错、就是跑不了」，且报错出现在**加载阶段**，
看起来像文件损坏或杀软拦截（见 #32）。

**解法**

**改当前用户的执行策略，不要改机器级，也不要动不动用 Bypass：**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

改完立刻生效，**不需要管理员权限，不影响其他用户**。

**三种策略的取舍**

| 策略 | 自己写的脚本 | 从网上下载的脚本 |
| --- | --- | --- |
| `Restricted`（默认） | ❌ 全部禁止 | ❌ |
| `RemoteSigned`（推荐） | ✅ 直接跑 | ⚠️ 需签名或 `Unblock-File` |
| `Bypass` | ✅ | ✅ 无限制（风险高） |

**从网上下载的脚本要额外解标记：**

```powershell
Unblock-File .\downloaded.ps1     # 去掉"来自网络"标记（Zone.Identifier 流）
Get-Item .\downloaded.ps1 -Stream *   # 之前能看到 :Zone.Identifier:$DATA
```

**代价**

会先去怀疑：

- 文件是不是坏了（其实是完整文件）
- 杀毒软件拦了（`SecurityError` 和 AV 的拦截提示长得很像）
- PowerShell 版本不对
- 路径/中文名问题

**而实际只有一条命令的差距。**

**适用边界**

- 只影响 `.ps1` / `.psm1` / `.psd1` 的**加载**
- **不影响**：`powershell -Command "..."`、`-File` 带 Bypass、cmd 批处理、已签名的脚本
- `CurrentUser` 作用域只改当前账户，**不需要管理员**
- 企业环境有 `MachinePolicy` / `UserPolicy`（组策略）时，**改 CurrentUser 也无效** —— 那得找 IT

**顺带一条**

**给别人的脚本里如果有 `.ps1`，最好在 README 里直接给这条 `Set-ExecutionPolicy` 命令**，
比事后让用户查「about_Execution_Policies」省事得多。

## 34. 一个 emoji 让整个脚本崩在错误处理里

**现象**

一个跑了十几天都正常的采集脚本，某天开始「跑一会儿就没了」：

- 日志里只有一行「开始采集」，**没有报错，没有结束**
- 部分数据已经写盘（`.partial.json` 里有前 2 个账号）
- 退出码 1，但控制台、日志、事件日志里都找不到原因

同一份代码，昨天还是好的。

**判断信号**

看崩溃时**正在做什么**，而不是看「哪一步失败了」。

这次的栈顶不在任何业务逻辑里，而在一句提示上：

```text
File "daily.py", line 83, in api
    _cool_down()
File "daily.py", line 56, in _cool_down
    print(f"    ⏸ 被限流，全局冷却 {wait}s", flush=True)
UnicodeEncodeError: 'gbk' codec can't encode character '\u23f8'
```

它是在**被限流之后、准备打印提示的时候**死的。

两条快速确认：

```powershell
# 1) 把输出接到管道（编码会变成 locale），立刻复现
python daily.py 2>&1 | ForEach-Object { $_ }
```

2）扫一遍源码里有没有 GBK 装不下的字符：

```python
bad = {}
for i, line in enumerate(src.splitlines(), 1):
    for ch in line:
        try:
            ch.encode("gbk")
        except UnicodeEncodeError:
            bad.setdefault(ch, []).append(i)

for ch, lines in bad.items():
    print(f"U+{ord(ch):04X}  {ch!r}  行数 {len(lines)}  首次行 {lines[:6]}")
```

（这段自己也可能崩在上面 —— 它要打印那个字符。所以跑它的时候加 `PYTHONIOENCODING=utf-8`。）

**根因**

**Windows 中文版的 Python 在输出被重定向（管道/文件）时，`sys.stdout` 的编码是 `gbk`（CP936），不是 UTF-8。**

`print` 里出现 GBK 编不出来的字符（`⏸` `⚠️` `⏱` `↳` 这类符号）就会抛 `UnicodeEncodeError`。

真正致命的是**位置**：这一句在 `except`/限流分支里——

> **本该处理「被限流」的代码，自己把进程带走了。**

于是症状看起来像「网络不好导致采集中断」，而不是「打印崩了」。

**解法**

两道保险一起上：

```python
# 1) 启动时把输出切到 UTF-8，最坏情况只显示成问号，不中止
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
```

```python
# 2) 日志里别用 emoji，用 ASCII 标记
print(f"    [限流] 全局冷却 {wait}s", flush=True)
```

改完验证：**走管道跑一遍**，确认 `stdout.encoding` 已经变成 `utf-8`。

**代价**

会先去怀疑：

- 被平台封了 / 限流了（它有 412，看起来完全说得通）
- 网络超时
- 磁盘写满
- 进程被计划任务杀了

而实际是**一行 `print`**。

更贵的代价是：**它只在「被限流」这条路径上触发**。所以开发时跑得很顺，一上量就死，而且**每次都死在同一个地方、每次都看起来像别的毛病**。

**适用边界**

- 只影响 **Windows 中文版（CP936/GBK）**；Linux/macOS 默认 UTF-8，不会复现
- **交互式终端可能正常，重定向就崩** —— 编码取决于 `isatty()` 和 locale
- 计划任务、`Start-Process -RedirectStandardOutput`、CI 里捕获输出，**全都是重定向场景**，最容易踩
- `PYTHONIOENCODING=utf-8` 可以绕过，但**要求每一个调用方都记得设**，不如在脚本里自己锁死

**顺带一条**

**把「`print` 只放 ASCII + 中文，不放 emoji」当成一条硬规矩。**

这条规矩不贵（少几个装饰符号），而违反它的代价是**在错误处理路径上炸掉整个进程** —— 也就是你最需要日志的那一刻，日志没了。

## 35. `python` 命令在，但执行返回 9009

**现象**

```powershell
PS> where.exe python
C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\python.exe

PS> python --version
（没有任何输出）

PS> echo $LASTEXITCODE
9009
```

`where` 找得到，**执行却等于「找不到命令」**。

最阴的不是这个报错，是它的下游：

- 写成 `python daily.py` 的计划任务，**任务状态显示「成功」，什么都没做**
- 批处理里 `python xxx.py`，静默跳过，后面照跑
- 有些机器上直接**弹出微软商店**的 Python 安装页

**判断信号**

```powershell
# 1) 命令是从哪来的
Get-Command python | Select-Object Source
#   ...\WindowsApps\python.exe   ← 危险信号

# 2) 退出码
python -c "print(1)"; $LASTEXITCODE
#   9009  = 不是程序报错，是根本没有这个程序

# 3) 找真的解释器（绕开 PATH）
Get-ChildItem 'C:\Users','C:\Program Files','D:\' -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
  Select-Object -First 10 FullName
```

再查一眼注册表里有没有登记安装：

```powershell
Get-ChildItem 'HKLM:\SOFTWARE\Python\PythonCore','HKCU:\SOFTWARE\Python\PythonCore' -ErrorAction SilentlyContinue
```

**根因**

`C:\Users\<用户>\AppData\Local\Microsoft\WindowsApps\python.exe` **不是 Python**，
它是 Windows 的「应用执行别名」（App Execution Alias）—— 一个 0 字节的重解析点，
作用是把命令转发给商店应用。

所以：

- 系统**有** `python` 这个命令（`where` 找得到，`Get-Command` 找得到）
- 但机器上**没有** Python，或者装了却没进 `PATH`
- 退出码 9009 是 **shell 的「命令未找到」**，不是 Python 的

**解法**

方案一（推荐）：**脚本里别写 `python`，写绝对路径**。

```powershell
$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
& $py daily.py
```

方案二：用 `py` 启动器（**前提是它真的存在**，这台机器上就没有）：

```powershell
py -3 daily.py
```

方案三：装一个真 Python，并把「应用执行别名」里的 `python.exe` / `python3.exe` 关掉
（设置 → 应用 → 高级应用设置 → 应用执行别名）。

**代价**

会先去怀疑：

- 依赖没装（于是 `pip install` 折腾半天，而 `pip` 也是同一个存根）
- 权限/杀软拦截
- 脚本第一行 `#!/usr/bin/env python3` 有问题（那在 Windows 上本来就不生效）
- 虚拟环境没激活

最贵的一笔：**计划任务会报「成功」。** 没有退出码异常、没有事件日志，只有「今天怎么没数据」这一句话。

**适用边界**

- 只影响 Windows 10/11 自带的 `WindowsApps` 存根，且**只有 `python.exe` / `python3.exe` 这两个名字**
- 商店版 Python 装好之后，同一个命令会变成真的 —— **所以「昨天还能跑」不代表今天还能跑**
- 很多工具自带运行时（编辑器、打包的桌面应用、`uv` 的独立安装），**它们不在 `PATH` 里，但完全可用**
- Linux/macOS 一般不会遇到，除非 `PATH` 里挂了个同名空壳

**顺带一条**

**判断「有没有装」不要用 `where`，用退出码。**

```powershell
(command -v python) -ne $null    # 只是"有这个名字"
python -c "print(1)"; $LASTEXITCODE -eq 0   # 才是"真的能跑"
```

同理：**任何要交给计划任务去跑的命令，必须先在一个干净 shell 里用绝对路径验证过一次。**
交互式终端里能跑，常常是因为当时的 `PATH` 和你手动 `activate` 过的东西不一样。

## 36. 在 Electron 宿主里测 Electron 程序，它变成了 node

**现象**

在一个 Electron 应用（本例是 DSH 桌面端）里执行：

```powershell
& "C:\...\Microsoft VS Code\Code.exe" --version
# 输出：v24.22.1        ← 这是 Node 的版本号，不是 VS Code 的 1.144.1
```

`Code.exe --help` 打印的是 **Node.js 的帮助**。

启动 GUI：**立刻退出、没有窗口、没有日志**，退出码 9 或 0。

于是一路排查「文件被删了」「被安全软件拦了」「签名不对」——**全是伪证据**。

**判断信号**

```powershell
# 1) 环境里有没有这个变量
echo $env:ELECTRON_RUN_AS_NODE
#   1      ← 就是它

# 2) 这个 exe 本质上是不是 Electron
(Get-Item .\Code.exe).VersionInfo.OriginalFilename
#   electron.exe      ← 是
```

**3）最干净的验证：清掉变量再跑一次**

```powershell
cmd /c "set ELECTRON_RUN_AS_NODE= && `"C:\...\Code.exe`" --version"
#   1.144.1   ← 这才是对的
```

**根因**

Electron 支持用环境变量 `ELECTRON_RUN_AS_NODE=1` 把自己**降级成纯 Node 解释器**（不初始化图形界面）。

而**宿主如果本身也是 Electron**（DSH、Slack、某些封装过的终端），
它给自己的子进程设了这个变量 —— 于是你在它里面启动的**每一个 Electron 程序都变成了 node**。

**解法**

测之前显式清掉，或者用 `cmd /c "set VAR= && ..."` 起一个干净环境：

```powershell
$env:ELECTRON_RUN_AS_NODE = $null
```

**代价**

这一轮诊断里，我拿到的三条"证据"全是真的，但**结论全反了**：

| 看到的现象 | 我当时的判断 | 实际含义 |
| --- | --- | --- |
| `--version` 输出 `v24.22.1` | 版本信息不对，安装包坏了 | 它在当 node 用 |
| 启动后静默退出、无日志 | 崩在初始化之前 | node 读完 stdin 就退 |
| 退出码 9 / `0xC0000409` | 二进制损坏 | 参数被 node 当成脚本名 |

差点因此重装一套软件，还误判了安全软件删文件。

**适用边界**

- 只影响 **Electron 程序**；原生 exe 不受影响 —— **正好可以拿它当对照组**

  本例里 `bin\code-tunnel.exe`（原生 CLI）在同样环境下正常输出 `1.144.1`，
  这一条差异本该更早引起怀疑。

- 值的名字就是 `ELECTRON_RUN_AS_NODE`，值为任意非空字符串都生效
- 在**用户级/系统级**都没有它时，说明它只活在当前进程树里（宿主设的）

**一句话**

> **在一个 Electron 程序里测另一个 Electron 程序，先 `echo` 一遍环境变量。**
> 你测的可能根本不是那个程序。

## 37. 程序装在 U 盘上：崩溃码天天不一样，签名却完全有效

**现象**

装在一块 USB 移动盘上的桌面程序（本例是 VS Code），症状**每天都在变**：

- 有时 2–6 分钟崩一次：`0xC0000005`（窗口提示「意外终止，代码 -1073741819」）
- 有时双击毫无反应：无窗口、无日志、无转储
- 有时 `0xC0000409`（fail-fast），连日志都不写
- 关掉某个特性（如 GPU 加速）能好几天，然后复发

**判断信号**

**① 看这块盘是什么类型、什么健康状态**

```powershell
Get-Volume -DriveLetter E | Select-Object DriveLetter, FileSystemType, DriveType, HealthStatus
# DriveLetter      : E
# FileSystemType   : Unknown      ← 文件系统都读不出来了
# DriveType        : Removable    ← U 盘 / 移动硬盘
# HealthStatus     : Warning      ← 卷状态警告
```

**② 关键一步：把整个安装目录复制到内置盘，用副本跑**

- 副本能跑 → **问题在盘，不在程序**
- 副本也崩 → 才回去查程序/系统

**③ 顺手确认文件本身没坏**

```powershell
Get-AuthenticodeSignature .\Code.exe | Select-Object Status
#  Valid      ← 字节和官方一致
```

**这一条最容易把人带偏：签名有效会让人坚信"文件是好的"，于是去查显卡、内存、驱动。**

**根因**

**U 盘（尤其是闪存）不适合承载"要长期运行的软件目录"。**

程序启动时要做大量**随机读**：映射几十个 DLL、读 pak、写日志、解压扩展。
闪存盘的随机读写寿命远低于顺序读写，磨损之后会出现**读出来是错的、但不报错**的情况。

于是：

- 算文件哈希（签名校验）那次读对了 → `Valid`
- 真正加载进内存的那次读错了 → `0xC0000005`

> **签名证明"文件是对的"，不证明"这块盘每次都能正确读出来"。**

**解法**

- **软件装内置盘**；U 盘只放**备份和安装包**
- 已经出现 `HealthStatus: Warning` 的盘，**先备份再考虑换掉**
- 排查这类问题时，**"换个盘位置跑一次"是最快的二分**

**代价**

会依次怀疑：显卡驱动 → 内存 → 系统更新 → 安全软件 → 电源。
因为上面每一项都能造成 `0xC0000005`，而 U 盘这条根本不在候选列表里。

**适用边界**

- 不只 U 盘：**网络盘、外接硬盘盒、虚拟磁盘、`Warning` 状态的任何卷**都算
- 便携软件（portable）放 U 盘"能用"，但**只在轻度使用下**；重度读写一样会踩
- 要区分两件事：

| 做法 | 风险 |
| --- | --- |
| 下载/备份**到** U 盘 | 低 —— 这是好习惯 |
| **从** U 盘运行程序 | 高 —— 等于把程序的命交给一根 USB |

**一句话**

> **「我的电脑容易坏，所以东西都放 U 盘」——这个习惯救的是数据，不是程序。**
> 数据放 U 盘，程序装内置盘，才是两头都保住。
