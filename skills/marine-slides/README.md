# marine-slides

将内容转换为专业幻灯片，支持 **PDF**（图片形式）或 **PPTX**（可编辑文字）两种输出模式。

## 功能特点

- **双格式输出**：PDF（高质量图片）默认，PPTX（可编辑文字）可选
- **17 种视觉风格**：从技术蓝图到水彩手绘，满足不同场景
- **17 种语言**：默认简体中文，支持中文、英文、日文等
- **引导模式**：一步步确认风格、受众、页数
- **跳过模式**：`--skip` 一键全自动生成
- **独立运行**：不依赖外部 baoyu-slide-deck，完全自包含

## 快速开始

### 方式一：粘贴内容（引导模式）

```bash
bun run --cwd /Users/marine/.claude/skills/marine-slides
```

然后粘贴你的内容即可。

### 方式二：指定文件

```bash
# 文本文件
bun marine-slides path/to/content.md

# PDF 文件（自动提取文字）
bun marine-slides --pdf path/to/file.pdf

# 指定风格和语言
bun marine-slides content.md --style sketch-notes --lang en

# 输出 PPTX（可编辑文字）
bun marine-slides content.md --format pptx
```

### 方式三：跳过确认（自动模式）

```bash
bun marine-slides content.md --skip
```

## 命令行选项

| 选项 | 说明 |
|------|------|
| `--input <file>` | 本地 .md / .txt 文件作为内容输入 |
| `--pdf <file>` | PDF 文件作为内容输入（通过 pdf-parse 提取文本） |
| `--format pdf\|pptx\|both` | 输出格式。默认：`pdf` |
| `--style <name>` | 视觉风格 preset 名称（见下方风格列表） |
| `--audience <type>` | 目标受众：`beginners`, `intermediate`, `experts`, `executives`, `general`（默认） |
| `--lang <code>` | 输出语言：`zh`（默认），`en`, `ja` 等 |
| `--slides <number>` | 目标页数（建议 8-25，最大 30） |
| `--skip-review` | 跳过大纲和 prompts 的确认步骤 |
| `--outline-only` | 仅生成大纲，跳过生成 |
| `--build-pptx` | 从现有大纲构建 PPTX |

## 视觉风格（17 种）

| Preset | 说明 |
|--------|------|
| `blueprint`（默认）| 网格 + 冷色调 + 技术感，适合架构、系统设计 |
| `chalkboard` | 有机 + 暖色 + 手绘感，适合教育、教程 |
| `corporate` | 干净 + 专业 + 几何感，适合商务提案 |
| `minimal` | 极简 + 中性，适合高管简报 |
| `sketch-notes` | 手绘 + 温暖，适合教育、教程 |
| `hand-drawn-edu` | 马卡龙色 + 手绘感，适合教育图解 |
| `watercolor` | 水彩 + 暖色，适合生活、健康内容 |
| `dark-atmospheric` | 深色 + 电影感，适合娱乐、游戏 |
| `notion` | 简洁 + 网格，适合产品演示、SaaS |
| `bold-editorial` | 大胆 + 杂志风，适合产品发布、演讲 |
| `editorial-infographic` | 编辑 + 数据感，适合科技解读、研究 |
| `fantasy-animation` | 奇幻 + 魔法感，适合教育故事 |
| `intuition-machine` | 技术 + 等宽字体，适合学术、技术文档 |
| `pixel-art` | 像素 + 复古，适合游戏、开发者演示 |
| `scientific` | 科研 + 专业，适合生物、化学、医学 |
| `vector-illustration` | 矢量 + 明快，适合创意、儿童内容 |
| `vintage` | 复古 + 杂志风，适合历史、传统 |

## 工作流程

```
Step 1  → 分析内容（文本或 PDF）
Step 2  → 确认风格、受众、页数（引导模式）
Step 3  → 生成大纲
Step 4  → 审阅大纲（可选）
Step 5  → 生成 Prompts（仅 PDF 模式）
Step 6  → 审阅 Prompts（可选）
Step 7  → 生成图片（仅 PDF 模式）
Step 8  → 构建输出（PDF 合并图片 或 PPTX 生成）
Step 9  → 输出摘要
```

**PPTX 模式**：跳过 Step 5-7（无 prompts 和图片生成），直接由大纲构建可编辑 PPTX。

## 使用示例

### PDF 模式（默认）

```bash
bun marine-slides content.md --style corporate --audience executives --slides 15
```

输出：`{topic-slug}.pdf`（图片形式幻灯片）

### PPTX 模式（可编辑）

```bash
bun marine-slides content.md --format pptx --style bold-editorial
```

输出：`{topic-slug}.pptx`（文字可编辑）

### 从 PDF 创建幻灯片

```bash
bun marine-slides --pdf research-paper.pdf --format both
```

- 自动提取 PDF 文本为 `source.md`
- 同时输出 PDF 和 PPTX 两种格式

### 编辑大纲后重新生成 PPTX

```bash
# 1. 查看大纲
cat my-deck/outline.md

# 2. 编辑大纲中的幻灯片内容
vim my-deck/outline.md

# 3. 重新构建 PPTX
bun marine-slides my-deck/ --build-pptx
```

## 文件结构

```
marine-slides/{topic-slug}/
├── source-{slug}.md       # 原始内容（文本或 PDF 提取）
├── outline.md             # 生成的大纲
├── analysis.md            # 内容分析元数据
├── prompts/              # 图片 prompts（仅 PDF 模式）
│   └── 01-slide-cover.md, ...
├── images/                # 生成的幻灯片图片（仅 PDF 模式）
│   └── 01-slide-cover.png, ...
├── {topic-slug}.pdf      # PDF 输出
└── {topic-slug}.pptx    # 可编辑 PPTX 输出
```

## 依赖

- **Bun** 或 **npx** — 运行时
- **baoyu-imagine** — 图片生成（PDF 模式）
- **pptxgenjs** — PPTX 生成
- **pdf-parse** — PDF 文本提取

## 目录结构

```
skills/marine-slides/
├── SKILL.md                    # Skill 定义文件（主入口）
├── EXTEND.md                   # 用户偏好设置模板
├── scripts/
│   ├── build-editable-pptx.ts  # PPTX 构建脚本
│   ├── extract-pdf-text.ts      # PDF 文本提取脚本
│   └── merge-to-pdf.ts         # 图片合并为 PDF 脚本
└── references/                 # 参考文档（29 个文件）
    ├── analysis-framework.md
    ├── outline-template.md
    ├── base-prompt.md
    ├── layouts.md
    ├── content-rules.md
    ├── design-guidelines.md
    ├── dimensions/             # 风格维度规格
    │   ├── density.md
    │   ├── mood.md
    │   ├── presets.md
    │   ├── texture.md
    │   └── typography.md
    └── styles/                 # 17 种风格规格
        ├── blueprint.md
        ├── chalkboard.md
        ├── corporate.md
        └── ... (17 files total)
```

## 自定义偏好设置

在项目根目录或用户主目录创建 `EXTEND.md`：

```markdown
# Style: blueprint
# Audience: general
# Language: zh
# Review: enabled
```

优先顺序：项目 `.marine-slides/EXTEND.md` > `$HOME/.config/marine-slides/EXTEND.md` > `$HOME/.marine-slides/EXTEND.md`

## 故障排除

**PPTX 模式没有 prompts？** 正常。PPTX 模式直接从 `outline.md` 构建可编辑文字，跳过图片生成步骤。

**PDF 模式想修改单页内容？** 编辑 `outline.md` 中对应幻灯片的条目，然后重新生成：

```bash
bun marine-slides deck-dir/ --build-pptx   # PPTX 模式
# 或
bun marine-slides deck-dir/ --regenerate 3  # PDF 模式：重新生成第 3 页
```

**图片生成失败？** 检查 `baoyu-imagine` 是否可用，或使用 `--skip-review` 跳过审阅直接生成。
