// Where the card goes: next to its anchor without covering it, inside the window, arrow pointing at it.
import type { Rect, Side } from "./dom";

const GAP = 12;          // from the outline (which itself sits 4 px outside the target)
const MARGIN = 10;       // from the window edge
const BOTTOM_RESERVE = 110;   // control bar + taskbar on the primary display

export interface Placement { x: number; y: number; arrow: "up" | "down" | "left" | "right" | ""; ax?: number; ay?: number }

export function placeCard(cw: number, ch: number, anchor: Rect | undefined, W: number, H: number,
                          prefer: Side[] = ["below", "above", "right", "left"], reserveBottom = BOTTOM_RESERVE): Placement {
  const maxY = H - reserveBottom;
  if (!anchor) return { x: Math.round((W - cw) / 2), y: Math.max(MARGIN, maxY - ch - 16), arrow: "" };
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
  for (const side of prefer) {
    const p = fits[side]();
    if (p) return p;
  }
  // Anchor is huge (a whole window) or the screen is tiny: sit inside the anchor, bottom-right, no arrow.
  return { x: clampX(a.x + a.w - cw - 24), y: clampY(a.y + a.h - ch - 24), arrow: "" };
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));
