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
