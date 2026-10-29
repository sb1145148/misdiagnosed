#!/bin/sh
# 检查容器时区与目标时区是否一致，并给出「天数」口径提醒
set -u
TARGET_TZ="${TARGET_TZ:-8}"
echo "容器时间(UTC):  $(date -u '+%Y-%m-%d %H:%M:%S')"
echo "容器本地时间:   $(date '+%Y-%m-%d %H:%M:%S')"
python3 - "$TARGET_TZ" <<'PY'
import datetime, sys
off = int(sys.argv[1])
tz = datetime.timezone(datetime.timedelta(hours=off))
utc = datetime.datetime.now(datetime.timezone.utc)
print(f"目标时区 UTC{off:+d}:  {utc.astimezone(tz):%Y-%m-%d %H:%M:%S}")
print()
print("提醒：")
print("  · 容器多半是 UTC，写报告要显式转目标时区（docs/data-hygiene.md#7）")
print("  · 统计「第 N 天」按自然日归并，不按采集次数（docs/data-hygiene.md#5）")
print("  · 累计值要先归一化再比较（docs/data-hygiene.md#6）")
PY
