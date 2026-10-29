# 文件系统

这类坑的共同点：**占了空间，但看不出来**。`du` 和 `ls` 都会骗你。

---

## 3. 硬链接被摊成真实拷贝

**现象**

目录体积比实际数据大一倍以上。

```console
$ du -sh files file-objects
110M    files
110M    file-objects      ← 两份都很大
```

**判断信号**

```bash
scripts/dup-scan.sh ~/.dsh
```

或者手工：

```bash
ls -li pathA pathB        # inode 相同 → 是硬链接；不同 → 是两份拷贝
stat -c '%h %n' pathA pathB
```

`sha256` 相同但 **`nlink` 各为 1** → 确认是两份真实拷贝。

**根因**

「一个内容对象 + 多个展示名」的设计本来靠硬链接共享数据：

```
objects/<sha256>                 内容本体
files/<sha256>/<原始文件名>       展示名（硬链接）
```

但下面两种情况会把这个设计弄坏：

1. **备份还原 / 跨文件系统拷贝** —— 硬链接不跟着走，解出来是独立文件
2. **文件系统不支持 `link()`** —— 实现退化成全量复制

**解法**

```bash
rm   files/<sha256>/<name>
ln   objects/<sha256>  files/<sha256>/<name>   # 注意是 ln，不是 cp
```

改完 `stat` 应该看到 `nlink=2`、两个路径 inode 相同。

批量处理用 `scripts/dup-scan.sh --apply`（默认 dry-run）。

**代价**

翻倍的不只是空间：**后续任何全量复制/校验的步骤都会慢一倍**，
严重时会撞上固定超时，表现为「启动失败」。

**适用边界**

`/sdcard` 上不可用（见下一条）。

---

## 4. `/sdcard` 上 hardlink 永远失败

**现象**

在共享存储目录里 `ln` 报错：

```console
$ ln a.bin b.bin
ln: failed to create hard link 'b.bin' => 'a.bin': Operation not permitted
```

**判断信号**

```bash
ln /sdcard/Download/x /sdcard/Download/y && echo OK || echo "不支持"
```

**根因**

`/sdcard` 在 Android 上是 FUSE 挂载（MediaProvider），**不允许硬链接**。
exFAT / FAT32 同理。

**解法**

没有解法 —— 只能：

- 在容器内（ext4）做硬链接
- `/sdcard` 上的副本只能删

**代价**

如果程序依赖硬链接做「同一份数据多个名字」，在 `/sdcard` 上就会退化成全量复制。
这正是某些应用「装插件后启动超时」的根源。

**适用边界**

同样影响 `link()` 的其他场景（Python `os.link`、`cp -l`）。
判断文件系统是否支持：

```bash
stat -f -c '%T' /sdcard      # fuseblk / msdos / exfat → 不支持
stat -f -c '%T' ~            # ext4 / overlayfs → 支持
```
