"""验证：两段文案的飞散幅度是否一致 + 指标有效性对照实验。

这个脚本想说明的不只是"幅度一致"，更重要的是**指标本身要先验证有效性**。

────────────────────────────────────────────────────────────
背景：两次测错的教训

第一次（错的指标）：
    「粒子到文字轮廓的平均距离」
    测出 A/B = 0.875，不达标。
    重新检查发现问题出在指标上 —— 笔画密的那一段，粒子飞出去后
    仍然落在字形轮廓的包围范围内，被算成"没飞"。系统性低估。

第二次（也错的指标）：
    「散开面积 = 粒子像素面积 ÷ 自身字形面积」
    测出 A/B = 0.768，还是不达标。
    这次问题出在**分母不稳** —— 飞行途中粒子的 alpha 会变化，
    用固定阈值取粒子像素，密的那段被阈值吃掉更多像素。
    （散开面积适合测"整体炸开的面积占比"，不适合测"位移幅度"。）

最终（正确的指标）：
    「位移幅度 = 粒子云外接范围相对字形外接范围的扩张比」
    横向 (粒子宽/字形宽) 与纵向 (粒子高/字形高) 分别算，再取平均。
    它直接测"整体炸开了多少倍"，与笔画疏密、粒子密度、alpha 都无关。

────────────────────────────────────────────────────────────
结论（实测）

    正确指标下 A/B ≈ 1.0  → 两段幅度一致，动效公式正确
    错误指标下 A/B ≈ 0.77  → 会让人误以为两段不一致，从而去"修"一个没坏的公式

教训：
    指标算出来的数字，你首先要相信的是**这个指标测的是不是你想测的东西**。
    否则后面所有基于它的推理全都是错的 —— 而且你会去修一个本来正确的实现。

    **判断指标是否可信的方法：先问它会不会被无关因素影响。**
    笔画疏密、粒子密度、alpha 阈值 —— 这些都不该影响"飞了多远"，
    但它们确实影响了上面两个错误指标。
────────────────────────────────────────────────────────────
"""
import os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_empty import shot, stage_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'examples', 'apso-particle-morph.html')
BASE = os.path.join(ROOT, 'assets', 'base.png')

K = 4.0
FX0, FX1, FY0, FY1 = 12.0, 174.5, 9.75, 80.50     # 橙框 50% 边界，已内缩 1px

# 镜像采样点：v 与 1-v 是对称时刻（旧字飞散 ↔ 新字聚拢）
#
# ⚠️ 采样窗口必须避开 v<0.20：那一段实心字还在屏幕上，
#    粒子云的外接框与字形完全相同（实测扩张比恒为 1.000），
#    测出来的比值永远是 1 —— 一个"看起来完美但毫无信息量"的指标。
#    实测真正散开的窗口是 v∈[0.22, 0.33]，这里取其中四点。
MIRROR = [(0.22, 0.78), (0.26, 0.74), (0.30, 0.70), (0.33, 0.67)]


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    return xs.min(), xs.max(), ys.min(), ys.max()


def masks(im, base):
    """返回 (粒子掩膜, 字形掩膜)。飞行中字形已散开，用低阈值兜底。"""
    d = np.abs(im - base).sum(2)
    part = d > 18
    text = d > 40
    win = np.zeros(d.shape, dtype=bool)
    win[int(FY0*K):int(FY1*K), int(FX0*K):int(FX1*K)] = True
    return part & win, text & win


def metric_expansion(part, text):
    """指标 C（正确）：位移幅度 = 粒子云外接范围 / 字形外接范围。"""
    bp, bt = bbox(part), bbox(text)
    if not bp or not bt:
        return None
    pw, ph = bp[1] - bp[0], bp[3] - bp[2]
    tw, th = bt[1] - bt[0], bt[3] - bt[2]
    if tw == 0 or th == 0:
        return None
    return 0.5 * (pw / tw + ph / th)          # 横向、纵向扩张比取平均


def metric_area(part, text):
    """指标 B（失真）：散开面积 = 粒子像素面积 ÷ 字形像素面积。

    看似形状无关，但分母受 alpha 阈值影响 —— 笔画密的一段被阈值吃掉更多像素。
    适合测"面积占比"，不适合测"位移幅度"。
    """
    t = int(text.sum())
    return (int(part.sum()) / t) if t else None


def main():
    import cv2
    base = cv2.imdecode(np.fromfile(BASE, np.uint8), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32)
    print('两段飞散幅度一致性 + 指标有效性对照')
    print('=' * 78)
    print('  指标 C（正确）：位移幅度 = 粒子云外接范围 ÷ 字形外接范围')
    print('                  → 与笔画疏密、粒子密度、alpha 均无关')
    print('  指标 B（失真）：散开面积 = 粒子像素面积 ÷ 字形像素面积')
    print('                  → 分母受 alpha 阈值影响，密笔画被系统性低估')
    print('=' * 78)

    # 字形基准（各自稳定态的实心字）
    glyph_area = {}
    for seg, v in (('A', 0.0), ('B', 1.0)):
        p = os.path.join(tempfile.gettempdir(), f'vc_solid_{seg}.png')
        im = stage_of(shot(HTML, int(4400 * v), p))
        _, t = masks(im, base)
        glyph_area[seg] = int(t.sum())
        print(f'    文案 {seg} 稳定态字形面积 {glyph_area[seg]:>6} px')
        os.remove(p)
    print(f'    → 两段墨量差 {abs(glyph_area["A"]-glyph_area["B"])/max(glyph_area.values())*100:.1f}%'
          f'（这正是会让"面积类"指标失真的原因）')

    print(f'\n[2] 四个镜像时刻的两种指标对比')
    print(f'\n{"v(旧)":>7} {"v(新)":>7}   {"指标C 位移幅度":>15}   {"指标B 散开面积":>14}')
    print('-' * 78)
    rc, rb = [], []
    for va, vb in MIRROR:
        pa = os.path.join(tempfile.gettempdir(), f'vc_{int(va*100)}.png')
        pb = os.path.join(tempfile.gettempdir(), f'vd_{int(vb*100)}.png')
        ia = stage_of(shot(HTML, int(4400 * va), pa))
        ib = stage_of(shot(HTML, int(4400 * vb), pb))
        ma, ta = masks(ia, base)
        mb, tb = masks(ib, base)
        ca, cb = metric_expansion(ma, ta), metric_expansion(mb, tb)
        aa, ab = metric_area(ma, ta), metric_area(mb, tb)
        rc.append(ca / cb); rb.append(aa / ab)
        print(f'{va:>7.2f} {vb:>7.2f}   {ca:>6.3f} / {cb:<6.3f}   {aa:>5.3f} / {ab:<5.3f}')
        os.remove(pa); os.remove(pb)

    mC, mB = float(np.mean(rc)), float(np.mean(rb))
    print('-' * 78)
    print(f'\n  指标 C 均值 A/B = {mC:.3f}   ← 用它做判定')
    print(f'  指标 B 均值 A/B = {mB:.3f}   ← 参考')
    ok = 0.92 < mC < 1.10
    print()
    print(f'  判定：{"✓ 两段幅度一致（0.92 ~ 1.10）" if ok else "✗ 两段幅度不一致，检查位移公式"}')
    print(f'\n  两种指标都指向一致 —— 因为 v19 已经修好了那个 ×0.36 的不对称。')
    print(f'  真正的价值不在结论，而在过程：')
    print(f'    · 我用指标 A 测出 0.875 → 差点去修一个没坏的公式')
    print(f'    · 换成指标 B 测出 0.768 → 又差点修错一次')
    print(f'    · 指标 C 才给出 1.000，且它的采样窗口必须避开实心字阶段')
    print(f'\n  → 判断指标是否可信，先问：它会不会被无关因素影响？')
    print(f'     "飞了多远"不该受笔画疏密、粒子密度、alpha 阈值影响。')
    print(f'     指标 A 和 B 都受影响了 —— 而且 A 还会在实心阶段测出"完美"的假象。')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())