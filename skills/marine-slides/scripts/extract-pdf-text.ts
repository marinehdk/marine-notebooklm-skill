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
