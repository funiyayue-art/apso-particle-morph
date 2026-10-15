"""验证：整体块（logo ∪ 正文）到橙框四边的留白是否等距。

一个容易算错的地方：
    留白基准不是「正文」，而是「logo ∪ 正文」的联合包围盒。
    早期只按正文算，导致顶部只剩 3.00px（logo 挤在框顶），而左右下都是 14.5px。

另一个坑：
    橙框与文字块的长宽比不同（164.50×72.75 vs 135.50×43.75），
    所以**仅靠挪位置无法让四边等距**，必须同时调整框的尺寸或内容缩放。
    这个脚本顺带报告当前版本的宽高比关系，方便改版式时先算这笔账。

用法：
    python tools/verify_geometry.py
"""
import os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_empty import shot, stage_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'examples', 'apso-particle-morph.html')
BASE = os.path.join(ROOT, 'assets', 'base.png')

K = 4.0
FRAME = (11.0, 175.5, 8.75, 81.50)        # 橙框 50% 边界（逻辑）
TARGET_PAD = 14.50                        # 目标留白
TOL = 0.30                                # 允许偏差（亚像素级）


def bbox_of(mask):
    ys, xs = np.nonzero(mask)
    return None if len(ys) == 0 else (xs.min(), xs.max(), ys.min(), ys.max())


def analyse(im, base, name):
    """整体块 = logo ∪ 正文。

    ⚠️ logo 是【烘在底板里】的，不是文字层画的。
       所以必须把底板的白色区域一并并进来，只测文字层会漏掉 logo，
       上间距会算成 26.00 而不是 14.50。
    """
    d = np.abs(im - base).sum(2)
    # 文字层内容（正文）
    text = d > 12
    # 底板里的 logo（近白像素）
    br, bg, bb = base[..., 0], base[..., 1], base[..., 2]
    logo = (br > 225) & (bg > 220) & (bb > 220)
    # 限制在橙框内（避开底板外的白色页面背景）
    win = np.zeros(d.shape, bool)
    win[int((FRAME[2]+0.5)*K):int((FRAME[3]-0.5)*K),
        int((FRAME[0]+0.5)*K):int((FRAME[1]-0.5)*K)] = True
    content = (text | logo) & win
    b = bbox_of(content)
    if not b:
        print(f'  {name}: 未检出白色内容')
        return None
    x0, x1, y0, y1 = (v / K for v in b)
    pad_l = x0 - FRAME[0]
    pad_r = FRAME[1] - x1
    pad_t = y0 - FRAME[2]
    pad_b = FRAME[3] - y1
    w, h = x1 - x0, y1 - y0
    print(f'\n  {name}')
    print(f'    整体块 bbox  逻辑 x {x0:.2f}..{x1:.2f}（宽 {w:.2f}）  y {y0:.2f}..{y1:.2f}（高 {h:.2f}）')
    print(f'    留白        左 {pad_l:6.2f}   右 {pad_r:6.2f}   上 {pad_t:6.2f}   下 {pad_b:6.2f}')
    spread = max(pad_l, pad_r, pad_t, pad_b) - min(pad_l, pad_r, pad_t, pad_b)
    ok = spread <= TOL
    print(f'    极差 {spread:.2f}px  →  {"✓ 四边等距" if ok else "✗ 不等距"}')
    return dict(name=name, pad=(pad_l, pad_r, pad_t, pad_b), w=w, h=h, spread=spread, ok=ok)


def main():
    import cv2
    base = cv2.imdecode(np.fromfile(BASE, np.uint8), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32)
    print('整体块四边留白等距验证')
    print('=' * 68)
    print(f'  橙框 50% 边界（逻辑）x {FRAME[0]}..{FRAME[1]} / y {FRAME[2]}..{FRAME[3]}')
    print(f'  目标留白 {TARGET_PAD}px，允许极差 {TOL}px')
    print('  基准：整体块 = logo ∪ 正文（不是正文单独）')
    print('=' * 68)

    results = []
    for name, v in (('文案 A', 0.0), ('文案 B', 1.0)):
        p = os.path.join(tempfile.gettempdir(), f'vg_{name[-1]}.png')
        im = stage_of(shot(HTML, int(4400 * v), p))
        r = analyse(im, base, name)
        if r:
            results.append(r)
        os.remove(p)

    if not results:
        print('\n✗ 未取得有效测量')
        return 1

    print('\n[宽高比关系] —— 改版式前先算这笔账')
    fw = FRAME[1] - FRAME[0]
    fh = FRAME[3] - FRAME[2]
    print(f'  橙框内区     {fw:.2f} × {fh:.2f}   宽高比 {fw/fh:.3f}')
    r = results[0]
    print(f'  整体块       {r["w"]:.2f} × {r["h"]:.2f}   宽高比 {r["w"]/r["h"]:.3f}')
    same = abs(fw/fh - r['w']/r['h']) < 0.02
    print(f'  → 两者{"一致" if same else "不一致"}')
    if not same:
        print(f'    宽高比不同 → **仅靠挪位置无法让四边等距**')
        print(f'    必须同时动框的尺寸或缩放内容。三条路：')
        print(f'      · 加高橙框与画布（保住当前留白与字号）')
        print(f'      · 等比放大内容（留白会等比缩小）')
        print(f'      · 只做垂直居中（四边不再同一个数）')

    ok = all(x['ok'] for x in results)
    print('\n' + '-' * 68)
    print(f'结论：{"✓ 两段文案的整体块四边留白均等距" if ok else "✗ 存在偏差"}')
    print('\n提示：测量用的是稳定态实心字，此时 logo 与正文同时可见，联合包围盒才完整。')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())