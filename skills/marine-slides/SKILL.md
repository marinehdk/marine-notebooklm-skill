---
name: marine-slides
description: 将内容转换为专业幻灯片，支持 PDF（图片形式）或 PPTX（可编辑文字）。当用户要求"创建幻灯片"、"制作 PPT"、"生成 deck"、"PPT"、"可编辑 PPT"或"带可编辑文字的幻灯片"时使用。
version: 1.0.0
metadata:
  openclaw:
    homepage: https://github.com/marine-2026/marine-notebooklm-skill
    requires:
      anyBins:
        - bun
        - npx
---

# marine-slides

将内容转换为专业幻灯片，支持两种输出模式：
- **PDF**（默认）：图片式幻灯片，与 baoyu-slide-deck 行为一致
- **PPTX**：基于 PptxGenJS 的可编辑文字版幻灯片

## 使用方式

```bash
/marine-slides path/to/content.md
/marine-slides path/to/content.md --format pptx
/marine-slides path/to/content.md --pdf path/to/file.pdf
/marine-slides path/to/content.md --style sketch-notes --format both
/marine-slides path/to/content.md --skip-review
/marine-slides  # 然后粘贴内容
```

## 脚本目录

**Agent 执行说明**：
1. 确定此 SKILL.md 文件所在目录为 `{baseDir}`
2. 脚本路径 = `{baseDir}/scripts/<script-name>.ts`
3. 解析 `${BUN_X}` 运行时：已安装 bun → `bun`；可用 npx → `npx -y bun`；否则提示安装 bun

| 脚本 | 用途 |
|------|------|
| `scripts/build-editable-pptx.ts` | 从 outline.md 构建可编辑 PPTX |
| `scripts/merge-to-pdf.ts` | 合并幻灯片图片为 PDF |
| `scripts/extract-pdf-text.ts` | 从 PDF 提取文本内容 |

## 选项

| 选项 | 说明 |
|------|------|
| `--input <file>` | 本地 .md / .txt 文件作为内容输入 |
| `--pdf <file>` | PDF 文件作为内容输入（通过 pdf-parse 提取文本） |
| `--format pdf\|pptx\|both` | 输出格式。默认：pdf |
| `--style <name>` | 视觉风格：preset 名称（见风格系统） |
| `--audience <type>` | 目标受众：beginners, intermediate, experts, executives, **general（默认）** |
| `--lang <code>` | 输出语言：**zh（默认）**，en, ja 等 |
| `--slides <number>` | 目标页数（建议 8-25，最大 30） |
| `--outline-only` | 仅生成 outline，跳过图片/文字生成 |
| `--prompts-only` | 仅生成 outline + prompts，跳过图片 |
| `--images-only` | 从现有 prompts 目录生成图片（仅 PDF 模式） |
| `--build-pptx` | 从现有 outline 构建 PPTX（PPTX 模式） |
| `--regenerate <N>` | 重新生成指定页 |
| `--skip-review` | 跳过大纲和 prompts 的确认步骤 |

## 风格系统

### Preset 风格（17种）

| Preset | 维度 | 最适合 |
|--------|------|--------|
| `blueprint`（默认）| grid + cool + technical + balanced | 架构、系统设计 |
| `chalkboard` | organic + warm + handwritten + balanced | 教育、教程 |
| `corporate` | clean + professional + geometric + balanced | 投资者提案 |
| `minimal` | clean + neutral + geometric + minimal | 高管简报 |
| `sketch-notes` | organic + warm + handwritten + balanced | 教育、教程 |
| `hand-drawn-edu` | organic + macaron + handwritten + balanced | 教育图解、流程说明 |
| `watercolor` | organic + warm + humanist + minimal | 生活、健康 |
| `dark-atmospheric` | clean + dark + editorial + balanced | 娱乐、游戏 |
| `notion` | clean + neutral + geometric + dense | 产品演示、SaaS |
| `bold-editorial` | clean + vibrant + editorial + balanced | 产品发布、演讲 |
| `editorial-infographic` | clean + cool + editorial + dense | 科技解读、研究 |
| `fantasy-animation` | organic + vibrant + handwritten + minimal | 教育故事 |
| `intuition-machine` | clean + cool + technical + dense | 技术文档、学术 |
| `pixel-art` | pixel + vibrant + technical + balanced | 游戏、开发者演讲 |
| `scientific` | clean + cool + technical + dense | 生物、化学、医学 |
| `vector-illustration` | clean + vibrant + humanist + balanced | 创意、儿童内容 |
| `vintage` | paper + warm + editorial + balanced | 历史、传统 |

### 风格维度

| 维度 | 选项 | 说明 |
|------|------|------|
| **Texture** | clean, grid, organic, pixel, paper | 视觉纹理和背景处理 |
| **Mood** | professional, warm, cool, vibrant, dark, neutral, macaron | 色彩温度和调色风格 |
| **Typography** | geometric, humanist, handwritten, editorial, technical | 标题和正文字体风格 |
| **Density** | minimal, balanced, dense | 每页信息密度 |

详细规格：`references/dimensions/*.md`

### 自动风格选择

| 内容信号 | Preset |
|---------|--------|
| tutorial, learn, education, guide, beginner | `sketch-notes` |
| hand-drawn, infographic, diagram, process, onboarding | `hand-drawn-edu` |
| classroom, teaching, school, chalkboard | `chalkboard` |
| architecture, system, data, analysis, technical | `blueprint` |
| creative, children, kids, cute | `vector-illustration` |
| briefing, academic, research, bilingual | `intuition-machine` |
| executive, minimal, clean, simple | `minimal` |
| saas, product, dashboard, metrics | `notion` |
| investor, quarterly, business, corporate | `corporate` |
| launch, marketing, keynote, magazine | `bold-editorial` |
| entertainment, music, gaming, atmospheric | `dark-atmospheric` |
| explainer, journalism, science communication | `editorial-infographic` |
| story, fantasy, animation, magical | `fantasy-animation` |
| gaming, retro, pixel, developer | `pixel-art` |
| biology, chemistry, medical, scientific | `scientific` |
| history, heritage, vintage, expedition | `vintage` |
| lifestyle, wellness, travel, artistic | `watercolor` |
| 默认 | `blueprint` |

详细参考：`references/styles/*.md`、`references/dimensions/presets.md`

## 工作流程

```
幻灯片进度：
- [ ] Step 1: 初始化与分析
  - [ ] 1.1 加载偏好设置（EXTEND.md）
  - [ ] 1.2 分析内容（文本或 PDF）
  - [ ] 1.3 检查现有 deck 目录
- [ ] Step 2: 确认 ⚠️ 必须
- [ ] Step 3: 生成大纲
- [ ] Step 4: 审阅大纲（条件触发）
- [ ] Step 5: 生成 prompts（仅 PDF 模式）
- [ ] Step 6: 审阅 prompts（条件触发）
- [ ] Step 7: 生成图片（仅 PDF 模式）
- [ ] Step 8: 构建输出
  - [ ] PDF 模式：合并图片 → PDF
  - [ ] PPTX 模式：从 outline 构建可编辑 PPTX
- [ ] Step 9: 输出摘要
```

### Step 1: 初始化与分析

**1.1 加载偏好设置**

检查 EXTEND.md（优先级顺序）：

```bash
# macOS, Linux, WSL, Git Bash
test -f .marine-slides/EXTEND.md && echo "project"
test -f "${XDG_CONFIG_HOME:-$HOME/.config}/marine-slides/EXTEND.md" && echo "xdg"
test -f "$HOME/.marine-slides/EXTEND.md" && echo "user"
```

| 路径 | 位置 |
|------|------|
| `.marine-slides/EXTEND.md` | 项目目录 |
| `$HOME/.config/marine-slides/EXTEND.md` | XDG 配置 |
| `$HOME/.marine-slides/EXTEND.md` | 用户主目录 |

**找到 EXTEND.md 时** → 读取并输出摘要：
```
📋 已从 [完整路径] 加载偏好设置
├─ Style: [preset]
├─ Audience: [audience 或 "auto-detect"]
├─ Language: [language 或 "auto-detect"]
└─ Review: [enabled/disabled]
```

**默认值**（无 EXTEND.md 时）：`--lang zh`、`--audience general`、`--format pdf`、`review: enabled`

**1.2 分析内容**

- 如果 `--input <file>`：读取文件内容
- 如果 `--pdf <file>`：运行 `pdf-parse` 提取文本，保存到 `source.md`
- 如果粘贴内容：保存到 `source.md`
- 按照 `references/analysis-framework.md` 进行内容分析
- 检测语言、确定页数、生成 topic slug

**1.3 检查现有目录**

```bash
test -d "{topic-slug}" && echo "exists"
```

如果目录存在，使用 AskUserQuestion：

```
header: "Existing"
question: "发现已有内容。如何处理？"
options:
  - label: "重新生成大纲"
    description: "保留图片，只重新生成 outline"
  - label: "重新生成图片"
    description: "保留 outline，只重新生成图片"
  - label: "备份并重新生成"
    description: "备份到 {slug}-backup-{timestamp}，然后全部重新生成"
  - label: "退出"
    description: "取消，保持现有内容不变"
```

### Step 2: 确认 ⚠️ 必须

**两轮确认**：Round 1 始终执行，Round 2 仅在选择了"自定义维度"时执行。

**语言**：使用用户输入语言或保存的语言偏好。

**显示摘要**：
- 内容类型 + 识别的主题
- 语言：[来自 EXTEND.md 或检测到的语言]
- **推荐风格**：[preset]（基于内容信号）
- **推荐页数**：[N]（基于内容长度）

#### Round 1（始终执行）

使用 AskUserQuestion 依次提问：

**问题 1：风格**
```
header: "Style"
question: "这个 deck 用什么视觉风格？"
options:
  - label: "{recommended_preset}（推荐）"
    description: "基于内容分析的最佳匹配"
  - label: "{alternative_preset}"
    description: "[备选风格描述]"
  - label: "自定义维度"
    description: "分别选择 texture、mood、typography、density"
```

**问题 2：受众**
```
header: "Audience"
question: "主要受众是谁？"
options:
  - label: "普通读者（推荐）"
    description: "广泛适用，内容易懂"
  - label: "初学者"
    description: "教育导向，解释清晰"
  - label: "专家/专业人士"
    description: "技术深度，需要领域知识"
  - label: "高管"
    description: "高层洞察，极简细节"
```

**问题 3：页数**
```
header: "Slides"
question: "多少页？"
options:
  - label: "{N} 页（推荐）"
    description: "基于内容长度"
  - label: "少一些（{N-3} 页）"
    description: "更精简"
  - label: "多一些（{N+3} 页）"
    description: "更详细分解"
```

**问题 4：审阅大纲**
```
header: "Outline"
question: "生成 prompts 前审阅大纲？"
options:
  - label: "是，审阅大纲（推荐）"
    description: "审阅幻灯片标题和结构"
  - label: "否，跳过大纲审阅"
    description: "直接进入 prompt 生成"
```

**问题 5：审阅 Prompts**
```
header: "Prompts"
question: "生成图片前审阅 prompts？"
options:
  - label: "是，审阅 prompts（推荐）"
    description: "审阅图片生成 prompts"
  - label: "否，跳过 prompt 审阅"
    description: "直接进入图片生成"
```

**问题 6：格式**
```
header: "Format"
question: "哪种输出格式？"
options:
  - label: "PDF（图片形式）（推荐）"
    description: "高质量图片，不可编辑"
  - label: "PPTX（可编辑文字）"
    description: "文字可编辑，视觉保真度较低"
  - label: "同时输出 PDF 和 PPTX"
    description: "生成两种格式"
```

#### Round 2（仅在"自定义维度"时执行）

**问题 1：Texture**
```
header: "Texture"
question: "哪种视觉纹理？"
options:
  - label: "clean"
    description: "纯色，无纹理"
  - label: "grid"
    description: "细微网格叠加，技术感"
  - label: "organic"
    description: "柔和纹理，手绘感"
  - label: "pixel"
    description: "块状像素，8-bit 美学"
```

**问题 2：Mood**
```
header: "Mood"
question: "哪种色彩情绪？"
options:
  - label: "professional"
    description: "冷中性，深蓝/金色"
  - label: "warm"
    description: "大地色调，友好"
  - label: "cool"
    description: "蓝色/灰色，分析感"
  - label: "vibrant"
    description: "高饱和度，醒目"
  - label: "macaron"
    description: "马卡龙色块（蓝、薄荷、薰衣草、桃）配奶油白"
```

**问题 3：Typography**
```
header: "Typography"
question: "哪种字体风格？"
options:
  - label: "geometric"
    description: "现代无衬线，干净"
  - label: "humanist"
    description: "友好，易读"
  - label: "handwritten"
    description: "马克笔/画笔，手绘感"
  - label: "editorial"
    description: "杂志风格，戏剧性"
```

**问题 4：Density**
```
header: "Density"
question: "信息密度？"
options:
  - label: "balanced（推荐）"
    description: "每页 2-3 个要点"
  - label: "minimal"
    description: "一个焦点，最大留白"
  - label: "dense"
    description: "多个数据点，紧凑"
```

**确认后**：存储 `skip_outline_review` 和 `skip_prompt_review` 标志。

### Step 3: 生成大纲

按照 `references/outline-template.md` 的结构生成大纲。

1. 如果是 preset → 读取 `references/styles/{preset}.md`
2. 如果是自定义维度 → 读取 `references/dimensions/` 并组合
3. 构建 STYLE_INSTRUCTIONS，应用确认的 audience、language、slide count
4. 保存为 `outline.md`

**生成后**：
- 如果 `--outline-only`，停止
- 如果 `--format pptx`：
  - 如果 `skip_outline_review` 为 true → 跳到 Step 8
  - 如果 `skip_outline_review` 为 false → 继续 Step 4
- 如果 `--format pdf` 或 `--format both`：
  - 如果 `skip_outline_review` 为 true → 跳到 Step 5
  - 如果 `skip_outline_review` 为 false → 继续 Step 4

### Step 4: 审阅大纲（条件触发）

**如果用户选择了"否，跳过大纲审阅"，跳过此步骤。**

**显示大纲摘要**：
- 总页数：N
- 风格：[preset 名称或 "custom: texture+mood+typography+density"]
- 幻灯片列表：

```
| # | 标题 | 类型 | 布局 |
|---|------|------|------|
| 1 | [标题] | Cover | title-hero |
| 2 | [标题] | Content | [布局] |
| 3 | [标题] | Content | [布局] |
| ... | ... | ... | ... |
```

使用 AskUserQuestion：
```
header: "Confirm"
question: "准备好继续？"
options:
  - label: "是，继续（推荐）"
    description: "PPTX模式直接构建，PDF模式生成image prompts"
  - label: "先编辑大纲"
    description: "我将修改 outline.md 后再继续"
  - label: "重新生成大纲"
    description: "用不同方式创建新大纲"
```

**用户响应后**：
1. 如果"先编辑大纲" → 提示用户编辑 `outline.md`，再次询问
2. 如果"重新生成大纲" → 返回 Step 3
3. 如果"是，继续" → PPTX 模式跳到 Step 8，PDF 模式继续 Step 5
   - **PPTX 模式注意**：此处"是，继续"直接构建 PPTX，不生成也不审阅 prompts

### Step 5: 生成 Prompts（仅 PDF 模式）

**完全跳过如果 `--format pptx`。**

1. 读取 `references/base-prompt.md`
2. 对于 outline 中的每页：
   - 从 outline 提取 STYLE_INSTRUCTIONS（不从 style 文件重新读取）
   - 添加该页特定内容
   - 如果指定了 `Layout:`，包含来自 `references/layouts.md` 的布局指导
3. 保存到 `prompts/` 目录

**生成后**：
- 如果 `--prompts-only`，停止并输出摘要
- 如果 `skip_prompt_review` 为 true → 跳到 Step 7
- 如果 `skip_prompt_review` 为 false → 继续 Step 6

### Step 6: 审阅 Prompts（条件触发）

**完全跳过如果 `--format pptx`。**
**如果用户选择了"否，跳过 prompt 审阅"，跳过此步骤。**

**显示 prompts 摘要**：
- 总数：N
- 风格：[preset 名称或自定义维度]
- 文件列表：

```
| # | 文件名 | 幻灯片标题 |
|---|--------|-----------|
| 1 | 01-slide-cover.md | [标题] |
| 2 | 02-slide-xxx.md | [标题] |
| ... | ... | ... |
```

使用 AskUserQuestion：
```
header: "Confirm"
question: "准备生成幻灯片图片？"
options:
  - label: "是，继续（推荐）"
    description: "生成所有幻灯片图片"
  - label: "先编辑 prompts"
    description: "我将修改 prompts 后再继续"
  - label: "重新生成 prompts"
    description: "用不同方式创建新 prompts"
```

### Step 7: 生成图片（仅 PDF 模式）

**完全跳过如果 `--format pptx`。**

1. 选择可用的图片生成 skill（`baoyu-imagine`）
2. 生成 session ID：`slides-{topic-slug}-{timestamp}`
3. 逐页生成图片（使用相同 session ID 保证风格一致）
4. 报告进度："已生成 X/N"（使用用户语言）
5. 失败时自动重试一次

### Step 8: 构建输出

**PDF 模式：**
```bash
${BUN_X} {baseDir}/scripts/merge-to-pdf.ts <deck-dir>
```

**PPTX 模式：**
```bash
${BUN_X} {baseDir}/scripts/build-editable-pptx.ts <deck-dir>
```

**Both 模式：**运行两个命令。

### Step 9: 输出摘要

```
marine-slides 完成！

主题：[topic]
风格：[preset]
格式：[pdf / pptx / both]
位置：[directory path]
页数：N

输出：
- {topic-slug}.pdf     （图片形式，N 页）
- {topic-slug}.pptx    （可编辑文字，N 页）
```

## 分段工作流

| 选项 | 工作流 |
|------|--------|
| `--outline-only` | Step 1-3（到大纲为止） |
| `--prompts-only` | Step 1-5（跳过图片） |
| `--images-only` | Step 7-9（需要 prompts/） |
| `--build-pptx` | Step 8 PPTX（需要 outline.md） |

### 使用 `--outline-only`

生成大纲但不生成图片：

```bash
/marine-slides content.md --outline-only
```

输出：`outline.md` + `prompts/*.md`（可审阅/编辑）

### 使用 `--images-only`

从现有 prompts 生成图片（从 Step 7 开始）：

```bash
/marine-slides marine-slides/topic-slug/ --images-only
```

前提条件：
- `prompts/` 目录包含幻灯片 prompt 文件
- `outline.md` 包含风格信息

### 使用 `--regenerate`

重新生成指定幻灯片：

```bash
# 单页
/marine-slides marine-slides/topic-slug/ --regenerate 3

# 多页
/marine-slides marine-slides/topic-slug/ --regenerate 2,5,8
```

流程：
1. 读取指定幻灯片的现有 prompts
2. 重新生成图片
3. 重新构建 PPTX/PDF

### 使用 `--regenerate`（PPTX 模式）

PPTX 模式下，`--regenerate` 的含义不同：
- PPTX 模式没有 prompts 和图片，所有内容都在 `outline.md` 中
- 编辑 `outline.md` 后直接运行 `--build-pptx` 即可
- 不需要 `--regenerate`，因为没有单页图片需要重新生成

如果用户想修改某一页内容：
1. 编辑 `outline.md` 中对应幻灯片的条目
2. 运行 `bun scripts/build-editable-pptx.ts marine-slides/{topic-slug}/`

## 大纲编辑（PPTX 模式）

PPTX 模式下，用户可以直接编辑 `outline.md`，然后重新构建：

1. 编辑 `outline.md` 中的大纲内容
2. 运行 `--build-pptx`：
```bash
/marine-slides marine-slides/topic-slug/ --build-pptx
```
3. 新的 PPTX 会覆盖旧的

**重要**：每次修改 `outline.md` 后，必须重新运行 `--build-pptx` 才能看到更改。

## 文件结构

```
marine-slides/{topic-slug}/
├── source-{slug}.md              # 原始内容（文本或 PDF 提取）
├── outline.md                    # 生成的大纲（含 STYLE_INSTRUCTIONS）
├── analysis.md                   # 内容分析元数据（用于调试）
├── prompts/                      # 图片 prompts（仅 PDF 模式）
│   └── 01-slide-cover.md, ...
├── images/                       # 生成的幻灯片图片（仅 PDF 模式）
│   └── 01-slide-cover.png, ...
├── {topic-slug}.pdf             # PDF 输出
└── {topic-slug}.pptx           # 可编辑 PPTX 输出
```

## 依赖

- **Bun** 或 **npx**（运行时）
- **baoyu-imagine**（图片生成，PDF 模式）
- **pptxgenjs**（可编辑 PPTX 输出）
- **pdf-parse**（PDF 文本提取）
- 本地参考文件在 `references/` 目录

## 参考文档

| 文件 | 内容 |
|------|------|
| `references/analysis-framework.md` | 内容分析框架 |
| `references/outline-template.md` | 大纲结构和格式 |
| `references/base-prompt.md` | 图片生成基础 prompt |
| `references/layouts.md` | 布局选项 |
| `references/dimensions/*.md` | 维度规格（texture, mood, typography, density） |
| `references/dimensions/presets.md` | Preset → 维度映射 |
| `references/styles/*.md` | 完整风格规格 |
| `references/content-rules.md` | 内容和风格指南 |
| `references/design-guidelines.md` | 受众、排版、颜色、视觉元素 |

## 与 baoyu-slide-deck 的关系

- marine-slides 完全独立
- 不引用外部 baoyu-slide-deck 文件
- 参考文档已复制到本地 `references/` 目录
- 两者可并行存在，用户按需选择
