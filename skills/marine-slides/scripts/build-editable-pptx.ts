import { existsSync, readFileSync } from "fs";
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

function buildSlide(
  pptx: InstanceType<typeof PptxGenJS>,
  slide: SlideEntry,
  style: ReturnType<typeof getStyleMapping>
) {
  const s = pptx.addSlide();
  s.background = { color: style.background.color };

  if (slide.type === "Cover") {
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

    s.addShape(pptx.ShapeType.rect, {
      x: 3.5,
      y: 1.6,
      w: 3,
      h: 0.05,
      fill: { color: style.accent1.color },
      line: { color: style.accent1.color, width: 0 },
    });

  } else if (slide.type === "Content") {
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

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
