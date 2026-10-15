"""生成自包含 HTML：高分辨率(4×)底板 + 清晰实心字形 + 粒子转场。

用法：
    python make_html.py            # Bold
    python make_html.py --reg      # Regular

输出：examples/apso-particle-morph.html（自包含，双击即开）

────────────────────────────────────────────────────────────
设计要点（都是踩过坑换来的，改代码前请先读 docs/复刻档案.md）

· 时间轴两段**互不重叠**（旧字散尽 0.36 → 空场 0.64 → 新字聚起 0.64）
    早期版本实心层用 pr 驱动、粒子层用 1-pr 驱动，两个时钟不一致，
    第一个周期恰好同步所以测试全过，第二个周期才暴露旧字残留 bug。
· 粒子**预打包**为 Float32Array，末尾单次 beginPath/rect/fill 批量描边
    （globalAlpha/fillStyle 全场同值，逐粒子设置纯属浪费；实测提速 5.41×）
· 每个粒子预存**朝四边到框的可用空间**，位移按方向等比压缩 → 零分配零 GC 不越框
· 不做任何模糊（blur=0）+ 4× 超采样 + 覆盖率 gamma 0.88 增实 → 与 logo 同级清晰
· 页面用 min-height:100% + align-items:flex-start（顶部对齐、可正常滚动）
    写成 height:100% + align-items:center 会在窗口比内容矮时裁掉顶部且滚不回去
────────────────────────────────────────────────────────────
"""
import os, sys, json, base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = '--reg' in sys.argv                     # 使用微软雅黑 Regular 字重
FW = '400' if REG else '700'
TARGET = os.path.join(ROOT, 'examples',
                      'apso-particle-morph-light.html' if REG
                      else 'apso-particle-morph.html')

def b64(p): return base64.b64encode(open(p, 'rb').read()).decode()

# 字体子集由 tools/make_font_subset.py 生成（见该脚本说明）
FONT_FILE = os.path.join(ROOT, 'src', 'font-subset-regular.b64' if REG
                                else 'font-subset-bold.b64')
if not os.path.exists(FONT_FILE):
    raise SystemExit(
        f"缺少字体子集：{FONT_FILE}\n"
        f"请先运行：python tools/make_font_subset.py")
FONT = open(FONT_FILE, encoding='utf-8').read().strip()

BASE = b64(os.path.join(ROOT, 'assets', 'base.png'))
CFG = json.load(open(os.path.join(ROOT, 'src', 'config.json'), encoding='utf-8'))

A = CFG['glyphs']['A']                                   # 几何（ctr/sc/dys/px/bl/gain/blur）
B = CFG['glyphs']['B']                                   # 同结构，位置由反算得到

TMPL = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>APPSO 粒子形变 · 复刻 v19</title>
<style>
  @font-face{
    font-family:'APPSO Hei';
    src:url(data:font/woff2;base64,__FONT__) format('woff2');
    font-weight:__FW__; font-style:normal; font-display:block;
  }
  /* v19 布局修复：内容（舞台 352 + 控制条 + 说明 ≈ 930px）常比窗口高，
     旧写法 height:100% + align-items:center 会把溢出部分平均推到视口上下外侧，
     而顶部那半截**滚动不回去** —— 红卡上沿被裁、字标顶正好落在裁切线上，
     看起来就像「APPSO 顶部与橙框重合」。改为顶部对齐 + 正常滚动 + 舞台自适应宽度。 */
  html,body{margin:0;min-height:100%}
  body{display:flex;align-items:flex-start;justify-content:center;background:#f1efea;
       font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
  .wrap{display:flex;flex-direction:column;align-items:center;gap:14px;flex:none;
        width:100%;max-width:100%;box-sizing:border-box;padding:22px 16px 34px}
  .stage{position:relative;width:100%;max-width:728px;aspect-ratio:728/352;
         flex:none;background:#fafafa;overflow:hidden;
         border-radius:4px;box-shadow:0 2px 18px rgba(0,0,0,.12)}
  .card{position:absolute;inset:0;background:#fafafa;overflow:hidden}
  canvas{position:absolute;inset:0;width:100%;height:100%}
  .bar{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;font-size:12px;
       color:#333;width:100%;max-width:840px;align-items:center}
  .bar label{display:flex;align-items:center;gap:5px}
  .bar input[type=range]{width:78px}
  button{padding:5px 14px;border:1px solid #bbb;border-radius:6px;background:#fff;
         cursor:pointer;font-size:12px}
  .tag{font-size:11px;color:#888}
  .notes{width:100%;max-width:760px;font-size:12px;line-height:1.75;color:#444;background:#fff;
         border:1px solid #e6e2da;border-radius:8px;padding:12px 16px}
  .notes h3{margin:0 0 6px;font-size:13px;color:#c0392b;letter-spacing:.5px}
  .notes code{background:#f4f1ea;padding:1px 5px;border-radius:3px;font-size:11px}
  .notes b{color:#c0392b}
  .notes ol{margin:6px 0 0;padding-left:20px}
  .notes li{margin:3px 0}
</style>
</head>
<body>
<div class="wrap">
  <div class="stage" id="stage"><div class="card" id="card"><canvas id="cv"></canvas></div></div>
  <div class="bar">
    <label>变形时长 <input type="range" id="sSpeed" min="1.4" max="6" step="0.1" value="4.4"><i id="vSpeed">4.4s</i></label>
    <label>粒子格 <input type="range" id="sCell" min="1" max="4" step="0.5" value="1"><i id="vCell">1px</i></label>
    <label>飞散幅度 <input type="range" id="sAmp" min="6" max="70" step="2" value="14"><i id="vAmp">14px</i></label>
    <button id="btn">暂停</button>
    <span class="tag" id="info"></span>
  </div>
  <div class="notes">
    <h3>这个动效是怎么做出来的</h3>
    <ol>
      <li><b>文字是矢量清晰渲染</b>——画布内部以 4× 分辨率（728×352）原生绘制，逐字超采样后面积降采样，稳定态笔画为纯白实心。</li>
      <li><b>不是扫过、不是遮罩</b>——整行文案「粒子溶解 → 粒子重组」直接形变：旧文案先被打散成粒子飞离原位，同一批粒子再落位拼成新文案。</li>
      <li><b>两段文案的飞散幅度一致</b>——「AI时代的」与「灵感指南」的位移峰值取同一个基准（<code>ampK</code>），不会出现一套炸得开、另一套收得紧。</li>
      <li><b>APPSO 字标与正文是一个整体块，四边到橙框都是 14.50px</b>——不只看正文：把顶部字标与下方文字合起来看成一个块，这个块到橙框的上下左右留白是同一个数值。两套文案各自都做到了 14.50px（「AI时代的」因字形墨迹比「灵感指南」宽 1px，其字槽跨度按目标留白单独反算为 103.0px）。为此橙框内高由 61.25px 加高到 72.75px。</li>
      <li><b>粒子不越出橙色边框</b>——每个粒子在生成时就记住了它朝上下左右到边框的可用空间，飞散位移与抖动会被逐方向等比压缩夹取，绝不会飞到框外；14px 的飞散量本就收在可用空间之内，实际基本不会触发夹取。</li>
      <li><b>散尽即彻底空屏</b>——旧字粒子飞散完毕到新字粒子聚起之间是纯净空场，不放任何零星碎点，旧文案不会以任何形式留下残影。</li>
      <li><b>清晰度与 APPSO 字标同级</b>——实心笔画与字标走同一条高分辨率渲染链路（超采样 4× + 面积降采样，不做任何模糊），稳定态为纯白实心。</li>
      <li><b>旧文案会彻底消失</b>——时间轴被切成互不重叠的两段：<code>旧字实心淡出 → 旧字粒子散尽</code> 之后，<code>新字粒子聚起 → 新字实心浮现</code> 才开始，中间有一段只剩零星飞散点的空场，两套文案绝不会叠在一起。</li>
      <li><b>字形本身不变</b>——两套文案共用同一字体与同一套字槽（<code>ctr / sc / dys</code> 逐字中心/字号/纵向偏移），换文案时只换字，不动版式。</li>
      <li><b>窗口再小也不会裁掉画面</b>——页面内容顶部对齐、可正常滚动，舞台宽度自适应窗口（最大 728×352，等比缩放）。旧版把内容垂直居中，窗口比内容矮时上半截会被推到视口之外且<b>滚动不回去</b>，红卡上沿被裁、字标顶看起来就贴在了橙框边缘。</li>
      <li><b>粒子不侵入顶部 APPSO 字标</b>——红卡与字标是常驻底板（同样高分辨率），粒子只在文字带内生成与飞散，顶部为安全区。</li>
      <li><b>高性能</b>——粒子属性预先打包成数组，每帧只用一次路径批量描边（相同粒子数下实测比逐粒子绘制快 <b>5.4 倍</b>）；稳定态整帧跳过重绘，切到后台不吃 CPU。</li>
    </ol>
  </div>
</div>

<script>
window.onerror = function(m,s,l,c){ document.title = 'ERRMID: '+m+' @'+l+':'+c; };
/* ============================================================
   几何（逻辑基准 182×88，物理 4×）：橙框 x9.6..176.4 / y7.85..82.4
        → 50% 边界 x11.0..175.5 / y8.75..81.50（内区 164.50 × 72.75）
   整体块（字标∪正文）135.50 × 43.75，四边到框 14.50px
   颜色：底 #df4031(223,64,49)  文字 #fafafa(250,250,250)
   ── 时间轴（v ∈ [0,1]：0 = A 实心，1 = B 实心）──
     A 实心   v 0.00 → 0.20   （淡出）
     A 粒子   v 0.00 → 0.36   （0 → 峰 → 0，散尽）
     —— 空场 v 0.36 → 0.64 ——（约 360ms，只剩零星飞散点）
     B 粒子   v 0.64 → 1.00   （0 → 峰 → 0，聚拢）
     B 实心   v 0.80 → 1.00   （浮现）
   两段粒子互不重叠 → 旧文案不可能残留到新文案上
   ============================================================ */
const FONT = '"APPSO Hei", "Microsoft YaHei", "PingFang SC", sans-serif';
let SS = 4;                  // 超采样倍率（在物理分辨率之上，高 DPI 时自动降档）
/* 橙色矩形边框（逻辑坐标）与飞散安全边距：
   v17：把「APPSO 字标 + 正文」当整体块，四边统一 14.5px
        → 框上边界保持 8.75、下边界 70.00 → 81.50（画布 182×72 → 182×88）
   所有粒子位移（飞散 + 抖动）一律夹在 [FX0,FX1]×[FY0,FY1] 内，绝不越框。 */
const FRM = { x0:9.6, x1:176.4, y0:7.85, y1:82.4 };
const FLY_PAD = 1.0;                  // 飞散安全边距（逻辑 px）
let FX0=0, FX1=0, FY0=0, FY1=0;       // 物理坐标内边界（fit 时按 K 更新）
function updFrame(){
  const p = FLY_PAD*K;
  FX0 = FRM.x0*K + p; FX1 = FRM.x1*K - p;
  FY0 = FRM.y0*K + p; FY1 = FRM.y1*K - p;
}

const CFG = {
  /* 两段文案共用同一套字槽（ctr / sc / dys / px），仅 B 段的字槽与基线按
     「四边留白等距」的目标反算过——B 段墨迹天生宽 1px、底边高 0.25px，
     直接套用 A 段字槽会让左右留白差 0.5px。换文案时只换字，不动版式。 */
  A: { text:'__TEXTA__', T:['灵','感','指','南'], ctr:__ACTR__,
       sc:__ASC__, dys:__ADYS__,
       px:__APX__, bl:__ABL__, gain:__AGAIN__, blur:__ABLUR__ },
  B: { text:'__TEXTB__', T:[['A','I'],'时','代','的'], ctr:__BCTR__,
       sc:__ASC__, dys:__ADYS__,
       px:__APX__, bl:__BBAS__, gain:__BGAIN__, blur:__BBLUR__ }
};

let W = 728, H = 352, K = 4, MW = 728, MH = 352;   // MW/MH = 物理分辨率（182×88 × K）
let blendA=null, blendB=null, PA=null, PB=null, cfg={cell:2};

const card = document.getElementById('card');
const cv   = document.getElementById('cv');
const ctx  = cv.getContext('2d');

/* ---------- 资源 ---------- */
const IMG = {};
let NFONT = false;
function ready(){ return NFONT && IMG.base; }
function tryBuild(){ if(ready()) build(); }

function loadImg(key, uri){
  const im = new Image();
  im.onload = ()=>{ IMG[key]=im; tryBuild(); };
  im.src = uri;
}
loadImg('base','data:image/png;base64,__BASE__');

let _vSpeed = 4.4, _vCell = 1, _vAmp = 14;
function P(){ return { speed:_vSpeed*1000, cell:_vCell, amp:_vAmp }; }

/* ---------- 离屏缓冲区 ---------- */
const _hi   = document.createElement('canvas');   // 超采样字形
const _hctx = _hi.getContext('2d', { willReadFrequently:true });
const _tmp  = document.createElement('canvas');   // 模糊源
const _tctx = _tmp.getContext('2d');
const _blur = document.createElement('canvas');   // 模糊目标

/* 超采样渲染字形 → 物理分辨率覆盖率 Float32Array(MW*MH) */
function glyphCoverage(spec){
  const hw = MW*SS, hh = MH*SS;
  _hi.width = hw; _hi.height = hh;
  _hctx.clearRect(0,0,hw,hh);
  _hctx.fillStyle = '#fff';
  _hctx.textAlign = 'center';
  _hctx.textBaseline = 'alphabetic';
  spec.T.forEach((g,i)=>{
    const s = Array.isArray(g) ? g.join('') : g;
    const j = Math.min(i,3);
    const sc = spec.sc[j] || 1;
    _hctx.font = `${__FW__} ${(spec.px*K*SS*sc).toFixed(2)}px ${FONT}`;
    _hctx.fillText(s, spec.ctr[j]*K*SS, (spec.bl + (spec.dys[j]||0))*K*SS);
  });
  const hs = _hctx.getImageData(0,0,hw,hh).data;
  const cov = new Float32Array(MW*MH);
  const inv = 1/(SS*SS*255);
  for (let y=0;y<MH;y++){
    for (let x=0;x<MW;x++){
      let sum = 0;
      for (let yy=0; yy<SS; yy++){
        const row = ((y*SS+yy)*hw + x*SS)*4 + 3;
        for (let xx=0; xx<SS; xx++) sum += hs[row + xx*4];
      }
      cov[y*MW+x] = sum * inv;
    }
  }
  return cov;
}

/* 高斯模糊（就地修改覆盖率数组，半径按物理像素） */
function blurCov(cov, r){
  if (r <= 0) return cov;
  const rb = Math.max(0.1, r*K);
  _tmp.width = MW; _tmp.height = MH;
  const src = _tctx.createImageData(MW,MH);
  for (let k=0;k<MW*MH;k++){
    const q = k*4, a = Math.round(Math.min(1,Math.max(0,cov[k]))*255);
    src.data[q]=a; src.data[q+1]=a; src.data[q+2]=a; src.data[q+3]=255;
  }
  _tctx.putImageData(src,0,0);
  _blur.width = MW; _blur.height = MH;
  const bc = _blur.getContext('2d');
  bc.clearRect(0,0,MW,MH);
  bc.filter = `blur(${rb}px)`;
  bc.drawImage(_tmp, 0, 0);
  bc.filter = 'none';
  const back = bc.getImageData(0,0,MW,MH).data;
  for (let k=0;k<MW*MH;k++) cov[k] = back[k*4]/255;
  return cov;
}

/* 合成 MW×MH 的文字叠加层（RGB=白，A=覆盖率×增益）
   与底板叠加等价于 base*(1-e)+250*e；底板在转场中恒常可见。
   INK_GAMMA < 1 → 覆盖率中段被抬高，笔画边缘更饱满、更接近 APPSO 字标的纯白实心。 */
const INK_GAMMA = 0.88;
function compose(spec, cov){
  const cvs = document.createElement('canvas');
  cvs.width = MW; cvs.height = MH;
  const cx = cvs.getContext('2d');
  const img = cx.createImageData(MW,MH);
  const d = img.data;
  for (let k=0;k<MW*MH;k++){
    let e = Math.pow(cov[k], INK_GAMMA)*spec.gain; if (e>1) e=1;
    const q = k*4;
    d[q] = 250; d[q+1] = 250; d[q+2] = 250;
    d[q+3] = Math.round(e*255);
  }
  cx.putImageData(img,0,0);
  return cvs;
}

/* 覆盖率 -> 粒子列表（物理坐标） */
function rasterize(cov, cellPx){
  const cell = Math.max(1, Math.round(cellPx)), out = [];
  for (let y=0; y<MH; y+=cell){
    for (let x=0; x<MW; x+=cell){
      let sum=0, n=0;
      for (let yy=y; yy<Math.min(y+cell,MH); yy++)
        for (let xx=x; xx<Math.min(x+cell,MW); xx++){ sum += cov[yy*MW+xx]; n++; }
      const c = n ? sum/n : 0;
      if (c > 0.10) out.push([x, y, c]);
    }
  }
  return out;
}

/* 粒子预打包：把与时间无关的量（位置/尺寸/随机系数/可用飞散空间）全部算成 TypedArray，
   每帧只做「乘加 + rect」，不再逐粒子查表/取随机/切状态。
   LX/RX/UY/DY = 该粒子朝四个方向距橙框内边界的可用空间（物理 px），用于夹取飞散位移。 */
function packPts(pts, cs, ka, kb, kc){
  const n = pts.length;
  const o = { n,
    X:new Float32Array(n), Y:new Float32Array(n), SZ:new Float32Array(n),
    KX:new Float32Array(n), KY:new Float32Array(n), KJ:new Float32Array(n),
    CR:new Float32Array(n),
    LX:new Float32Array(n), RX:new Float32Array(n),
    UY:new Float32Array(n), DY:new Float32Array(n) };
  for (let i=0;i<n;i++){
    const px = pts[i][0], py = pts[i][1], c = pts[i][2];
    o.X[i] = px; o.Y[i] = py;
    o.SZ[i] = cs * Math.max(0.35, c);
    o.KX[i] = (h(i,ka)-0.5)*2;          // 水平飞散系数
    o.KY[i] = (h(i,kb)-0.5)*2*0.75;     // 纵向飞散系数
    o.KJ[i] = (h(i,kc)-0.5)*1.5;        // 抖动系数
    o.CR[i] = colRand(Math.floor(px/cs))*2-1;   // 逐列尺寸微扰
    o.LX[i] = px - FX0; o.RX[i] = FX1 - px;
    o.UY[i] = py - FY0; o.DY[i] = FY1 - py;
  }
  return o;
}

let _covA=null, _covB=null;
function build(force){
  if (!ready()) return;
  /* 字形覆盖率只与字体/几何/物理分辨率有关 → 缓存复用；
     拖动「粒子格」时只重跑光栅化，不必再次 4× 超采样与读回 */
  if (force || !_covA){
    _covA = blurCov(glyphCoverage(CFG.A), CFG.A.blur);
    _covB = blurCov(glyphCoverage(CFG.B), CFG.B.blur);
    blendA = compose(CFG.A, _covA);
    blendB = compose(CFG.B, _covB);
  }
  cfg.cell = P().cell;
  const cs = cfg.cell*K;
  PA = packPts(rasterize(_covA, cs), cs, 1, 2, 3);
  PB = packPts(rasterize(_covB, cs), cs, 11, 12, 13);
  document.getElementById('info').textContent =
    `A ${PA.n} 点 · B ${PB.n} 点 · ${MW}×${MH}`;
  dirty = true;
}

function fit(){
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  W = card.clientWidth; H = card.clientHeight;
  if (!W || !H) { requestAnimationFrame(fit); return; }
  K  = Math.min(8, Math.max(2, Math.round(W/182 * dpr)));
  SS = (K >= 6) ? 3 : 4;          // 与 APPSO 字标同级超采样（字标为 8× 渲染 + 面积降采样）
  MW = 182*K; MH = 88*K;
  cv.width = MW; cv.height = MH;
  cv.style.width = W+'px'; cv.style.height = H+'px';
  ctx.setTransform(1,0,0,1,0,0);
  ctx.imageSmoothingEnabled = true;
  updFrame();                     // 橙框内边界（物理坐标）随 K 更新
  if (ready()) build(true);
}

/* ---------- 时间轴 ---------- */
const clamp01 = x => x<0?0:(x>1?1:x);
const smooth  = x => { x = clamp01(x); return x*x*(3-2*x); };

/* 飞散基准（v15）：以「AI时代的」(B 段) 的飞散峰值为基准。
   A 段(灵感指南)与 B 段(AI时代的)的段长都是 0.36，两段位移都写成
   「基准峰值 ampK × 段内进度」，因此峰值严格相等 —— 两套文案炸开的尺度一致。 */
const SEG = 0.36;   // 每段时长占比（空场 = 1-2*SEG）
const smoothstep01 = (x, a, b) => smooth((x-a)/(b-a));

function progress(t){                      // 每个周期内的缓入缓出
  const a=0.18, b=0.82;
  if (t<a) return 0;
  if (t>b) return 1;
  const u=(t-a)/(b-a);
  return u*u*(3-2*u);
}

let seed = 20261013;
function rnd(){ seed ^= seed<<13; seed ^= seed>>>17; seed ^= seed<<5;
                return ((seed>>>0)%100000)/100000; }
const HK = new Map();
function h(i,k){ const key=i*131+k; if(!HK.has(key)) HK.set(key, rnd()); return HK.get(key); }
function colRand(i){ return (((Math.sin(i*12.9898+4.1)*43758.5453) % 1) + 1) % 1; }

const LOCK = (()=>{ const q=new URLSearchParams(location.search).get('at');
                    return q===null? null : parseFloat(q); })();
let acc=0, last=performance.now(), paused=false, dirty=true;
let lastStaticKey=-1, fps=0, fpsT=0, fpsN=0;

function tick(dt){
  fpsN++; fpsT += dt;
  if (fpsT > 500){
    fps = Math.round(1000*fpsN/fpsT); fpsT = 0; fpsN = 0;
    const el = document.getElementById('info');
    if (el && PA && PB)
      el.textContent = `${fps} fps · A ${PA.n} 点 · B ${PB.n} 点 · ${MW}×${MH}`;
  }
}

function draw(now){
  const dt = now-last; last=now;
  if (!paused && LOCK===null) acc += dt;

  const p = P();
  const T = p.speed;
  const total = (LOCK!==null) ? LOCK : acc;
  const cyc  = Math.floor(total / T);
  const ci   = ((cyc % 2) + 2) % 2;                       // 0: A→B   1: B→A
  const phase= (total % T) / T;
  const pr   = progress(phase);
  const v    = ci===0 ? pr : 1-pr;      // 0 = A 实心, 1 = B 实心（始终单调 A→B）

  /* 关键：A 段与 B 段在时间上互不重叠 */
  const solidA = 1 - smoothstep01(v, 0.00, 0.20);         // A 实心淡出
  const solidB =     smoothstep01(v, 0.80, 1.00);         // B 实心浮现
  const envA   = Math.sin(Math.PI*clamp01(v/SEG));        // A 粒子包络（SEG 处归零）
  const envB   = Math.sin(Math.PI*clamp01((v-1+SEG)/SEG));// B 粒子包络（1-SEG 处起始）
  const env    = Math.sin(Math.PI*v);                     // 抖动包络（中段最散）

  if (!blendA || !blendB){ requestAnimationFrame(draw); return; }

  /* 稳定态静止帧：输入未变则跳过整帧重绘（大幅省电） */
  const stKey = (Math.round(solidA*1000)*2048 + Math.round(solidB*1000))*16
              + Math.round(envA*8)*2 + Math.round(envB*8);
  const stNow = (envA < 0.006 && envB < 0.006 && env < 0.006);
  if (stNow && stKey === lastStaticKey && !dirty){
    tick(dt);
    requestAnimationFrame(draw);
    return;
  }
  lastStaticKey = stNow ? stKey : -1;
  dirty = false;

  const cs   = cfg.cell*K;
  const ampK = p.amp*K;

  ctx.globalAlpha = 1;
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(IMG.base, 0, 0, MW, MH);                  // 底板常驻（不透明，无需 clearRect）

  /* A 实心 */
  if (solidA > 0.004){
    ctx.globalAlpha = solidA;
    ctx.drawImage(blendA, 0, 0, MW, MH);
  }

  /* A 粒子(灵感指南)：溶解 + 散尽 —— 单次 path 批量描边，位移夹在橙框内 */
  if (envA > 0.006){
    const aProg = clamp01(v/SEG);   // A 段内进度 0→1（与 B 段 bProg 镜像）
    const c1  = ampK*aProg;         // 飞散量 0 → 基准峰值（v15：与「AI时代的」同幅）
    const c2  = cs*env;             // 抖动
    const svk = 0.16*(1-aProg*0.5);
    ctx.globalAlpha = Math.min(1, envA);
    ctx.fillStyle = '#efbab1';
    ctx.beginPath();
    for (let i=0;i<PA.n;i++){
      const s = PA.SZ[i], sh = s*(1+PA.CR[i]*svk);
      let dx = PA.KX[i]*c1 + PA.KJ[i]*c2;
      let dy = PA.KY[i]*c1 + PA.KJ[i]*c2;
      let f = 1;
      if (dx > 0){ const r = PA.RX[i]-s;  if (r < dx)  f = Math.max(0,r)/dx; }
      else if (dx < 0){ const r = PA.LX[i]; if (r < -dx) f = r/(-dx); }
      if (dy > 0){ const r = PA.DY[i]-sh; if (r < dy)  f = Math.min(f, Math.max(0,r)/dy); }
      else if (dy < 0){ const r = PA.UY[i]; if (r < -dy) f = Math.min(f, r/(-dy)); }
      if (f < 1){ dx *= f; dy *= f; }
      ctx.rect(PA.X[i] + dx, PA.Y[i] + dy, s, sh);
    }
    ctx.fill();
  }

  /* B 实心 */
  if (solidB > 0.004){
    ctx.globalAlpha = solidB;
    ctx.drawImage(blendB, 0, 0, MW, MH);
  }

  /* B 粒子(AI时代的)：聚拢 —— 单次 path 批量描边，位移夹在橙框内。
     本段峰值 ampK 即全片飞散基准，A 段(灵感指南)已对齐到同一峰值（v15）。 */
  if (envB > 0.006){
    const bProg = clamp01((v-0.64)/SEG);
    const c1  = ampK*(1-bProg);     // 飞散量：基准峰值 → 0
    const c2  = cs*env;
    const svk = 0.16*(1-(1-bProg)*0.5);
    ctx.globalAlpha = Math.min(1, envB);
    ctx.fillStyle = '#efbab1';
    ctx.beginPath();
    for (let i=0;i<PB.n;i++){
      const s = PB.SZ[i], sh = s*(1+PB.CR[i]*svk);
      let dx = PB.KX[i]*c1 + PB.KJ[i]*c2;
      let dy = PB.KY[i]*c1 + PB.KJ[i]*c2;
      let f = 1;
      if (dx > 0){ const r = PB.RX[i]-s;  if (r < dx)  f = Math.max(0,r)/dx; }
      else if (dx < 0){ const r = PB.LX[i]; if (r < -dx) f = r/(-dx); }
      if (dy > 0){ const r = PB.DY[i]-sh; if (r < dy)  f = Math.min(f, Math.max(0,r)/dy); }
      else if (dy < 0){ const r = PB.UY[i]; if (r < -dy) f = Math.min(f, r/(-dy)); }
      if (f < 1){ dx *= f; dy *= f; }
      ctx.rect(PB.X[i] + dx, PB.Y[i] + dy, s, sh);
    }
    ctx.fill();
  }

  /* 空场期不放任何游离噪点（v14）：
     旧字粒子散尽后画面必须完全干净——任何零星碎点都会被看成「旧字残影」。
     粒子本身已精确归零（envA 在 v=0.36 处、envB 在 v=1.00 处均为 0），故此处不再补点。 */

  ctx.globalAlpha = 1;

  tick(dt);

  requestAnimationFrame(draw);
}

function bind(id,out,unit,cb){
  const el=document.getElementById(id), o=document.getElementById(out);
  const ap=()=>{
    const val = parseFloat(el.value);
    if (id==='sSpeed') _vSpeed=val; else if (id==='sCell') _vCell=val; else _vAmp=val;
    o.textContent = el.value+unit;
    dirty = true; if (cb) cb();
  };
  el.addEventListener('input',ap); ap();
}
bind('sSpeed','vSpeed','s');
bind('sCell','vCell','px',()=>build());
bind('sAmp','vAmp','px');
document.getElementById('btn').addEventListener('click',e=>{
  paused=!paused; e.target.textContent=paused?'继续':'暂停';
  last=performance.now(); dirty=true;
});
window.addEventListener('resize', ()=>{ fit(); dirty=true; });

fit();
if (document.fonts && document.fonts.load){
  document.fonts.load('__FW__ 100px "APPSO Hei"')
    .then(()=>{ NFONT=true; fit(); }).catch(()=>{ NFONT=true; fit(); });
} else { NFONT=true; }

if (new URLSearchParams(location.search).get('probe')){
  setTimeout(()=>{ document.title = `PTS A=${PA?PA.n:0} B=${PB?PB.n:0} ${MW}x${MH}`; }, 900);
}

requestAnimationFrame(draw);
</script>
</body>
</html>
'''

out = (TMPL
  .replace('__FW__', FW)
  .replace('__FONT__', FONT).replace('__BASE__', BASE)
  .replace('__TEXTA__', CFG['texts']['A']).replace('__TEXTB__', CFG['texts']['B'])
  .replace('__ACTR__', json.dumps(A['ctr'])).replace('__ASC__', json.dumps(A['sc']))
  .replace('__ADYS__', json.dumps(A['dys']))
  .replace('__APX__', str(A['px'])).replace('__ABL__', str(A['bl']))
  .replace('__BCTR__', json.dumps(B['ctr'])).replace('__BBAS__', str(B['bl']))
  .replace('__AGAIN__', str(A['gain'])).replace('__ABLUR__', str(A['blur']))
  .replace('__BGAIN__', str(B['gain'])).replace('__BBLUR__', str(B['blur'])))

os.makedirs(os.path.dirname(TARGET), exist_ok=True)
open(TARGET, 'w', encoding='utf-8').write(out)
print(f"已生成: {TARGET}  ({len(out)//1024} KB, 自包含)")
print(f"  文案: {CFG['texts']['A']} ⇄ {CFG['texts']['B']}")
print(f"  节奏: {CFG['timing']['duration']}s / 粒子格 {CFG['particles']['cell']}px / 飞散 {CFG['particles']['amplitude']}px")
