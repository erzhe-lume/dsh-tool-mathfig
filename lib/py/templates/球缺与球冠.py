# -*- coding: utf-8 -*-
"""球缺与球冠的几何图：球缺截面（标 R、h、r、球心）+ 立体图。纯几何标注，不解题。"""

import numpy as np

from common import BLUE, FILL, GREY, LBLUE, ORANGE, RED, save

DEFAULTS = {
    "R": 1.0,              # 球半径
    "h": 0.55,             # 球缺高（顶点到截面的距离）
    "views": [[18, -60]],  # 立体图候选视角
    "labels": {"O": "O（球心）", "R": "R", "h": "h", "r": "r"},
    "outPrefix": "球缺",
    "dpi": 170,
}


def _geom(R, h):
    h = min(max(h, 1e-6), 2 * R - 1e-6)
    z0 = R - h                                        # 截面高度
    r = float(np.sqrt(max(0.0, 2 * R * h - h * h)))   # 底面半径 = √(2Rh − h²)
    return z0, r


def _right_angle(ax, x, y, d, color="#333333"):
    """在 (x, y) 处画一个开口朝右上的直角标记。"""
    ax.plot([x, x + d], [y, y], color=color, lw=0.9)
    ax.plot([x + d, x + d], [y, y + d], color=color, lw=0.9)
    ax.plot([x, x + d], [y + d, y + d], color=color, lw=0.9)


def render(params, out_dir):
    import matplotlib.pyplot as plt

    p = dict(DEFAULTS)
    p.update(params or {})
    R, h = float(p["R"]), float(p["h"])
    z0, r = _geom(R, h)
    lab = dict(DEFAULTS["labels"])
    lab.update(p.get("labels") or {})
    views = p["views"] or DEFAULTS["views"]
    if not hasattr(views[0], "__len__"):
        views = [views]

    notes = ["几何量：R=%.4f，h=%.4f，截面高 z0=R−h=%.4f，底面半径 r=√(2Rh−h²)=%.4f" % (R, h, z0, r),
             "只画几何，不给体积/面积结论（按要求不解题）"]

    fig = plt.figure(figsize=(13.0, 5.4), dpi=int(p["dpi"]))

    # ---------------------------------------------------------------- 截面
    ax = fig.add_axes([0.03, 0.05, 0.40, 0.84])
    th = np.linspace(0, 2 * np.pi, 721)
    ax.plot(R * np.sin(th), R * np.cos(th), color=GREY, lw=1.6, zorder=2)
    tc = np.linspace(-np.arccos(z0 / R), np.arccos(z0 / R), 400)
    ax.fill_between(R * np.sin(tc), z0, R * np.cos(tc), color=FILL, alpha=0.95, zorder=1)
    ax.plot(R * np.sin(tc), R * np.cos(tc), color=ORANGE, lw=2.8, zorder=3)
    ax.plot([-1.28 * r, 1.28 * r], [z0, z0], color=RED, lw=1.8, ls="--", zorder=3)
    ax.plot([0, 0], [-1.10 * R, 1.18 * R], color="#333333", lw=1.0, ls=":", zorder=2)
    ax.plot([0], [0], "o", color="#111111", ms=5, zorder=5)
    ax.text(0.08, -0.16, lab["O"], fontsize=10.5, color="#111111")
    ax.plot([0, r], [z0, z0], color=BLUE, lw=2.0, zorder=4)          # 底面半径 r
    ax.plot([0, r], [0, z0], color=BLUE, lw=2.0, zorder=4)           # 球半径 R
    ax.text(0.42 * r, z0 + 0.055 * R, lab["r"], fontsize=13, color=BLUE, ha="center")
    ax.text(0.66 * r, 0.40 * z0, lab["R"], fontsize=13, color=BLUE)
    ax.plot([0], [z0], "o", color=BLUE, ms=4, zorder=5)
    _right_angle(ax, 0.0, z0, 0.085 * R)
    ax.annotate("", xy=(0.16 * R, R), xytext=(0.16 * R, z0),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.6), zorder=5)
    ax.text(0.215 * R, 0.5 * (z0 + R), lab["h"], fontsize=13, color=RED, va="center")
    ax.plot([0], [R], "o", color=ORANGE, ms=5, zorder=5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("截面：红色弦以上是球缺（O 为球心）", fontsize=11.5)

    # ---------------------------------------------------------------- 立体
    ax3 = fig.add_axes([0.42, 0.00, 0.57, 0.92], projection="3d")
    u = np.linspace(0, 2 * np.pi, 97)
    vv = np.linspace(0, np.pi, 65)
    U, V = np.meshgrid(u, vv)
    X, Y, Z = R * np.sin(V) * np.cos(U), R * np.sin(V) * np.sin(U), R * np.cos(V)
    phi0 = float(np.arccos(z0 / R))
    cap = V <= phi0
    ax3.plot_surface(X, Y, Z, color=LBLUE, alpha=0.20, linewidth=0, antialiased=True, shade=False)
    ax3.plot_surface(np.where(cap, X, np.nan), np.where(cap, Y, np.nan), np.where(cap, Z, np.nan),
                     color="#f2a33c", alpha=0.95, linewidth=0, antialiased=True, shade=True)
    ax3.plot(r * np.cos(u), r * np.sin(u), np.full_like(u, z0), color=RED, lw=2.8)
    ax3.plot([0, 0], [0, 0], [-1.02 * R, 1.04 * R], color="#333333", lw=1.2, ls=":")
    ax3.plot([0, r], [0, 0], [0, z0], color=BLUE, lw=2.2)
    ax3.plot([0, r], [0, 0], [z0, z0], color=BLUE, lw=2.2, ls="--")
    ax3.plot([0, 0], [0, 0], [z0, R], color=RED, lw=2.4)
    ax3.scatter([0], [0], [z0], color=BLUE, s=20, depthshade=False)
    ax3.text(0, 0, -0.20 * R, lab["O"], fontsize=10.5)
    ax3.text(0.62 * r, 0.02 * R, 0.36 * z0, lab["R"], fontsize=12, color=BLUE)
    ax3.text(r * 0.42, 0.02 * R, z0 + 0.05 * R, lab["r"], fontsize=12, color=BLUE)
    ax3.text(0.14 * R, 0.14 * R, 0.5 * (z0 + R), lab["h"], fontsize=12, color=RED)
    ax3.set_xlim(-1.02 * R, 1.02 * R)
    ax3.set_ylim(-1.02 * R, 1.02 * R)
    ax3.set_zlim(-1.02 * R, 1.10 * R)
    ax3.set_box_aspect((1, 1, 1))
    ax3.set_xlabel("x")
    ax3.set_ylabel("y")
    ax3.set_zlabel("z")
    ax3.view_init(elev=int(views[0][0]), azim=int(views[0][1]))
    ax3.set_title("立体：橙色球缺 + 红圈底面圆", fontsize=11.5)

    path, warn = save(fig, out_dir.rstrip("/\\") + "/" + p["outPrefix"] + ".png", dpi=int(p["dpi"]))
    return {"outputs": [path], "notes": notes + warn}


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(render(args, "."), ensure_ascii=False, indent=1))
