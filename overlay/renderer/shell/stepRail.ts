// Step list: every step with ✓ done, » skipped (stays marked), current highlighted. Click to jump.
import type { FromOverlay, StateMsg } from "../../shared/messages";
import { el, esc } from "../dom";

const MARK = { done: "✓", skipped: "»", pending: "" } as const;

export class StepRail {
  open = false;
  private rail?: HTMLDivElement;

  constructor(private layer: HTMLElement, private send: (m: FromOverlay) => void) {}

  render(s: StateMsg | undefined) {
    this.rail?.remove();
    this.rail = undefined;
    if (!this.open || !s || s.hidden) return;
    const done = s.statuses.filter(x => x === "done").length, skipped = s.statuses.filter(x => x === "skipped").length;
    const rows = s.titles.map((t, i) => {
      const n = i + 1, st = s.statuses[i];
      return `<div class="row ${st}${n === s.current ? " cur" : ""}" data-n="${n}"><span class="n">${n}</span>` +
             `<span class="st">${n === s.current && st === "pending" ? "•" : MARK[st]}</span><span class="t">${esc(t)}</span></div>`;
    }).join("");
    this.rail = el(this.layer, "rail hit", "",
      `<div class="hd">${esc(s.tutorial)} · ${done} done${skipped ? `, ${skipped} skipped` : ""}</div>${rows}`);
    this.rail.querySelectorAll<HTMLElement>(".row").forEach(r => r.addEventListener("click", () => this.send({ type: "jump", n: Number(r.dataset.n) })));
    this.rail.querySelector<HTMLElement>(".row.cur")?.scrollIntoView({ block: "center" });
  }
}
