// What the person chose, kept between runs: only whether the shortcut bar shows, for now.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export interface Settings { keyBar: boolean }
const DEFAULTS: Settings = { keyBar: true };

/** Anything missing or unreadable is the default: a bad settings file must never stop the overlay. */
export function parseSettings(text: string | undefined): Settings {
  try {
    const d = JSON.parse(text ?? "{}");
    return { keyBar: typeof d?.keyBar === "boolean" ? d.keyBar : DEFAULTS.keyBar };
  } catch {
    return { ...DEFAULTS };
  }
}

export function loadSettings(path: string): Settings {
  try {
    return parseSettings(readFileSync(path, "utf-8"));
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(path: string, s: Settings): void {
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(s, null, 1), "utf-8");
  } catch (e) {
    console.warn("couldn't save settings", e);
  }
}
