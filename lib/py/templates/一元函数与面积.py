# -*- coding: utf-8 -*-
"""一元函数图像 + 两曲线所夹区域 + 面积标注（定积分求面积、切线、区间再现类配图）。"""
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

from common import BLUE, FILL, ORANGE, RED, expr, save

DEFAULTS = {
    "F": "x**2", "G": "x", "A": -0.4, "B": 1.4,
    "title": "两曲线所夹区域", "xlabel": "x", "ylabel": "y",
    "markX": 0.5, "markText": "最高差处", "shade": True,
    "out": "一元函数_面积.png", "dpi": 170,
}


def render(params, out_dir):
    import matplotlib.pyplot as plt
    p = dict(DEFAULTS)
    p.update(params or {})
    F, G = expr(p["F"]), expr(p["G"])
    a, b = float(p["A"]), float(p["B"])
    x = np.linspace(a, b, 1500)
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.plot(x, F(x), color=BLUE, lw=2.2, label="上曲线  " + str(p["F"]))
    ax.plot(x, G(x), color=ORANGE, lw=2.2, label="下曲线  " + str(p["G"]))
    H = F(x) - G(x)
    roots = []
    for i in np.where(np.diff(np.sign(H)) != 0)[0]:
        try:
            roots.append(float(brentq(lambda u: F(u) - G(u), x[i], x[i + 1])))
        except Exception:
            pass
    notes = []
    if p["shade"]:
        ax.fill_between(x, G(x), F(x), where=H >= 0, color=FILL, alpha=0.9, interpolate=True)
        for r in roots:
            ax.plot([r], [F(r)], "o", color=RED, ms=6)
            ax.annotate("%.4f" % r, xy=(r, F(r)), xytext=(r, F(r) + 0.1 * max(1.0, abs(F(r)))),
                        fontsize=9, color=RED, ha="center")
        notes.append("交点 x = " + ", ".join("%.6f" % r for r in roots) if roots else "区间内没有交点")
        if len(roots) >= 2:
            segs = [abs(quad(lambda u: F(u) - G(u), roots[i], roots[i + 1])[0])
                    for i in range(len(roots) - 1)]
            good = [v for v in segs if np.isfinite(v)]
            if len(good) == len(segs):
                area = sum(good)
                ax.set_title("%s    面积 = %.6f" % (p["title"], area), fontsize=12)
                notes.append("面积 ≈ %.6f（数值积分，交付前用它核对）" % area)
            else:
                # 区间内有可去奇点（如 sin(x)/x 在 x=0）或发散点，逐段报告，不要撒谎
                ax.set_title(p["title"], fontsize=12)
                notes.append("面积数值积分有 %d/%d 段未收敛（区间内可能有可去奇点或发散点，"
                             "必要时把区间拆开分别积分）" % (len(segs) - len(good), len(segs)))
        else:
            ax.set_title(p["title"], fontsize=12)
    elif not roots:
        ax.set_title(p["title"], fontsize=12)
    if p["markX"] is not None:
        mx = float(p["markX"])
        ax.plot([mx], [F(mx)], "o", color=RED, ms=6)
        ax.annotate(p["markText"] or "x=%.3f" % mx, xy=(mx, F(mx)),
                    xytext=(mx + 0.05 * (b - a), F(mx) + 0.12 * max(1.0, abs(F(mx)))),
                    fontsize=9, color=RED, arrowprops=dict(arrowstyle="->", color=RED, lw=1))
    ax.set_xlabel(p["xlabel"])
    ax.set_ylabel(p["ylabel"])
    ax.legend(fontsize=9)
    path, warn = save(fig, out_dir.rstrip("/\\") + "/" + p["out"], dpi=int(p["dpi"]))
    return {"outputs": [path], "notes": notes + warn}


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(render(args, "."), ensure_ascii=False, indent=1))
