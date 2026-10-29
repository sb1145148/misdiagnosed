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
