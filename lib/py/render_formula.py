# -*- coding: utf-8 -*-
"""渲染公式：读 JSON 作业文件 → 出 PNG → 写回结果 JSON。由插件 Host 侧调用。"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mathtex  # noqa: E402



def _norm_bg(bg):
    """背景归一化：transparent/none/空 -> None（透明）；white -> #ffffff；其余按颜色传给 matplotlib。"""
    if bg is None:
        return None
    b = str(bg).strip().lower()
    if b in ("", "none", "transparent", "alpha"):
        return None
    if b == "white":
        return "#ffffff"
    return str(bg)


def main(job_path):
    with open(job_path, encoding="utf-8-sig") as f:
        job = json.load(f)
    style = job.get("style") or {}
    results = []
    for item in job.get("items") or []:
        rec = {"tex": item.get("tex", ""), "out": item.get("out"), "error": None}
        try:
            info = mathtex.render(
                item["tex"], item["out"],
                fontsize=float(style.get("fontsize", 26)),
                dpi=int(style.get("dpi", 300)),
                color=style.get("color", "#111111"),
                bg=_norm_bg(style.get("bg")),
                pad=float(style.get("pad", 8)),
                cjk_font=style.get("cjkFont") or None,
                fontset=style.get("fontset", "cm"),
            )
            rec["size_px"] = list(info["size_px"])
        except Exception as e:  # 单条失败不影响其他条
            msg = str(e).strip().splitlines()
            rec["error"] = (next((l for l in msg if "Parse" in l), msg[0] if msg else type(e).__name__)).strip()
            if rec["error"] == "":
                rec["error"] = "%s: 结构不受支持" % type(e).__name__
        results.append(rec)
    return {"ok": all(r["error"] is None for r in results), "results": results}


if __name__ == "__main__":
    job_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(job_path)[0] + ".result.json"
    try:
        payload = main(job_path)
    except Exception:
        payload = {"ok": False, "fatal": traceback.format_exc()[-1500:], "results": []}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
