# -*- coding: utf-8 -*-
"""mathfig 模板公共层：中文字体、配色、表达式求值、缺字告警、数值自校验。"""
from __future__ import annotations

import math
import os
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

BLUE, ORANGE, RED, GREY = "#2f6fb0", "#b5761b", "#c0392b", "#5a5a5a"
FILL, LBLUE = "#f6d9a8", "#cfe0f2"

_FUNCS = ("exp", "log", "log10", "sqrt", "abs", "sin", "cos", "tan", "arcsin", "arccos",
          "arctan", "sinh", "cosh", "tanh", "maximum", "minimum", "where", "power",
          "sign", "floor", "ceil", "pi", "e", "inf")
_SAFE = {k: getattr(np, k) for k in _FUNCS}
_SAFE.update({"np": np, "math": math})


def expr(spec):
    """把参数字符串（如 '1-(x-1)**2-(y+1)**2'）编译成函数 f(x, y=None)。"""
    if callable(spec):
        return spec

    def f(x, y=None):
        env = dict(_SAFE)
        env["x"] = x
        env["y"] = y
        # 说明：这里给的是 numpy 命名空间 + 正常 builtins。
        # 不能用 {"__builtins__": {}}：scipy.quad 的回调会触发 __import__ 而报 KeyError，
        # 而这个模板本来就允许调用方提供任意表达式，收紧 builtins 没有实际安全收益。
        return eval(spec, {"np": np, "math": math}, env)

    return f


def save(fig, path, dpi=170):
    """存图 + 缺字检查（缺字在图上显示为空框，必须报出来）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.savefig(path, dpi=dpi, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    miss = {str(w.message) for w in caught if "missing from font" in str(w.message)}
    plt.close(fig)
    notes = []
    if miss:
        notes.append("字体缺字（图上是空框，请把该符号改写成 mathtext 或换字体）：" + "；".join(sorted(miss))[:300])
    return path, notes


def grid(f_up, f_down, xmin, xmax, ymin, ymax, n=900):
    x = np.linspace(xmin, xmax, n)
    y = np.linspace(ymin, ymax, n)
    X, Y = np.meshgrid(x, y)
    return X, Y, f_up(X, Y) - f_down(X, Y)


def masked_volume(up, down, xmin, xmax, ymin, ymax, n=1400):
    X, Y, H = grid(up, down, xmin, xmax, ymin, ymax, n)
    H = np.where(H > 0, H, 0.0)
    return float(np.trapezoid(np.trapezoid(H, Y[:, 0], axis=0), X[0, :]))


def region_bounds(up, down, xmin, xmax, ymin, ymax, n=900):
    X, Y, H = grid(up, down, xmin, xmax, ymin, ymax, n)
    m = H > 0
    if not m.any():
        return xmin, xmax, ymin, ymax
    xs, ys = X[0, :][m.any(axis=0)], Y[:, 0][m.any(axis=1)]
    return float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
