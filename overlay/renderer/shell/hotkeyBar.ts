// The shortcut bar (primary display, bottom left): every key at a glance. It never takes a click except on its own ×,
// because it sits over your app, and main remembers when you hide it.
import type { ShellInfo, StateMsg } from "../../shared/messages";
import { el, esc, kc } from "../dom";

export class HotkeyBar {
  private bar?: HTMLDivElement;
  private info?: ShellInfo;
  private state?: StateMsg;

  constructor(private layer: HTMLElement, private setShown: (show: boolean) => void) {}

  setInfo(info: ShellInfo) { this.info = info; this.draw(); }
  setState(s: StateMsg) { this.state = s; this.draw(); }

  private draw() {
    this.bar?.remove();
    this.bar = undefined;
    const s = this.state, info = this.info;
    if (!s || !info?.keyBar || s.hidden || s.finished) return;
    const keys = info.keys.map(k =>
      `<span class="k${k.taken ? " taken" : ""}"${k.taken ? ` title="Another app holds this key"` : ""}>${kc(k.key, "sm")}${esc(k.label)}</span>`).join("");
    // Not for screen readers or the checks that read the overlay: the same actions are on the control bar.
    this.bar = el(this.layer, "keybar", "", `<span class="mods">Ctrl + Alt +</span>${keys}<button class="x hit" title="Hide these (Ctrl+Alt+K)">×</button>`);
    this.bar.setAttribute("aria-hidden", "true");
    this.bar.querySelector("button")!.addEventListener("click", () => this.setShown(false));
  }
}
