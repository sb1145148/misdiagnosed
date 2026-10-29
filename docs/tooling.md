# 工具与命令

命令行工具自己的坑：**它会让你以为是别的坏了。**

---

## 12. `pkill -f` 打中自己

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

## 13. apt 官方源慢到以为卡死

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

## 17. `grep -c` 找不到时给两个 0

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

## 18. `awk` 引号不配对，检查永远"通过"

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

## 19. 硬编码白名单，工具永远说"没问题"

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
