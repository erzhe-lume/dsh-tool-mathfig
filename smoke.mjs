// 冒烟测试：不启动 DSH，直接用假 ctx 调用插件注册的三个工具。
// 用法： node smoke.mjs   （需要 NODE_PATH 指向 profile 的 node_modules）
const PLUGIN = "file:///D:/DeepSeek/mathfig-plugin/dsh-tool-mathfig/lib/index.js";
const os = await import("node:os");
const path = await import("node:path");


// ---- DSH 只接受无损 JSON 的工具返回值：这里逐字复刻 host 的 visitJsonValue 规则，
// ---- 任何嵌套 undefined / -0 / NaN / 非 Object.prototype 原型都会让整个调用失败。
function visitJsonValue(value, ancestors = new Set()) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value) && !Object.is(value, -0);
  if (typeof value !== "object") return false;
  if (ancestors.has(value)) return false;
  ancestors.add(value);
  if (Array.isArray(value)) {
    if (Object.getPrototypeOf(value) !== Array.prototype) return false;
    for (let i = 0; i < value.length; i++)
      if (!Object.hasOwn(value, i) || !visitJsonValue(value[i], ancestors)) return false;
    return true;
  }
  const proto = Object.getPrototypeOf(value);
  if (proto !== Object.prototype && proto !== null) return false;
  for (const k of Reflect.ownKeys(value)) {
    if (typeof k !== "string") return false;
    if (!Object.prototype.propertyIsEnumerable.call(value, k)) return false;
    if (!visitJsonValue(value[k], ancestors)) return false;
  }
  return true;
}

const mod = await import(PLUGIN);
console.log("模块导出:", Object.keys(mod).join(", "));

const tools = [];
const ctx = {
  get: (n) =>
    n === "attachments"
      ? {
          saveImage: async (a) => ({
            attachmentId: "att-smoke",
            mediaType: a.mediaType,
            bytes: a.data.length,
            width: 320,
            height: 120,
          }),
        }
      : undefined,
  tools: { register: (t) => tools.push(t) },
};

mod.apply(ctx, { pythonPath: "C:\\Python314\\python.exe", defaultDpi: 150, defaultFontsize: 24 });
console.log("注册工具:", tools.map((t) => t.name).join(", "));

const by = Object.fromEntries(tools.map((t) => [t.name, t]));
const tmp = path.join(os.tmpdir(), "mathfig_smoke");
(await import("node:fs")).mkdirSync(tmp, { recursive: true });

// 1) 公式（含 cases + 中文，最容易挂的组合）
const r1 = await by.figure_formula.execute({
  tex: "f(x)=\\begin{cases}x^{2},&x>0\\\\ 0,&x\\le0\\end{cases},\\qquad \\int_0^{1}x\\,\\mathrm{d}x=\\frac12",
  savePath: path.join(tmp, "formula.png"),
});
console.log("\n[figure_formula] ok=" + r1.ok + " image=" + !!r1.image);
console.log(r1.report);

// 2) 模板：曲面与切平面体积（默认参数就是 π/2 那道题）
const r2 = await by.figure_template.execute({
  template: "曲面与切平面体积",
  params: { views: [[26, -66]] },
  outDir: tmp,
  returnImage: false,
});
console.log("\n[figure_template] ok=" + r2.ok + " outputs=" + r2.outputs.length);
console.log(r2.report);

// 3) 体检
const r3 = await by.figure_selftest.execute({});
console.log("\n[figure_selftest] ok=" + r3.ok);
console.log(r3.report);

// 4) 故意送一条画不出来的，确认报错路径也正常
const r4 = await by.figure_formula.execute({ tex: "\\begin{tabular}{cc}a&b\\end{tabular}" });
console.log("\n[错误路径] ok=" + r4.ok);
console.log(r4.report.split("\n").slice(0, 3).join("\n"));

// ---- 无损 JSON 回归：任何一次工具返回都必须能被 host 接受
const _checked = [];
function audit(name, value) {
  const ok = visitJsonValue(value);
  _checked.push(name + "=" + (ok ? "ok" : "FAIL"));
  if (!ok) { console.error("✗ " + name + " 的返回值不是无损 JSON（DSH 会拒绝整次调用）"); process.exitCode = 1; }
}
audit("figure_formula", r1);
audit("figure_template", r2);
audit("figure_selftest", r3);
audit("figure_formula(错误路径)", r4);
console.log("无损 JSON 检查: " + _checked.join("  "));
