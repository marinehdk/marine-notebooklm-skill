# marine-slides Skill 设计文档

**日期**：2026-04-21
**作者**：marine
**状态**：草稿

---

## 1. 概述

`/marine-slides` 是一个独立的幻灯片生成 Skill，基于 baoyu-slide-deck 的核心流程构建，支持两种输出模式：
- **PDF 模式**（默认）：生成图片式幻灯片 PDF，与 baoyu-slide-deck 行为一致
- **PPTX 模式**：生成基于 PptxGenJS 的可编辑文字版 PPTX

两个模式共享相同的输入解析、风格系统和大纲生成流程，PPTX 模式跳过图片生成步骤，直接用代码构建可编辑幻灯片。

---

## 2. 输入

### 2.1 文本输入
- 用户直接粘贴文本或 Markdown 内容
- 支持通过 `--input` 参数指定本地 `.txt` / `.md` 文件路径
- 内容过短时提示用户扩充

### 2.2 PDF 解析
- 用户通过 `--pdf <file>` 参数上传 PDF 文件
- 使用 pdf-parse 提取 PDF 文本内容
- 图片暂不处理（未来可扩展）
- 解析结果自动生成 source.md 存入 deck 目录

---

## 3. 风格系统

直接复用 baoyu-slide-deck 的 style preset 和自定义维度系统，不重新实现。

### 3.1 Preset 风格（16种）
`blueprint`, `chalkboard`, `corporate`, `minimal`, `sketch-notes`, `hand-drawn-edu`, `watercolor`, `dark-atmospheric`, `notion`, `bold-editorial`, `editorial-infographic`, `fantasy-animation`, `intuition-machine`, `pixel-art`, `scientific`, `vector-illustration`, `vintage`

### 3.2 自定义维度（4维 x 多档）
- **Texture**: clean, grid, organic, pixel, paper
- **Mood**: professional, warm, cool, vibrant, dark, neutral, macaron
- **Typography**: geometric, humanist, handwritten, editorial, technical
- **Density**: minimal, balanced, dense

### 3.3 参数
- `--style <name>` 选择 preset 或自定义维度组合
- `--audience` 受众（beginners, intermediate, experts, executives, general）
- `--lang` 输出语言（en, zh, ja 等）

---

## 4. 工作流程

### 4.1 完整流程（9步）

```
1. Setup & Analyze    — 解析输入，检查已有 deck 状态
2. Style Confirmation — 确认风格、受众、页数、输出格式
3. Generate Outline   — 生成 outline.md（含 STYLE_INSTRUCTIONS）
4. Review Outline    — [引导模式] 用户逐页确认/修改；[跳过模式] 直接使用
5. Generate Prompts  — 为每页生成 baoyu-imagine 提示词（仅 PDF 模式）
6. Review Prompts    — [引导模式] 用户可编辑提示词；[跳过模式] 直接使用
7. Generate Images   — [PDF 模式] 逐页生成图片；[PPTX 模式] 跳过此步
8. Build PPTX/PDF    — [PDF 模式] 合并为 PDF；[PPTX 模式] PptxGenJS 构建可编辑 PPTX
9. Output Summary    — 输出文件路径，完成提示
```

### 4.2 跳过模式（--skip-review）
用户添加 `--skip-review` 参数时：
- 步骤 4：自动使用 outline.md，不逐页确认
- 步骤 6：自动使用生成的 prompts，不逐页确认
- 等同于 baoyu-slide-deck 的 `--skip-review` 行为

### 4.3 分段执行（部分工作流）
- `--outline-only` — 仅生成 outline.md
- `--prompts-only` — 仅生成 prompts 目录（依赖 outline.md）
- `--images-only` — 仅生成图片（依赖 prompts）
- `--build-pdf` — 仅合并 PDF（依赖 images）
- `--build-pptx` — 仅构建 PPTX（依赖 outline.md + 可选的 images）
- `--regenerate N` — 重新生成第 N 页（图片 + 对应输出）

### 4.4 输出格式参数
- `--format pdf` — 仅输出 PDF（默认）
- `--format pptx` — 仅输出可编辑 PPTX
- `--format both` — 同时输出 PDF 和 PPTX

---

## 5. PDF 模式

与 baoyu-slide-deck 完全一致：
- 使用 `baoyu-imagine` 逐页生成 PNG 图片
- 使用 `merge-to-pdf.ts` 合并为 PDF
- 幻灯片为图片形式，不可编辑

---

## 6. PPTX 模式（可编辑）

### 6.1 核心差异
PPTX 模式跳过图片生成步骤，使用 PptxGenJS 直接构建文字版幻灯片。文字可编辑，但视觉效果依赖代码实现的样式还原程度。

### 6.2 构建流程
1. 读取 outline.md 获取每页内容（标题、正文要点、类型：Cover / Content / Back Cover）
2. 读取 STYLE_INSTRUCTIONS 获取风格配置
3. 根据风格配置构建 PptxGenJS 幻灯片：
   - 选择匹配的配色方案（从 style preset 映射）
   - 设置字体（从 typography 维度映射）
   - 布局密度（从 density 维度映射）
   - 添加背景、装饰元素（尽量还原视觉风格）
4. 每页添加备注（notes），内容为该页的 baoyu-imagine prompt 原文（可选）
5. 输出为 `.pptx` 文件

### 6.3 视觉风格映射

| baoyu style | PptxGenJS 配色 | 字体 |
|-------------|---------------|------|
| blueprint | 蓝白网格 | Courier New / monospace |
| chalkboard | 深绿黑板色 | Handlee |
| corporate | 商务蓝灰 | Arial |
| minimal | 纯白黑字 | Inter |
| ... | ... | ... |

### 6.4 限制
- PPTX 内容为文字，不是图片，因此与 PDF 版本的视觉可能有差异
- 复杂视觉效果（手绘、插画风格）只能近似还原，无法 1:1 再现
- 不支持动态效果、动画

---

## 7. 文件结构

```
marine-slides/{topic-slug}/
├── source-{slug}.{ext}           # 用户输入源文件（.md / .pdf）
├── source-{slug}.md              # PDF 解析后的文本（仅 PDF 输入时）
├── outline.md                    # 生成的大纲（含 STYLE_INSTRUCTIONS）
├── prompts/                     # 图片提示词（仅 PDF 模式）
│   ├── 01-slide-cover.md
│   └── 02-slide-{slug}.md
├── images/                      # 生成的幻灯片图片（仅 PDF 模式）
│   ├── 01-slide-cover.png
│   └── 02-slide-{slug}.png
├── {topic-slug}.pdf             # 合并 PDF 输出
└── {topic-slug}.pptx            # 可编辑 PPTX 输出
```

---

## 8. 命令行接口

```
/marine-slides <content> [options]
/marine-slides --input <file> [options]
/marine-slides --pdf <file> [options]
/marine-slides --skip-review [options]
/marine-slides --outline-only [options]
/marine-slides --prompts-only [options]
/marine-slides --images-only [options]
/marine-slides --build-pdf [options]
/marine-slides --build-pptx [options]
/marine-slides --regenerate N [options]
```

### 参数

| 参数 | 说明 |
|------|------|
| `--input <file>` | 本地 .md / .txt 文件作为输入 |
| `--pdf <file>` | PDF 文件作为输入 |
| `--style <name>` | 风格 preset 或自定义维度 |
| `--audience` | 受众群体 |
| `--lang` | 输出语言 |
| `--slides <N>` | 目标页数（8-30） |
| `--format pdf\|pptx\|both` | 输出格式，默认 pdf |
| `--skip-review` | 跳过大纲和提示词的确认步骤 |
| `--outline-only` | 仅生成 outline.md |
| `--prompts-only` | 仅生成 prompts |
| `--images-only` | 仅生成图片 |
| `--build-pdf` | 仅合并 PDF |
| `--build-pptx` | 仅构建 PPTX |
| `--regenerate N` | 重新生成第 N 页 |
| `--deck <path>` | 指定 deck 输出目录 |

---

## 9. 依赖

- **baoyu-imagine**：图片生成（PDF 模式必需）
- **baoyu-slide-deck**：复用 outline 生成逻辑、style 系统
- **PptxGenJS**：构建可编辑 PPTX
- **pdf-parse**：解析 PDF 文件
- **merge-to-pdf.ts**：PDF 合并（复用 baoyu-slide-deck 版本）
- **merge-to-pptx.ts**：可编辑 PPTX 构建脚本（新建）

---

## 10. 与 baoyu-slide-deck 的关系

- marine-slides 是独立 Skill，代码不复用 baoyu-slide-deck
- 仅复用 baoyu-slide-deck 的设计思路（流程、style 系统、大纲格式）
- marine-slides 自主维护，不受 baoyu-slide-deck 更新影响
- 两者可以并行存在，用户按需选择

---

## 11. 实现优先级

### Phase 1（MVP）
- 文本输入 → outline 生成 → PDF 输出（复用 baoyu-slide-deck 流程）
- 跳过模式（--skip-review）完整流程

### Phase 2
- PDF 文件输入支持
- PPTX 模式（可编辑输出）
- 引导模式（逐页确认/修改大纲）

### Phase 3
- 部分工作流参数（--outline-only, --regenerate N 等）
- 双格式同时输出（--format both）
