# 网络 / DNS

排查顺序建议：**先跑 `scripts/net-probe.sh`**，它能一次区分「DNS 慢」「连接慢」「服务端慢」。

---

## 1. 无 IPv6 出口时 Python 每个请求卡 30–40 秒

**现象**

同一个 URL：

- `curl` 0.4 秒返回
- Python（`urllib` / `requests`）每个请求 30–40 秒，不报错，只是慢
- 脚本「卡住」，没有任何输出

**判断信号**

```bash
python3 - <<'PY'
import socket
a = socket.getaddrinfo('example.com', 443)
print([(x[0].name, x[4][0]) for x in a[:3]])
PY
```

如果**首条是 `AF_INET6`**，且下面这条直接超时：

```bash
python3 -c "import socket;s=socket.socket(socket.AF_INET6,socket.SOCK_STREAM);s.settimeout(5);s.connect(('2400:xxxx::1',443,0,0))"
```

→ 基本确认。

**根因**

1. DNS 返回 AAAA 排在 A 前面（正常，IPv6 优先是标准行为）
2. 设备**没有 IPv6 路由**，包发出去没有回应，只能等 socket 超时
3. Python 没有 Happy Eyeballs（RFC 8305），逐个地址试，**每个都等满超时**
4. `curl` 有 Happy Eyeballs，IPv6 试 200ms 就并行 IPv4，所以看不出问题

**解法**

系统级（推荐，一次修好所有脚本）：

```bash
echo 'precedence ::ffff:0:0/96  100' >> /etc/gai.conf
```

脚本级兜底：

```python
import socket
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: [r for r in _orig(*a, **k) if r[0] == socket.AF_INET]
```

**代价**

两天。期间一直以为是接口风控。

**适用边界**

- 只在「无 IPv6 出口」的网络里成立（移动网络、部分企业网、容器）
- 有 IPv6 出口时不该改 `gai.conf`，会让能走 IPv6 的流量退回 IPv4

**实测对照**

```
默认（不限制地址族）：OK  36.31s
强制 IPv4          ：OK   0.27s
```

---

## 2. DNS 解析固定卡 5 秒

**现象**

所有网络请求的 `time_namelookup` 稳定在 5.0–5.2 秒，**零波动**。

**判断信号**

```bash
for i in 1 2 3; do
  curl -s -o /dev/null -w "#$i dns=%{time_namelookup}s\n" https://example.com
done
```

**三次都接近 5.1 秒且几乎不抖动** → 这不是网络抖动，是固定的超时值。

**根因**

`/etc/resolv.conf` 里第一个 nameserver 不可达（常见是把 `8.8.8.8` 写在前面，
但在某些网络里它被丢包），glibc 等满 5 秒才试下一个。

**解法**

```bash
# 把可达的 DNS 放前面
cat /etc/resolv.conf
# 例：nameserver 223.5.5.5
#     nameserver 8.8.8.8
```

或用 `resolv.conf` 的 `options timeout:1 attempts:2` 缩短等待。

**代价**

容易误判成「服务端慢」，因为 `total` 时间也只多 5 秒。

**适用边界**

和第 1 条会叠加：DNS 5 秒 + 连接 N 次超时 = 单请求 35 秒以上。
**排查时一定要分开测 DNS 和连接。**
