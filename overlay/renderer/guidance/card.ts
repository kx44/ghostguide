// The tooltip card: step meta, title, why, what to do, suggested value, done-when, and the help buttons.
import type { Card, GuideMsg } from "../../shared/messages";
import { Ctx, Mounted, Rect, Side, el, esc, kc } from "../dom";
import { placeCard } from "../place";
import { codeBoxHtml } from "./codeCard";
import { keycapsHtml } from "./keycaps";
import { chipsHtml } from "./pathChips";

const LABELS: Record<string, string> = { show_me: "Show me", do_it: "Do it for me", next: "Next ›", skip_wait: "Skip waiting", use_window: "Use this window" };

/** Card content for the card-only fallback (no target on screen): what the style would have shown. */
export function fallbackHtml(g: GuideMsg): { top: string; body: string } {
  const x = g.extra;
  const top = x.path?.length ? chipsHtml(x.path, x.path_done ?? 0) : "";
  let h = "";
  if (x.keys?.length) h += keycapsHtml(x.keys);
  if (x.value && x.action === "type") h += codeBoxHtml(x.value, x.multiline || x.value.length > 40 ? "Code" : "Text");
  if (x.action === "switch_app") h += `<div class="alt">Or press ${kc("Alt", "sm")} + ${kc("Tab", "sm")}</div>`;
  if (x.action === "wait") h += `<div class="bar"></div>` + (x.signals ?? []).map(s => `<div class="sig"><i></i>${esc(s)}</div>`).join("");
  return { top, body: h };
}

// Where the user dragged the card to (window px). Once set, every later card goes there too, until a
// double-click on its top row hands placement back to the automatic rule.
let pinned: { x: number; y: number } | null = null;
let sized: number | null = null;       // the width dragged to, for every card from then on; double-click the corner to undo
const MIN_W = 240, MAX_W = 900;

export function mountCard(ctx: Ctx, g: GuideMsg, c: Card, m: Mounted, onAction: (a: string, btn: HTMLElement) => void,
                          reserveBottom: number, avoid: Rect[] = []): HTMLDivElement {
  const actions = c.actions.map(a => {
    const label = a === "do_it" && c.confirm ? "Press again to do it" : a === "do_it" && g.extra.action === "type" ? "Fill it for me" : LABELS[a] ?? a;
    return `<button data-a="${esc(a)}" class="${a === "next" && c.actions.length > 1 ? "link" : a === "next" || (a === "do_it" && c.confirm) ? "pri" : ""}">${esc(label)}</button>`;
  }).join("");
  const meta = `<div class="meta" title="Drag to move · double-click to put it back"><span>${esc(c.meta)}</span>` +
    `${c.low_confidence ? `<span class="unsure" title="This step was inferred or unclear in the source">unsure</span>` : ""}` +
    `${c.source ? `<button class="src" data-a="source" title="This step in the original tutorial (Ctrl+Alt+O)">${esc(c.source)}</button>` : ""}</div>`;
  const html = c.compact
    // Repeat step: the light guide stays light, but the instruction never disappears.
    ? meta + `<b>${esc(c.title)}</b>` + (c.up_next ? `<div class="upnext">Up next: ${esc(c.up_next)}</div>` : "") +
      (c.dev_hint ? `<div class="devhint">${esc(c.dev_hint)}</div>` : "") + (actions ? `<div class="acts">${actions}</div>` : "")
    : meta +
      (m.cardTop ?? "") +
      `<b>${esc(c.title)}</b>` +
      (c.why ? `<div>${esc(c.why)}</div>` : "") +
      (c.detail ? `<div class="detail">${esc(c.detail)}</div>` : "") +
      (m.cardHtml ?? "") +
      (c.suggested ? `<div class="sug">Suggested: ${esc(c.suggested)} <span>(ours; the tutorial leaves it open)</span></div>` : "") +
      (c.done_when ? `<div class="done">Done when: ${esc(c.done_when)}</div>` : "") +
      (c.dev_hint ? `<div class="devhint">${esc(c.dev_hint)}</div>` : "") +
      (actions ? `<div class="acts">${actions}</div>` : "");
  const card = el(ctx.ov, `card hit${m.wide && !c.compact ? " wide" : ""}${c.compact ? " compact" : ""}`, "visibility:hidden",
                  html + `<div class="grip" title="Drag to resize · double-click to put it back"></div>`);
  if (sized) { card.style.width = `${sized}px`; card.style.maxWidth = "none"; }
  card.querySelectorAll<HTMLButtonElement>("button[data-a]").forEach(b => b.addEventListener("click", () => onAction(b.dataset.a!, b)));
  card.querySelectorAll<HTMLButtonElement>("button[data-copy]").forEach(b => b.addEventListener("click", () => copied(b)));

  const auto = () => {
    const p = placeCard(card.offsetWidth, card.offsetHeight, m.anchor, ctx.W, ctx.H, m.prefer as Side[] | undefined, reserveBottom, avoid);
    card.classList.remove("up", "down", "left", "right");
    card.style.left = `${p.x}px`;
    card.style.top = `${p.y}px`;
    if (p.arrow) card.classList.add(p.arrow);
    if (p.ax != null) card.style.setProperty("--ax", `${p.ax}px`);
    if (p.ay != null) card.style.setProperty("--ay", `${p.ay}px`);
  };
  const put = (x: number, y: number) => {          // a dragged card: no arrow, kept on screen
    card.classList.remove("up", "down", "left", "right");
    card.style.left = `${Math.min(Math.max(4, x), ctx.W - card.offsetWidth - 4)}px`;
    card.style.top = `${Math.min(Math.max(4, y), ctx.H - card.offsetHeight - 4)}px`;
  };
  if (pinned) put(pinned.x, pinned.y); else auto();
  card.style.visibility = "";
  draggable(card, ctx, put, auto);
  resizable(card, ctx, () => { if (pinned) put(pinned.x, pinned.y); else auto(); });
  return card;
}

/** Wider or narrower, by the bottom-right corner, with a shield like a drag so a fast move can't drop it. Height follows. */
function resizable(card: HTMLDivElement, ctx: Ctx, place: () => void) {
  const grip = card.querySelector<HTMLElement>(".grip")!;
  grip.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const sx = e.clientX, w0 = card.offsetWidth;
    let shield: HTMLElement | undefined;       // only once it's really a drag: a double-click must still reach the corner
    const move = (ev: PointerEvent) => {
      if (!shield) {
        if (Math.abs(ev.clientX - sx) < 4) return;
        shield = el(ctx.ov, "dragshield hit", "cursor:ew-resize");
        window.dispatchEvent(new Event("ghost:hits"));
      }
      sized = Math.round(Math.min(Math.max(MIN_W, w0 + ev.clientX - sx), Math.min(MAX_W, ctx.W - 8)));
      card.style.width = `${sized}px`;
      card.style.maxWidth = "none";
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (!shield) return;
      shield.remove();
      place();                // the arrow and the room around the target follow the new size
      window.dispatchEvent(new Event("ghost:hits"));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  grip.addEventListener("dblclick", () => {
    sized = null;
    card.style.width = card.style.maxWidth = "";
    place();
    window.dispatchEvent(new Event("ghost:hits"));
  });
}

/** Drag the card by its top row. While dragging, a full-window hit area keeps the (normally click-through)
 *  overlay window taking the mouse, so a fast drag can't drop it. */
function draggable(card: HTMLDivElement, ctx: Ctx, put: (x: number, y: number) => void, auto: () => void) {
  const handle = card.querySelector<HTMLElement>(".meta")!;
  handle.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    const sx = e.clientX, sy = e.clientY;
    const dx = sx - card.offsetLeft, dy = sy - card.offsetTop;
    let shield: HTMLElement | undefined;          // only once it's really a drag (moved 4 px): a click or a
    const move = (ev: PointerEvent) => {          // double-click on the row must still reach the row
      if (!shield) {
        if (Math.abs(ev.clientX - sx) + Math.abs(ev.clientY - sy) < 4) return;
        shield = el(ctx.ov, "dragshield hit", "");
        window.dispatchEvent(new Event("ghost:hits"));
        card.classList.add("dragging");
      }
      put(ev.clientX - dx, ev.clientY - dy);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (!shield) return;
      shield.remove();
      card.classList.remove("dragging");
      pinned = { x: card.offsetLeft, y: card.offsetTop };
      window.dispatchEvent(new Event("ghost:hits"));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  handle.addEventListener("dblclick", () => { pinned = null; auto(); });
}

/** Copy: the text goes to the clipboard through main; the button says so and the code box flashes. */
function copied(b: HTMLButtonElement) {
  window.ghost.copy(b.dataset.copy ?? "");
  const box = b.closest(".codebox");
  b.textContent = "Copied ✓";
  b.classList.add("done");
  box?.classList.remove("flash"); void (box as HTMLElement | null)?.offsetWidth; box?.classList.add("flash");
  clearTimeout(Number(b.dataset.t));
  b.dataset.t = String(setTimeout(() => { b.textContent = "Copy"; b.classList.remove("done"); }, 1600));
}
