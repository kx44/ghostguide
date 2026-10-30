// Toasts: success / warning, bottom-centre above the control bar, ~2 s. Colour is never the only signal.
import { el, esc } from "../dom";

export function toast(layer: HTMLElement, text: string, kind: "ok" | "warn", ms: number, bottom: number) {
  layer.querySelectorAll(".toast").forEach(t => t.remove());
  const t = el(layer, `toast ${kind}`, `bottom:${bottom}px`, esc(text));
  setTimeout(() => t.remove(), ms);
  return t;
}
