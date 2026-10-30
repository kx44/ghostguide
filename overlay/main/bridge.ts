// Link to the engine: a WebSocket client that reconnects, or (--replay) a recorded .jsonl played back on
// its timestamps, so the overlay can be built and demoed with no engine and no model calls.
import { readFileSync } from "node:fs";
import WebSocket from "ws";
import type { FromOverlay, ToOverlay } from "../shared/messages";

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

export function replayFile(path: string, onMsg: (m: ToOverlay) => void, speed = 1, loop = false): Link {
  const lines = readFileSync(path, "utf-8").split(/\r?\n/).filter(Boolean)
    .map(l => JSON.parse(l) as { t: number; msg: ToOverlay });
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
