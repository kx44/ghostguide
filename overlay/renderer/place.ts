// Where the card goes: next to its anchor without covering it, inside the window, arrow pointing at it,
// and off the areas the engine says you're about to work in (`avoid`: the lines your code goes on, a menu
// that opens). The first preferred side that clears them wins; if none does, the side covering least.
import type { Rect, Side } from "./dom";

const GAP = 12;          // from the outline (which itself sits 4 px outside the target)
const MARGIN = 10;       // from the window edge
const BOTTOM_RESERVE = 110;   // control bar + taskbar on the primary display

export interface Placement { x: number; y: number; arrow: "up" | "down" | "left" | "right" | ""; ax?: number; ay?: number }

export function placeCard(cw: number, ch: number, anchor: Rect | undefined, W: number, H: number,
                          prefer: Side[] = ["below", "above", "right", "left"], reserveBottom = BOTTOM_RESERVE,
                          avoid: Rect[] = []): Placement {
  const maxY = H - reserveBottom;
  // Nothing to point at: bottom right, out of the middle of the window, where the work usually is.
  if (!anchor) return { x: Math.max(MARGIN, W - cw - 24), y: Math.max(MARGIN, maxY - ch - 16), arrow: "" };
  const a = { x: anchor.x - 4, y: anchor.y - 4, w: anchor.w + 8, h: anchor.h + 8 };
  const cx = a.x + a.w / 2, cy = a.y + a.h / 2;
  const clampX = (x: number) => Math.min(Math.max(MARGIN, x), W - cw - MARGIN);
  const clampY = (y: number) => Math.min(Math.max(MARGIN, y), maxY - ch);
  const fits: Record<Side, () => Placement | null> = {
    below: () => {
      const y = a.y + a.h + GAP;
      if (y + ch > maxY) return null;
      const x = clampX(cx - 40);
      return { x, y, arrow: "up", ax: clamp(cx - x - 7, 12, cw - 26) };
    },
    above: () => {
      const y = a.y - GAP - ch;
      if (y < MARGIN) return null;
      const x = clampX(cx - 40);
      return { x, y, arrow: "down", ax: clamp(cx - x - 7, 12, cw - 26) };
    },
    right: () => {
      const x = a.x + a.w + GAP;
      if (x + cw > W - MARGIN) return null;
      const y = clampY(cy - 30);
      return { x, y, arrow: "left", ay: clamp(cy - y - 7, 12, ch - 26) };
    },
    left: () => {
      const x = a.x - GAP - cw;
      if (x < MARGIN) return null;
      const y = clampY(cy - 30);
      return { x, y, arrow: "right", ay: clamp(cy - y - 7, 12, ch - 26) };
    },
  };
  const order = [...prefer, ...(["below", "above", "right", "left"] as Side[]).filter(s => !prefer.includes(s))];
  let best: { p: Placement; cover: number } | undefined;
  for (const side of order) {
    const p = fits[side]();
    if (!p) continue;
    const cover = avoid.reduce((sum, r) => sum + overlap({ x: p.x, y: p.y, w: cw, h: ch }, r), 0);
    if (cover === 0) return p;
    if (!best || cover < best.cover) best = { p, cover };
  }
  // Every side touches an avoid area (a context menu opening right next to the target): try just past it,
  // to its right, then below it, before settling for the side that covers least.
  if (best && avoid.length) {
    const right = Math.max(...avoid.map(r => r.x + r.w)) + GAP;
    const bottom = Math.max(...avoid.map(r => r.y + r.h)) + GAP;
    const beyond: Placement[] = [];
    if (right + cw <= W - MARGIN) beyond.push({ x: right, y: clampY(a.y), arrow: "" });
    if (bottom + ch <= maxY) beyond.push({ x: clampX(a.x), y: bottom, arrow: "" });
    for (const p of beyond) {
      const r = { x: p.x, y: p.y, w: cw, h: ch };
      if (avoid.every(v => overlap(r, v) === 0) && overlap(r, a) === 0) return p;
    }
  }
  if (best) return best.p;
  // Anchor is huge (a whole window) or the screen is tiny: sit inside the anchor, bottom-right, no arrow.
  return { x: clampX(a.x + a.w - cw - 24), y: clampY(a.y + a.h - ch - 24), arrow: "" };
}

/** Area two rects share, px². */
export function overlap(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));
