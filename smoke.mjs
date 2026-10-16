// 冒烟测试：不启动 DSH，直接用假 ctx 调用插件注册的三个工具。
// 用法： node smoke.mjs   （需要 NODE_PATH 指向 profile 的 node_modules）
const PLUGIN = "file:///D:/DeepSeek/mathfig-plugin/dsh-tool-mathfig/lib/index.js";
const os = await import("node:os");
const path = await import("node:path");

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
