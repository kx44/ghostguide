// Small DOM + SVG helpers shared by the guidance styles.
import type { Box } from "../shared/messages";

export const NS = "http://www.w3.org/2000/svg";
export interface Rect { x: number; y: number; w: number; h: number }

export interface Ctx {
  ov: HTMLElement;          // HTML layer for this step's guidance
  svg: SVGSVGElement;       // SVG layer for this step's guidance
  W: number;                // window size in DIPs
  H: number;
}

/** A mounted style. `anchor` is what the card points at; `cardTop` goes above the card title (path chips),
 *  `cardHtml` below the text, above the buttons. */
export interface Mounted {
  anchor?: Rect;
  cardTop?: string;
  cardHtml?: string;
  wide?: boolean;
  prefer?: Side[];
  mark?(result: "ok" | "bad"): void;
  remove(): void;
}
export type Side = "below" | "above" | "right" | "left";

export const esc = (s: unknown): string =>
  String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export function el(parent: HTMLElement, cls: string, css: Partial<CSSStyleDeclaration> | string = "", html = ""): HTMLDivElement {
  const d = document.createElement("div");
  d.className = cls;
  if (typeof css === "string") d.style.cssText = css; else Object.assign(d.style, css);
  d.innerHTML = html;
  parent.appendChild(d);
  return d;
}

/** SVG element; values containing var() go into `style` so CSS variables resolve. */
export function sv<K extends keyof SVGElementTagNameMap>(parent: Element, tag: K, attrs: Record<string, string | number>): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag);
  let st = "";
  for (const [a, v] of Object.entries(attrs)) {
    const s = String(v);
    if (s.includes("var(")) st += `${a}:${s};`; else e.setAttribute(a, s);
  }
  if (st) e.setAttribute("style", (e.getAttribute("style") || "") + st);
  parent.appendChild(e);
  return e;
}

/** 2 px outline, clear of the target. */
export function outline(parent: HTMLElement, b: Rect, cls = ""): HTMLDivElement {
  return el(parent, `outline ${cls}`, `left:${b.x - 4}px;top:${b.y - 4}px;width:${b.w + 8}px;height:${b.h + 8}px`);
}

export const kc = (k: string, cls = "") => `<span class="kc ${cls}" data-k="${esc(k)}">${esc(prettyKey(k))}</span>`;

export function prettyKey(k: string): string {
  const m: Record<string, string> = { enter: "Enter ↵", return: "Enter ↵", backspace: "⌫", tab: "Tab ⇥", esc: "Esc", escape: "Esc",
    up: "↑", down: "↓", left: "←", right: "→", space: "Space", control: "Ctrl", ctrl: "Ctrl", cmd: "⌘", win: "Win" };
  return m[k.toLowerCase()] ?? (k.length === 1 ? k.toUpperCase() : k);
}

export const toRect = (b?: Box): Rect | undefined => (b ? { x: b.x, y: b.y, w: b.w, h: b.h } : undefined);

export const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

/** Group of nodes that a style can remove in one go. */
export class Bag {
  private nodes: (Element | (() => void))[] = [];
  add<T extends Element>(n: T): T { this.nodes.push(n); return n; }
  onRemove(f: () => void) { this.nodes.push(f); }
  remove() { for (const n of this.nodes) typeof n === "function" ? n() : n.remove(); this.nodes = []; }
}
