#!/usr/bin/env python3
"""只读检查：会话文件的帧布局和路径身份。

两个模式：
  frame-check.py DIR           首帧是不是恰好一行
  frame-check.py --identity DIR  目录名和 header 的 id/cwd 是否一致
  frame-check.py -h, --help     显示这段说明

不改任何文件。退出码 0 = 全部正常，1 = 有问题。
"""
import ctypes, glob, json, os, sys

def _lib():
    for name in ('libzstd.so.1', 'libzstd.so', 'libzstd.dylib'):
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    sys.exit('找不到 libzstd')

lib = _lib()
for _n, _r, _a in (
    ('ZSTD_findFrameCompressedSize', ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_size_t]),
    ('ZSTD_decompress', ctypes.c_size_t,
     [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]),
    ('ZSTD_getFrameContentSize', ctypes.c_ulonglong, [ctypes.c_void_p, ctypes.c_size_t]),
):
    _f = getattr(lib, _n); _f.restype = _r; _f.argtypes = _a


def _dec(buf):
    cap = lib.ZSTD_getFrameContentSize(buf, len(buf))
    if cap >= (1 << 59):
        cap = len(buf) * 200 + 65536
    out = ctypes.create_string_buffer(cap)
    n = lib.ZSTD_decompress(out, cap, buf, len(buf))
    return out.raw[:n]


def first_frame(buf):
    """返回（首帧解压结果, 首帧长度）。"""
    n = lib.ZSTD_findFrameCompressedSize(buf, len(buf))
    if not n:
        return None, 0
    return _dec(buf[:n]), n


def first_line(buf):
    """解出足够的头部行（首帧有时就是一整行）。"""
    text = _dec(buf[:lib.ZSTD_findFrameCompressedSize(buf, len(buf))] or len(buf))
    return text.split(b'\n', 1)[0]


def sessions(root):
    pats = [os.path.join(root, '**', 'session.v*.jsonl.zstd')]
    out = []
    for p in pats:
        out.extend(glob.glob(p, recursive=True))
    return sorted(out)


def check_frames(root):
    bad = 0
    files = sessions(root)
    for p in files:
        buf = open(p, 'rb').read()
        head, _ = first_frame(buf)
        if head is None:
            print(f'  ❌ 首帧读不出: {p}')
            bad += 1
            continue
        lines = head.count(b'\n')
        if head.endswith(b'\n'):
            lines = head.count(b'\n')
        else:
            lines += 1
        if lines != 1:
            print(f'  ❌ 首帧 {lines} 行（应为 1）: {p}')
            bad += 1
    print(f'  共 {len(files)} 个会话，首帧不合规 {bad} 个')
    return 1 if bad else 0


def check_identity(root):
    bad = 0
    files = sessions(root)
    for p in files:
        buf = open(p, 'rb').read()
        head = first_line(buf)
        try:
            h = json.loads(head)
        except Exception:
            print(f'  ❌ 首行不是 JSON: {p}')
            bad += 1
            continue
        sid, cwd = h.get('id'), h.get('cwd')
        d = os.path.dirname(p)
        base = os.path.basename(d)
        if sid and base != sid:
            print(f'  ❌ 目录名 {base} ≠ header id {sid}')
            bad += 1
        if cwd:
            slug = cwd.strip('/').replace('/', '-')
            parent = os.path.basename(os.path.dirname(d))
            if parent != f'--{slug}--':
                print(f'  ❌ 工作区目录 {parent} ≠ --{slug}--  (cwd={cwd})')
                bad += 1
    print(f'  共 {len(files)} 个会话，路径身份不符 {bad} 个')
    return 1 if bad else 0


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    if any(a in ('-h', '--help') for a in args):
        print(__doc__.strip())
        sys.exit(0)
    identity = '--identity' in args
    args = [a for a in args if a != '--identity']
    root = args[0] if args else os.path.expanduser('~/.dsh/sessions')
    if not os.path.isdir(root):
        sys.exit(f'不是目录: {root}')
    sys.exit(check_identity(root) if identity else check_frames(root))
