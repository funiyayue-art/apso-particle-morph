# apso-particle-morph

> 一行文字被粒子打散、在空中消失、再从虚空聚拢成另一行。
> 一个可复现、可验证、可参数化的网页文字形变动效引擎。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![验证器 4/4 通过](https://img.shields.io/badge/验证-4%2F4%20通过-success.svg)](tools/)

复刻自 APPSO 品牌动图（182×72 / 268 帧 / 16.7fps / 循环周期 4.25s）。
**不是 GIF 播放，也不是遮罩扫描** —— 是文字本体被粒子逐点溶解后重组。

**在线试玩**：[→ funiyayue-art.github.io/apso-particle-morph](https://funiyayue-art.github.io/apso-particle-morph/)
**单文件版**：[Bold](examples/apso-particle-morph.html) ｜ [Regular](examples/apso-particle-morph-light.html) —— 保存到本地双击即开，无需构建、无网络依赖

```
旧字实心淡出  ────────  旧字粒子散尽
                    ↓
              ┌─── 空场 ───┐
              ↓             ↓
        新字粒子聚拢  ←────  新字实心浮现
```

### 四个验证器（全部实测通过）

```
$ python tools/verify_empty.py
  v=0.44 ~ 0.56   差异 10 px（= 基线噪声）    ✓ 空场与纯底板逐像素一致

$ python tools/verify_boundary.py
  14 个进度点 × 4 边   越框恒为 20 px（基线） ✓ 全程未越框

$ python tools/verify_amplitude.py
  位移幅度 A/B = 1.001                          ✓ 两段炸开的尺度一致

$ python tools/verify_geometry.py
  左/右/上/下 = 14.50 / 14.50 / 14.50 / 14.50    ✓ 极差 0.00
```

---

## 这个仓库想解决什么

大部分「文字形变」的 CSS 教程给你的是**表象**：一个遮罩扫过去，一个 blur 拉起来。
真正难的三个问题，这个仓库正面处理并提供了验证工具：

| 问题 | 本仓库的做法 |
|---|---|
| **怎么证明它真的"旧字消失"了？** | `tools/verify_empty.py` —— 与无粒子底板逐像素比对，空场期差异必须为基线噪声 |
| **怎么证明粒子没飞出边框？** | `tools/verify_boundary.py` —— 框外差异像素统计 + 滑块上限压力测试 |
| **怎么证明我说的指标测的是我想测的？** | `tools/verify_amplitude.py` —— 用**形状无关**的散开面积，而不是"到轮廓的距离" |

**核心主张：动效的所有断言都应该是可测量的，而不是"看起来对"。**

---

## 快速开始

### 只看效果

打开 `examples/` 下任一 HTML，无需服务器、无需构建、无网络依赖：

```
examples/apso-particle-morph.html       # Bold
examples/apso-particle-morph-light.html # Regular
```

页面内有三个滑块（变形时长 / 粒子格 / 飞散幅度）和一个暂停按钮，
左下角实时显示 fps、粒子数、渲染分辨率。

### 改文案重新生成

```bash
pip install -r requirements.txt

# 1. 生成底板（红卡 + logo）
python src/make_base.py

# 2. 生成 HTML
python src/make_html.py                    # Bold
python src/make_html.py --reg              # Regular
```

改文案：编辑 `src/config.json` 里的 `texts.A` / `texts.B` 和 `glyphs`（逐字中心/字号/纵向偏移）。

### 验证

```bash
python tools/verify_empty.py        # 空场零残留
python tools/verify_boundary.py     # 粒子不越框
python tools/verify_amplitude.py    # 两段飞散幅度一致
python tools/verify_geometry.py     # 四边留白等距
```

每个脚本都会输出实测数字，不是 pass/fail 了事。

---

## 技术要点

### 渲染链路

```
make_base.py          烘 728×352 底板（红卡 + logo，sigmoid 边缘）≈4.9KB
   ↓ base.png
make_html.py          内嵌 woff2 字体子集 + 底板 base64 → 单文件 HTML
   ├ 离屏 Canvas 渲染文案 → getImageData 采样覆盖率
   ├ 4× 超采样 → 面积降采样 → 清晰实心字形（blur=0, gamma 0.88）
   ├ packPts() 预打包粒子为 Float32Array + 逐粒子四向可用空间
   ├ frame(): 底板常驻 + 文字层 alpha 叠加
   └ 单次 beginPath/rect/fill 批量描边
   ↓
   39KB 自包含 HTML
```

### 三个关键设计

**① 粒子预打包 + 批量描边（性能）**

粒子属性（位置/尺寸/飞散系数/抖动系数）全部预计算成 `Float32Array`，
每帧只做乘加，最后**一次** `beginPath/rect/fill` 描边所有粒子。

实测 1600 粒子 × 60 帧：**29ms → 5ms（5.41×）**。
关键在于 `globalAlpha` 和 `fillStyle` 实际上**全场同值**（不依赖粒子序号），逐粒子设置纯属浪费。

**② 时间轴两段互不重叠（不残留）**

单一进度 `v ∈ [0,1]` 驱动，两段**物理上不可能重叠**：

| 阶段 | v 区间 |
|---|---|
| 旧字实心淡出 | 0.00 → 0.20 |
| 旧字粒子散尽 | 0.00 → 0.36 |
| **空场** | **0.36 → 0.64** |
| 新字粒子聚拢 | 0.64 → 1.00 |
| 新字实心浮现 | 0.80 → 1.00 |

> **踩过的坑**：早期版本实心层用 `pr` 驱动、粒子层用 `1-pr` 驱动。
> 第一个周期两者恰好同步所以测试全过，第二个周期时钟翻转才暴露 bug。
> **有周期的系统，只验一半等于没验。**

**③ 边界约束预计算（不越框）**

每个粒子在生成时记住自己**朝上下左右到边框的可用空间**，
位移按方向等比压缩 —— 零分配、零 GC，不影响性能优化。

实测：滑块拉到上限 70px，越框像素仍为 4–6（舞台圆角固有噪声）。

---

## 目录结构

```
apso-particle-morph/
├ index.html               在线试玩入口（GitHub Pages 首页）
├ src/
│  ├ make_base.py          底板生成器
│  ├ make_html.py          HTML 生成器（含粒子引擎，约 600 行）
│  └ config.json           文案 / 几何 / 节奏参数
├ tools/                   逐像素验证工具（4 个）
├ examples/                开箱即看的成品（Bold / Regular）
├ assets/                  底板与原始动图素材
├ docs/
│  ├ 复刻档案.md            11 轮迭代全过程 + 15 条踩坑
│  ├ 复刻历程.md            版本演进时间线
│  └ 方法论.md              给 Agent / 模型设计者的 3 条启示
└ README.md
```

---

## 给 Agent / 模型设计者的三条启示

这个项目本身是个 Agent 系统，跑了 19 个版本、第 19 版才找到真 bug。三条经验值得写下来：

**① 验收环境必须与真实使用环境一致**

第 1–18 版的核验全部在 1000×1600 的无头窗口里跑，页面完整显示，**全部通过**。
真实用户在 690×736 的窗口里看，页面垂直居中导致**顶部溢出且不可滚动**，画面被裁掉 31px。

> Agent 的测试环境总是比生产环境干净。这是所有 Agent 系统最常见的失效模式——
> 测试全绿，上线就炸。要么让测试环境覆盖真实约束，要么在报告里写清"我是在什么条件下测的"。

**② 多周期 / 多状态系统，只验一半等于没验**

实心层与粒子层用了两个不同的驱动时钟，第一个周期恰好同步，**每个测试都过**。
第二个周期时钟翻转，`solidA=1`，旧字被画了出来。

> 任何有状态、有周期、有分支的系统，只验一个周期的通过率没有意义。验收必须覆盖完整状态空间。

**③ 指标本身要先验证有效性**

量化"两段飞散幅度是否一致"时，用「粒子到文字轮廓的距离」测出比值 0.875，判定"不达标"。
但问题出在指标上——**笔画密的字，粒子飞出去之后仍然落在字形轮廓内部**，被算成"没飞"。

换成散开面积（`粒子像素面积 ÷ 自身字形面积`，与形状无关），才测出真实差距。

> 指标算出来的数字，你首先要相信的是**这个指标测的是不是你想测的东西**。
> 否则后面所有基于它的推理，全都是错的。

---

## License

代码 MIT。原始 APPSO 动图与品牌标识归其所有者所有，本仓库仅作技术复刻研究，
不含任何原品牌素材的再分发承诺。

字体：正文使用微软雅黑（Bold/Regular），构建时子集化内嵌。
若需替换字体，编辑 `src/make_html.py` 中的 `FONT` 处理流程。

---

## 致谢

复刻自一段公开可见的品牌动图。动效机制由像素级统计反推得出，
过程中共推翻判断 1 次、定位真 bug 18 个、逐像素验证 11 轮。

完整过程记录见 `docs/复刻档案.md`。