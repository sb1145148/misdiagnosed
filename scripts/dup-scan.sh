#!/bin/sh
# 找出「同一份内容的多个真实拷贝」（不是硬链接）
#   dup-scan.sh [目录...] [--apply] [--min 1M]
# 默认只扫描；--apply 会把副本改成硬链接（要求文件系统支持 link）。
set -u
APPLY=0; MIN="1M"; DIRS=""
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --min) shift 2>/dev/null; MIN="${1:-1M}" ;;
    -*) ;;
    *) DIRS="$DIRS $a" ;;
  esac
done
[ -n "$DIRS" ] || DIRS="$HOME/.dsh"
MODE=$([ "$APPLY" = 1 ] && echo apply || echo scan)
for d in $DIRS; do
  if command -v dsh-relink >/dev/null 2>&1; then
    if [ "$MODE" = apply ]; then dsh-relink --root "$d" --min "$MIN" --apply --verify
    else dsh-relink --root "$d" --min "$MIN"; fi
  else
    echo "需要 dsh-relink（https://github.com/sb1145148/dsh-tools）" >&2
    exit 1
  fi
done
