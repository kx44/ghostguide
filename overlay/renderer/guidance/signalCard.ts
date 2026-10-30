// 12 · Wait: a slim card naming what we wait for, ticking cheap signals as they arrive (ticking needs the
// phase 3 signals; phase 2 shows them). Auto-advance comes with the checks; Skip waiting always works.
import type { GuideMsg, Local } from "../../shared/messages";
import { Ctx, Mounted, esc, toRect } from "../dom";

export function mountSignalCard(_ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const sigs = g.extra.signals ?? [];
  return {
    anchor: toRect(local.box),
    // The moving bar promises an automatic move; only show it when the engine will advance by itself.
    cardHtml: (g.card?.actions.includes("skip_wait") ? `<div class="bar"></div>` : "") + sigs.map((s, i) => `<div class="sig" data-i="${i}"><i></i>${esc(cap(s))}</div>`).join(""),
    mark(result) {
      if (result !== "ok") return;
      document.querySelectorAll(".card .sig").forEach(s => { s.classList.add("on"); s.querySelector("i")!.textContent = "✓"; });
      document.querySelector<HTMLElement>(".card .bar")?.style.setProperty("display", "none");
    },
    remove() {},
  };
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
