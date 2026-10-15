"""生成品牌卡底板 base.png（728×352 = 逻辑 182×88 × 4）。

底板 = 红色卡片 + 顶部 logo 字标，边缘用 sigmoid 斜坡做抗锯齿。
输出是「不含文字的静止底板」——文字层在 HTML 里实时绘制，两者叠加。

版面规则（重要）：
    留白基准是「logo ∪ 正文」的联合包围盒，不是正文单独。
    这个联合块 135.50 × 43.75，到橙框四边统一 14.50px。
    正因为要装下 logo，橙框内高从 61.25 加高到 72.75，画布 182×72 → 182×88。

用法：python make_base.py
输出：assets/base.png（约 4.9KB）
"""
import os, json
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = 4                          # 输出倍率：逻辑 182×88 -> 物理 728×352
W, H = 182 * K, 88 * K
RED = np.array([223, 64, 49], np.float32)
PURE = np.array([250, 250, 250], np.float32)

CFG = json.load(open(os.path.join(ROOT, 'src', 'config.json'), encoding='utf-8'))
LOGO = CFG.get('logo', {'text': 'APPSO', 'font': 'Segoe UI', 'size': 9.4,
                        'track': -0.1, 'cx': 93.5, 'by': 14.75, 'gain': 1.0})


def ramp(v, a, b):
    t = np.clip((v - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# 逻辑坐标（保留原 2px 抗锯齿斜坡的视觉比例）
# v17：整体块（字标∪正文）四边统一 14.5px —— 上边界保持 8.75、下边界 69.5→70.0→81.50
xs = np.arange(W, dtype=np.float32) / K
ys = np.arange(H, dtype=np.float32) / K
cx = ramp(xs, 9.6, 12.4) * (1 - ramp(xs, 174.6, 176.4))
cy = ramp(ys, 7.85, 9.65) * (1 - ramp(ys, 80.6, 82.4))
m = (cy[:, None] * cx[None, :]).astype(np.float32)
im = np.full((H, W, 3), PURE, np.float32)
for c in range(3):
    im[..., c] = PURE[c] * (1 - m) + RED[c] * m

# ---- 顶部 logo 字标：高分辨率、清晰（不做纹理调制）----
# 位置 by 是「框顶→字标顶 14.50px、字标→正文顶 5.00px」这两个条件解出来的，
# 改动版式时这两个数都要重算，不能凭感觉挪。
FONTP = CFG['logo']['font_path']
SS = 8
lim = Image.new('L', (W * SS, H * SS), 0)
dl = ImageDraw.Draw(lim)
f = ImageFont.truetype(FONTP, int(round(LOGO['size'] * K * SS)))
txt = LOGO['text']
ws = [dl.textlength(ch, font=f) for ch in txt]
tot = sum(ws) + LOGO['track'] * K * SS * (len(txt) - 1)
x = LOGO['cx'] * K * SS - tot / 2
for ch, w in zip(txt, ws):
    dl.text((x, LOGO['by'] * K * SS), ch, font=f, fill=255, anchor='ls')
    x += w + LOGO['track'] * K * SS
cov = cv2.resize(np.asarray(lim, np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)
e = np.clip(cov * LOGO['gain'], 0, 1)     # 清晰字标（原 gain 1.2 是为匹配低分辨率模糊）
for c in range(3):
    im[..., c] = im[..., c] * (1 - e) + PURE[c] * e

im8 = np.clip(im, 0, 255).astype(np.uint8)
TARGET = os.path.join(ROOT, 'assets', 'base.png')
os.makedirs(os.path.dirname(TARGET), exist_ok=True)
cv2.imencode('.png', im8[..., ::-1], [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tofile(TARGET)
print(f"已生成: {TARGET}  {im8.shape[1]}×{im8.shape[0]}  {os.path.getsize(TARGET)} bytes")
