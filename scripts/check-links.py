#!/usr/bin/env python3
"""检查 README 索引里的锚点是否都能对上文档里的标题。

用法：
  check-links.py [仓库根目录]    默认当前目录
  check-links.py --quiet         只在出错时输出

为什么需要：
  索引是手写的 `docs/xxx.md#12-标题`。改标题、改编号、拆文档之后，
  锚点会静默失效——点过去停在页面顶部，看着像能点，实际没跳。

  这个脚本按 GitHub 的 slug 规则重算锚点，和索引里的逐条比对。
退出码：0 全部正确，1 有不匹配（或文件缺失）。
"""
import os, re, sys


def gh_slug(text: str) -> str:
    """GitHub 标题锚点规则：转小写 → 去掉非单词字符（保留连字符和空格）→ 空格换连字符。"""
    s = text.strip().lower()
    s = re.sub(r'[^\w\- ]', '', s, flags=re.UNICODE)
    return s.replace(' ', '-')


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    quiet = '--quiet' in sys.argv
    root = args[0] if args else '.'

    readme = os.path.join(root, 'README.md')
    if not os.path.isfile(readme):
        print(f'找不到 {readme}')
        return 1

    text = open(readme, encoding='utf-8').read()
    links = re.findall(r'\]\((docs/[^)#]+)#([^)]+)\)', text)

    # 收集所有文档标题的锚点
    anchors = set()
    missing_doc = set()
    for path in {p for p, _ in links}:
        fp = os.path.join(root, path)
        if not os.path.isfile(fp):
            missing_doc.add(path)
            continue
        body = open(fp, encoding='utf-8').read()
        for m in re.finditer(r'^## (\d+)\. (.+)$', body, re.M):
            anchors.add((path, gh_slug(f'{m.group(1)}. {m.group(2)}')))

    bad = [(p, a) for p, a in links if (p, a) not in anchors]

    if not quiet:
        print(f'索引 {len(links)} 个链接，文档 {len(anchors)} 条标题')
    if missing_doc:
        print('文件缺失：')
        for p in sorted(missing_doc):
            print(f'  ✗ {p}')
    if bad:
        print('锚点对不上：')
        for p, a in bad:
            print(f'  ✗ {p}  #{a}')
            cand = [x for x in anchors if x[0] == p]
            for c in cand[:3]:
                if a.split("-")[0] == c[1].split("-")[0]:
                    print(f'      可能应该是：#{c[1]}')
    if not bad and not missing_doc:
        if not quiet:
            print('✅ 全部对得上')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
