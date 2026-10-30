// The tooltip card: step meta, title, why, what to do, suggested value, done-when, and the help buttons.
import type { Card, GuideMsg } from "../../shared/messages";
import { Ctx, Mounted, Side, el, esc, kc } from "../dom";
import { placeCard } from "../place";
import { keycapsHtml } from "./keycaps";
import { chipsHtml } from "./pathChips";

const LABELS: Record<string, string> = { show_me: "Show me", do_it: "Do it for me", next: "Next ›", skip_wait: "Skip waiting" };

/** Card content for the card-only fallback (no target on screen): what the style would have shown. */
export function fallbackHtml(g: GuideMsg): { top: string; body: string } {
  const x = g.extra;
  const top = x.path?.length ? chipsHtml(x.path, x.path_done ?? 0) : "";
  let h = "";
  if (x.keys?.length) h += keycapsHtml(x.keys);
  if (x.value && (x.multiline || x.value.length > 40)) h += `<pre class="code">${esc(x.value)}</pre>`;
  if (x.action === "switch_app") h += `<div class="alt">Or press ${kc("Alt", "sm")} + ${kc("Tab", "sm")}</div>`;
  if (x.action === "wait") h += `<div class="bar"></div>` + (x.signals ?? []).map(s => `<div class="sig"><i></i>${esc(s)}</div>`).join("");
  return { top, body: h };
}

export function mountCard(ctx: Ctx, g: GuideMsg, c: Card, m: Mounted, onAction: (a: string, btn: HTMLElement) => void,
                          reserveBottom: number): HTMLDivElement {
  const actions = c.actions.map(a => {
    const label = a === "do_it" && g.extra.action === "type" ? "Fill it for me" : LABELS[a] ?? a;
    return `<button data-a="${esc(a)}" class="${a === "next" && c.actions.length > 1 ? "link" : a === "next" ? "pri" : ""}">${esc(label)}</button>`;
  }).join("");
  const html =
    `<div class="meta"><span>${esc(c.meta)}</span>${c.low_confidence ? `<span class="unsure" title="This step was inferred or unclear in the source">unsure</span>` : ""}</div>` +
    (m.cardTop ?? "") +
    `<b>${esc(c.title)}</b>` +
    (c.why ? `<div>${esc(c.why)}</div>` : "") +
    (c.detail ? `<div class="detail">${esc(c.detail)}</div>` : "") +
    (m.cardHtml ?? "") +
    (c.suggested ? `<div class="sug">Suggested: ${esc(c.suggested)} <span>(ours; the tutorial leaves it open)</span></div>` : "") +
    (c.done_when ? `<div class="done">Done when: ${esc(c.done_when)}</div>` : "") +
    (actions ? `<div class="acts">${actions}</div>` : "");
  const card = el(ctx.ov, `card hit${m.wide ? " wide" : ""}`, "visibility:hidden", html);
  card.querySelectorAll<HTMLButtonElement>("button[data-a]").forEach(b => b.addEventListener("click", () => onAction(b.dataset.a!, b)));
  const p = placeCard(card.offsetWidth, card.offsetHeight, m.anchor, ctx.W, ctx.H, m.prefer as Side[] | undefined, reserveBottom);
  card.style.left = `${p.x}px`;
  card.style.top = `${p.y}px`;
  if (p.arrow) card.classList.add(p.arrow);
  if (p.ax != null) card.style.setProperty("--ax", `${p.ax}px`);
  if (p.ay != null) card.style.setProperty("--ay", `${p.ay}px`);
  card.style.visibility = "";
  return card;
}
