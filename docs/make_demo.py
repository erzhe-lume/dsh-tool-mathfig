# -*- coding: utf-8 -*-
"""生成 README 用的演示图：上面是公式渲染，下面是模板出图。图本身由插件自己的 Python 侧产出。"""
import io
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

PLUGIN = r"D:\DeepSeek\mathfig-plugin\dsh-tool-mathfig"
PY = r"C:\Python314\python.exe"
DOCS = os.path.join(PLUGIN, "docs")
TMP = tempfile.mkdtemp(prefix="mathfig-demo-")
os.makedirs(DOCS, exist_ok=True)

# ---------------------------------------------------------------- 1) 公式
FORMULAS = [
    r"\int_0^{\pi/2}\sin^nx\,dx=\begin{cases}\dfrac{(n-1)!!}{n!!}, & n\text{ 为奇数},\\[8pt]"
    r"\dfrac{(n-1)!!}{n!!}\cdot\dfrac\pi2, & n\text{ 为偶数}.\end{cases}",
    r"\oint_{L}P\,dx+Q\,dy+R\,dz=\iint_{\Sigma}"
    r"\begin{vmatrix}dy\,dz & dz\,dx & dx\,dy\\[2pt] \dfrac{\partial}{\partial x} & \dfrac{\partial}{\partial y}"
    r" & \dfrac{\partial}{\partial z}\\[2pt] P & Q & R\end{vmatrix}",
    r"y=\underbrace{Y(x)}_{\text{齐次通解}}+\underbrace{y^{*}(x)}_{\text{一个特解}},"
    r"\qquad \lim_{x\to0}\dfrac{\displaystyle\int_{0}^{x}f(u)\,\mathrm{d}u}{x^{2}}=\dfrac{A}{2}",
]
job = {"style": {"fontsize": 26, "dpi": 300, "bg": "white", "pad": 10},
       "items": [{"tex": t, "out": os.path.join(TMP, "f%d.png" % i)} for i, t in enumerate(FORMULAS)]}
job_path = os.path.join(TMP, "job.json")
res_path = os.path.join(TMP, "res.json")
io.open(job_path, "w", encoding="utf-8").write(json.dumps(job, ensure_ascii=False))
subprocess.run([PY, os.path.join(PLUGIN, "lib", "py", "render_formula.py"), job_path, res_path], check=True)
res = json.loads(io.open(res_path, encoding="utf-8-sig").read())
assert res["ok"], res
print("公式 %d 条渲染完成" % len(res["results"]))

# ---------------------------------------------------------------- 2) 模板
tpl_job = {"template": "球缺与球冠", "outDir": TMP, "params": {"R": 1.0, "h": 0.55, "views": [[18, -60]]}}
tpl_path = os.path.join(TMP, "tpl.json")
tpl_res = os.path.join(TMP, "tplres.json")
io.open(tpl_path, "w", encoding="utf-8").write(json.dumps(tpl_job, ensure_ascii=False))
subprocess.run([PY, os.path.join(PLUGIN, "lib", "py", "run_template.py"), tpl_path, tpl_res], check=True)
tres = json.loads(io.open(tpl_res, encoding="utf-8-sig").read())
assert tres["ok"], tres
print("模板出图:", tres["outputs"][0])

# ---------------------------------------------------------------- 3) 拼图
def load(path, bg="white"):
    im = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", im.size, (255, 255, 255, 255) if bg == "white" else (0, 0, 0, 0))
    base.alpha_composite(im)
    return base.convert("RGB")


formula_imgs = [load(r["out"]) for r in res["results"]]
W = max(i.width for i in formula_imgs) + 60
H = sum(i.height for i in formula_imgs) + 18 * (len(formula_imgs) + 1)
card = Image.new("RGB", (W, H), (255, 255, 255))
y = 18
for im in formula_imgs:
    card.paste(im, (30, y))
    y += im.height + 18

tpl_img = load(tres["outputs"][0])
scale = min(1.0, card.width / tpl_img.width)
tpl_img = tpl_img.resize((int(tpl_img.width * scale), int(tpl_img.height * scale)), Image.LANCZOS)

total_w = max(card.width, tpl_img.width) + 40
total_h = card.height + tpl_img.height + 60
sheet = Image.new("RGB", (total_w, total_h), (250, 250, 252))
sheet.paste(card, ((total_w - card.width) // 2, 20))
sheet.paste(tpl_img, ((total_w - tpl_img.width) // 2, card.height + 40))
out = os.path.join(DOCS, "demo.png")
sheet.save(out, optimize=True)
print("演示图:", out, sheet.size, "%.0f KB" % (os.path.getsize(out) / 1024))
