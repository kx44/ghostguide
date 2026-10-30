// Physical pixels (engine: UIA, screenshots, pins) ⇄ Electron DIPs, per display.
// On Windows Electron converts exactly, even with mixed DPI across monitors; elsewhere (dev only) we scale
// by the display's factor.
import { Display, Rectangle, screen } from "electron";
import type { Box, DisplayInfo, Pt } from "../shared/messages";

const WIN = process.platform === "win32";

export function physicalDisplays(): DisplayInfo[] {
  const primary = screen.getPrimaryDisplay().id;
  return screen.getAllDisplays().map(d => {
    const r = WIN ? screen.dipToScreenRect(null, d.bounds) : scaleRect(d.bounds, d.scaleFactor);
    return { id: d.id, x: r.x, y: r.y, w: r.width, h: r.height, scale: d.scaleFactor, primary: d.id === primary };
  });
}

export function toDipRect(b: Box): Rectangle {
  const r = { x: b.x, y: b.y, width: b.w, height: b.h };
  return WIN ? screen.screenToDipRect(null, r) : scaleRect(r, 1 / primaryScale());
}

export function toDipPoint(p: Pt): Pt {
  if (WIN) { const d = screen.screenToDipPoint({ x: p[0], y: p[1] }); return [d.x, d.y]; }
  const s = primaryScale();
  return [p[0] / s, p[1] / s];
}

export function displayForRect(r: Rectangle): Display { return screen.getDisplayMatching(r); }
export function displayForPoint(p: Pt): Display { return screen.getDisplayNearestPoint({ x: Math.round(p[0]), y: Math.round(p[1]) }); }

const primaryScale = () => screen.getPrimaryDisplay().scaleFactor;
const scaleRect = (r: Rectangle, s: number): Rectangle =>
  ({ x: Math.round(r.x * s), y: Math.round(r.y * s), width: Math.round(r.width * s), height: Math.round(r.height * s) });
