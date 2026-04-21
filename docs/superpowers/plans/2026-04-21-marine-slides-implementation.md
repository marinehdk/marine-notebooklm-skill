# marine-slides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/marine-slides` skill — a slide deck generator supporting PDF (image-based) and PPTX (editable text-based) output formats, built on baoyu-slide-deck's workflow and style system.

**Architecture:** Phase 1 reuses baoyu-slide-deck's existing workflow and outline/style references as-is (read-only reference). The marine-slides SKILL.md owns the full workflow definition. A new `build-editable-pptx.ts` script creates the text-based PPTX by parsing outline.md and applying style mappings. No code is shared via import — references are read from baoyu-slide-deck's files at runtime.

**Tech Stack:** Bun/TypeScript, PptxGenJS, pdf-parse, baoyu-imagine (for PDF mode image generation)

---

## File Structure

```
marine-notebooklm-skill/
└── skills/
    └── marine-slides/
        ├── SKILL.md                          # Main skill definition (workflow, options, CLI)
        ├── scripts/
        │   ├── build-editable-pptx.ts        # New: builds text-based PPTX from outline + style
        │   └── merge-to-pdf.ts               # Copy of baoyu-slide-deck merge-to-pdf.ts
        └── references/
            └── style-mapping.ts               # Maps baoyu style presets → PptxGenJS colors/fonts
```

**Note:** `references/` in baoyu-slide-deck are read at runtime (not copied). The `SKILL.md` references them via path. Only `style-mapping.ts` is new code.

---

### Task 1: Create marine-slides directory and SKILL.md

**Files:**
- Create: `skills/marine-slides/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: marine-slides
description: Generates slide decks in PDF (image) or PPTX (editable text) format. Use when user asks to "create slides", "make a presentation", "generate deck", "PPT", "editable PPT", or "slides with editable text".
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

Transform content into professional slide decks with two output modes:
- **PDF** (default): Image-based slides, identical to baoyu-slide-deck
- **PPTX**: Editable text-based slides built with PptxGenJS

## Usage

```bash
/marine-slides path/to/content.md
/marine-slides path/to/content.md --format pptx
/marine-slides path/to/content.md --pdf path/to/file.pdf
/marine-slides path/to/content.md --style sketch-notes --format both
/marine-slides path/to/content.md --skip-review
/marine-slides  # Then paste content
```

## Script Directory

**Agent Execution Instructions**:
1. Determine this SKILL.md file's directory path as `{baseDir}`
2. Script path = `{baseDir}/scripts/<script-name>.ts`
3. Resolve `${BUN_X}` runtime: if `bun` installed → `bun`; if `npx` available → `npx -y bun`; else suggest installing bun

| Script | Purpose |
|--------|---------|
| `scripts/build-editable-pptx.ts` | Build editable text-based PPTX from outline.md |
| `scripts/merge-to-pdf.ts` | Merge slide images into PDF (copied from baoyu-slide-deck) |

## Options

| Option | Description |
|--------|-------------|
| `--input <file>` | Local .md / .txt file as content input |
| `--pdf <file>` | PDF file as content input (text extracted via pdf-parse) |
| `--format pdf\|pptx\|both` | Output format. Default: pdf |
| `--style <name>` | Visual style: preset name (see Style System) |
| `--audience <type>` | Target: beginners, intermediate, experts, executives, general |
| `--lang <code>` | Output language (en, zh, ja, etc.) |
| `--slides <number>` | Target slide count (8-25 recommended, max 30) |
| `--outline-only` | Generate outline only, skip image/text generation |
| `--prompts-only` | Generate outline + prompts, skip images |
| `--images-only` | Generate images from existing prompts directory (PDF mode only) |
| `--build-pptx` | Build PPTX from existing outline (PPTX mode) |
| `--regenerate <N>` | Regenerate specific slide(s) |
| `--skip-review` | Skip outline and prompt review steps |

## Style System

Identical to baoyu-slide-deck. Presets: `blueprint` (default), `chalkboard`, `corporate`, `minimal`, `sketch-notes`, `hand-drawn-edu`, `watercolor`, `dark-atmospheric`, `notion`, `bold-editorial`, `editorial-infographic`, `fantasy-animation`, `intuition-machine`, `pixel-art`, `scientific`, `vector-illustration`, `vintage`.

Auto-selection, custom dimensions, and all style references are identical to baoyu-slide-deck.

**Reference files** (read-only, from baoyu-slide-deck):
- Style presets: `{baoyu-baseDir}/references/styles/*.md`
- Dimensions: `{baoyu-baseDir}/references/dimensions/*.md`
- Outline template: `{baoyu-baseDir}/references/outline-template.md`
- Base prompt: `{baoyu-baseDir}/references/base-prompt.md`
- Layouts: `{baoyu-baseDir}/references/layouts.md`

## Workflow

```
Slide Deck Progress:
- [ ] Step 1: Setup & Analyze
  - [ ] 1.1 Load preferences (EXTEND.md)
  - [ ] 1.2 Analyze content (text or PDF)
  - [ ] 1.3 Check existing deck directory
- [ ] Step 2: Confirmation ⚠️ REQUIRED
- [ ] Step 3: Generate outline
- [ ] Step 4: Review outline (conditional on --skip-review)
- [ ] Step 5: Generate prompts (PDF mode only)
- [ ] Step 6: Review prompts (conditional on --skip-review)
- [ ] Step 7: Generate images (PDF mode only)
- [ ] Step 8: Build output
  - [ ] PDF mode: merge images → PDF
  - [ ] PPTX mode: build-editable-pptx.ts from outline
- [ ] Step 9: Output summary
```

### Step 1: Setup & Analyze

**1.1 Load Preferences**

Check EXTEND.md at project and user levels:

```bash
test -f .marine-slides/EXTEND.md && echo "project"
test -f "${XDG_CONFIG_HOME:-$HOME/.config}/marine-slides/EXTEND.md" && echo "xdg"
test -f "$HOME/.marine-slides/EXTEND.md" && echo "user"
```

**1.2 Analyze Content**

- If `--input <file>`: read file content
- If `--pdf <file>`: use pdf-parse to extract text, save to `source.md`
- If pasted content: save to `source.md`
- Follow baoyu-slide-deck's analysis framework for style recommendation
- Detect language, determine slide count, generate topic slug

**1.3 Check Existing Directory**

```bash
test -d "marine-slides/{topic-slug}" && echo "exists"
```

**1.4 Save analysis.md** with topic, audience, style recommendation, slide count, language.

### Step 2: Confirmation ⚠️ REQUIRED

Ask 5 questions (same as baoyu-slide-deck Step 2 Round 1), plus one format question:

**Format Question** (insert after style/audience/slides questions):
```
header: "Format"
question: "Which output format?"
options:
  - label: "PDF (image-based) (Recommended)"
    description: "High-quality images, no text editing"
  - label: "PPTX (editable text)"
    description: "Text can be edited, less visual fidelity"
  - label: "Both PDF and PPTX"
    description: "Generate both formats"
```

### Step 3: Generate Outline

Identical to baoyu-slide-deck Step 3. Read style from baoyu-slide-deck's `references/styles/{preset}.md`, build STYLE_INSTRUCTIONS, save to `outline.md`.

### Step 4: Review Outline (Conditional)

Same as baoyu-slide-deck Step 4. Skip if `--skip-review`.

### Step 5: Generate Prompts (PDF mode only)

Skip entirely if `--format pptx`. Otherwise identical to baoyu-slide-deck Step 5.

### Step 6: Review Prompts (Conditional)

Skip entirely if `--format pptx`. Skip if `--skip-review`.

### Step 7: Generate Images (PDF mode only)

Skip entirely if `--format pptx`. Identical to baoyu-slide-deck Step 7.

### Step 8: Build Output

**PDF mode:**
```bash
${BUN_X} {baseDir}/scripts/merge-to-pdf.ts <marine-slides-dir>
```

**PPTX mode:**
```bash
${BUN_X} {baseDir}/scripts/build-editable-pptx.ts <marine-slides-dir> --format pptx
```

**Both mode:** run both commands.

### Step 9: Output Summary

```
marine-slides Complete!

Topic: [topic]
Style: [preset]
Format: [pdf / pptx / both]
Location: [directory path]
Slides: N total

Output:
- {topic-slug}.pdf     (image-based, N pages)
- {topic-slug}.pptx    (editable text, N slides)
```

## Partial Workflows

| Option | Workflow |
|--------|----------|
| `--outline-only` | Steps 1-3 (stop after outline) |
| `--prompts-only` | Steps 1-5 (skip images) |
| `--images-only` | Steps 7-9 (requires prompts/) |
| `--build-pptx` | Step 8 PPTX only (requires outline.md) |

## File Structure

```
marine-slides/{topic-slug}/
├── source-{slug}.md           # Original content (text or PDF extracted)
├── outline.md                 # Generated outline with STYLE_INSTRUCTIONS
├── prompts/                   # Image prompts (PDF mode only)
│   └── 01-slide-cover.md, ...
├── images/                     # Generated slide images (PDF mode only)
│   └── 01-slide-cover.png, ...
├── {topic-slug}.pdf           # PDF output
└── {topic-slug}.pptx          # Editable PPTX output
```

## Dependencies

- **Bun** or **npx** (runtime)
- **baoyu-imagine** (image generation, PDF mode)
- **pptxgenjs** (editable PPTX output)
- **pdf-parse** (PDF text extraction)
- Style references from **baoyu-slide-deck** (read-only at runtime)

## Relationship with baoyu-slide-deck

- marine-slides is fully independent
- References baoyu-slide-deck files for style/outline/templates (read-only)
- baoyu-slide-deck is not modified; no shared code
- Both skills can coexist; user chooses per invocation
```

- [ ] **Step 2: Run verification**

Verify the file was created correctly:
```bash
test -f "skills/marine-slides/SKILL.md" && echo "exists" || echo "missing"
head -5 skills/marine-slides/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/marine-slides/SKILL.md
git commit -m "feat: add marine-slides SKILL.md skeleton with PDF and PPTX output modes"
```

---

### Task 2: Copy merge-to-pdf.ts from baoyu-slide-deck

**Files:**
- Create: `skills/marine-slides/scripts/merge-to-pdf.ts` (copy from baoyu-slide-deck)
- Reference: `{baoyu-baseDir}/scripts/merge-to-pdf.ts`

- [ ] **Step 1: Copy merge-to-pdf.ts**

```bash
cp ~/.claude/plugins/marketplaces/baoyu-skills/skills/baoyu-slide-deck/scripts/merge-to-pdf.ts skills/marine-slides/scripts/merge-to-pdf.ts
```

- [ ] **Step 2: Verify it runs**

```bash
cd skills/marine-slides && bun scripts/merge-to-pdf.ts 2>&1 | head -5
# Expected: "Usage: bun merge-to-pdf.ts <slide-deck-dir>" error (no dir provided is correct)
```

- [ ] **Step 3: Commit**

```bash
git add skills/marine-slides/scripts/merge-to-pdf.ts
git commit -m "feat: add merge-to-pdf.ts from baoyu-slide-deck"
```

---

### Task 3: Create style-mapping.ts — map baoyu style presets to PptxGenJS colors/fonts

**Files:**
- Create: `skills/marine-slides/references/style-mapping.ts`

- [ ] **Step 1: Write style-mapping.ts**

```typescript
export interface StyleMapping {
  name: string;
  background: { color: string };
  primaryText: { color: string; fontSize: number; fontFace: string; bold?: boolean };
  headline: { color: string; fontSize: number; fontFace: string; bold?: boolean };
  body: { color: string; fontSize: number; fontFace: string };
  accent1: { color: string };
  accent2: { color: string };
  layout: "title-hero" | "two-column" | "bullet-list" | "full-bleed" | "centered";
}

const STYLES: Record<string, StyleMapping> = {
  blueprint: {
    name: "blueprint",
    background: { color: "FAF8F5" },
    primaryText: { color: "334155", fontSize: 18, fontFace: "Arial" },
    headline: { color: "334155", fontSize: 36, fontFace: "Arial", bold: true },
    body: { color: "334155", fontSize: 16, fontFace: "Arial" },
    accent1: { color: "2563EB" },
    accent2: { color: "1E3A5F" },
    layout: "title-hero",
  },
  chalkboard: {
    name: "chalkboard",
    background: { color: "2D4A3E" },
    primaryText: { color: "F5F5DC", fontSize: 18, fontFace: "Georgia" },
    headline: { color: "F5F5DC", fontSize: 36, fontFace: "Georgia", bold: true },
    body: { color: "E8E4D9", fontSize: 16, fontFace: "Georgia" },
    accent1: { color: "8FBC8F" },
    accent2: { color: "F0E68C" },
    layout: "centered",
  },
  corporate: {
    name: "corporate",
    background: { color: "FFFFFF" },
    primaryText: { color: "1E3A5F", fontSize: 18, fontFace: "Arial" },
    headline: { color: "1E3A5F", fontSize: 36, fontFace: "Arial", bold: true },
    body: { color: "334155", fontSize: 16, fontFace: "Arial" },
    accent1: { color: "2563EB" },
    accent2: { color: "F59E0B" },
    layout: "title-hero",
  },
  minimal: {
    name: "minimal",
    background: { color: "FFFFFF" },
    primaryText: { color: "000000", fontSize: 18, fontFace: "Inter" },
    headline: { color: "000000", fontSize: 40, fontFace: "Inter", bold: true },
    body: { color: "333333", fontSize: 16, fontFace: "Inter" },
    accent1: { color: "000000" },
    accent2: { color: "666666" },
    layout: "centered",
  },
  sketchNotes: {
    name: "sketch-notes",
    background: { color: "FDF6E3" },
    primaryText: { color: "5C4A32", fontSize: 18, fontFace: "Patrick Hand" },
    headline: { color: "5C4A32", fontSize: 34, fontFace: "Patrick Hand", bold: true },
    body: { color: "5C4A32", fontSize: 16, fontFace: "Patrick Hand" },
    accent1: { color: "E07A5F" },
    accent2: { color: "81B29A" },
    layout: "bullet-list",
  },
  darkAtmospheric: {
    name: "dark-atmospheric",
    background: { color: "1A1A2E" },
    primaryText: { color: "EAEAEA", fontSize: 18, fontFace: "Arial" },
    headline: { color: "FFFFFF", fontSize: 36, fontFace: "Arial", bold: true },
    body: { color: "CCCCCC", fontSize: 16, fontFace: "Arial" },
    accent1: { color: "E94560" },
    accent2: { color: "0F3460" },
    layout: "title-hero",
  },
  notion: {
    name: "notion",
    background: { color: "FFFFFF" },
    primaryText: { color: "37352F", fontSize: 18, fontFace: "Inter" },
    headline: { color: "37352F", fontSize: 32, fontFace: "Inter", bold: true },
    body: { color: "6B6B6B", fontSize: 14, fontFace: "Inter" },
    accent1: { color: "2383E2" },
    accent2: { color: "E8E8E8" },
    layout: "bullet-list",
  },
};

export function getStyleMapping(presetName: string): StyleMapping {
  const key = presetName.toLowerCase().replace(/[-_]/g, "");
  const found = Object.entries(STYLES).find(
    ([k]) => k.toLowerCase().replace(/[-_]/g, "") === key
  );
  if (found) return found[1];
  return STYLES["blueprint"];
}

export function getAllStyleNames(): string[] {
  return Object.keys(STYLES);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd skills/marine-slides && bun build references/style-mapping.ts --target node 2>&1
# Expected: no errors
```

- [ ] **Step 3: Commit**

```bash
git add skills/marine-slides/references/style-mapping.ts
git commit -m "feat: add style-mapping.ts for PptxGenJS color/font mapping"
```

---

### Task 4: Create build-editable-pptx.ts — the core PPTX builder script

**Files:**
- Create: `skills/marine-slides/scripts/build-editable-pptx.ts`
- Read: `skills/marine-slides/references/style-mapping.ts`
- Read: `{baoyu-baseDir}/references/outline-template.md` (for STYLE_INSTRUCTIONS format)

- [ ] **Step 1: Write the script header and parseArgs**

```typescript
import { existsSync, readFileSync, readdirSync } from "fs";
import { join, basename } from "path";
import PptxGenJS from "pptxgenjs";
import { getStyleMapping } from "../references/style-mapping.ts";

interface SlideEntry {
  index: number;
  type: "Cover" | "Content" | "Back Cover";
  filename: string;
  headline: string;
  subheadline?: string;
  body?: string[];
  layout?: string;
}

interface OutlineMeta {
  topic: string;
  style: string;
  audience: string;
  language: string;
  slideCount: number;
}

function parseArgs(): { dir: string; format?: string } {
  const args = process.argv.slice(2);
  let dir = "";
  let format: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--format") {
      format = args[++i];
    } else if (!args[i].startsWith("-")) {
      dir = args[i];
    }
  }

  if (!dir) {
    console.error("Usage: bun build-editable-pptx.ts <marine-slides-dir> [--format pptx]");
    process.exit(1);
  }

  return { dir, format: format || "pptx" };
}
```

- [ ] **Step 2: Write parseOutline function**

```typescript
function parseOutlineMeta(content: string): OutlineMeta {
  const meta: OutlineMeta = {
    topic: "",
    style: "blueprint",
    audience: "general",
    language: "en",
    slideCount: 0,
  };

  const topicMatch = content.match(/\*\*Topic\*\*:\s*(.+)/);
  if (topicMatch) meta.topic = topicMatch[1].trim();

  const styleMatch = content.match(/\*\*Style\*\*:\s*(.+)/);
  if (styleMatch) meta.style = styleMatch[1].trim();

  const audienceMatch = content.match(/\*\*Audience\*\*:\s*(.+)/);
  if (audienceMatch) meta.audience = audienceMatch[1].trim();

  const langMatch = content.match(/\*\*Language\*\*:\s*(.+)/);
  if (langMatch) meta.language = langMatch[1].trim();

  const countMatch = content.match(/\*\*Slide Count\*\*:\s*(\d+)/);
  if (countMatch) meta.slideCount = parseInt(countMatch[1], 10);

  return meta;
}

function parseSlideEntries(content: string): SlideEntry[] {
  const slides: SlideEntry[] = [];
  // Split on ## Slide X of N pattern
  const slideBlocks = content.split(/(?=^## Slide \d+ of \d+)/m);

  for (const block of slideBlocks) {
    const headerMatch = block.match(/^## Slide (\d+) of \d+/m);
    if (!headerMatch) continue;

    const index = parseInt(headerMatch[1], 10);
    const typeMatch = block.match(/\*\*Type\*\*:\s*(Cover|Content|Back Cover)/);
    const filenameMatch = block.match(/\*\*Filename\*\*:\s*(.+)/);
    const headlineMatch = block.match(/Headline:\s*(.+)/);
    const subheadlineMatch = block.match(/Sub-headline:\s*(.+)/);
    const layoutMatch = block.match(/Layout:\s*(.+)/);

    const bodyLines: string[] = [];
    const bodyMatch = block.match(/Body:\s*([\s\S]*?)(?=\/\/|^\/\/|$$)/m);
    if (bodyMatch) {
      const bodyContent = bodyMatch[1];
      const bulletMatches = bodyContent.matchAll(/^- (.+)/gm);
      for (const m of bulletMatches) {
        bodyLines.push(m[1]);
      }
    }

    if (filenameMatch) {
      slides.push({
        index,
        type: (typeMatch?.[1] as SlideEntry["type"]) || "Content",
        filename: filenameMatch[1].trim(),
        headline: headlineMatch?.[1].trim() || "",
        subheadline: subheadlineMatch?.[1].trim(),
        body: bodyLines.length > 0 ? bodyLines : undefined,
        layout: layoutMatch?.[1].trim(),
      });
    }
  }

  return slides.sort((a, b) => a.index - b.index);
}
```

- [ ] **Step 3: Write buildSlide function**

```typescript
function buildSlide(
  pptx: InstanceType<typeof PptxGenJS>,
  slide: SlideEntry,
  style: ReturnType<typeof getStyleMapping>
) {
  const s = pptx.addSlide();

  // Background
  s.background = { color: style.background.color };

  if (slide.type === "Cover") {
    // Title-centered cover layout
    s.addText(slide.headline, {
      x: 0.5,
      y: 2.0,
      w: 9,
      h: 1.5,
      fontSize: style.headline.fontSize,
      fontFace: style.headline.fontFace,
      color: style.headline.color,
      bold: style.headline.bold,
      align: "center",
    });

    if (slide.subheadline) {
      s.addText(slide.subheadline, {
        x: 0.5,
        y: 3.6,
        w: 9,
        h: 0.8,
        fontSize: style.body.fontSize + 4,
        fontFace: style.body.fontFace,
        color: style.accent1.color,
        align: "center",
      });
    }

    // Accent bar
    s.addShape(pptx.ShapeType.rect, {
      x: 3.5,
      y: 1.6,
      w: 3,
      h: 0.05,
      fill: { color: style.accent1.color },
      line: { color: style.accent1.color, width: 0 },
    });

  } else if (slide.type === "Content") {
    // Headline
    s.addText(slide.headline, {
      x: 0.5,
      y: 0.4,
      w: 9,
      h: 0.9,
      fontSize: style.headline.fontSize,
      fontFace: style.headline.fontFace,
      color: style.headline.color,
      bold: style.headline.bold,
    });

    // Sub-headline if present
    if (slide.subheadline) {
      s.addText(slide.subheadline, {
        x: 0.5,
        y: 1.3,
        w: 9,
        h: 0.5,
        fontSize: style.body.fontSize + 2,
        fontFace: style.body.fontFace,
        color: style.accent2.color,
      });
    }

    // Body bullets
    if (slide.body && slide.body.length > 0) {
      const bulletItems = slide.body.map((text) => ({
        text,
        options: {
          bullet: { type: "bullet", color: style.accent1.color },
          fontSize: style.body.fontSize,
          fontFace: style.body.fontFace,
          color: style.body.color,
          paraSpaceAfter: 8,
        },
      }));

      s.addText(bulletItems, {
        x: 0.5,
        y: slide.subheadline ? 1.9 : 1.5,
        w: 9,
        h: 3.5,
        valign: "top",
      });
    }

  } else if (slide.type === "Back Cover") {
    // Centered closing
    s.addText(slide.headline, {
      x: 0.5,
      y: 2.2,
      w: 9,
      h: 1.2,
      fontSize: style.headline.fontSize,
      fontFace: style.headline.fontFace,
      color: style.headline.color,
      bold: style.headline.bold,
      align: "center",
    });

    if (slide.body) {
      s.addText(
        slide.body.map((b) => ({
          text: b,
          options: { fontSize: style.body.fontSize, fontFace: style.body.fontFace, color: style.body.color, align: "center" },
        })),
        { x: 0.5, y: 3.5, w: 9, h: 1.5, align: "center" }
      );
    }
  }
}
```

- [ ] **Step 4: Write main function**

```typescript
async function main() {
  const { dir, format } = parseArgs();

  if (!existsSync(dir)) {
    console.error(`Directory not found: ${dir}`);
    process.exit(1);
  }

  const outlinePath = join(dir, "outline.md");
  if (!existsSync(outlinePath)) {
    console.error(`outline.md not found in: ${dir}`);
    process.exit(1);
  }

  const outlineContent = readFileSync(outlinePath, "utf-8");
  const meta = parseOutlineMeta(outlineContent);
  const slides = parseSlideEntries(outlineContent);

  if (slides.length === 0) {
    console.error("No slide entries found in outline.md");
    process.exit(1);
  }

  const style = getStyleMapping(meta.style);

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_16x9";
  pptx.author = "marine-slides";
  pptx.subject = meta.topic;

  for (const slide of slides) {
    buildSlide(pptx, slide, style);
  }

  const outputPath = join(dir, `${basename(dir)}.pptx`);
  await pptx.writeFile({ fileName: outputPath });

  console.log(`Created editable PPTX: ${outputPath}`);
  console.log(`Total slides: ${slides.length}`);
  console.log(`Style: ${meta.style}`);
}
```

- [ ] **Step 5: Wrap with error handler**

```typescript
main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
```

- [ ] **Step 6: Verify the script compiles**

```bash
cd skills/marine-slides && bun build scripts/build-editable-pptx.ts --target node 2>&1
# Expected: no errors
```

- [ ] **Step 7: Commit**

```bash
git add skills/marine-slides/scripts/build-editable-pptx.ts
git commit -m "feat: add build-editable-pptx.ts for text-based PPTX generation"
```

---

### Task 5: Create a test outline.md and verify the PPTX build pipeline

**Files:**
- Create: `skills/marine-slides/test/test-outline.md` (sample outline)
- Run: `skills/marine-slides/scripts/build-editable-pptx.ts` on test data

- [ ] **Step 1: Create test outline**

```markdown
# Slide Deck Outline

**Topic**: Introduction to Machine Learning
**Style**: blueprint
**Dimensions**: grid + cool + technical + balanced
**Audience**: beginners
**Language**: en
**Slide Count**: 4 slides
**Generated**: 2026-04-21 10:00

---

<STYLE_INSTRUCTIONS>
Design Aesthetic: Clean, digital precision with crisp edges. Technical grid overlay with engineering precision.

Background:
  Texture: grid
  Base Color: Blueprint Off-White (#FAF8F5)

Typography:
  Headlines: bold geometric sans-serif with precise letterforms
  Body: clean readable sans-serif

Color Palette:
  Primary Text: Deep Slate (#334155)
  Background: Blueprint Paper (#FAF8F5)
  Accent 1: Engineering Blue (#2563EB)
  Accent 2: Navy Blue (#1E3A5F)

Visual Elements:
  - Technical schematics and clean vector graphics
  - Thin line work in technical drawing style

Density Guidelines:
  - Content per slide: balanced (2-3 key points)
  - Whitespace: moderate

Style Rules:
  Do: Maintain consistent line weights, use grid alignment
  Don't: Use hand-drawn shapes, add decorative flourishes
</STYLE_INSTRUCTIONS>

---

## Slide 1 of 4

**Type**: Cover
**Filename**: 01-slide-cover.png

// NARRATIVE GOAL
Introduce the topic and set the stage for learning ML fundamentals

// KEY CONTENT
Headline: Introduction to Machine Learning
Sub-headline: From Data to Predictions

// VISUAL
Clean blueprint-style cover with technical grid background

## Slide 2 of 4

**Type**: Content
**Filename**: 02-slide-what-is-ml.png

// NARRATIVE GOAL
Define machine learning and explain its core concept

// KEY CONTENT
Headline: What is Machine Learning?
Sub-headline: Computers that learn from experience
Body:
- Machine learning is a subset of artificial intelligence
- Systems improve performance through data exposure
- Traditional programming: rules + input = output
- ML paradigm: data + output = rules

// VISUAL
Blueprint diagram showing the ML paradigm shift

## Slide 3 of 4

**Type**: Content
**Filename**: 03-slide-types.png

// NARRATIVE GOAL
Explain the three main types of machine learning

// KEY CONTENT
Headline: Three Types of Machine Learning
Body:
- Supervised Learning: learn from labeled examples
- Unsupervised Learning: discover hidden patterns
- Reinforcement Learning: learn through trial and error

// VISUAL
Three-column layout with icons for each type

## Slide 4 of 4

**Type**: Back Cover
**Filename**: 04-slide-back-cover.png

// NARRATIVE GOAL
Provide a memorable closing and next steps

// KEY CONTENT
Headline: Start Your ML Journey Today
Body:
- Practice with real datasets
- Build your first model
- Join the community
```

- [ ] **Step 2: Run the PPTX builder**

```bash
cd skills/marine-slides
mkdir -p test-deck
cp test/test-outline.md test-deck/outline.md
bun scripts/build-editable-pptx.ts test-deck
# Expected: "Created editable PPTX: test-deck/test-deck.pptx"
# Expected: "Total slides: 4"
```

- [ ] **Step 3: Verify the PPTX was created**

```bash
test -f test-deck/test-deck.pptx && echo "PPTX created successfully" || echo "FAILED"
ls -lh test-deck/
```

- [ ] **Step 4: Clean up test files**

```bash
rm -rf test-deck test/test-outline.md
```

- [ ] **Step 5: Commit**

```bash
git add skills/marine-slides/test/
git commit -m "test: add test outline and verify PPTX build pipeline"
```

---

### Task 6: Add PPTX format question to SKILL.md Step 2 confirmation

**Files:**
- Modify: `skills/marine-slides/SKILL.md` — add format question to Step 2

- [ ] **Step 1: Verify current SKILL.md Step 2 section exists**

```bash
grep -n "Step 2" skills/marine-slides/SKILL.md | head -3
# Should show Step 2: Confirmation
```

- [ ] **Step 2: Add format question after the slide count question in Step 2 Round 1**

Insert this after the slide count question in Step 2 Round 1:

```markdown
**Question 5: Format**
```
header: "Format"
question: "Which output format?"
options:
  - label: "PDF (image-based) (Recommended)"
    description: "High-quality images, no text editing"
  - label: "PPTX (editable text)"
    description: "Text can be edited, less visual fidelity"
  - label: "Both PDF and PPTX"
    description: "Generate both formats"
```
```

- [ ] **Step 3: Commit**

```bash
git add skills/marine-slides/SKILL.md
git commit -m "docs: add format question to Step 2 confirmation in SKILL.md"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|------------------|------|
| 独立 Skill（marine-slides） | Task 1 |
| 文本输入支持 | Task 1 (SKILL.md Step 1) |
| PDF 输入支持 | Task 1 (SKILL.md --pdf option + pdf-parse) |
| PDF 模式输出 | Task 1 (SKILL.md) + Task 2 (merge-to-pdf.ts) |
| PPTX 模式输出（可编辑） | Task 3 (style-mapping.ts) + Task 4 (build-editable-pptx.ts) |
| 双格式同时输出（--format both） | Task 1 (SKILL.md --format both) + Task 4 (build-editable-pptx.ts) |
| 引导模式（逐页确认）+ 跳过模式 | Task 1 (SKILL.md --skip-review + Step 4/6) |
| 风格系统（复用 baoyu-slide-deck） | Task 1 (SKILL.md references baoyu files) |
| Outline 生成 | Task 1 (SKILL.md Step 3, uses baoyu outline-template.md) |
| 分段执行参数 | Task 1 (SKILL.md Partial Workflows table) |

---

## Self-Review Checklist

- [ ] No TBD/TODO placeholders anywhere
- [ ] All file paths are absolute from project root
- [ ] `style-mapping.ts` has 7 mapped styles (blueprint, chalkboard, corporate, minimal, sketch-notes, dark-atmospheric, notion) — sufficient for Phase 1
- [ ] `build-editable-pptx.ts` reads `outline.md` from the deck directory and writes `{dirname}.pptx`
- [ ] `merge-to-pdf.ts` is copied verbatim from baoyu-slide-deck
- [ ] SKILL.md Step 2 includes the format question
- [ ] All new files are committed

---

Plan complete and saved to `docs/superpowers/plans/2026-04-21-marine-slides-implementation.md`.
