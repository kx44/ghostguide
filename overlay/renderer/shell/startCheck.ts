// The start check: the tutorial's start state as a checklist, read from the real screen by the engine. It's
// up only while something isn't ready, and Start anyway always works: nothing is ever blocked.
import type { FromOverlay, StartCheckMsg } from "../../shared/messages";
import { el, esc } from "../dom";

const MARK = { yes: "✓", no: "✗", look: "•" };

export class StartCheck {
  private card?: HTMLDivElement;

  constructor(private layer: HTMLElement, private send: (m: FromOverlay) => void) {}

  render(m: StartCheckMsg) {
    this.clear();
    const rows = m.items.map(i => {
      const k = i.ok === true ? "yes" : i.ok === false ? "no" : "look";
      return `<div class="startitem ${k}"><i>${MARK[k]}</i>${esc(i.text)}</div>`;
    }).join("");
    this.card = el(this.layer, "card startcheck hit", "",
      `<div class="meta"><span>${esc(m.tutorial)}</span></div><b>Before you start</b><div class="detail">This tutorial starts from here. It moves on by itself once everything is ticked.</div>` +
      rows + `<div class="acts"><button data-a="start_ok">Start anyway</button></div>`);
    this.card.querySelector("button")!.addEventListener("click", () => this.send({ type: "start_ok" }));
  }

  clear() { this.card?.remove(); this.card = undefined; }
}
