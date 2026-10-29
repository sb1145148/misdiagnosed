#!/bin/sh
# 判断「请求慢」到底是 DNS 慢、连接慢，还是地址族问题
#   net-probe.sh [host]
# 只读，不改任何配置。
set -u
HOST="${1:-api.bilibili.com}"
say() { printf '%s\n' "$*"; }

say "目标: $HOST"
say ""

say "① 地址族顺序"
python3 - "$HOST" <<'PY'
import socket, sys
h = sys.argv[1]
try:
    a = socket.getaddrinfo(h, 443)
except Exception as e:
    print("   解析失败:", e); raise SystemExit(0)
v6 = [x for x in a if x[0] == socket.AF_INET6]
v4 = [x for x in a if x[0] == socket.AF_INET]
print(f"   AAAA 记录 {len(v6)} 条, A 记录 {len(v4)} 条")
print(f"   首选: {a[0][0].name} {a[0][4][0]}")
if v6:
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM); s.settimeout(5)
    import time; t = time.time()
    try:
        s.connect((v6[0][4][0], 443, 0, 0)); print(f"   IPv6 连接: 成功 {time.time()-t:.1f}s")
    except Exception as e:
        print(f"   IPv6 连接: 失败 {time.time()-t:.1f}s ({type(e).__name__})  ← 若无 IPv6 出口，这就是慢的根源")
    finally:
        s.close()
PY

say ""
say "② curl 对照（它会自动回落 IPv4）"
curl -s -o /dev/null -w "   dns=%{time_namelookup}s conn=%{time_connect}s total=%{time_total}s\n" \
  --max-time 20 "https://$HOST" 2>/dev/null || say "   curl 失败"

say ""
say "③ Python 对照（没有 Happy Eyeballs）"
python3 - "$HOST" <<'PY'
import time, urllib.request, sys
h = sys.argv[1]
t = time.time()
try:
    urllib.request.urlopen(urllib.request.Request(f"https://{h}", headers={"User-Agent": "probe"}), timeout=40).read(1024)
    print(f"   耗时 {time.time()-t:.2f}s")
except Exception as e:
    print(f"   失败 {time.time()-t:.2f}s ({type(e).__name__})")
PY

say ""
say "判断:"
say "  curl 快 + Python 慢  → 地址族问题，见 docs/network.md#1"
say "  两者都慢且 dns 固定 5s → DNS 问题，见 docs/network.md#2"
say "  两者都慢且 conn 慢 → 链路/服务端问题"
