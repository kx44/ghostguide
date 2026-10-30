// Control bar (primary display, bottom-right): Back · step n/N (opens the step rail) · Skip · Next · Hide.
// Every button has a global hotkey too (main/hotkeys.ts), since the overlay never takes focus.
import type { FromOverlay, StateMsg } from "../../shared/messages";
import { el, esc } from "../dom";

export class ControlBar {
  private bar?: HTMLDivElement;
  onToggleRail: () => void = () => {};

  constructor(private layer: HTMLElement, private send: (m: FromOverlay) => void) {}

  render(s: StateMsg, railOpen: boolean) {
    this.bar?.remove();
    const done = s.statuses.filter(x => x !== "pending").length;
    let html: string;
    if (s.hidden) {
      html = `<button data-a="resume" class="pri" title="Ctrl+Alt+H">GhostGuide paused · Resume</button><span class="kh">Ctrl+Alt+H</span>`;
    } else if (s.finished) {
      html = `<span style="padding:0 8px">✓ ${esc(s.tutorial)} complete</span><button data-a="back" title="Ctrl+Alt+←">‹ Back</button>` +
             `<button data-a="rail">${railOpen ? "▾" : "▴"} Steps</button>`;
    } else {
      html = `<button data-a="back" title="Back (Ctrl+Alt+←)" ${s.current <= 1 ? "disabled style='opacity:.4'" : ""}>‹ Back</button>` +
        `<button data-a="rail" class="prog" title="Step list">${railOpen ? "▾" : "▴"} Step ${s.current} of ${s.of}<i><b style="width:${(100 * done / s.of).toFixed(1)}%"></b></i></button>` +
        `<button data-a="skip" title="Skip (Ctrl+Alt+S)">Skip »</button>` +
        `<button data-a="next" title="Next (Ctrl+Alt+→)">Next ›</button><span class="sep"></span>` +
        `<button data-a="hide" title="Hide (Ctrl+Alt+H)">Hide</button>`;
    }
    this.bar = el(this.layer, "bar-ctl hit", "", html);
    this.bar.querySelectorAll<HTMLButtonElement>("button[data-a]").forEach(b => b.addEventListener("click", () => {
      const a = b.dataset.a!;
      if (a === "rail") this.onToggleRail();
      else this.send({ type: a } as FromOverlay);
    }));
  }

  clear() { this.bar?.remove(); this.bar = undefined; }
}
