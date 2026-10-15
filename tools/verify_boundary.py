"""验证：粒子是否飞出橙色边框。

原理：
    base.png 是静止底板。橙框 50% 边界之外若出现与底板不同的像素，
    说明有粒子跑到了框外（框内本来也是红底，粒子在里面是允许的）。
    基线噪声（舞台圆角）约 4–6 px，判定阈值取 20 px。

两个必须知道的坑：
  1. 测量窗口要从橙框边界【向内缩 1px】再统计。紧贴边缘量，
     边缘的抗锯齿过渡带会被当成越框，导致假阳性。
  2. 不要只看单帧。粒子位移的峰值时刻很难猜，必须扫多个进度点，
     尤其是两段粒子位移最大的时刻（本项目是 v≈0.18 与 v≈0.82）。

用法：
    python tools/verify_boundary.py
    python tools/verify_boundary.py --stress      # 压力测试：把飞散幅度拉到上限
"""
import os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_empty import shot, stage_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'examples', 'apso-particle-morph.html')
BASE = os.path.join(ROOT, 'assets', 'base.png')

# 逻辑坐标系 182×88，舞台 728×352 → 物理/逻辑 = 4.0
K = 4.0
# 橙框 50% 边界（逻辑），向内缩 1px 作为测量窗口外沿
FX0, FX1, FY0, FY1 = 11.0, 175.5, 8.75, 81.50
MARGIN = 1.0
THRESH = 18          # 差异阈值（三通道和）
PASS_PX = 20         # 允许的基线噪声


def outside_count(im, base):
    """统计框外与底板不同的像素数。"""
    d = np.abs(im - base).sum(2) > THRESH
    x0 = int((FX0 + MARGIN) * K); x1 = int((FX1 - MARGIN) * K)
    y0 = int((FY0 + MARGIN) * K); y1 = int((FY1 - MARGIN) * K)
    left = int(d[:, :x0].sum())
    right = int(d[:, x1:].sum())
    top = int(d[:y0, :].sum())
    bot = int(d[y1:, :].sum())
    return left, right, top, bot


def main():
    stress = '--stress' in sys.argv
    import cv2
    base = cv2.imdecode(np.fromfile(BASE, np.uint8), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32)
    html = HTML
    if stress:
        # 复制一份并把滑块默认值改成上限 70
        src = open(HTML, encoding='utf-8').read()
        tmp = os.path.join(tempfile.gettempdir(), 'apso_stress.html')
        open(tmp, 'w', encoding='utf-8').write(
            src.replace('id="sAmp" min="6" max="70" step="2" value="14"',
                        'id="sAmp" min="6" max="70" step="2" value="70"'))
        html = tmp
        print('压力测试模式：飞散幅度 = 70px（滑块上限）\n')

    print('粒子越框验证')
    print('=' * 72)
    print(f'  橙框 50% 边界（逻辑）x {FX0}..{FX1} / y {FY0}..{FY1}')
    print(f'  测量窗口向内缩 {MARGIN}px，基线噪声容忍 {PASS_PX}px')
    print('=' * 72)

    # 扫 14 个进度点，覆盖两段粒子位移峰值
    probes = [0.02, 0.06, 0.10, 0.14, 0.18, 0.22, 0.30, 0.36,
              0.50, 0.64, 0.70, 0.78, 0.82, 0.90]
    ok = True
    print(f'\n{"v":>6} {"时刻":>8}  {"左":>6} {"右":>6} {"上":>6} {"下":>6} {"合计":>7}  判定')
    print('-' * 72)
    for v in probes:
        at = int(4400 * v)
        p = os.path.join(tempfile.gettempdir(), f'vb_{int(v*100)}.png')
        im = stage_of(shot(html, at, p))
        if im.shape != base.shape:
            print(f'{v:>6.2f} {at:>6}ms  尺寸不一致 {im.shape} vs {base.shape}')
            ok = False
            continue
        l, r, t, b = outside_count(im, base)
        tot = l + r + t + b
        good = tot <= PASS_PX
        ok &= good
        print(f'{v:>6.2f} {at:>6}ms  {l:>6} {r:>6} {t:>6} {b:>6} {tot:>7}  '
              f'{"✓ 未越框" if good else "✗ 越框"}')
        os.remove(p)

    print('-' * 72)
    print(f'结论：{"✓ 全程未越框" if ok else "✗ 存在越框"}')
    print(f'\n说明：基线噪声 4–6px 来自舞台圆角（红卡边缘的抗锯齿过渡带），不是粒子。')
    if not stress:
        print('提示：加 --stress 可把飞散幅度拉到上限 70px 做压力测试。')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())