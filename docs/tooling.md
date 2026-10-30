# 工具与命令

命令行工具自己的坑：**它会让你以为是别的坏了。**

---

## 17. `pkill -f` 打中自己

**现象**

```bash
pkill -f "port 39999"
```

执行完之后，**自己的 shell 也没了**，后面的命令全没跑。

**判断信号**

```bash
ps -eo pid,args | grep "[m]y-pattern"     # 看有没有匹配到自己
```

如果匹配到的进程数比预期多 1，且多出来的那个是当前 shell 的父进程 —— 就是这个坑。

**根因**

`pkill -f` 匹配**整条命令行**。而执行它的那条 `bash -c 'pkill -f "xxx"'` 自身命令行里
就含有 `xxx`，所以它自己也被匹配到了。

**解法**

三种任选：

```bash
pkill -f "[m]y-pattern"        # 字符类，不匹配自身
pkill -f 'pattern' -x          # 精确匹配进程名
ps -eo pid,args | awk '/pattern/ && !/awk/ {print $1}' | xargs -r kill
```

**代价**

最坏的情况：把父进程杀了，正在跑的长任务全丢。

**适用边界**

任何 `-f`（整命令行）匹配：`pkill`、`pgrep`、`killall -r`。

---

## 18. apt 官方源慢到以为卡死

**现象**

```bash
apt-get install -y some-package
```

半小时没动静，`dpkg` 没开始，缓存目录在慢慢变大。

**判断信号**

```bash
du -sh /var/cache/apt/archives     # 隔 30 秒看两次，涨得极慢
ps -eo args | grep "[a]pt/methods/http"
```

如果下载速度 < 50 KB/s，且源是 `ports.ubuntu.com` / `archive.ubuntu.com` 之类的海外源
→ 换镜像。

**根因**

不是卡死，是**在慢慢下载**。包很大（比如字体包 100MB+），海外源带宽很低。

**解法**

```bash
# 换成地理更近的镜像（以清华为例）
sed -i 's|http://ports.ubuntu.com/ubuntu-ports/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/|g' \
  /etc/apt/sources.list.d/ubuntu.sources
apt-get update
apt-get install -y some-package
```

**代价**

等半小时才发现是在下载，而不是在装。

**适用边界**

镜像可用性因网络而异，换之前先 `curl -I` 测一下目标镜像。

---

---

## 19. `grep -c` 找不到时给两个 0

**现象**

```bash
err=$(grep -c "pattern" file || echo 0)
[ "$err" -eq 0 ] && echo "正常"
# bash: [: 0
# 0: 整数表达式期待
```

或者不报错，但判断走了错误的分支。

**判断信号**

```bash
x=$(grep -c zzz /dev/null || echo 0); printf 'x=[%s]\n' "$x"
```

输出

```console
x=[0
0]
```

变量里是**两行**而不是一行 → 就是这个坑。

**根因**

`grep -c` 在**匹配 0 行时已经打印了 `0`，同时退出码是 1**。

`||` 于是又追加一个 `0`。两个 `0` 拼成了 `0\n0`。

**解法**

```bash
n=$(grep -c "pattern" file 2>/dev/null) || true
n=${n:-0}
```

或者截掉多余行：

```bash
n=$(grep -c "pattern" file 2>/dev/null | head -1); n=${n:-0}
```

**代价**

统计悄悄失效：要么永远走 `||` 分支，要么 `[` 直接报语法错。
在 `if` 里的话，可能整段判断被跳过，**看起来一切正常**。

**适用边界**

所有"有输出但退出码非零"的命令：`grep -c`、`diff`、`cmp`、`test`。
`grep -q` 没有这个问题（它不打印）。

---

## 20. `awk` 引号不配对，检查永远"通过"

**现象**

一段检查嵌在 shell 里跑，从来不报警。
手动验证数据明明有问题。

**判断信号**

把 `2>/dev/null` 摘掉跑一次：

```bash
awk '...你的程序...' file 2>&1 >/dev/null | head -3
```

出现 `runaway string constant` 或 `unexpected newline` → 就是这个坑。

**根因**

要在 awk 里输出一个字面量 `}`，很容易写成这种拼接：

```bash
awk '... {print $7" }"}' file
```

在**单引号**包裹的 shell 字符串里多了一个 `"`，
awk 解析到行尾仍停在字符串里 → 整个程序编译失败。

而脚本里恰好写了 `2>/dev/null`，错误被丢掉，
外层只看到"没有输出"，就当成"没有发现问题"。

**解法**

不要在 awk 程序里内联跨引号的字面量，用 `printf`：

```bash
awk '{ printf "%-40s %s\n", $7, $8 }' file
```

**并且：测试阶段不要加 `2>/dev/null`。**

**代价**

我自己的工具里有一条检查因此从来没触发过。
用户报了一个真实 bug，工具回"全部正常"——
两个人都被误导，用户白等了一轮。

**适用边界**

任何把 awk / sed 程序写在单引号里、又用 `2>/dev/null` 遮蔽错误的地方。
如果确实需要静默，至少先把 stderr 落盘。

---

## 21. 硬编码白名单，工具永远说"没问题"

**现象**

工具报告"全部正常"，但运行时报 `unknown event type` 之类的错误。

**判断信号**

```bash
diff <(tool --list-types) <(runtime --list-types)
```

有差集 → 就是这个坑。差集里多出来的，就是工具不认识的。

**根因**

工具把"认识哪些东西"**写死在自己的源码里**。

运行时新增了类型 → 工具不认识 →
要么把它当成问题误报，要么直接跳过导致漏报。

维护两份必须同步的列表，**不同步是默认结果，同步是需要额外付出的**。

**解法**

**从运行时取**，不要维护第二份：

```bash
tool --list-types   # 改为读运行时的导出，而不是内置常量
```

**代价**

一次"检查通过"的假阴性。
最坏的情况是：以为问题解决了，实际只是没检测到，
下一轮用户又贴一份原始输出过来说"还是这样"。

**适用边界**

只在"两边必须同步"的场景成立。
有些白名单本来就该独立（安全策略、协议版本），那种不能从运行时取。

---

## 22. `wc -l` 数的是换行符，不是行

**现象**

```console
$ printf 'abc' | wc -l
0
```

明明有一行内容，算出来 0。

**判断信号**

```bash
printf 'abc'   | wc -l    # 0
printf 'abc\n' | wc -l    # 1
```

同一个内容，加不加结尾换行，结果差 1 → 就是这个坑。

**根因**

`wc -l` 统计的是 `\n` 的个数，不是「行数」。

文件最后一行没有换行符时，那一行**不计入**。

**解法**

```bash
awk 'END { print NR }' file                 # 按记录数
grep -c '' file                             # 非空行数（注意条目 19 的坑）
python3 -c "print(len(open('file').read().splitlines()))"
```

**代价**

我判断「首帧是不是恰好一行」时，用了 `count('\n')`，
结果是 0 行而不是 1 行——差点把正常文件判成坏的。

**适用边界**

所有按「行」计数的场景。二进制文件、没有结尾换行的单行文件都会踩。

---

## 23. `zstd: command not found` ≠ 解不了 zstd

**现象**

```console
$ zstd -d file.zst
bash: zstd: command not found
$ apt-get install -y zstd
E: Unable to locate package zstd
```

两条路都断，于是以为这条路走不通。

**判断信号**

```bash
command -v zstd              # 空
ldconfig -p | grep zstd      # 有 libzstd.so.1
```

命令没有、库有 → 就是这个坑。

**根因**

**命令行工具和库是两回事。**

`libzstd.so.1` 几乎在所有 Linux 上都存在——Python、Node、curl、systemd 都依赖它。
但 `zstd` 这个可执行文件属于单独的可选包，很多精简镜像里没有。

**解法**

直接调库，不走 CLI：

```python
import ctypes
lib = ctypes.CDLL('libzstd.so.1')
lib.ZSTD_decompress.restype  = ctypes.c_size_t
lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                ctypes.c_void_p, ctypes.c_size_t]
```

多帧文件还要配 `ZSTD_findFrameCompressedSize` 逐帧切（见条目 24）。

**代价**

一度以为「没有 zstd 就没法读这些文件」，于是想绕开问题，而不是解决问题。

**适用边界**

只对「库在、CLI 不在」成立。
库也没有的极简容器里，必须装（或换用镜像）。

---

## 24. Node 的 `zstdDecompressSync` 只解第一帧，不报错

**现象**

```console
$ node -e "...zlib.zstdDecompressSync(buf)..."
文件 26 字节   得到 "AAAA"      期望 "AAAABBBB"
```

两个帧拼成的文件，只解出前半段，**不抛错**。

**判断信号**

用 `ZSTD_findFrameCompressedSize` 数帧数，和 `zstdDecompressSync` 的输出比对：

```bash
python3 - <<'PY'
import ctypes
lib = ctypes.CDLL('libzstd.so.1')
lib.ZSTD_findFrameCompressedSize.restype = ctypes.c_size_t
lib.ZSTD_findFrameCompressedSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
b = open('file.zst','rb').read()
off, n = 0, 0
while off < len(b):
    s = lib.ZSTD_findFrameCompressedSize(b[off:], len(b)-off)
    if not s: break
    off += s; n += 1
print('帧数', n)
PY
```

帧数 > 1，而 Node 的结果只对应第一帧 → 就是这个坑。

**根因**

Node 的 zstd API 按**单个帧**处理。遇到后续帧就停，
把「后面还有数据」当成正常结束——**不报错、不提示**。

**解法**

先切帧，再逐帧解：

```js
let off = 0;
const parts = [];
while (off < buf.length) {
  const n = frameSize(buf.subarray(off));          // ZSTD_findFrameCompressedSize
  parts.push(zlib.zstdDecompressSync(buf.subarray(off, off + n)));
  off += n;
}
```

**代价**

**读到一半的数据看起来完全合法**，会得出「文件只有这么多内容」的错误结论，
然后拿这个结论去判断别的环节。

**适用边界**

只在多帧可选压缩格式上成立。
单帧文件（`zstd -o` 的产出）没有这个问题——但那正是条目 6 的坑。

---


**已验证**

Node **v24.19.0**，两帧文件（`AAAA` + `BBBB`，共 26 字节）：
`zstdDecompressSync` 返回 `"AAAA"`，**不抛错**。
和只喂第一帧的结果完全相同 —— 证明它确实在帧边界停下，而不是数据损坏。

## 25. 全仓库搜不到某个错误码，于是以为不是这份代码

**现象**

```bash
grep -rn "SOME_ERROR_CODE" ./src ./node_modules/     # 无结果
```

而运行时这个错误码确实出现了。

**判断信号**

```bash
grep -rl "SOME_ERROR" . 2>/dev/null | head
grep -rl "SOME_" . 2>/dev/null | head          # 放宽到前缀
```

两个都为空 → 要么这个码是拼出来的，要么它在编译产物里。

**根因**

两种常见情况：

1. **错误码是运行时拼的**——`"PREFIX_" + reason`，源码里永远搜不到完整字面量
2. **代码不在这个语言里**——前端是 TypeScript，报错来自 Android 侧的 Kotlin（已编译进 APK）

**解法**

- 搜**前缀或片段**，不要搜完整字面量
- 搜不到就换层：看是不是另一个进程、另一种语言抛的
- 有编译产物时，直接搜产物（DEX / 字节码），或者去源码仓库搜

**代价**

会得出「这不是这份代码的问题」的结论，然后往完全错误的方向查——
甚至去怀疑是底层库或系统的问题。

**适用边界**

只对「错误码可能被拼接、或来自另一层」成立。
有些情况确实就是找不到，别把这条当成万能的。

---

## 27. `cmd | tail` 让退出码永远是 0

**现象**

```bash
wrangler pages deploy . | tail -5
echo $?          # 0
```

看起来成功，实际上部署被超时杀了——日志停在 `Uploading... (29/31)`。

**判断信号**

```bash
set -o pipefail
false | tail -1; echo "退出码=$?"     # 有 pipefail → 1；没有 → 0
```

或者更直接：**看输出里有没有那句「成功标记」**（`Deployment complete!`、`✨ Done`），而不是看退出码。

**根因**

管道的退出码是**最后一个命令**的退出码。`tail` 成功读完输入就返回 0，
前面的命令是死是活它不管。

**解法**

```bash
set -o pipefail          # 管道里任一命令失败 → 整体失败
cmd 2>&1 | tail -20
```

或者不要管道，把输出写文件再看：

```bash
cmd > /tmp/out.log 2>&1; rc=$?; tail -5 /tmp/out.log; echo "rc=$rc"
```

**代价**

把一次**失败的部署**当成成功，然后去别处找「为什么页面没变」——
它和条目 26（缓存）的症状完全一样，很难区分。

**适用边界**

所有 `| head`、`| tail`、`| grep` 的用法。脚本里尤其危险，因为没人盯着看。

---

## 28. 数据看起来是空的，其实是外面包了一层

**现象**

```bash
curl -s https://api.example.com/api/profile | jq '.projects | length'
# 0
```

但页面明明显示着项目列表。

**判断信号**

```bash
curl -s https://api.example.com/api/profile | jq 'keys'
```

顶层是 `["ok", "data"]` 而不是 `["projects", "name"]` → 读的是信封，不是信。

**根因**

接口统一包了一层：

```json
{ "ok": true, "data": { "projects": [ ... ] } }
```

**「字段不存在」和「空数组」返回的东西是一样的**——都是 `null` 或 0，
很容易误判成「后端没数据」。

**解法**

```bash
jq '.data.projects | length'
```

写代码时也一样：先打一行 `Object.keys(resp)`，确认层级再取值。

**代价**

会得出「接口没返回数据」「后端挂了」的结论，然后去查服务端——
而数据一直在，只是多了一层。

**适用边界**

所有「统一响应信封」的设计（`{ok,data}`、`{code,message,result}`、`{success,payload}`）。
反过来说，这也是个设计权衡：信封让错误处理统一，但让调试多一次翻层。

---

## 附：常用判断命令速查

```bash
# 这到底是 DNS 慢还是连接慢？
curl -w 'dns=%{time_namelookup} conn=%{time_connect} total=%{time_total}\n' -so /dev/null https://example.com

# 两个文件是不是硬链接？
ls -li A B; stat -c '%h' A

# 这个数和那个数是不是同一个东西？
sha256sum A B

# 进程到底在等什么？
cat /proc/<pid>/wchan; cat /proc/<pid>/status | grep State
```
