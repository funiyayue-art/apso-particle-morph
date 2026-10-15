"""生成字体子集（woff2 → base64 文本），供 make_html.py 内嵌。

为什么需要这一步：
    产物要求是「单文件 HTML，双击即开，无网络依赖」。
    完整的中文字体有 5–10MB，直接内嵌会让 HTML 体积失控。
    所以只把用到的字符子集化，压成 woff2（≈30KB），再转 base64 内嵌。

用法：
    python tools/make_font_subset.py

依赖：
    pip install fonttools brotli

跨平台字体路径：
    Windows: C:/Windows/Fonts/msyhbd.ttc（微软雅黑 Bold）/ msyh.ttc（Regular）
    macOS:   /System/Library/Fonts/PingFang.ttc
    Linux:   /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc

    换字体只需改下面的 FONT_PATHS，**但必须重新拟合字槽**（config.json 里的
    ctr / sc / dys）——不同字体的字面宽不同，直接套用会让四边留白失衡。
"""
import os, sys, subprocess, base64, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '.fonttmp')

FONT_PATHS = {
    'bold': [
        r'C:/Windows/Fonts/msyhbd.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    ],
    'regular': [
        r'C:/Windows/Fonts/msyh.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ],
}

CFG = json.load(open(os.path.join(ROOT, 'src', 'config.json'), encoding='utf-8'))
CHARS = sorted(set(CFG['texts']['A'] + CFG['texts']['B']))


def pick(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise SystemExit(
        '找不到中文字体。请编辑本脚本的 FONT_PATHS，指向一个系统里的中文 TTF/TTC。\n'
        '候选：Windows msyh.ttc / macOS PingFang.ttc / Linux NotoSansCJK')


def build(kind):
    src = pick(FONT_PATHS[kind])
    os.makedirs(TMP, exist_ok=True)
    txt = os.path.join(TMP, f'sub-{kind}.txt')
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(''.join(CHARS))
    woff2 = os.path.join(TMP, f'sub-{kind}.woff2')
    # ttc 需要 --font-number=0 指定第一个字体
    subprocess.run([
        sys.executable, '-m', 'fontTools.subset', src,
        f'--text-file={txt}',
        f'--output-file={woff2}',
        '--flavor=woff2',
        '--layout-features=*',
        '--no-hinting',
        '--desubroutinize',
    ], check=True)
    b64 = base64.b64encode(open(woff2, 'rb').read()).decode()
    dst = os.path.join(ROOT, 'src', f'font-subset-{kind}.b64')
    open(dst, 'w', encoding='utf-8').write(b64)
    print(f'  {kind:<8} {os.path.basename(src)} → {len(b64)//1024}KB base64  → src/font-subset-{kind}.b64')


if __name__ == '__main__':
    print(f'子集字符集（{len(CHARS)} 个）: {"".join(CHARS)}')
    print('生成字体子集...')
    for kind in ('bold', 'regular'):
        build(kind)
    print('\n完成。现在可以运行：python src/make_html.py')
    print('提示：字体子集是构建产物，建议加入 .gitignore，让使用者自行生成。')