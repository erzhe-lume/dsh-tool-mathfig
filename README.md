# dsh-tool-mathfig

[![npm version](https://img.shields.io/npm/v/dsh-tool-mathfig)](https://www.npmjs.com/package/dsh-tool-mathfig) [![license](https://img.shields.io/npm/l/dsh-tool-mathfig)](https://github.com/erzhe-lume/dsh-tool-mathfig/blob/main/LICENSE) [![DeepSeek Harness](https://img.shields.io/badge/DSH-0.1.0--rc.6%20%7C%200.2.x-4c8fd6)](https://github.com/deepseek-ai)

**公式与数学插图工具** —— 给 [DeepSeek Harness](https://github.com/deepseek-ai) 的 Cordis 插件。

LaTeX 公式转 PNG（离线，不需要 LaTeX 发行版 / 浏览器 / 联网）、参数化几何与曲面模板、以及每次出图的数值自校验。

> Formula & math-figure tools for DeepSeek Harness: LaTeX → PNG (fully offline), parameterised geometry templates, numeric self-check.

![演示](https://raw.githubusercontent.com/erzhe-lume/dsh-tool-mathfig/main/docs/demo.png)

<sub>上：`figure_formula` 渲染的公式（含 cases 分段、vmatrix 行列式、underbrace 中文标注）。下：`figure_template` 的「球缺与球冠」模板。</sub>

---

## 功能

### 1. `figure_formula` —— 公式转图片

离线把 LaTeX 渲染成 PNG，默认透明背景，可直接贴进 PPT / Word / 笔记。

| 能力 | 说明 |
|:--|:--|
| 原生数学排版 | 分式、根式、积分、求和、极限、上下标、希腊字母、`\left(...\right)` |
| **分段函数 / 方程组** | `\begin{cases} … \end{cases}`，支持 `\\[8pt]` 行距与中文条件 |
| **矩阵 / 行列式** | `pmatrix`、`bmatrix`、`Bmatrix`、`vmatrix`、`matrix`，括号按内容高度现画 |
| **多行对齐** | `aligned`、`gathered`、`align*`，按 `&` 对齐 |
| **花括号标注** | `\underbrace{X}_{说明}`、`\overbrace` |
| **方框与等号上写字** | `\boxed{…}`、`\xlongequal{定义}`、`\overset`、`\xrightarrow` |
| **公式里的中文** | `n\text{ 为奇数}`，甚至裸写中文；自动用系统中文字体并按基线对齐 |
| **自动改写** | `\displaystyle`、`\limits`、`\bigl\Bigl`、`\lvert\rVert`、`\le\ge\lt\tfrac`、`\frac1n`、`\dfrac\pi2`、`\mathbf a`、`\tag{1}` 等写法 |

参数：`tex`（必填）、`savePath`、`fontsize`、`dpi`、`color`、`bg`、`pad`、`cjkFont`、`fontset`、`returnImage`。

### 2. `figure_template` —— 参数化数学插图

出图的同时回**数值解**（网格积分算出的体积 / 面积 / 积分值），先验算再交付。

| 模板 | 画什么 | 主要参数 |
|:--|:--|:--|
| `一元函数与面积` | 两曲线所夹区域、交点、面积标注 | `F, G, A, B, markX, shade, out` |
| `二重积分区域` | 积分区域 + 被积函数高度场 | `region, integrand, xmin..ymax, mark, out` |
| `曲面与切平面体积` | 两曲面所围立体（子午切片）+ 截面 + 高度场 | `up, down, xmin..ymax, views, nslices, mark` |
| `球缺与球冠` | 球缺截面（R、h、r、球心）+ 立体 | `R, h, views, labels` |

表达式用字符串写，变量为 `x` / `y`，例如 `up="2*x-2*y-1"`、`down="x**2+y**2"`。
`曲面与切平面体积` 会按 `views` 里每个候选视角各出一张（如 `views=[[18,-88],[26,-66]]`），挑最清楚的那张交付。

### 3. `figure_selftest` —— 链路体检

一条命令分清「Python 解释器问题 / 引擎问题 / 公式写法问题」：报告解释器、引擎路径、模板清单、
**当前 host 的包版本**（`@deepseek-ai/dsh-tools` / `schemastery` / `cordis`）与声明范围是否匹配，并真渲染一条含中文的 `cases` 公式。

### 画不了什么

`tabular` 之类表格环境；把 `cases` 塞进 `\frac` 参数里的深度嵌套。遇到会在返回值里明确报错并给出出错片段，不会静默画错。

---

## 安装

装进 DSH 的 profile（以 Windows 桌面版为例）：

```powershell
# 1) profile 的 package.json 加 link 依赖与 bundle
#    ~/.dsh/profiles/<profile>/package.json
#    "dependencies": { "dsh-tool-mathfig": "link:D:/DeepSeek/mathfig-plugin/dsh-tool-mathfig" }
#    "dsh": { "profile": { "bundles": [ ..., "dsh-tool-mathfig" ] } }

# 2) 在 profile 目录用 DSH 自带的 Node + pnpm 安装（离线即可，link 不需要下载）
cd ~/.dsh/profiles/<profile>
& "<DSH>/runtime/node/bin/node.exe" "<DSH>/runtime/pnpm/bin/pnpm.mjs" install --offline
```

两个坑：

- **必须用 DSH 自带的 Node 与 pnpm**（本机 Node 20 + 自带 pnpm 会报 `ERR_UNKNOWN_BUILTIN_MODULE`）。
- 装完是 `node_modules/dsh-tool-mathfig` 指向本目录的链接，**重启 DSH** 后在设置 → 插件里可见。

配置项写在 `cordis.patch.yml`（`pythonPath`、`outputDir`、`defaultDpi`、`defaultFontsize`、`timeoutMs`），
也可以在 profile 的 `cordis.patch.yml` 里按 `id: tool-mathfig` 覆盖。

## 版本兼容

插件按发行线声明 `peerDependencies`，**必须覆盖你正在运行的 DSH 版本**：

| host | 声明 |
|:--|:--|
| `@deepseek-ai/dsh 0.1.0-rc.6` | `"@deepseek-ai/dsh-tools": "^0.1.0-rc.6 \|\| ^0.2.0-rc.1"` |
| `@deepseek-ai/dsh 0.2.0-rc.2` | 同上（并集覆盖两条线） |
| `@deepseek-ai/dsh 0.2.1-rc.2` | 同上（`^0.2.0-rc.1` 上界 `<0.3.0`，自动覆盖 0.2.x 后续版本） |

注意 `^0.1.0-rc.6` 的上界是 `<0.2.0`——**只写这一条，host 升到 0.2.x 后会被版本闸门拒绝加载**，
所以要用 `||` 并列多条发行线。`cordis`（4.x）与 `schemastery`（3.x）不在 DSH 的 0.x 锁步线上，写 `^4.0.1` / `^3.18.1` 即可。

本插件**不声明** `engines.dsh`：本地 `link:` 安装不读它，写了写错反而把自己挡在门外。

## 依赖

- **Python ≥ 3.12 + matplotlib**（默认 `C:\Python314\python.exe`，可在 `cordis.patch.yml` 改）。
  模板额外用到 `scipy`（数值积分）。
- Node ≥ 20（由 DSH 提供）。

## 目录结构

```
dsh-tool-mathfig/
├── package.json          插件清单（dsh.bundle.patch、peerDependencies）
├── cordis.patch.yml      组合包补丁：insert 本插件 + 默认配置
├── lib/
│   ├── index.js          Host 插件：三个工具的定义与注册
│   └── py/               Python 侧
│       ├── mathtex.py            公式排版引擎（盒子模型 / 环境补齐 / CJK 基线对齐）
│       ├── render_formula.py     JSON 作业 → PNG → 结果 JSON
│       ├── run_template.py       模板分发
│       └── templates/            common.py + 四个模板
├── docs/                 演示图与其生成脚本
└── smoke.mjs             冒烟测试：假 ctx 直接调三个工具，不需要启动 DSH
```

## 开发

```powershell
node smoke.mjs
```

覆盖：模块导出 → 工具注册 → 公式渲染（含 `cases` + 中文）→ 模板渲染与数值自校验 → 体检 → 故意送一条画不出来的公式（验证报错路径）。

## License

MIT
