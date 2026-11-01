// Engine ⇄ overlay messages: mirror of engine/schema/messages.py (tests/test_messages.py keeps the
// lists below in sync). All coordinates are physical screen pixels; main.ts converts them to DIPs.

export const STYLES = [
  "outline", "ghost_line", "beacon", "static_line", "code_card", "ghost_text", "keycaps", "mask",
  "path_chips", "offscreen", "taskbar", "click_type", "signal_card", "card",
] as const;
export type Style = (typeof STYLES)[number];
export type Scheme = "light" | "dark";

export const TO_OVERLAY = [
  "guide", "clear", "state", "toast", "show_me", "mark", "start_check", "compile_progress", "compile_done",
  "source_view",
] as const;
export const FROM_OVERLAY = [
  "hello", "show_me", "do_it", "next", "back", "skip", "hide", "resume", "jump", "pin", "unpin", "import", "open_tutorial", "start_ok", "use_window",
  "source", "source_file", "toggle_scheme", "toggle_local", "end",
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
  clip?: Box;          // ghost text in an editor: its visible area (physical px), to clip to
  backing?: string;    // …its background colour, for a solid backing over the code already there
  line_h?: number;     // …its line height (physical px), so multi-line code lines up with its lines
  col?: number;        // …a mid-line insert starts at this character column
  insert?: "line" | "before" | "col" | "end";   // type on the line / new lines go before it / mid-line / after the last code
  scroll?: "up" | "down";   // the spot is scrolled out of the editor's view
  context_before?: string;  // code just before the spot, shown in the code box in purple (not copied)
  context_after?: string;   // code just after it, for a mid-line insert
  avoid?: Box[];       // where you're about to work (the code's lines, an opening menu): the card keeps off them
  route?: { path?: string[]; shortcut?: string };   // the target isn't on screen: how to get there
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
  dev_hint?: string;          // dev pins: how to pin this step's target
  compact?: boolean;          // repeat steps: title + Up next + Next only
  up_next?: string;           // the next step's title (compact cards)
  confirm?: boolean;          // Do it for me is waiting for its second press
  source?: string;            // the source button's words: "▶ 01:40" for a clip, "Source" for text
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
  titles: string[]; statuses: StepStatus[]; scheme: Scheme; local_only?: boolean; privacy?: string;
}
export interface ToastMsg { type: "toast"; text: string; kind: "ok" | "warn"; ms: number }
export interface ShowMeMsg { type: "show_me"; to: Pt; path?: Pt[]; click: "left" | "right" | "double" | "none" }
export interface MarkMsg { type: "mark"; result: "ok" | "bad" }
export interface StartCheckMsg { type: "start_check"; tutorial: string; items: { text: string; ok?: boolean; use_window?: boolean }[] }
export interface CompileProgressMsg { type: "compile_progress"; stage: string; pct: number }
export interface CompileDoneMsg {
  type: "compile_done"; ok: boolean; path?: string; title?: string; steps?: number; cached?: boolean; cost_usd?: number;
  score?: string[]; warnings?: string[]; error?: string; blocked?: boolean;
}

export interface SourceBlock { kind: "heading" | "text" | "image"; text: string; anchor?: string; image?: string; web_image?: string }
export interface SourceViewMsg {
  type: "source_view"; kind: "video" | "text" | "none" | "loading"; n: number; of: number; title: string; tutorial: string;
  follow?: boolean;        // the step moved on while the window is open: no window of its own, no autoplay
  where?: string;          // "01:39–01:44", or the section's heading
  video?: string;          // file:// address
  start?: number;          // seconds in that file
  end?: number;
  doc?: string;            // which text this is, so the window keeps it when only the section changes
  blocks?: SourceBlock[];
  anchor?: string;
  note?: string;
  message?: string;        // why the source isn't here
  link?: string;           // http(s) only
  link_label?: string;
  choose?: "video" | "page";
}

export type ToOverlay = GuideMsg | ClearMsg | StateMsg | ToastMsg | ShowMeMsg | MarkMsg | StartCheckMsg | CompileProgressMsg | CompileDoneMsg | SourceViewMsg;

export interface DisplayInfo { id: number | string; x: number; y: number; w: number; h: number; scale: number; primary: boolean }
export type FromOverlay =
  | { type: "hello"; displays: DisplayInfo[]; version?: string; replay?: boolean }
  | { type: "show_me" | "do_it" | "next" | "back" | "skip" | "hide" | "resume" | "unpin" | "start_ok" | "use_window" | "toggle_scheme" | "toggle_local" | "end" }
  | { type: "pin"; at: Pt }
  | { type: "jump"; n: number }
  | { type: "import"; url?: string; file?: string; text?: string; start?: string; end?: string }
  | { type: "open_tutorial"; path: string }
  | { type: "source"; follow?: boolean }
  | { type: "source_file"; path: string };

// What main.ts hands a display's renderer: the message plus the same geometry in that window's DIPs.
export interface Local {
  box?: Box;
  clip?: Box;          // ghost text: the editor's visible area (from extra.clip), this window's DIPs
  avoid?: Box[];       // extra.avoid in this window's DIPs
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
  /** Where this window's cards and buttons are (window DIPs); main makes only these clickable. */
  setHitRects(rects: HitRect[]): void;
  /** Put text on the clipboard (main process: this window never has focus, so the page can't). */
  copy(text: string): void;
  /** Open the source window for this step, or close it if it's open. */
  toggleSource(): void;
  /** The shortcuts panel: what it shows, and whether it's wanted. Main keeps the choice. */
  onShell(cb: (s: ShellInfo) => void): void;
  setKeyBar(show: boolean): void;
}
export interface HitRect { x: number; y: number; w: number; h: number }
export interface KeyHint { key: string; label: string; taken: boolean }
export interface ShellInfo { keyBar: boolean; keys: KeyHint[] }

// The bridge exposed by sourcePreload.ts as window.ghostSource (the source window: a normal window, opened without focus).
export interface SourceBridge {
  on(cb: (m: SourceViewMsg) => void): void;
  loadPictures(url: string): Promise<void>;
  openLink(url: string): void;
  choose(kind: "video" | "page"): void;
  close(): void;
}

// The bridge exposed by importPreload.ts as window.ghostImport (the import window, the one window that takes focus).
export interface ImportBridge {
  on(cb: (m: CompileProgressMsg | CompileDoneMsg) => void): void;
  send(msg: FromOverlay): void;
  pickFile(): Promise<string | undefined>;
  pathOf(file: File): string;
  close(): void;
}
