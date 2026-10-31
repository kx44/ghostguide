// Link to the engine: a WebSocket client that reconnects, or (--replay) a recorded .jsonl, so the overlay
// can be checked with no engine and no model calls.
//
// Replay is step by step by default: it shows one recorded step and waits. Next / Skip (bar, card or
// hotkey) go forward, Back goes back, Show me plays that step's recorded Show me, Hide / Resume work.
// `--timed` plays the file on its timestamps instead (hands-off demo).
import { readFileSync } from "node:fs";
import WebSocket from "ws";
import type { FromOverlay, StateMsg, ToOverlay } from "../shared/messages";

export interface Link {
  send(msg: FromOverlay): void;
  close(): void;
}

export function connectEngine(url: string, onMsg: (m: ToOverlay) => void, onOpen: () => void,
                              onStatus: (connected: boolean) => void): Link {
  let ws: WebSocket | undefined;
  let closed = false;
  let timer: NodeJS.Timeout | undefined;
  const open = () => {
    ws = new WebSocket(url);
    ws.on("open", () => { onStatus(true); onOpen(); });
    ws.on("message", data => {
      try { onMsg(JSON.parse(String(data)) as ToOverlay); } catch (e) { console.error("bad message from engine", e); }
    });
    ws.on("close", () => { onStatus(false); if (!closed) timer = setTimeout(open, 1000); });
    ws.on("error", () => { /* close follows; we retry every second */ });
  };
  open();
  return {
    send(msg) { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); },
    close() { closed = true; if (timer) clearTimeout(timer); ws?.close(); },
  };
}

function readLines(path: string) {
  return readFileSync(path, "utf-8").split(/\r?\n/).filter(Boolean).map(l => JSON.parse(l) as { t: number; msg: ToOverlay });
}

export function replayTimed(path: string, onMsg: (m: ToOverlay) => void, speed = 1, loop = false): Link {
  const lines = readLines(path);
  let timers: NodeJS.Timeout[] = [];
  const run = () => {
    timers = lines.map(({ t, msg }) => setTimeout(() => onMsg(msg), t / speed));
    if (loop && lines.length) timers.push(setTimeout(run, lines[lines.length - 1].t / speed + 3000));
  };
  run();
  return {
    send(msg) { console.log("[replay] overlay →", JSON.stringify(msg)); },
    close() { timers.forEach(clearTimeout); },
  };
}

/** One recorded step: the state + guide that drew it, and its Show me if one was recorded. */
interface Frame { state: StateMsg; guide: ToOverlay; showMe?: ToOverlay }

export function replaySteps(path: string, onMsg: (m: ToOverlay) => void): Link {
  const frames: Frame[] = [];
  let state: StateMsg | undefined, finished: ToOverlay[] = [];
  for (const { msg } of readLines(path)) {
    if (msg.type === "state") state = msg;
    else if (msg.type === "guide" && state) frames.push({ state, guide: msg });
    else if (msg.type === "show_me" && frames.length) frames[frames.length - 1].showMe = msg;
    else if (msg.type === "clear" && state?.finished) finished = [state, msg];
  }
  let i = 0, hidden = false;
  const statuses = frames.map(() => "pending" as StateMsg["statuses"][number]);
  const show = (toast?: string) => {
    if (i >= frames.length) {
      finished.forEach(onMsg);
      onMsg({ type: "toast", text: "✓ End of the recording. Back to go back.", kind: "ok", ms: 3000 });
      return;
    }
    const f = frames[i];
    onMsg({ ...f.state, current: i + 1, hidden, finished: false, statuses: [...statuses] });
    onMsg(hidden ? { type: "clear", reason: "hidden" } : f.guide);
    if (toast) onMsg({ type: "toast", text: toast, kind: "warn", ms: 2000 });
  };
  show();
  return {
    send(msg) {
      console.log("[replay] overlay →", JSON.stringify(msg));
      switch (msg.type) {
        case "next": if (i < frames.length) { statuses[i] = "done"; onMsg({ type: "mark", result: "ok" }); i++; show(); } break;
        case "skip": if (i < frames.length) { statuses[i] = "skipped"; i++; show(`Skipped step ${i}. It stays marked in the step list.`); } break;
        case "back": if (i > 0) { i--; show(); } break;
        case "jump": if (msg.n >= 1 && msg.n <= frames.length) { i = msg.n - 1; show(); } break;
        case "hide": hidden = true; show(); break;
        case "resume": hidden = false; show(); break;
        case "show_me": { const sm = frames[i]?.showMe; if (sm && !hidden) onMsg(sm); break; }
        case "hello": break;
        case "source": if (!msg.follow) onMsg({ type: "toast", text: "The source needs the engine (replay only plays the recording).", kind: "warn", ms: 2000 }); break;
        default: onMsg({ type: "toast", text: `${msg.type} needs the engine (replay only plays the recording).`, kind: "warn", ms: 2000 });
      }
    },
    close() {},
  };
}
