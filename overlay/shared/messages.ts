// Engine ⇄ overlay messages: mirror of engine/schema/messages.py (tests/test_messages.py keeps the
// lists below in sync). All coordinates are physical screen pixels; main.ts converts them to DIPs.

export const STYLES = [
  "outline", "ghost_line", "beacon", "static_line", "ghost_text", "keycaps", "mask",
  "path_chips", "offscreen", "taskbar", "click_type", "signal_card", "card",
] as const;
export type Style = (typeof STYLES)[number];
export type Scheme = "light" | "dark";

export const TO_OVERLAY = [
  "guide", "clear", "state", "toast", "show_me", "mark", "start_check", "compile_progress",
] as const;
export const FROM_OVERLAY = [
  "hello", "show_me", "do_it", "next", "back", "skip", "hide", "resume", "jump", "pin", "unpin", "import",
] as const;

export interface Box { x: number; y: number; w: number; h: number }
export type Pt = [number, number];
export interface LineSpec { from: Pt; to: Pt }

export interface ClickType { button: "left" | "right"; count: number; modifiers: string[]; label: string }

export interface GuideExtra {
  action?: string;
  label?: string;
  click_type?: ClickType;
  value?: string;
  multiline?: boolean;
  then_key?: string;
  keys?: string[];
  path?: string[];
  path_done?: number;
  shortcut?: string;
  signals?: string[];
  app?: string;
  pill?: string;
  edge_point?: Pt;
  direction?: "left" | "right" | "up" | "down";
  original_style?: Style;
  [k: string]: unknown;
}

export interface Card {
  meta: string;
  title: string;
  why?: string;
  detail?: string;
  done_when?: string;
  suggested?: string;
  actions: string[];          // show_me | do_it | next | skip_wait
  low_confidence?: boolean;
  dev_hint?: string;          // phase 2: how to pin this step's target
}

export interface StepInfo { n: number; of: number; title: string; part?: string; source_t?: string; confidence?: string }

export interface GuideMsg {
  type: "guide";
  step: StepInfo;
  style: Style;
  scheme: Scheme;
  box?: Box;
  line?: LineSpec;
  extra: GuideExtra;
  card?: Card;
}
export interface ClearMsg { type: "clear"; reason?: string }
export type StepStatus = "pending" | "done" | "skipped";
export interface StateMsg {
  type: "state"; tutorial: string; current: number; of: number; hidden: boolean; finished: boolean;
  titles: string[]; statuses: StepStatus[]; scheme: Scheme;
}
export interface ToastMsg { type: "toast"; text: string; kind: "ok" | "warn"; ms: number }
export interface ShowMeMsg { type: "show_me"; to: Pt; path?: Pt[]; click: "left" | "right" | "double" | "none" }
export interface MarkMsg { type: "mark"; result: "ok" | "bad" }
export interface StartCheckMsg { type: "start_check"; items: string[] }
export interface CompileProgressMsg { type: "compile_progress"; stage: string; pct: number }

export type ToOverlay = GuideMsg | ClearMsg | StateMsg | ToastMsg | ShowMeMsg | MarkMsg | StartCheckMsg | CompileProgressMsg;

export interface DisplayInfo { id: number | string; x: number; y: number; w: number; h: number; scale: number; primary: boolean }
export type FromOverlay =
  | { type: "hello"; displays: DisplayInfo[]; version?: string; replay?: boolean }
  | { type: "show_me" | "do_it" | "next" | "back" | "skip" | "hide" | "resume" | "unpin" }
  | { type: "pin"; at: Pt }
  | { type: "jump"; n: number }
  | { type: "import"; url?: string; file?: string };

// What main.ts hands a display's renderer: the message plus the same geometry in that window's DIPs.
export interface Local {
  box?: Box;
  line?: LineSpec;
  edge_point?: Pt;
  to?: Pt;
  path?: Pt[];
}
export interface Routed { msg: ToOverlay; local: Local; primary: boolean; display: { w: number; h: number } }

// The bridge exposed by preload.ts as window.ghost.
export interface GhostBridge {
  on(cb: (r: Routed) => void): void;
  send(msg: FromOverlay): void;
  setInteractive(on: boolean): void;
}
