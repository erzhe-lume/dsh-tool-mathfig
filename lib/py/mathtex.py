# -*- coding: utf-8 -*-
"""
mathtex —— 纯离线公式排版引擎（不依赖 LaTeX，不依赖浏览器）。

单行排版交给 matplotlib 的 mathtext；mathtext 缺失的结构由本文件自建盒子模型补齐：
  * 环境：cases / array / aligned / align* / gathered / matrix / pmatrix / bmatrix /
          Bmatrix / vmatrix / Vmatrix
  * 结构：\\underbrace \\overbrace \\boxed \\overset \\underset \\stackrel
          \\xlongequal \\xrightarrow \\xleftarrow
  * 中文：\\text{中文} \\mathrm{中文} 以及裸中文，用系统中文字体单独排版并按基线对齐
  * 兼容层：\\displaystyle \\limits \\bigl/\\Bigl \\lvert \\rvert \\lVert \\rVert
          \\color \\cancel \\iff \\cfrac 等 mathtext 不认的写法

坐标系统一用「点」(1/72 英寸)，y 轴向上，每个盒子的锚点是「左端 + 基线」。
"""
from __future__ import annotations

import math
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import MathTextParser
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from matplotlib.transforms import Affine2D

MATH_PARSER = MathTextParser("path")
_SCRATCH = plt.figure(figsize=(1, 1), dpi=72)
_SCRATCH_RENDERER = _SCRATCH.canvas.get_renderer()

KAPPA = 0.5522847498
CJK_RE = re.compile(r"[\u2e80-\u9fff\u3000-\u303f\uff00-\uffef\u201c\u201d\u2018\u2019]")

# 公式里中文的字体链：宋体为主，缺字（如 ⑪⑫ 圈号、生僻符号）自动往后找
DEFAULT_CJK = ["SimSun", "Microsoft YaHei", "Segoe UI Symbol", "DejaVu Sans"]


def configure(fontset: str = "cm"):
    """cm = Computer Modern（LaTeX 观感）；stix / dejavusans / stixsans 亦可。"""
    matplotlib.rcParams["mathtext.fontset"] = fontset
    matplotlib.rcParams["mathtext.default"] = "it"
    try:
        matplotlib.rcParams["mathtext.fallback"] = "stix"
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 基础度量
# --------------------------------------------------------------------------- #
def measure_math(tex: str, fs: float):
    """返回 (宽, 基线上高, 基线下深)，单位点。"""
    w, h, d, _, _ = MATH_PARSER.parse("$" + tex + "$", dpi=72, prop=FontProperties(size=fs))
    return float(w), float(h), float(d)


def measure_text(s: str, fs: float, family):
    prop = FontProperties(family=family, size=fs)
    w, h, d = _SCRATCH_RENDERER.get_text_width_height_descent(s, prop, ismath=False)
    return float(w), float(h), float(d)


def cjk_families(spec=None):
    """把 'SimSun,Microsoft YaHei' 补成完整的字体回退链。"""
    if spec is None:
        return list(DEFAULT_CJK)
    if isinstance(spec, (list, tuple)):
        names = [str(x).strip() for x in spec if str(x).strip()]
    else:
        names = [x.strip() for x in str(spec).split(",") if x.strip()]
    return names + [f for f in DEFAULT_CJK if f not in names]


class Ctx:
    def __init__(self, fig, fs, color, cjk_font, lw, store):
        self.fig = fig
        self.fs = fs
        self.color = color
        self.cjk_font = cjk_font
        self.lw = lw
        self.store = store
        self.trans = Affine2D().scale(1.0 / 72.0) + fig.dpi_scale_trans

    @property
    def em(self):
        return self.fs


# --------------------------------------------------------------------------- #
# 盒子模型
# --------------------------------------------------------------------------- #
class Box:
    w = 0.0
    h = 0.0
    d = 0.0

    def measure(self, ctx: Ctx):
        raise NotImplementedError

    def draw(self, ctx: Ctx, x: float, y: float):
        raise NotImplementedError


class SpaceBox(Box):
    def __init__(self, w):
        self.w, self.h, self.d = float(w), 0.0, 0.0

    def measure(self, ctx):
        return self

    def draw(self, ctx, x, y):
        return None


class MathBox(Box):
    """一段交给 mathtext 的数学片段。"""

    def __init__(self, tex):
        self.tex = tex

    def measure(self, ctx):
        self.w, self.h, self.d = measure_math(self.tex, ctx.fs)
        return self

    def draw(self, ctx, x, y):
        ctx.fig.text(x, y, "$" + self.tex + "$",
                     fontproperties=FontProperties(size=ctx.fs),
                     ha="left", va="baseline", color=ctx.color, transform=ctx.trans)


class TextBox(Box):
    """一段普通文本（中文）。两侧各留一点缝隙，模拟 TeX 的 \\text 间距。"""

    PAD = 0.10  # em

    def __init__(self, s, family=None):
        self.s = s
        self.family = family

    def measure(self, ctx):
        fam = self.family or ctx.cjk_font
        self.w, self.h, self.d = measure_text(self.s, ctx.fs, fam)
        self.pad = TextBox.PAD * ctx.fs
        self.w += 2 * self.pad
        return self

    def draw(self, ctx, x, y):
        ctx.fig.text(x + self.pad, y, self.s,
                     fontproperties=FontProperties(family=self.family or ctx.cjk_font, size=ctx.fs),
                     ha="left", va="baseline", color=ctx.color, transform=ctx.trans)


class HBox(Box):
    def __init__(self, children, sep=0.0):
        self.children = [c for c in children if c is not None]
        self.sep = sep

    def measure(self, ctx):
        for c in self.children:
            c.measure(ctx)
        self.h = max([c.h for c in self.children], default=0.0)
        self.d = max([c.d for c in self.children], default=0.0)
        self.w = sum(c.w for c in self.children) + self.sep * max(0, len(self.children) - 1)
        return self

    def draw(self, ctx, x, y):
        cur = x
        for c in self.children:
            c.draw(ctx, cur, y)
            cur += c.w + self.sep


class VBox(Box):
    """纵向堆叠，子项逐行放；对齐方式 center / left。"""

    def __init__(self, rows, gap=0.45, align="center"):
        self.rows = rows
        self.gap = gap  # em
        self.align = align

    def measure(self, ctx):
        gap = self.gap * ctx.fs
        widths = []
        for r in self.rows:
            r.measure(ctx)
            widths.append(r.w)
        self.w = max(widths, default=0.0)
        if not self.rows:
            self.h = self.d = 0.0
            self._offsets = []
            return self
        total = sum(r.h + r.d for r in self.rows) + gap * max(0, len(self.rows) - 1)
        # 基线取最后一行（多行公式的常规做法）
        last = self.rows[-1]
        self.d = last.d
        self.h = total - last.d
        # 记录每行相对本盒基线的基线偏移
        self._offsets = []
        y_cursor = 0.0  # 从本盒顶部向下：顶部 = baseline + h
        top = self.h
        for r in self.rows:
            base = top - r.h
            self._offsets.append(base)
            top -= (r.h + r.d + gap)
        return self

    def draw(self, ctx, x, y):
        for r, off in zip(self.rows, self._offsets):
            if self.align == "center":
                r.draw(ctx, x + (self.w - r.w) / 2.0, y + off)
            else:
                r.draw(ctx, x, y + off)


class GridBox(Box):
    """
    网格：rows 为若干行，每行是若干盒子。
    align: 'center'（矩阵）| 'left'（每列左对齐）| 'alt'（aligned：偶数列右对齐、奇数列左对齐）
    """

    def __init__(self, rows, align="center", colgap=0.9, rowgap=0.42, vcenter=True):
        self.rows = rows
        self.align = align
        self.colgap = colgap  # em
        self.rowgap = rowgap  # em
        self.vcenter = vcenter

    def measure(self, ctx):
        cg, rg = self.colgap * ctx.fs, self.rowgap * ctx.fs
        ncol = max((len(r) for r in self.rows), default=0)
        for r in self.rows:
            for c in r:
                c.measure(ctx)
        self.colw = [0.0] * ncol
        for r in self.rows:
            for j, c in enumerate(r):
                self.colw[j] = max(self.colw[j], c.w)
        self.rh = [max([c.h for c in r], default=0.0) for r in self.rows]
        self.rd = [max([c.d for c in r], default=0.0) for r in self.rows]
        self.w = sum(self.colw) + cg * max(0, ncol - 1)
        if not self.rows:
            self.h = self.d = 0.0
            self._offsets = []
            return self
        total = sum(h + d for h, d in zip(self.rh, self.rd)) + rg * max(0, len(self.rows) - 1)
        if self.vcenter:
            # 与 LaTeX 一致：整块以垂直中心对齐数学轴（0.25em）
            axis = 0.25 * ctx.fs
            d = max(total / 2.0 - axis, self.rd[-1])
            h = total - d
            if h < self.rh[0]:
                h = self.rh[0]
                d = total - h
            self.h, self.d = h, d
        else:
            self.d = self.rd[-1]
            self.h = total - self.d
        self._offsets = []
        top = self.h
        for h, d in zip(self.rh, self.rd):
            self._offsets.append(top - h)
            top -= (h + d + rg)
        return self

    def _col_align(self, j):
        if self.align == "custom":
            spec = getattr(self, "colspec", [])
            return spec[j] if j < len(spec) else "l"
        if self.align == "center":
            return "c"
        if self.align == "left":
            return "l"
        return "r" if j % 2 == 0 else "l"  # alt：aligned 的标准对齐

    def draw(self, ctx, x, y):
        cg = self.colgap * ctx.fs
        xs = []
        cur = x
        for w in self.colw:
            xs.append(cur)
            cur += w + cg
        for i, r in enumerate(self.rows):
            for j, c in enumerate(r):
                a = self._col_align(j)
                if a == "c":
                    cx = xs[j] + (self.colw[j] - c.w) / 2.0
                elif a == "l":
                    cx = xs[j]
                else:
                    cx = xs[j] + (self.colw[j] - c.w)
                c.draw(ctx, cx, y + self._offsets[i])


# --------------------------------------------------------------------------- #
# 括号（可变高度，用矢量路径画）
# --------------------------------------------------------------------------- #
def _arc_cubic(c, p0, p1):
    r = math.hypot(p0[0] - c[0], p0[1] - c[1])
    t0 = (p0[0] - c[0], p0[1] - c[1])
    t1 = (p1[0] - c[0], p1[1] - c[1])
    cross = t0[0] * t1[1] - t0[1] * t1[0]
    s = -1.0 if cross < 0 else 1.0
    d0 = (-t0[1] * s / r, t0[0] * s / r)
    d1 = (-t1[1] * s / r, t1[0] * s / r)
    cp1 = (p0[0] + KAPPA * r * d0[0], p0[1] + KAPPA * r * d0[1])
    cp2 = (p1[0] - KAPPA * r * d1[0], p1[1] - KAPPA * r * d1[1])
    return [cp1, cp2, p1]


def _paren_path(x0, y0, y1, w, side):
    """
    椭圆弧近似的圆括号；side='left' 开口向右。
    取 115°~245° 的弧：竖直跨度 = 1.8138*ry，水平墨迹宽 = 0.5774*rx，
    因此 rx = w/0.5774 时墨迹宽度正好是 w。
    """
    span = max(y1 - y0, 1e-6)
    ry = span / (2.0 * math.sin(math.radians(65.0)))
    rx = w / 0.5774
    cx = (x0 + rx) if side == "left" else (x0 + w - rx)
    t1, t2 = (115.0, 245.0) if side == "left" else (-65.0, 65.0)
    pts = []
    n = 48
    for k in range(n + 1):
        t = math.radians(t1 + (t2 - t1) * k / n)
        pts.append((cx + rx * math.cos(t), (y0 + y1) / 2.0 + ry * math.sin(t)))
    codes = [Path.MOVETO] + [Path.LINETO] * (len(pts) - 1)
    return Path(pts, codes)


def _brace_path(x0, y0, y1, w, tip_left=True):
    """花括号：两段竖干 + 四个圆弧，尖端指向左（cases 用）或右。"""
    span = y1 - y0
    w = min(w, span * 0.5)
    r = w * 0.5
    stem = x0 + w * 0.5
    tipx = x0 if tip_left else x0 + w
    outx = x0 + w if tip_left else x0
    ym = (y0 + y1) / 2.0
    verts = [(outx, y1)]
    codes = [Path.MOVETO]
    # 顶部钩
    verts += _arc_cubic((stem, y1), (outx, y1), (stem, y1 - r))
    codes += [Path.CURVE4] * 3
    # 上半竖干
    verts.append((stem, ym + r)); codes.append(Path.LINETO)
    # 上尖
    verts += _arc_cubic((stem, ym), (stem, ym + r), (tipx, ym))
    codes += [Path.CURVE4] * 3
    # 下尖
    verts += _arc_cubic((stem, ym), (tipx, ym), (stem, ym - r))
    codes += [Path.CURVE4] * 3
    # 下半竖干
    verts.append((stem, y0 + r)); codes.append(Path.LINETO)
    # 底部钩
    verts += _arc_cubic((stem, y0), (stem, y0 + r), (outx, y0))
    codes += [Path.CURVE4] * 3
    return Path(verts, codes)


def _bracket_path(x0, y0, y1, w, side):
    if side == "left":
        pts = [(x0 + w, y1), (x0, y1), (x0, y0), (x0 + w, y0)]
    else:
        pts = [(x0, y1), (x0 + w, y1), (x0 + w, y0), (x0, y0)]
    return Path(pts, [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO])


class DelimBox(Box):
    """可变高的定界符：() [] {} | ‖ . （'.' 表示不画）"""

    def __init__(self, kind, h, d, fs):
        self.kind = kind
        self.h, self.d = float(h), float(d)
        if kind in "()[]{}":
            self.w = 0.34 * fs
        elif kind in "|‖":
            self.w = 0.16 * fs
        else:
            self.w = 0.0

    def measure(self, ctx):
        return self

    def draw(self, ctx, x, y):
        if self.kind == ".":
            return
        y0, y1 = y - self.d, y + self.h
        lw = max(ctx.lw, 0.055 * ctx.fs)
        if self.kind in "()":
            path = _paren_path(x, y0, y1, self.w, "left" if self.kind == "(" else "right")
        elif self.kind in "[]":
            path = _bracket_path(x, y0, y1, self.w, "left" if self.kind == "[" else "right")
        elif self.kind in "{}":
            path = _brace_path(x, y0, y1, self.w, tip_left=(self.kind == "{"))
        else:  # 竖线
            off = self.w * 0.5
            if self.kind == "‖":
                path = Path([(x + self.w * 0.15, y0), (x + self.w * 0.15, y1),
                             (x + self.w * 0.85, y0), (x + self.w * 0.85, y1)],
                            [Path.MOVETO, Path.LINETO, Path.MOVETO, Path.LINETO])
            else:
                path = Path([(x + off, y0), (x + off, y1)], [Path.MOVETO, Path.LINETO])
        patch = PathPatch(path, transform=ctx.trans, fill=False, color=ctx.color,
                          linewidth=lw, capstyle="round", joinstyle="round")
        ctx.fig.add_artist(patch)


# --------------------------------------------------------------------------- #
# 复合结构
# --------------------------------------------------------------------------- #
def _delim_kind(ch: str) -> str:
    ch = (ch or "").strip()
    if ch in "()[]|":
        return ch
    if ch in (r"\{", r"\lbrace"):
        return "{"
    if ch in (r"\}", r"\rbrace"):
        return "}"
    if ch in (r"\|", r"\Vert", r"\lVert", r"\rVert"):
        return "‖"
    if ch == r"\langle":
        return "("
    if ch == r"\rangle":
        return ")"
    return "."


class CasesBox(Box):
    """\\begin{cases} / \\begin{array} 之类：左侧一个花括号（或指定括号）。"""

    def __init__(self, rows, brace="{"):
        self.grid = GridBox(rows, align="left", colgap=1.0, rowgap=0.45)
        self.brace = brace

    def measure(self, ctx):
        self.grid.measure(ctx)
        self.gap = 0.12 * ctx.fs
        self.delim = None
        if self.brace and self.brace != ".":
            self.delim = DelimBox(self.brace, self.grid.h, self.grid.d, ctx.fs)
            self.delim.measure(ctx)
            self.w = self.delim.w + self.gap + self.grid.w
        else:
            self.w = self.grid.w
        self.h, self.d = self.grid.h, self.grid.d
        return self

    def draw(self, ctx, x, y):
        if self.delim is not None:
            self.delim.draw(ctx, x, y)
            self.grid.draw(ctx, x + self.delim.w + self.gap, y)
        else:
            self.grid.draw(ctx, x, y)


class MatrixBox(Box):
    def __init__(self, rows, left="(", right=")"):
        self.grid = GridBox(rows, align="center", colgap=1.0, rowgap=0.55)
        self.left, self.right = left, right

    def measure(self, ctx):
        self.grid.measure(ctx)
        self.gap = 0.10 * ctx.fs
        self.dl = DelimBox(self.left, self.grid.h, self.grid.d, ctx.fs) if self.left != "." else None
        self.dr = DelimBox(self.right, self.grid.h, self.grid.d, ctx.fs) if self.right != "." else None
        for dm in (self.dl, self.dr):
            if dm is not None:
                dm.measure(ctx)
        self.w = (self.dl.w + self.gap if self.dl else 0.0) + self.grid.w + \
                 (self.gap + self.dr.w if self.dr else 0.0)
        self.h, self.d = self.grid.h, self.grid.d
        return self

    def draw(self, ctx, x, y):
        cur = x
        if self.dl is not None:
            self.dl.draw(ctx, cur, y)
            cur += self.dl.w + self.gap
        self.grid.draw(ctx, cur, y)
        if self.dr is not None:
            self.dr.draw(ctx, cur + self.grid.w + self.gap, y)


class BraceBox(Box):
    """\\underbrace{X}_{label} / \\overbrace{X}^{label}：横置花括号 + 标注。"""

    def __init__(self, inner, label, above=False):
        self.inner = inner
        self.label = label
        self.above = above

    def measure(self, ctx):
        self.inner.measure(ctx)
        if self.label is not None:
            self.label.measure(ctx)
        self.t = 0.42 * ctx.fs            # 花括号的"厚度"
        self.g_brace = 0.10 * ctx.fs      # 内容与花括号的间隙
        self.g_label = 0.10 * ctx.fs      # 花括号与标注的间隙
        lab_h = (self.label.h + self.label.d) if self.label else 0.0
        self.w = max(self.inner.w, self.label.w if self.label else 0.0)
        if self.above:
            self.h = self.inner.h + self.g_brace + self.t + \
                     (self.g_label + lab_h if self.label else 0.0)
            self.d = self.inner.d
        else:
            self.h = self.inner.h
            self.d = self.inner.d + self.g_brace + self.t + \
                     (self.g_label + lab_h if self.label else 0.0)
        return self

    def _brace_patch(self, ctx, x0, width, y_tip, tip_up):
        local = _brace_path(0.0, 0.0, width, self.t, tip_left=True)
        if tip_up:
            m = Affine2D.from_values(0, -1, 1, 0, x0, y_tip)
        else:
            m = Affine2D.from_values(0, 1, 1, 0, x0, y_tip)
        return PathPatch(local, transform=m + ctx.trans, fill=False, color=ctx.color,
                         linewidth=ctx.lw, capstyle="round", joinstyle="round")

    def draw(self, ctx, x, y):
        cx = x + self.w / 2.0
        x0 = cx - self.inner.w / 2.0
        if self.above:
            self.inner.draw(ctx, x + (self.w - self.inner.w) / 2.0, y)
            brace_bottom = y + self.inner.h + self.g_brace
            y_tip = brace_bottom + self.t
            ctx.fig.add_artist(self._brace_patch(ctx, x0, self.inner.w, y_tip, tip_up=True))
            if self.label:
                ly = y_tip + self.g_label + self.label.d
                self.label.draw(ctx, cx - self.label.w / 2.0, ly)
        else:
            self.inner.draw(ctx, x + (self.w - self.inner.w) / 2.0, y)
            brace_top = y - self.inner.d - self.g_brace
            y_tip = brace_top - self.t
            ctx.fig.add_artist(self._brace_patch(ctx, x0, self.inner.w, y_tip, tip_up=False))
            if self.label:
                ly = y_tip - self.g_label - self.label.h
                self.label.draw(ctx, cx - self.label.w / 2.0, ly)


class BoxedBox(Box):
    def __init__(self, inner):
        self.inner = inner

    def measure(self, ctx):
        self.inner.measure(ctx)
        self.pad = 0.34 * ctx.fs
        self.w = self.inner.w + 2 * self.pad
        self.h = self.inner.h + self.pad * 0.8
        self.d = self.inner.d + self.pad * 0.8
        return self

    def draw(self, ctx, x, y):
        self.inner.draw(ctx, x + self.pad, y)
        rect = Rectangle((x, y - self.d), self.w, self.h + self.d, transform=ctx.trans,
                         fill=False, edgecolor=ctx.color, linewidth=max(ctx.lw, 0.8))
        ctx.fig.add_artist(rect)


class StackBox(Box):
    """把 top 放在 bottom 正上方（\\overset、\\xlongequal、\\xrightarrow 用）。"""

    def __init__(self, bottom, top=None, below=None, small=True):
        self.bottom = bottom
        self.top = top
        self.below = below
        self.scale = 0.72 if small else 1.0

    def measure(self, ctx):
        self.bottom.measure(ctx)
        w = self.bottom.w
        for part in (self.top, self.below):
            if part is not None:
                part.measure(ctx)
                w = max(w, part.w)
        self.w = w
        gap = 0.16 * ctx.fs
        self.gap = gap
        th = (self.top.h + self.top.d + gap) if self.top else 0.0
        bh = (self.below.h + self.below.d + gap) if self.below else 0.0
        self.h = self.bottom.h + th
        self.d = self.bottom.d + bh
        return self

    def draw(self, ctx, x, y):
        cx = x + self.w / 2.0
        self.bottom.draw(ctx, cx - self.bottom.w / 2.0, y)
        if self.top:
            ty = y + self.bottom.h + self.gap + self.top.d
            self.top.draw(ctx, cx - self.top.w / 2.0, ty)
        if self.below:
            by = y - self.bottom.d - self.gap - self.below.h
            self.below.draw(ctx, cx - self.below.w / 2.0, by)


class ScaleBox(Box):
    """整体缩放（下标/上下标注里的小字用）。"""

    def __init__(self, inner, scale):
        self.inner = inner
        self.scale = scale

    def measure(self, ctx):
        sub = Ctx(ctx.fig, ctx.fs * self.scale, ctx.color, ctx.cjk_font, ctx.lw * self.scale, ctx.store)
        self.inner.measure(sub)
        self.w, self.h, self.d = self.inner.w, self.inner.h, self.inner.d
        return self

    def draw(self, ctx, x, y):
        # 注意：必须用「当前」ctx 派生子上下文，否则会把字画进测量用的临时画布
        sub = Ctx(ctx.fig, ctx.fs * self.scale, ctx.color, ctx.cjk_font, ctx.lw * self.scale, ctx.store)
        self.inner.draw(sub, x, y)


# --------------------------------------------------------------------------- #
# 预处理：把 mathtext 不认的写法改写成它认的
# --------------------------------------------------------------------------- #
def _has_cjk(s):
    return bool(HOIST_RE.search(s))


def read_group(s, i):
    """s[i] == '{'；返回 (组内内容, 右括号之后的下标)。"""
    assert s[i] == "{"
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("花括号不配对：%r" % s[i:i + 40])


_TEXT_CMD = re.compile(r"\\(text|textrm|textnormal|mbox|hbox|mathrm|operatorname|textup|textit|textbf)\s*\{")


def preprocess_text(tex, store):
    """把含中文的 \\text{...} 挖出来，替换成占位符 @@PHn@@。"""
    out = []
    i = 0
    while i < len(tex):
        m = _TEXT_CMD.match(tex, i)
        if m:
            body, end = read_group(tex, m.end() - 1)
            if _has_cjk(body):
                store.append(("text", body))
                out.append("@@PH%d@@" % (len(store) - 1))
            else:
                out.append(tex[i:end])
            i = end
        else:
            out.append(tex[i])
            i += 1
    return "".join(out)


# mathtext 不认的符号别名（左边写成常用的 LaTeX 写法，右边是 mathtext 认的）
SYMBOL_ALIASES = [
    (r"\\le(?![a-zA-Z])", r"\\leq"),
    (r"\\ge(?![a-zA-Z])", r"\\geq"),
    (r"\\leqslant(?![a-zA-Z])", r"\\leq"),
    (r"\\geqslant(?![a-zA-Z])", r"\\geq"),
    (r"\\lt(?![a-zA-Z])", "<"),
    (r"\\gt(?![a-zA-Z])", ">"),
    (r"\\ne(?![a-zA-Z])", r"\\neq"),
    (r"\\tfrac(?![a-zA-Z])", r"\\frac"),
    (r"\\square(?![a-zA-Z])|\\Box(?![a-zA-Z])", "\u25a1"),
    (r"\\blacksquare(?![a-zA-Z])", "\u25a0"),
    (r"\\surd(?![a-zA-Z])", "\u221a"),
]

# 需要单独排版（而不是交给 mathtext）的字符：CJK、全角标点、圈号、几何方块、根号
HOIST_RE = re.compile(
    r"[\u2e80-\u9fff\u3000-\u303f\uff00-\uffef\u201c\u201d\u2018\u2019"
    r"\u2460-\u24ff\u25a0-\u25ff\u221a]")

# 必须带花括号参数的命令（mathtext 不接受 \frac1n 这种写法）
_ONE_ARG = {
    "sqrt", "mathbf", "mathrm", "mathbb", "mathcal", "mathit", "mathsf", "mathtt",
    "mathfrak", "boldsymbol", "pmb", "vec", "hat", "bar", "tilde", "dot", "ddot",
    "widehat", "widetilde", "overline", "underline", "boxed", "operatorname",
    "text", "mathnormal", "mathring", "overbrace", "underbrace", "binom",
}
_TWO_ARG = {"frac", "dfrac", "tfrac", "cfrac", "binom", "overset", "underset", "stackrel"}


def _take_token(s, k):
    """取一个 token：\\cmd 或单个字符。返回 (token, 新位置)，取不到返回 (None, k)。"""
    if k >= len(s):
        return None, k
    if s[k] == "\\":
        m = re.match(r"\\([a-zA-Z]+)", s[k:])
        if m:
            return m.group(0), k + m.end()
        return s[k:k + 2], min(k + 2, len(s))
    if s[k] in "{} ":
        return None, k
    return s[k], k + 1


def brace_args(s):
    """
    把 \\frac1n / \\dfrac\\pi2 / \\mathbf a 这类免括号写法补上花括号。
    注意要递归进花括号内部：\\sqrt{\\dfrac2n} 里的 \\dfrac2n 也得补。
    """
    out, i, n = [], 0, len(s)
    while i < n:
        m = re.match(r"\\([a-zA-Z]+)", s[i:])
        if not m:
            out.append(s[i]); i += 1; continue
        name = m.group(1)
        j = i + m.end()
        out.append(s[i:j]); i = j
        if name not in _ONE_ARG and name not in _TWO_ARG:
            continue
        if name == "sqrt":  # 可选次数 [3]
            k = i
            while k < n and s[k] == " ":
                k += 1
            if k < n and s[k] == "[":
                e = s.find("]", k)
                if e != -1:
                    out.append(s[i:e + 1]); i = e + 1
        for _ in range(2 if name in _TWO_ARG else 1):
            k = i
            while k < n and s[k] == " ":
                k += 1
            if k < n and s[k] == "{":
                body, e = read_group(s, k)
                out.append(s[i:k + 1] + brace_args(body) + "}")
                i = e
            else:
                tok, e = _take_token(s, k)
                if tok is None:
                    out.append(s[i:k]); i = k; break
                out.append(s[i:k] + "{" + brace_args(tok) + "}")
                i = e
    return "".join(out)


def normalize_math(tex):
    """把 mathtext 不支持的常见写法改写成支持的形式。"""
    # 公式里的换行（多行 $$...$$ 常这么写）在 TeX 里等价于空格
    s = tex.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    # \textcolor{c}{X} -> X
    s = re.sub(r"\\textcolor\s*\{[^{}]*\}\s*\{", "{", s)
    # \cancel{X} \bcancel{X} \xcancel{X} \sout{X} -> X
    for cmd in ("cancel", "bcancel", "xcancel", "sout"):
        while True:
            m = re.search(r"\\" + cmd + r"\s*\{", s)
            if not m:
                break
            body, end = read_group(s, m.end() - 1)
            s = s[:m.start()] + "{" + body + "}" + s[end:]
    # \bigl \Bigl \bigr \Bigr ... -> \left \right
    def _big(m):
        name = m.group(0).lstrip("\\").strip()
        return r"\left" if name[:3].lower() == "big" and "l" in name[3:] else \
               (r"\right" if name[:3].lower() == "big" else m.group(0))
    s = re.sub(r"\\(?:bigl|Bigl|biggl|Biggl|bigr|Bigr|biggr|Biggr)(?![a-zA-Z])", _big, s)
    # \big \Big \bigg \Bigg（无 l/r 后缀）：直接丢掉
    s = re.sub(r"\\(?:bigg|Bigg|big|Big)(?![a-zA-Z])", "", s)
    # \lvert \rvert \vert -> |   \lVert \rVert \Vert -> \|
    s = re.sub(r"\\lvert(?![a-zA-Z])|\\rvert(?![a-zA-Z])|\\vert(?![a-zA-Z])", "|", s)
    s = re.sub(r"\\lVert(?![a-zA-Z])|\\rVert(?![a-zA-Z])|\\Vert(?![a-zA-Z])", r"\\|", s)
    # 其余别名
    s = re.sub(r"\\displaystyle(?![a-zA-Z])|\\textstyle(?![a-zA-Z])|\\scriptstyle(?![a-zA-Z])"
               r"|\\scriptscriptstyle(?![a-zA-Z])", "", s)
    s = re.sub(r"\\limits(?![a-zA-Z])|\\nolimits(?![a-zA-Z])", "", s)
    s = re.sub(r"\\iff(?![a-zA-Z])", r"\\Longleftrightarrow", s)
    s = re.sub(r"\\cfrac(?![a-zA-Z])", r"\\dfrac", s)
    s = re.sub(r"\\stackrel(?![a-zA-Z])", r"\\overset", s)
    s = re.sub(r"\\color\s*\{[^{}]*\}", "", s)
    s = re.sub(r"\\lbrace(?![a-zA-Z])", r"\\{", s)
    s = re.sub(r"\\rbrace(?![a-zA-Z])", r"\\}", s)
    s = re.sub(r"\\mbox(?![a-zA-Z])", r"\\text", s)
    # 符号别名
    for pat, rep in SYMBOL_ALIASES:
        s = re.sub(pat, rep, s)
    # \tag{1} / \tag*{1.2} -> 行尾的 (1)
    s = re.sub(r"\\tag\*?\s*\{", r"\\qquad\\text{(", s)
    while True:
        m = re.search(r"\\qquad\\text\{\(([^{}]*)\}\s*$", s)
        if not m:
            break
        s = s[:m.start()] + r"\qquad(" + m.group(1) + ")"
    # 空组 {}：原文里 \frac{?}{} 这类占位，补一个空档，否则 mathtext 直接报错
    s = re.sub(r"\{(\s*)\}", r"{\\;}", s)
    # "\ "（反斜杠+空格）统一换成 \;，避免被 strip 掉后留下孤零零的反斜杠
    s = re.sub(r"\\ +", r"\\;", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = brace_args(s)
    return s.strip()


def fix_delimiters(s):
    """
    \\left/\\right 配对不上时（原文笔误，比如多打了一个 \\bigr|），
    把多余的那个去掉，而不是让整条公式渲染失败。
    """
    ms = list(_DELIM_AT.finditer(s))
    if not ms:
        return s
    drop, stack = set(), []
    for i, m in enumerate(ms):
        if m.group(1) == "left":
            stack.append(i)
        elif stack:
            stack.pop()
        else:
            drop.add(i)          # 多出来的 \right
    drop.update(stack)           # 没闭合的 \left
    if not drop:
        return s
    out, pos = [], 0
    for i, m in enumerate(ms):
        out.append(s[pos:m.start()])
        if i in drop:
            out.append("" if m.group(2) in (".",) else m.group(2))
        else:
            out.append(m.group(0))
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)


def normalize_delims(s):
    """
    只做定界符相关的归一化，必须在「扫描构造」之前跑：
    这样 \\bigl[ ... \\text{中文} ... \\bigr] 里的 \\left/\\right 才能被识别成跨构造的一对。
    """
    def _big(m):
        name = m.group(0).lstrip("\\").strip()
        if name[:3].lower() != "big":
            return m.group(0)
        return r"\left" if name.endswith(("l", "L")) or name[3:4] == "l" else r"\right"

    s = re.sub(r"\\(?:bigl|Bigl|biggl|Biggl|bigr|Bigr|biggr|Biggr)(?![a-zA-Z])", _big, s)
    s = re.sub(r"\\(?:bigg|Bigg|big|Big)(?![a-zA-Z])", "", s)
    s = re.sub(r"\\lvert(?![a-zA-Z])|\\rvert(?![a-zA-Z])|\\vert(?![a-zA-Z])", "|", s)
    s = re.sub(r"\\lVert(?![a-zA-Z])|\\rVert(?![a-zA-Z])|\\Vert(?![a-zA-Z])", r"\\|", s)
    s = re.sub(r"\\lbrace(?![a-zA-Z])", r"\\{", s)
    s = re.sub(r"\\rbrace(?![a-zA-Z])", r"\\}", s)
    return fix_delimiters(s)


def strip_outer_braces(s):
    """{\\boxed{...}} 这种整体被一层多余花括号包住的情况，剥掉外层。"""
    s = s.strip()
    while s.startswith("{") and s.endswith("}"):
        body, e = read_group(s, 0)
        if e != len(s):
            break
        s = body.strip()
    return s


# --------------------------------------------------------------------------- #
# 解析：字符串 -> 盒子树
# --------------------------------------------------------------------------- #
ENV_DELIMS = {
    "matrix": (".", "."),
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("‖", "‖"),
    "smallmatrix": (".", "."),
}
ENV_KINDS = set(ENV_DELIMS) | {"cases", "array", "aligned", "align", "align*", "alignedat",
                               "gathered", "gather", "gather*", "split", "subarray"}

SENTINEL_RE = re.compile(r"@@PH(\d+)@@")
LEFT_DELIM_RE = re.compile(r"\\left\s*(\\[a-zA-Z]+|\\?.|\S)\s*$")
RIGHT_DELIM_RE = re.compile(r"^\s*\\right\s*(\\[a-zA-Z]+|\\?.|\S)")
CONSTRUCT_PAT = [
    ("boxed", re.compile(r"\\boxed\s*\{")),
    ("underbrace", re.compile(r"\\underbrace\s*\{")),
    ("overbrace", re.compile(r"\\overbrace\s*\{")),
    ("overset", re.compile(r"\\(?:overset|stackrel)\s*\{")),
    ("underset", re.compile(r"\\underset\s*\{")),
    ("xlongequal", re.compile(r"\\xlongequal\s*\{")),
    ("xarrow", re.compile(r"\\x(?:right|left)arrow\s*(?:\[[^\]]*\])?\s*\{")),
]


def _split_top(s, sep):
    """按顶层分隔符切分（忽略花括号与环境内部）。sep 为 '\\\\' 或 '&'。"""
    parts, cur, i, depth = [], [], 0, 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+)", s[i:])
            if c == "\\" and s.startswith("\\\\", i) and depth == 0:
                j = i + 2
                m2 = re.match(r"\s*\[[^\]]*\]", s[j:])
                if m2:
                    j += m2.end()
                parts.append("".join(cur)); cur = []; i = j; continue
            if m:
                name = m.group(1)
                if name in ("begin", "end"):
                    j = i + m.end()
                    while j < len(s) and s[j] == " ":
                        j += 1
                    if j < len(s) and s[j] == "{":
                        _, j2 = read_group(s, j)
                        depth += 1 if name == "begin" else -1
                        cur.append(s[i:j2]); i = j2; continue
                cur.append(s[i:i + m.end()]); i += m.end(); continue
            cur.append(s[i:i + 2]); i += 2; continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == sep and depth == 0:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(c); i += 1
    parts.append("".join(cur))
    return parts


def _find_env_end(s, start, env):
    """从 start 起找匹配的 \\end{env}，返回 (content, end_index)。"""
    i = start
    depth = 0
    pat_begin = re.compile(r"\\begin\s*\{([a-zA-Z*]+)\}")
    pat_end = re.compile(r"\\end\s*\{([a-zA-Z*]+)\}")
    while i < len(s):
        mb = pat_begin.match(s, i)
        me = pat_end.match(s, i)
        if mb:
            if mb.group(1) == env:
                depth += 1
            i = mb.end(); continue
        if me:
            if me.group(1) == env:
                if depth == 0:
                    return s[start:i], me.end()
                depth -= 1
            i = me.end(); continue
        i += 1
    raise ValueError("找不到 \\end{%s}" % env)


def _scan_construct(s, store):
    """找最靠前的顶层构造，返回 (kind, payload, start, end)。"""
    i, depth = 0, 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            if s.startswith("\\\\", i):
                i += 2; continue
            m = re.match(r"\\([a-zA-Z]+)", s[i:])
            if not m:
                i += 2; continue
            name = m.group(1)
            if name in ("begin", "end"):
                j = i + m.end()
                while j < len(s) and s[j] == " ":
                    j += 1
                if j < len(s) and s[j] == "{":
                    env, j2 = read_group(s, j)
                    if depth == 0:
                        if name == "end":
                            raise ValueError("多余的 \\end{%s}" % env)
                        body, end = _find_env_end(s, j2, env)
                        return ("env", (env, body), i, end)
                    depth += 1 if name == "begin" else -1
                    i = j2; continue
                i = j + 1; continue
            if depth == 0:
                for kind, pat in CONSTRUCT_PAT:
                    mc = pat.match(s, i)
                    if mc:
                        return (kind, None, i, mc.end())   # mc.end() 已是绝对下标
            i += m.end(); continue
        if s.startswith("@@PH", i):
            m = SENTINEL_RE.match(s, i)
            if m and depth == 0:
                return ("placeholder", int(m.group(1)), i, m.end())
            i += 4; continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return None


def _parse_cells(body, ncol_hint=None):
    rows = []
    for r in _split_top(body, None):
        cells = _split_top(r, "&")
        rows.append(cells)
    return rows


def _read_arg(s, i):
    """读取一个 {...} 参数，i 指向 '{'。"""
    return read_group(s, i)


# 注意 (?![a-zA-Z])：否则 \leftrightarrow / \rightarrow 里的 \left / \right 会被误认成定界符命令
_DELIM_AT = re.compile(r"\\(left|right)(?![a-zA-Z])\s*(\\[a-zA-Z]+|\\?.|\S)")


def _find_unmatched_left(s):
    """prefix 里最后一个没配对的 \\leftX（返回 match 或 None）。"""
    stack = []
    for m in _DELIM_AT.finditer(s):
        if m.group(1) == "left":
            stack.append(m)
        elif stack:
            stack.pop()
    return stack[-1] if stack else None


def _find_top_right(s):
    """suffix 里第一个处于最外层的 \\rightX（返回 match 或 None）。"""
    depth = 0
    for m in _DELIM_AT.finditer(s):
        if m.group(1) == "left":
            depth += 1
        elif depth == 0:
            return m
        else:
            depth -= 1
    return None


def parse(tex, ctx):
    """字符串 -> Box（递归）。"""
    tex = normalize_delims(tex)
    s = strip_outer_braces(tex).strip()
    if s.endswith("\\"):          # strip() 把 "\ " 的空格吃掉了，补回来
        s = s + " "
    if not s:
        return SpaceBox(0.0)

    # 1) 顶层 \\ 分行
    lines = _split_top(s, None)
    if len(lines) > 1:
        rows = [parse(x, ctx) for x in lines if x.strip()]
        return VBox(rows, gap=0.5, align="center")

    # 2) 找构造
    found = _scan_construct(s, ctx.store)
    if found is None:
        if _has_cjk(s):
            return _cjk_split(s, ctx)
        return MathBox(normalize_math(s))

    kind, payload, start, end = found
    prefix, suffix = s[:start], s[end:]

    if kind == "env":
        env, body = payload
        node, _ = _build_env(env, body, ctx)
    elif kind == "placeholder":
        node = TextBox(ctx.store[payload][1])
        node.measure(ctx)
    elif kind == "boxed":
        body, e2 = _read_arg(s, end - 1)
        node = BoxedBox(parse(body, ctx))
        end = e2
        suffix = s[end:]
    elif kind in ("underbrace", "overbrace"):
        body, e2 = _read_arg(s, end - 1)
        lab = None
        m = re.match(r"\s*[_^]\s*\{", s[e2:])
        if m:
            lab_body, e3 = _read_group_at(s, e2 + m.end() - 1)
            lab = ScaleBox(parse(lab_body, ctx), 0.72)
            e2 = e3
        node = BraceBox(parse(body, ctx), lab, above=(kind == "overbrace"))
        end = e2
        suffix = s[end:]
    elif kind in ("overset", "underset"):
        top_body, e2 = _read_arg(s, end - 1)
        m = re.match(r"\s*\{", s[e2:])
        bot_body, e3 = _read_group_at(s, e2 + m.end() - 1)
        top = ScaleBox(parse(top_body, ctx), 0.72)
        bot = parse(bot_body, ctx)
        node = StackBox(bot, top) if kind == "overset" else StackBox(bot, below=top)
        end = e3
        suffix = s[end:]
    elif kind == "xlongequal":
        body, e2 = _read_arg(s, end - 1)
        node = StackBox(parse(r"=", ctx), ScaleBox(parse(body, ctx), 0.72))
        end = e2
        suffix = s[end:]
    elif kind == "xarrow":
        arrow = r"\longrightarrow" if "right" in s[start:start + 12] else r"\longleftarrow"
        body, e2 = _read_arg(s, end - 1)
        node = StackBox(parse(arrow, ctx), ScaleBox(parse(body, ctx), 0.72))
        end = e2
        suffix = s[end:]
    else:
        raise ValueError("未知构造 %s" % kind)

    # 3) 跨构造的 \left...\right：把外层定界符接管过来自己画（mathtext 只认整段配对）
    ml = _find_unmatched_left(prefix)
    if ml is not None:
        mr = _find_top_right(suffix)
        if mr is not None:
            left_kind = _delim_kind(ml.group(2))
            right_kind = _delim_kind(mr.group(2))
            in_prefix = prefix[ml.end():]
            in_suffix = suffix[:mr.start()]
            inner = []
            if in_prefix.strip():
                inner.append(parse(in_prefix, ctx))
            inner.append(node)
            if in_suffix.strip():
                inner.append(parse(in_suffix, ctx))
            node = _wrap_delims(inner[0] if len(inner) == 1 else HBox(inner, sep=0.0),
                                left_kind, right_kind, ctx)
            prefix = prefix[:ml.start()]
            suffix = suffix[mr.end():]

    parts = []
    if prefix.strip():
        parts.append(parse(prefix, ctx))
    parts.append(node)
    if suffix.strip():
        parts.append(parse(suffix, ctx))
    if len(parts) == 1:
        return parts[0]
    return HBox(parts, sep=0.0)


def _read_group_at(s, i):
    return read_group(s, i)


def _wrap_delims(node, left, right, ctx):
    node.measure(ctx)
    gap = 0.12 * ctx.fs
    children = []
    if left and left != ".":
        dl = DelimBox(left, node.h, node.d, ctx.fs); dl.measure(ctx)
        children.append(dl)
        children.append(SpaceBox(gap))
    children.append(node)
    if right and right != ".":
        dr = DelimBox(right, node.h, node.d, ctx.fs); dr.measure(ctx)
        children.append(SpaceBox(gap))
        children.append(dr)
    return HBox(children, sep=0.0)


def _build_env(env, body, ctx):
    """把环境内容编成盒子。"""
    body = body.strip()
    if env in ENV_DELIMS:
        rows = [[parse(c, ctx) for c in r] for r in _parse_cells(body)]
        l, r = ENV_DELIMS[env]
        return MatrixBox(rows, l, r), None
    if env == "cases":
        rows = [[parse(c, ctx) for c in r] for r in _parse_cells(body)]
        return CasesBox(rows, "{"), None
    if env in ("aligned", "align", "align*", "split", "alignedat"):
        rows = [[parse(c, ctx) for c in r] for r in _parse_cells(body)]
        g = GridBox(rows, align="alt", colgap=0.45, rowgap=0.55)
        return g, None
    if env in ("gathered", "gather", "gather*"):
        rows = [[parse(c, ctx) for c in r] for r in _parse_cells(body)]
        return GridBox(rows, align="center", colgap=0.5, rowgap=0.55), None
    if env in ("array", "subarray"):
        # 可选列格式 {llcr}
        spec = ""
        m = re.match(r"\s*\{([lcr|]+)\}", body)
        if m:
            spec = m.group(1)
            body = body[m.end():]
        rows_raw = _parse_cells(body)
        rows = [[parse(c, ctx) for c in r] for r in rows_raw]
        if spec:
            ncol = len(spec.replace("|", ""))
            grids = []
            # 逐列对齐：交给 GridBox 的自定义对齐
            g = GridBox(rows, align="custom", colgap=0.9, rowgap=0.45)
            g.colspec = [ch for ch in spec if ch in "lcr"]
            return g, None
        return GridBox(rows, align="left", colgap=0.9, rowgap=0.45), None
    raise ValueError("不支持的环境：%s" % env)


def _cjk_split(s, ctx):
    """裸中文（没写在 \\text 里）、圈号①②、方块□、根号√ 等也照样排。"""
    parts = re.split("(" + HOIST_RE.pattern + "+)", s)
    children = []
    for p in parts:
        if not p:
            continue
        if HOIST_RE.search(p):
            children.append(TextBox(p))
        else:
            children.append(MathBox(normalize_math(p)))
    return HBox(children, sep=0.0)


# --------------------------------------------------------------------------- #
# 顶层渲染
# --------------------------------------------------------------------------- #
def strip_delims(tex):
    s = tex.strip()
    for a, b in (("$$", "$$"), ("$", "$"), (r"\[", r"\]"), (r"\(", r"\)")):
        if s.startswith(a) and s.endswith(b) and len(s) > len(a) + len(b) - 1:
            return s[len(a):-len(b)].strip()
    return s


def render(tex, out, fontsize=24, dpi=300, color="#111111", bg=None, pad=8.0,
           cjk_font=None, fontset="cm", line_gap=0.5):
    """把一段 LaTeX 公式渲染成 PNG。bg=None 表示透明背景。"""
    configure(fontset)
    cjk_font = cjk_families(cjk_font)
    src = strip_delims(tex)
    scratch = plt.figure(figsize=(2, 2), dpi=72)
    store = []
    try:
        ctx = Ctx(scratch, fontsize, color, cjk_font, max(0.7, fontsize * 0.045), store)
        src2 = preprocess_text(src, store)
        root = parse(src2, ctx)
        root.measure(ctx)
        w = root.w + 2 * pad
        h = root.h + root.d + 2 * pad
        plt.close(scratch)

        fig = plt.figure(figsize=(w / 72.0, h / 72.0), dpi=dpi)
        if bg:
            fig.patch.set_facecolor(bg)
        else:
            fig.patch.set_alpha(0.0)
        ctx2 = Ctx(fig, fontsize, color, cjk_font, max(0.7, fontsize * 0.045), store)
        root.draw(ctx2, pad, pad + root.d)
        fig.savefig(out, dpi=dpi, transparent=(bg is None),
                    facecolor=(bg if bg else "none"), edgecolor="none")
        plt.close(fig)
        px = (int(round(w / 72.0 * dpi)), int(round(h / 72.0 * dpi)))
        return {"out": out, "size_px": px, "size_pt": (w, h), "tex": src}
    except Exception:
        plt.close(scratch)
        raise
