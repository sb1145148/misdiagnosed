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
