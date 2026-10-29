# 更新日志

## 未发布

初始化框架，收录 13 条。

- network：IPv6 黑洞、DNS 固定 5 秒
- filesystem：硬链接被摊平、`/sdcard` 不支持 hardlink
- data-hygiene：轮次当天数、累计值当首日、时区错位
- platform-quirks：静默变慢、搜索非全量、改名误判、同质折叠
- tooling：`pkill -f` 打中自己、apt 源慢

脚本：`net-probe.sh` / `dup-scan.sh` / `timezone-check.sh`（全部只读，已实测）
