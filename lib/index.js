/**
 * dsh-tool-mathfig —— 公式与数学插图工具（DSH Host 插件）
 *
 * 版本适配：@deepseek-ai/dsh 0.1.0-rc.6
 *   · 骨架与同机可用的 dsh-tool-diagram 完全一致：name / inject / Config / apply(ctx, config)
 *   · 工具用 @deepseek-ai/dsh-tools 的 defineTool 定义，经 ctx.tools.register 注册
 *   · 图片经 ctx.get("attachments").saveImage 作为附件内联返回
 *   · 刻意不写 enginesDsh（本地 link 安装不读它；写了反而容易把自己挡在门外）
 *
 * 工具：
 *   figure_formula   LaTeX 公式 → PNG（离线，不需要 LaTeX / 浏览器）
 *   figure_template  参数化几何/曲面模板 → PNG（带数值自校验）
 *   figure_selftest  体检：Python 引擎、模板清单、版本约束
 */
import z from "@deepseek-ai/schemastery";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const name = "tool-mathfig";
export const inject = ["tools"];

export const Config = z.object({
  /** 带 matplotlib 的 Python 解释器 */
  pythonPath: z.string().default("C:\\Python314\\python.exe"),
  /** 额外的落盘目录；不填则图只作为附件返回 */
  outputDir: z.string(),
  defaultDpi: z.number().default(300),
  defaultFontsize: z.number().default(26),
  timeoutMs: z.number().default(240000),
});

const HERE = dirname(fileURLToPath(import.meta.url));
const PY_DIR = join(HERE, "py");
const RENDER_FORMULA = join(PY_DIR, "render_formula.py");
const RUN_TEMPLATE = join(PY_DIR, "run_template.py");
const TEMPLATES = ["一元函数与面积", "二重积分区域", "曲面与切平面体积", "球缺与球冠"];

/** 读取 host（DSH 应用）提供的包版本，用于体检；解析不到就记 null，不抛错。 */
function hostVersions() {
  const req = createRequire(import.meta.url);
  const out = {};
  for (const name of ["@deepseek-ai/dsh-tools", "@deepseek-ai/schemastery",
                      "@deepseek-ai/cordis", "@deepseek-ai/dsh-attachment"]) {
    try {
      out[name] = JSON.parse(readFileSync(req.resolve(name + "/package.json"), "utf8")).version;
    } catch {
      out[name] = null;
    }
  }
  return out;
}

/** 声明覆盖的 dsh-tools 发行线：0.1.x 与 0.2.x。 */
const DECLARED_LINES = ["0.1", "0.2"];

export function apply(ctx, config) {
  const cfg = {
    pythonPath: config?.pythonPath || "C:\\Python314\\python.exe",
    outputDir: config?.outputDir || "",
    defaultDpi: config?.defaultDpi ?? 300,
    defaultFontsize: config?.defaultFontsize ?? 26,
    timeoutMs: config?.timeoutMs ?? 240000,
  };

  // 说明：image 是可选属性，所以这里不能写 required: true（DSH 用属性 schema 根部的
  // required 标记「该属性必填」）。mediaType 也不能钉死成 image/png——附件服务会把图
  // 规范化后重新编码（见 attachment-local 的 prepareImageFile），返回的媒体类型以服务为准。
  const imageSchema = {
    type: "object",
    additionalProperties: false,
    properties: {
      attachmentId: { type: "string", required: true },
      mediaType: { type: "string", required: true },
      bytes: { type: "integer", required: true },
      width: { type: "integer", required: true },
      height: { type: "integer", required: true },
    },
  };

  const renderOut = (_args, v) => {
    const blocks = [{ type: "text", text: v.report }];
    if (v.image) {
      blocks.push({
        type: "image",
        attachment: {
          attachmentId: v.image.attachmentId,
          mediaType: v.image.mediaType,
          bytes: v.image.bytes,
          width: v.image.width,
          height: v.image.height,
        },
      });
    }
    return blocks;
  };

  /** 跑一个 Python 脚本：作业 JSON 进，结果 JSON 出（结果走文件，避免和 matplotlib 的 warning 抢 stdout）。 */
  function runPy(script, job) {
    const dir = mkdtempSync(join(tmpdir(), "mathfig-"));
    const jobPath = join(dir, "job.json");
    const resPath = join(dir, "result.json");
    writeFileSync(jobPath, JSON.stringify(job), "utf8");
    return new Promise((done) => {
      execFile(
        cfg.pythonPath,
        [script, jobPath, resPath],
        { timeout: cfg.timeoutMs, windowsHide: true, maxBuffer: 32 * 1024 * 1024 },
        (err, _stdout, stderr) => {
          if (!existsSync(resPath)) {
            done({
              fatal:
                "Python 侧没有产出结果文件。\n" +
                "解释器：" + cfg.pythonPath + "\n" +
                "脚本：" + script + "\n" +
                (err ? "错误：" + String(err.message).slice(0, 400) + "\n" : "") +
                (stderr ? "stderr：" + String(stderr).slice(-800) : ""),
            });
            return;
          }
          try {
            const raw = readFileSync(resPath, "utf8").replace(/^\uFEFF/, "");   // 容忍 BOM
            done({ result: JSON.parse(raw) });
          } catch (e) {
            done({ fatal: "结果 JSON 解析失败：" + String(e).slice(0, 300) });
          }
        },
      );
    });
  }

  /**
   * DSH 只接受「无损 JSON」的工具返回值（见 host 的 visitJsonValue）：
   * 嵌套 undefined、-0、NaN、Infinity，以及原型不是 Object.prototype 的对象
   * （例如附件服务返回的 branded String）都会被判为非法，整个工具调用直接失败。
   * 统一走一遍 JSON 往返，把这些形态规整成纯 JSON 值。
   */
  const lossless = (value) => JSON.parse(JSON.stringify(value));

  /** 把 PNG 存成附件，供内联显示；没有附件服务时降级为提示。 */
  async function attach(pngPath, note) {
    if (!pngPath || !existsSync(pngPath)) return lossless({ image: undefined, note });
    const attachments = ctx.get("attachments");
    if (!attachments) {
      return lossless({ image: undefined, note: note + "\n（当前没有挂载附件服务，图未内联返回；可用 savePath 落盘后再 read_image）" });
    }
    try {
      const ref = await attachments.saveImage({
        data: readFileSync(pngPath),
        mediaType: "image/png",
        name: pngPath.split(/[\\/]/).pop(),
      });
      return lossless({
        image: {
          attachmentId: ref.attachmentId,
          mediaType: ref.mediaType,
          bytes: ref.bytes,
          width: ref.width,
          height: ref.height,
        },
        note,
      });
    } catch (e) {
      return lossless({ image: undefined, note: note + "\n（附件写入失败：" + String(e).slice(0, 200) + "）" });
    }
  }

  function outPath(savePath, fallbackName) {
    if (savePath) {
      mkdirSync(dirname(savePath), { recursive: true });
      return savePath;
    }
    const dir = cfg.outputDir || mkdtempSync(join(tmpdir(), "mathfig-out-"));
    mkdirSync(dir, { recursive: true });
    return join(dir, fallbackName);
  }

  const outSchemaBase = {
    type: "object",
    additionalProperties: false,
    properties: {
      ok: { type: "boolean", required: true },
      report: { type: "string", required: true, description: "人可读的结果说明（含数值自校验）" },
      savedPath: { type: "string" },
      image: imageSchema,
    },
  };

  // ------------------------------------------------------------------ 公式
  ctx.tools.register(defineTool({
    name: "figure_formula",
    description:
      "把 LaTeX 数学公式渲染成 PNG（离线：不需要 LaTeX 发行版、不需要浏览器、不需要联网）。\n" +
      "支持 mathtext 原生结构，并补齐了它没有的：cases 分段、pmatrix/vmatrix 等矩阵、aligned 多行对齐、\n" +
      "underbrace/overbrace 花括号标注、boxed、xlongequal、公式里的中文（\\text{中文}），\n" +
      "以及 \\displaystyle \\limits \\bigl \\lvert \\le \\tfrac \\frac1n 这类写法的自动改写。\n" +
      "默认透明背景，可直接贴进 PPT/Word；要白底传 bg=\"white\"。",
    parameters: {
      tex: { type: "string", required: true, description: "LaTeX 公式（可带或不带 $ 定界符）" },
      savePath: { type: "string", description: "落盘路径（.png）。不填则只作为附件返回" },
      fontsize: { type: "number", description: "字号 pt，默认取插件配置（26）" },
      dpi: { type: "integer", description: "分辨率，默认取插件配置（300）" },
      color: { type: "string", description: "文字颜色，默认 #111111" },
      bg: { type: "string", description: "背景：transparent（默认）/ white / #RRGGBB" },
      pad: { type: "number", description: "四周留白 pt，默认 8" },
      cjkFont: { type: "string", description: "公式内中文字体链，默认 SimSun,Microsoft YaHei" },
      fontset: { type: "string", description: "数学字体：cm（默认，LaTeX 观感）/ stix / dejavusans" },
      returnImage: { type: "boolean", description: "是否内联返回图片，默认 true" },
    },
    output: { schema: outSchemaBase, render: renderOut },
    async execute(args) {
      const out = outPath(args.savePath, "formula.png");
      const { result, fatal } = await runPy(RENDER_FORMULA, {
        style: {
          fontsize: args.fontsize ?? cfg.defaultFontsize,
          dpi: args.dpi ?? cfg.defaultDpi,
          color: args.color ?? "#111111",
          bg: args.bg ?? "transparent",
          pad: args.pad ?? 8,
          cjkFont: args.cjkFont ?? "",
          fontset: args.fontset ?? "cm",
        },
        items: [{ tex: args.tex, out }],
      });
      if (fatal) return lossless({ ok: false, report: "渲染失败：\n" + fatal });
      const rec = (result.results || [])[0] || {};
      if (rec.error) {
        return lossless({
          ok: false,
          report:
            "公式没渲染出来（不是整条报错就一定是我改写得不够，可把出错片段发我）：\n  " + rec.error +
            "\n提示：矩阵/分段/中文都可以；表格环境 tabular 与把 cases 塞进 \\frac 参数里这类深度嵌套不支持。",
        });
      }
      const size = rec.size_px ? rec.size_px.join("×") + " px" : "?";
      const sent = args.returnImage === false
        ? { image: undefined, note: "" }
        : await attach(out, "");
      const lines = [
        "公式已渲染：" + size + "（dpi=" + (args.dpi ?? cfg.defaultDpi) + "）",
        "落盘：" + out,
        sent.note,
      ].filter(Boolean);
      return lossless({ ok: true, report: lines.join("\n"), savedPath: out, image: sent.image });
    },
  }));

  // ------------------------------------------------------------------ 模板
  ctx.tools.register(defineTool({
    name: "figure_template",
    description:
      "用参数化模板画数学插图，并返回数值自校验（体积/面积/积分值的网格数值解），出图前先验算。\n" +
      "可用模板：\n" +
      "  一元函数与面积      两曲线所夹区域：{F,G,A,B,markX,markText,title,shade,out}\n" +
      "  二重积分区域        {region,integrand,xmin,xmax,ymin,ymax,mark,title,out}（表达式字符串，如 \"1-(x-1)**2-(y+1)**2\"）\n" +
      "  曲面与切平面体积    {up,down,xmin,xmax,ymin,ymax,views,nslices,upName,downName,mark,outPrefix}\n" +
      "  球缺与球冠          {R,h,views,labels,outPrefix}（只画几何：球半径 R、球缺高 h、底面半径 r、球心 O）\n" +
      "约定：曲面模板会按 views 里每个候选视角各出一张（规范要求先出候选、挑最清楚的那张交付）。",
    parameters: {
      template: { type: "string", required: true, enum: TEMPLATES, description: "模板名" },
      params: {
        type: "object",
        additionalProperties: true,
        description: "模板参数（表达式写成字符串，变量用 x / y）。不填则用模板自带默认参数",
      },
      outDir: { type: "string", description: "输出目录；不填则用插件配置的 outputDir 或临时目录" },
      returnImage: { type: "boolean", description: "是否内联返回第一张图，默认 true" },
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean", required: true },
          report: { type: "string", required: true },
          outputs: { type: "array", required: true, items: { type: "string" } },
          image: imageSchema,
        },
      },
      render: renderOut,
    },
    async execute(args) {
      const dir = args.outDir
        ? (mkdirSync(args.outDir, { recursive: true }), args.outDir)
        : (cfg.outputDir || mkdtempSync(join(tmpdir(), "mathfig-tpl-")));
      const { result, fatal } = await runPy(RUN_TEMPLATE, {
        template: args.template,
        outDir: dir,
        params: args.params || {},
      });
      if (fatal) return lossless({ ok: false, report: "模板执行失败：\n" + fatal, outputs: [] });
      if (!result.ok) {
        return lossless({ ok: false, report: "模板内部报错：\n" + String(result.fatal || "").slice(-1200), outputs: [] });
      }
      const outs = result.outputs || [];
      const sent = args.returnImage === false || outs.length === 0
        ? { image: undefined, note: "" }
        : await attach(outs[0], outs.length > 1 ? "（另有 " + (outs.length - 1) + " 张候选视角图，见 outputs）" : "");
      const report = [
        "模板：" + result.template,
        "出图 " + outs.length + " 张：",
        ...outs.map((p) => "  " + p),
        "数值自校验与提示：",
        ...(result.notes || []).map((n) => "  · " + n),
        sent.note,
      ].filter(Boolean).join("\n");
      return lossless({ ok: true, report, outputs: outs, image: sent.image });
    },
  }));

  // ------------------------------------------------------------------ 体检
  ctx.tools.register(defineTool({
    name: "figure_selftest",
    description:
      "绘图链路体检：Python 解释器是否可用、公式引擎能否出图、模板清单、以及本插件的版本约束。\n" +
      "画图报错时先跑它，能直接区分「解释器问题」「引擎问题」「公式写法问题」。",
    parameters: {
      returnImage: { type: "boolean", description: "是否把体检用的测试图也返回，默认 false" },
    },
    output: { schema: outSchemaBase, render: renderOut },
    async execute(args) {
      const lines = [];
      lines.push("插件：dsh-tool-mathfig（Host）");
      lines.push("Python： " + cfg.pythonPath + (existsSync(cfg.pythonPath) ? "（存在）" : "（不存在！改 cordis.patch.yml 的 pythonPath）"));
      lines.push("引擎： " + RENDER_FORMULA + (existsSync(RENDER_FORMULA) ? "（存在）" : "（缺失）"));
      lines.push("模板： " + TEMPLATES.join("、") + "（目录 " + join(PY_DIR, "templates") + "）");
      const host = hostVersions();
      lines.push("声明：@deepseek-ai/dsh-tools ^0.1.0-rc.6 || ^0.2.0-rc.1（覆盖 " + DECLARED_LINES.join(".x 与 ") + ".x 两条发行线）");
      lines.push("host 实测：" + Object.entries(host)
        .map(([k, v]) => k.replace("@deepseek-ai/", "") + " " + (v ?? "读取失败")).join("、"));
      const dt = host["@deepseek-ai/dsh-tools"];
      if (dt && !DECLARED_LINES.some((l) => dt.startsWith(l + "."))) {
        lines.push("⚠️ host 的 dsh-tools 是 " + dt + "，不在声明范围内 —— 版本闸门会拒绝加载；"
          + "请把 ^" + dt.split(".").slice(0, 2).join(".") + ".0-rc.1 补进 peerDependencies");
      }
      const out = outPath(undefined, "selftest.png");
      const { result, fatal } = await runPy(RENDER_FORMULA, {
        style: { fontsize: cfg.defaultFontsize, dpi: 150, bg: "white" },
        items: [{ tex: "f(x)=\\begin{cases}x^{2},&x>0\\\\ 0,&x\\le0\\end{cases},\\qquad \\int_0^{1}x\\,\\mathrm{d}x=\\frac12", out }],
      });
      let ok = false;
      if (fatal) {
        lines.push("渲染测试：失败");
        lines.push(fatal);
      } else {
        const rec = (result.results || [])[0] || {};
        ok = !rec.error;
        lines.push(ok ? "渲染测试：成功（" + (rec.size_px || []).join("×") + " px）" : "渲染测试：失败\n  " + rec.error);
      }
      const sent = ok && args.returnImage ? await attach(out, "") : { image: undefined, note: "" };
      return lossless({ ok, report: lines.join("\n") + (sent.note ? "\n" + sent.note : ""), savedPath: ok ? out : undefined, image: sent.image });
    },
  }));
}
