# -*- coding: utf-8 -*-
"""二重积分区域 + 被积函数高度场（换序、极坐标、区域分型、对称性类配图）。"""
import numpy as np

from common import RED, expr, save

DEFAULTS = {
    "region": "1-(x-1)**2-(y+1)**2",      # > 0 即在区域 D 内
    "integrand": "1-(x-1)**2-(y+1)**2",   # 高度函数；None/"" 表示不画
    "xmin": -0.4, "xmax": 2.4, "ymin": -2.4, "ymax": 0.4,
    "title": "积分区域与高度场",
    "mark": [1.0, -1.0, "(1,-1)"],
    "out": "二重积分区域.png", "dpi": 170, "n": 700,
}


def render(params, out_dir):
    import matplotlib.pyplot as plt
    p = dict(DEFAULTS)
    p.update(params or {})
    R = expr(p["region"])
    n = int(p["n"])
    x = np.linspace(float(p["xmin"]), float(p["xmax"]), n)
    y = np.linspace(float(p["ymin"]), float(p["ymax"]), n)
    X, Y = np.meshgrid(x, y)
    r = R(X, Y)
    mask = r > 0
    area = float(np.trapezoid(np.trapezoid(mask.astype(float), y, axis=0), x))
    notes = ["区域面积 ≈ %.6f（网格积分，交付前用它核对）" % area]

    has_int = bool(p["integrand"])
    fig, axes = plt.subplots(1, 2 if has_int else 1, figsize=(11.6, 4.9))
    ax = axes[0] if has_int else axes
    ax.contourf(X, Y, np.where(mask, r, np.nan), levels=8, cmap="Blues", alpha=0.6)
    ax.contour(X, Y, r, levels=[0], colors=RED, linewidths=2)
    if p["mark"]:
        mx, my = float(p["mark"][0]), float(p["mark"][1])
        ax.plot([mx], [my], "o", color=RED, ms=6)
        ax.text(mx + 0.02 * (float(p["xmax"]) - float(p["xmin"])), my, str(p["mark"][2]),
                color=RED, fontsize=9)
    ax.set_aspect("equal")
    ax.set_title("%s：区域 D（红线为边界）" % p["title"], fontsize=11)
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    if has_int:
        G = expr(p["integrand"])
        hh = np.where(mask, G(X, Y), np.nan)
        ax2 = axes[1]
        cs = ax2.contourf(X, Y, hh, levels=12, cmap="YlOrBr")
        ax2.contour(X, Y, hh, levels=6, colors="#8a6a3a", linewidths=0.6)
        ax2.contour(X, Y, r, levels=[0], colors=RED, linewidths=2)
        ax2.set_aspect("equal")
        ax2.set_title("被积函数高度场", fontsize=11)
        fig.colorbar(cs, ax=ax2, shrink=0.9, pad=0.03)
        val = float(np.trapezoid(np.trapezoid(np.where(mask, G(X, Y), 0.0), y, axis=0), x))
        notes.append("积分值 ≈ %.6f（网格积分，交付前用它核对）" % val)
    path, warn = save(fig, out_dir.rstrip("/\\") + "/" + p["out"], dpi=int(p["dpi"]))
    return {"outputs": [path], "notes": notes + warn}


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(render(args, "."), ensure_ascii=False, indent=1))
