# -*- coding: utf-8 -*-
"""两张曲面所围立体的体积（切平面/抛物面/锥面类体积题）。出图 + 数值自校验。"""
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from common import BLUE, ORANGE, RED, expr, masked_volume, region_bounds, save

DEFAULTS = {
    "up": "2*x-2*y-1",            # 上面的曲面
    "down": "x**2+y**2",          # 下面的曲面
    "xmin": -0.4, "xmax": 2.4, "ymin": -2.4, "ymax": 0.4,
    "views": [[18, -88], [26, -66]],
    "nslices": 9,
    "upName": "切平面", "downName": "抛物面",
    "mark": [1.0, -1.0, 3.0, "切点 M(1,-1,3)"],
    "outPrefix": "曲面体积", "dpi": 165, "n": 900,
}


def render(params, out_dir):
    import matplotlib.pyplot as plt
    p = dict(DEFAULTS)
    p.update(params or {})
    up, down = expr(p["up"]), expr(p["down"])
    xmin, xmax = float(p["xmin"]), float(p["xmax"])
    ymin, ymax = float(p["ymin"]), float(p["ymax"])
    n = int(p["n"])
    vol = masked_volume(up, down, xmin, xmax, ymin, ymax, n=1400)
    x0, x1, y0, y1 = region_bounds(up, down, xmin, xmax, ymin, ymax, n)
    notes = ["所围体积 ≈ %.6f（网格积分，交付前用它核对）" % vol,
             "区域包围盒：x∈[%.4f, %.4f]，y∈[%.4f, %.4f]" % (x0, x1, y0, y1)]

    x = np.linspace(xmin, xmax, n)
    y = np.linspace(ymin, ymax, n)
    X, Y = np.meshgrid(x, y)
    H = up(X, Y) - down(X, Y)
    mask = H > 0

    # 交线（H=0 的等值线），2D 与 3D 共用
    tmp = plt.figure()
    cs = plt.contour(X, Y, H, levels=[0])
    segs = [s.copy() for s in cs.allsegs[0]]
    plt.close(tmp)

    yc = 0.5 * (y0 + y1)
    ry = np.where(H[np.argmin(np.abs(y - yc))] > 0)[0]
    xa, xb = (x[ry.min()], x[ry.max()]) if len(ry) else (x0, x1)

    views = p["views"] or DEFAULTS["views"]
    if not hasattr(views[0], "__len__"):   # 容忍写成 [elev, azim] 的扁平形式
        views = [views]
    outputs = []
    for vi, view in enumerate(views):
        el, az = int(view[0]), int(view[1])
        fig = plt.figure(figsize=(13.5, 6.6), dpi=int(p["dpi"]))
        ax = fig.add_axes([0.005, 0.02, 0.44, 0.92], projection="3d")

        ys = np.linspace(y0, y1, int(p["nslices"]))
        polys, cols = [], []
        for i, v in enumerate(ys):
            row = np.argmin(np.abs(y - v))
            idx = np.where(H[row] > 0)[0]
            if len(idx) < 2:
                continue
            xs = x[idx]
            yv = np.full_like(xs, v)
            top = up(xs, yv)
            bot = down(xs, yv)
            polys.append(list(zip(xs, yv, top)) + list(zip(xs[::-1], yv[::-1], bot[::-1])))
            tt = i / max(1.0, len(ys) - 1.0)
            cols.append((0.99 - 0.16 * tt, 0.78 - 0.30 * tt, 0.42 - 0.24 * tt, 0.92))
        if polys:
            ax.add_collection3d(Poly3DCollection(polys, facecolors=cols, edgecolors="#4a4a4a",
                                                 linewidths=0.55))
        for s in segs:
            zz = down(s[:, 0], s[:, 1])
            ax.plot(s[:, 0], s[:, 1], zz, color=RED, lw=2.8)
        if p["mark"]:
            mx, my, mz, mt = float(p["mark"][0]), float(p["mark"][1]), float(p["mark"][2]), str(p["mark"][3])
            ax.scatter([mx], [my], [mz], color=RED, s=40, depthshade=False)
            ax.text(mx, my, mz + 0.12, mt, color=RED, fontsize=10)
        zlo = float(np.nanmin(down(X, Y)[mask])) if mask.any() else 0.0
        zhi = float(np.nanmax(up(X, Y)[mask])) if mask.any() else 1.0
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_zlim(zlo - 0.05 * (zhi - zlo + 1e-9), zhi + 0.08 * (zhi - zlo + 1e-9))
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_box_aspect((1.0, 1.0, 0.62))
        ax.view_init(elev=el, azim=az)
        ax.set_title("立体按 y 切成 %d 片（elev=%d, azim=%d）" % (len(polys), el, az), fontsize=11)

        ax2 = fig.add_axes([0.50, 0.57, 0.47, 0.38])
        xs = np.linspace(xa, xb, 400)
        yv = np.full_like(xs, yc)
        ax2.fill_between(xs, down(xs, yv), up(xs, yv), color="#f6d9a8", alpha=0.9)
        ax2.plot(xs, up(xs, yv), color=ORANGE, lw=2.2, label="%s（截面 y=%.4f）" % (p["upName"], yc))
        ax2.plot(xs, down(xs, yv), color=BLUE, lw=2.2, label="%s（截面 y=%.4f）" % (p["downName"], yc))
        hmax = float(np.max(up(xs, yv) - down(xs, yv)))
        xm = float(xs[int(np.argmax(up(xs, yv) - down(xs, yv)))])
        ax2.plot([xm, xm], [down(xm, yv[0]), up(xm, yv[0])], color="#111111", lw=1.6)
        ax2.annotate("最大高差 %.4f" % hmax, xy=(xm, 0.5 * (up(xm, yv[0]) + down(xm, yv[0]))),
                     xytext=(xm, down(xm, yv[0]) - 0.18 * (zhi - zlo + 1e-9)), fontsize=9,
                     ha="center", arrowprops=dict(arrowstyle="->", color="#111111", lw=1))
        ax2.set_xlabel("x")
        ax2.set_ylabel("z")
        ax2.set_title("竖直截面：所夹区域就是立体的一个剖面", fontsize=11)
        ax2.legend(fontsize=8.5, loc="upper left")

        ax3 = fig.add_axes([0.52, 0.08, 0.235, 0.34])
        HH = np.where(mask, H, np.nan)
        cs3 = ax3.contourf(X, Y, HH, levels=12, cmap="YlOrBr")
        ax3.contour(X, Y, H, levels=[0], colors=RED, linewidths=2)
        ax3.set_aspect("equal")
        ax3.set_title("高度场 up − down", fontsize=10.5)
        fig.colorbar(cs3, ax=ax3, shrink=0.85, pad=0.03)

        ax4 = fig.add_axes([0.80, 0.10, 0.19, 0.32])
        ax4.axis("off")
        ax4.text(0.0, 0.86, "体积 = 区域上每点", fontsize=9.5)
        ax4.text(0.0, 0.72, "高度差的总和", fontsize=9.5)
        ax4.text(0.0, 0.40, r"$V=%.6f$" % vol, fontsize=13, color="#b5761b")

        name = "%s_视角%s.png" % (p["outPrefix"], "ABCDEFG"[vi] if vi < 7 else str(vi))
        path, warn = save(fig, out_dir.rstrip("/\\") + "/" + name, dpi=int(p["dpi"]))
        outputs.append(path)
        notes += warn
    notes.append("已按 %d 个候选视角各出一张，挑最清楚的那张交付（这是规范要求的一步）" % len(views))
    return {"outputs": outputs, "notes": notes}


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(render(args, "."), ensure_ascii=False, indent=1))
