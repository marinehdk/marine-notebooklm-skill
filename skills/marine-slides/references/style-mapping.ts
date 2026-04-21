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
    primaryText: { color: "000000", fontSize: 18, fontFace: "Arial" },
    headline: { color: "000000", fontSize: 40, fontFace: "Arial", bold: true },
    body: { color: "333333", fontSize: 16, fontFace: "Arial" },
    accent1: { color: "000000" },
    accent2: { color: "666666" },
    layout: "centered",
  },
  sketchNotes: {
    name: "sketch-notes",
    background: { color: "FDF6E3" },
    primaryText: { color: "5C4A32", fontSize: 18, fontFace: "Arial" },
    headline: { color: "5C4A32", fontSize: 34, fontFace: "Arial", bold: true },
    body: { color: "5C4A32", fontSize: 16, fontFace: "Arial" },
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
    primaryText: { color: "37352F", fontSize: 18, fontFace: "Arial" },
    headline: { color: "37352F", fontSize: 32, fontFace: "Arial", bold: true },
    body: { color: "6B6B6B", fontSize: 14, fontFace: "Arial" },
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
