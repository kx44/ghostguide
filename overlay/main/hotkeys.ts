// Global hotkeys: the overlay never has focus, so these must be system-wide. Plain H / S would eat typing
// in the app, hence Ctrl+Alt. Do it for me has no key on purpose: acting on your app takes a deliberate click.
import { globalShortcut } from "electron";
import type { FromOverlay, KeyHint } from "../shared/messages";
import { cursorPhysical } from "./displays";

type Local = "quit" | "import" | "source" | "keybar";
export interface Hotkey { accel: string; what: string; bar?: string; dev?: boolean; msg: (hidden: boolean) => FromOverlay | Local }

export const HOTKEYS: Hotkey[] = [
  { accel: "Control+Alt+Right", what: "next", bar: "Next step", msg: () => ({ type: "next" }) },
  { accel: "Control+Alt+Left", what: "back", bar: "Back", msg: () => ({ type: "back" }) },
  { accel: "Control+Alt+S", what: "skip", bar: "Skip", msg: () => ({ type: "skip" }) },
  { accel: "Control+Alt+G", what: "show me (G for guide)", bar: "Show me", msg: () => ({ type: "show_me" }) },
  { accel: "Control+Alt+O", what: "this step in the original tutorial", bar: "Source", msg: () => "source" },
  { accel: "Control+Alt+H", what: "hide / resume", bar: "Hide / resume", msg: hidden => ({ type: hidden ? "resume" : "hide" }) },
  { accel: "Control+Alt+D", what: "light / dark, or back to automatic", bar: "Light / dark", msg: () => ({ type: "toggle_scheme" }) },
  { accel: "Control+Alt+I", what: "import a tutorial", bar: "Import a tutorial", msg: () => "import" },
  { accel: "Control+Alt+K", what: "show / hide the shortcuts", bar: "These shortcuts", msg: () => "keybar" },
  { accel: "Control+Alt+Q", what: "end the tutorial and quit", bar: "End", msg: () => "quit" },
  { accel: "Control+Alt+P", what: "pin a corner under the mouse", dev: true, msg: () => ({ type: "pin", at: cursorPhysical() }) },
  { accel: "Control+Alt+U", what: "remove this step's pin", dev: true, msg: () => ({ type: "unpin" }) },
];

/** The keys a person gets: the pin keys only for development, so they aren't taken from other apps. */
export const activeHotkeys = (dev: boolean) => HOTKEYS.filter(h => dev || !h.dev);

const KEY_NAMES: Record<string, string> = { Right: "→", Left: "←" };
export const keyName = (accel: string) => { const k = accel.split("+").pop()!; return KEY_NAMES[k] ?? k; };

/** What the shortcut bar shows. A key another app holds is marked rather than left out. */
export const keyHints = (failed: string[]): KeyHint[] =>
  HOTKEYS.filter(h => h.bar).map(h => ({ key: keyName(h.accel), label: h.bar!, taken: failed.includes(h.accel) }));

export interface HotkeyActions { send(m: FromOverlay): void; quit(): void; openImport(): void; toggleSource(): void; toggleKeyBar(): void }

export function registerHotkeys(isHidden: () => boolean, a: HotkeyActions, dev: boolean): string[] {
  const failed: string[] = [];
  for (const h of activeHotkeys(dev)) {
    const ok = globalShortcut.register(h.accel, () => {
      const m = h.msg(isHidden());
      if (m === "quit") a.quit();
      else if (m === "import") a.openImport();
      else if (m === "source") a.toggleSource();
      else if (m === "keybar") a.toggleKeyBar();
      else a.send(m);
    });
    if (!ok) failed.push(h.accel);     // taken by another app
  }
  return failed;
}

export function unregisterHotkeys() { globalShortcut.unregisterAll(); }
