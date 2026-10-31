// Global hotkeys: the overlay never has focus, so these must be system-wide. Plain H / S would eat typing
// in the app, hence Ctrl+Alt.
import { globalShortcut } from "electron";
import type { FromOverlay } from "../shared/messages";
import { cursorPhysical } from "./displays";

export const HOTKEYS: { accel: string; what: string; msg: (hidden: boolean) => FromOverlay | "quit" | "import" }[] = [
  { accel: "Control+Alt+H", what: "hide / resume", msg: hidden => ({ type: hidden ? "resume" : "hide" }) },
  { accel: "Control+Alt+S", what: "skip", msg: () => ({ type: "skip" }) },
  { accel: "Control+Alt+Right", what: "next", msg: () => ({ type: "next" }) },
  { accel: "Control+Alt+Left", what: "back", msg: () => ({ type: "back" }) },
  { accel: "Control+Alt+G", what: "show me (G for guide)", msg: () => ({ type: "show_me" }) },
  { accel: "Control+Alt+P", what: "pin a corner under the mouse (dev)", msg: () => ({ type: "pin", at: cursorPhysical() }) },
  { accel: "Control+Alt+U", what: "remove this step's pin (dev)", msg: () => ({ type: "unpin" }) },
  { accel: "Control+Alt+I", what: "import a tutorial", msg: () => "import" },
  { accel: "Control+Alt+Q", what: "quit overlay", msg: () => "quit" },
];

export function registerHotkeys(isHidden: () => boolean, send: (m: FromOverlay) => void, quit: () => void, openImport: () => void): string[] {
  const failed: string[] = [];
  for (const h of HOTKEYS) {
    const ok = globalShortcut.register(h.accel, () => {
      const m = h.msg(isHidden());
      if (m === "quit") quit(); else if (m === "import") openImport(); else send(m);
    });
    if (!ok) failed.push(h.accel);     // taken by another app
  }
  return failed;
}

export function unregisterHotkeys() { globalShortcut.unregisterAll(); }
