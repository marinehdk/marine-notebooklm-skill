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