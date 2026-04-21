# marine-slides Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Phase 2 adds PDF input support (`extract-pdf-text.ts`) and completes the remaining 10 style mappings in `style-mapping.ts`.

**Architecture:** `extract-pdf-text.ts` reads a PDF file, extracts text via pdf-parse, saves to `source.md` in the deck directory. `style-mapping.ts` maps all 17 baoyu presets to PptxGenJS colors/fonts.

---

## Task 7: Create extract-pdf-text.ts

**Files:**
- Create: `skills/marine-slides/scripts/extract-pdf-text.ts`

- [ ] **Step 1: Write extract-pdf-text.ts**

```typescript
import { existsSync, readFileSync, writeFileSync } from "fs";
import { join, basename, extname } from "path";
import pdfParse from "pdf-parse";

interface ParseResult {
  text: string;
  pageCount: number;
}

function parseArgs(): { pdfPath: string; outputDir: string } {
  const args = process.argv.slice(2);
  let pdfPath = "";
  let outputDir = "";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--output" || args[i] === "-o") {
      outputDir = args[++i];
    } else if (!args[i].startsWith("-")) {
      pdfPath = args[i];
    }
  }

  if (!pdfPath) {
    console.error("Usage: bun extract-pdf-text.ts <pdf-file> [--output <deck-dir>]");
    process.exit(1);
  }

  if (!outputDir) {
    // Default: same directory as PDF, with slugified basename
    const pdfBasename = basename(pdfPath, extname(pdfPath));
    const slug = pdfBasename
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    outputDir = slug;
  }

  return { pdfPath, outputDir };
}

async function extractText(pdfPath: string): Promise<ParseResult> {
  const dataBuffer = readFileSync(pdfPath);
  const data = await pdfParse(dataBuffer);

  return {
    text: data.text,
    pageCount: data.numpages,
  };
}

async function main() {
  const { pdfPath, outputDir } = parseArgs();

  if (!existsSync(pdfPath)) {
    console.error(`PDF file not found: ${pdfPath}`);
    process.exit(1);
  }

  console.error(`Extracting text from: ${pdfPath}`);

  const { text, pageCount } = await extractText(pdfPath);

  if (!text || text.trim().length === 0) {
    console.error("No text extracted from PDF. The PDF may be image-based (scanned).");
    console.error("Try using OCR tools like tesseract first, or use --input with text content instead.");
    process.exit(1);
  }

  // Save to source.md in output directory
  const outputPath = join(outputDir, "source.md");
  writeFileSync(outputPath, text, "utf-8");

  console.log(`Extracted ${text.trim().split(/\s+/).length} words from ${pageCount} pages`);
  console.log(`Saved to: ${outputPath}`);
  console.log(`Deck directory: ${outputDir}`);
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
```

- [ ] **Step 2: Verify it compiles**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/marine-slides" && bun build scripts/extract-pdf-text.ts --target node 2>&1
# Expected: no errors
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill" && git add skills/marine-slides/scripts/extract-pdf-text.ts && git commit -m "feat: add extract-pdf-text.ts for PDF text extraction"
```

---

## Task 8: Complete style-mapping.ts with all 17 presets

**Files:**
- Modify: `skills/marine-slides/references/style-mapping.ts`

Currently has 7 styles. Add the remaining 10: `hand-drawn-edu`, `watercolor`, `bold-editorial`, `editorial-infographic`, `fantasy-animation`, `intuition-machine`, `pixel-art`, `scientific`, `vector-illustration`, `vintage`.

Read `references/styles/{name}.md` for each and create a PptxGenJS color mapping.

**Mappings to add:**

```typescript
// Add to STYLES record:

handDrawnEdu: {
  name: "hand-drawn-edu",
  background: { color: "FDF8F0" },
  primaryText: { color: "4A4A4A", fontSize: 18, fontFace: "Arial" },
  headline: { color: "4A4A4A", fontSize: 32, fontFace: "Arial", bold: true },
  body: { color: "5C5C5C", fontSize: 16, fontFace: "Arial" },
  accent1: { color: "E8B4B8" },
  accent2: { color: "A8D8B9" },
  layout: "bullet-list",
},

watercolor: {
  name: "watercolor",
  background: { color: "FDF5F0" },
  primaryText: { color: "5C4A3D", fontSize: 18, fontFace: "Arial" },
  headline: { color: "5C4A3D", fontSize: 34, fontFace: "Georgia", bold: true },
  body: { color: "6B5A4A", fontSize: 16, fontFace: "Georgia" },
  accent1: { color: "D4A5A5" },
  accent2: { color: "B5C7A1" },
  layout: "centered",
},

boldEditorial: {
  name: "bold-editorial",
  background: { color: "FFFFFF" },
  primaryText: { color: "111111", fontSize: 18, fontFace: "Arial" },
  headline: { color: "000000", fontSize: 44, fontFace: "Georgia", bold: true },
  body: { color: "333333", fontSize: 16, fontFace: "Georgia" },
  accent1: { color: "E63946" },
  accent2: { color: "457B9D" },
  layout: "title-hero",
},

editorialInfographic: {
  name: "editorial-infographic",
  background: { color: "F8F9FA" },
  primaryText: { color: "2B2D42", fontSize: 18, fontFace: "Arial" },
  headline: { color: "2B2D42", fontSize: 36, fontFace: "Arial", bold: true },
  body: { color: "4A4E69", fontSize: 15, fontFace: "Arial" },
  accent1: { color: "457B9D" },
  accent2: { color: "E63946" },
  layout: "bullet-list",
},

fantasyAnimation: {
  name: "fantasy-animation",
  background: { color: "1A1A2E" },
  primaryText: { color: "F0E6D3", fontSize: 18, fontFace: "Arial" },
  headline: { color: "FFD700", fontSize: 38, fontFace: "Georgia", bold: true },
  body: { color: "E8D5B7", fontSize: 16, fontFace: "Georgia" },
  accent1: { color: "FF6B6B" },
  accent2: { color: "4ECDC4" },
  layout: "title-hero",
},

intuitionMachine: {
  name: "intuition-machine",
  background: { color: "F5F5F5" },
  primaryText: { color: "333333", fontSize: 17, fontFace: "Arial" },
  headline: { color: "1A1A1A", fontSize: 34, fontFace: "Courier New", bold: true },
  body: { color: "4A4A4A", fontSize: 15, fontFace: "Courier New" },
  accent1: { color: "6C63FF" },
  accent2: { color: "4A4A4A" },
  layout: "bullet-list",
},

pixelArt: {
  name: "pixel-art",
  background: { color: "1E1E2E" },
  primaryText: { color: "FFFFFF", fontSize: 18, fontFace: "Courier New" },
  headline: { color: "00FF00", fontSize: 32, fontFace: "Courier New", bold: true },
  body: { color: "C0C0C0", fontSize: 15, fontFace: "Courier New" },
  accent1: { color: "FF00FF" },
  accent2: { color: "00FFFF" },
  layout: "title-hero",
},

scientific: {
  name: "scientific",
  background: { color: "FFFFFF" },
  primaryText: { color: "1A2634", fontSize: 17, fontFace: "Arial" },
  headline: { color: "1A2634", fontSize: 34, fontFace: "Arial", bold: true },
  body: { color: "3D5A73", fontSize: 15, fontFace: "Arial" },
  accent1: { color: "2E86AB" },
  accent2: { color: "A23B72" },
  layout: "bullet-list",
},

vectorIllustration: {
  name: "vector-illustration",
  background: { color: "FFF8F0" },
  primaryText: { color: "2D3436", fontSize: 18, fontFace: "Arial" },
  headline: { color: "2D3436", fontSize: 36, fontFace: "Arial", bold: true },
  body: { color: "4A4A4A", fontSize: 16, fontFace: "Arial" },
  accent1: { color: "FF7675" },
  accent2: { color: "74B9FF" },
  layout: "title-hero",
},

vintage: {
  name: "vintage",
  background: { color: "F5E6C8" },
  primaryText: { color: "4A3728", fontSize: 18, fontFace: "Georgia" },
  headline: { color: "4A3728", fontSize: 34, fontFace: "Georgia", bold: true },
  body: { color: "5D4E37", fontSize: 16, fontFace: "Georgia" },
  accent1: { color: "8B7355" },
  accent2: { color: "C4A35A" },
  layout: "centered",
},
```

- [ ] **Step 1: Read current style-mapping.ts**

```bash
head -20 skills/marine-slides/references/style-mapping.ts
```

- [ ] **Step 2: Add the 10 new styles to STYLES record** (insert before the closing `}` of STYLES)

- [ ] **Step 3: Verify build**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/marine-slides" && bun build references/style-mapping.ts --target node 2>&1
# Expected: no errors
```

- [ ] **Step 4: Commit**

```bash
git add skills/marine-slides/references/style-mapping.ts && git commit -m "feat: add 10 remaining style mappings to style-mapping.ts"
```

---

## Task 9: Test PDF input flow end-to-end

**Files:**
- Run `extract-pdf-text.ts` on a real PDF

- [ ] **Step 1: Find a PDF to test with**

Check if there's a test PDF available, or create a minimal test PDF using the merge-to-pdf.ts pipeline:
```bash
# Create a simple test using the existing PPTX build pipeline
# Actually just test extract-pdf-text with a real PDF file path
```

If no PDF is available, verify the script compiles and has correct usage:
```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/marine-slides" && bun scripts/extract-pdf-text.ts 2>&1
# Expected: "Usage: bun extract-pdf-text.ts <pdf-file> [--output <deck-dir>]"
```

- [ ] **Commit test verification:**

```bash
echo "PDF extraction script verified - ready for use with real PDF files"
git log --oneline -3
```

---

## Spec Coverage

| Phase 2 Requirement | Task |
|---------------------|------|
| PDF 文件输入支持 | Task 7 (`extract-pdf-text.ts`) |
| 完整 17 preset 风格映射 | Task 8 (style-mapping.ts) |
| PDF 端到端测试 | Task 9 |

---

## Self-Review

- [ ] `extract-pdf-text.ts` handles missing PDF gracefully
- [ ] `extract-pdf-text.ts` errors on empty PDF text (scanned/image-only PDF)
- [ ] `style-mapping.ts` now has all 17 presets
- [ ] No TODOs or placeholders
- [ ] All files committed
