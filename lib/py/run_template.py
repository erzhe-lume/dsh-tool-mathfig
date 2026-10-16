# -*- coding: utf-8 -*-
"""跑一个绘图模板：读 JSON 作业文件 → 出图 → 写回结果 JSON。由插件 Host 侧调用。"""
import importlib.util
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(HERE, "templates")
sys.path.insert(0, TPL_DIR)


def load_template(name):
    path = os.path.join(TPL_DIR, name + ".py")
    if not os.path.exists(path):
        raise FileNotFoundError("没有这个模板：%s（可用：%s）" % (name, list_templates()))
    spec = importlib.util.spec_from_file_location("tpl_" + str(abs(hash(name))), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def list_templates():
    if not os.path.isdir(TPL_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(TPL_DIR)
                  if f.endswith(".py") and not f.startswith("_") and f != "common.py")


def main(job):
    name = job["template"]
    out_dir = job.get("outDir") or HERE
    os.makedirs(out_dir, exist_ok=True)
    mod = load_template(name)
    print("模板 %s：%s" % (name, (mod.__doc__ or "").strip().splitlines()[0]))
    res = mod.render(job.get("params") or {}, out_dir)
    return {"ok": True, "template": name, "outputs": res.get("outputs", []),
            "notes": res.get("notes", []), "templates": list_templates()}


if __name__ == "__main__":
    job_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(job_path)[0] + ".result.json"
    try:
        with open(job_path, encoding="utf-8-sig") as f:
            payload = main(json.load(f))
    except Exception:
        payload = {"ok": False, "fatal": traceback.format_exc()[-1500:], "outputs": []}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
