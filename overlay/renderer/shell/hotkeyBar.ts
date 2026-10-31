// The shortcuts panel (primary display, above the control bar): every key, one per line. Closed until you ask for it,
// with Ctrl+Alt+K or Keys on the control bar, and main remembers your choice. It sits over your app, so it never takes a click.
import type { ShellInfo, StateMsg } from "../../shared/messages";
import { el, esc, kc } from "../dom";

export class HotkeyPanel {
  private panel?: HTMLDivElement;
  private info?: ShellInfo;
  private state?: StateMsg;
  private railOpen = false;

  constructor(private layer: HTMLElement) {}

  get open() { return !!this.info?.keyBar; }
  setInfo(info: ShellInfo) { this.info = info; this.draw(); }
  setState(s: StateMsg) { this.state = s; this.draw(); }
  setRail(open: boolean) { this.railOpen = open; this.draw(); }

  private draw() {
    this.panel?.remove();
    this.panel = undefined;
    const s = this.state, info = this.info;
    if (!s || !info?.keyBar || s.hidden || s.finished) return;
    const rows = info.keys.map(k =>
      `<div class="k${k.taken ? " taken" : ""}"${k.taken ? ` title="Another app holds this key"` : ""}>${kc(k.key, "sm")}<span>${esc(k.label)}</span></div>`).join("");
    this.panel = el(this.layer, `keypanel${this.railOpen ? " beside" : ""}`, "", `<div class="mods">Ctrl + Alt +</div>${rows}`);
    // Not for screen readers or the checks that read the overlay: the same actions are on the control bar.
    this.panel.setAttribute("aria-hidden", "true");
  }
}
