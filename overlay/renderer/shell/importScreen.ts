// The import window: a link, a dropped file or pasted text → compile, with progress and the score → Play.
// It's a normal window, because the overlay's own windows never take focus and you couldn't type into them.
import type { CompileDoneMsg, CompileProgressMsg, ImportBridge } from "../../shared/messages";

declare global { interface Window { ghostImport: ImportBridge } }

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const bridge = window.ghostImport;
let chosen: string | undefined;
let compiled: string | undefined;

function show(form: boolean) {
  $("form").hidden = !form;
  $("work").hidden = form;
}

function fail(id: string, text?: string) {
  const e = $(id);
  e.hidden = !text;
  e.textContent = text ?? "";
}

function start() {
  const url = $<HTMLInputElement>("link").value.trim();
  const text = $<HTMLTextAreaElement>("text").value.trim();
  if (!url && !chosen && !text) { fail("err", "Paste a link or some text, or drop a file."); return; }
  fail("err");
  fail("err2");
  $("result").hidden = true;
  $("play").hidden = true;
  $("again").hidden = true;
  $("fill").style.width = "2%";
  $("stage").textContent = "Starting";
  show(false);
  bridge.send({ type: "import", ...(url ? { url } : chosen ? { file: chosen } : { text }),
                start: $<HTMLInputElement>("start").value.trim() || undefined,
                end: $<HTMLInputElement>("end").value.trim() || undefined });
}

function choose(path: string | undefined) {
  if (!path) return;
  chosen = path;
  $("drop").textContent = path.split(/[\\/]/).pop() ?? path;
  $<HTMLInputElement>("link").value = "";
  fail("err");
}

function progress(m: CompileProgressMsg) {
  $("fill").style.width = `${Math.round(m.pct * 100)}%`;
  $("stage").textContent = m.stage;
}

function done(m: CompileDoneMsg) {
  $("again").hidden = false;
  if (!m.ok) {
    if (m.blocked) {   // the site says no: back to the form, ready for the saved file
      show(true);
      $("again").hidden = true;
      fail("err", m.error);
      return;
    }
    $("stage").textContent = "Stopped";
    fail("err2", m.error ?? "That didn't work.");
    return;
  }
  compiled = m.path;
  $("fill").style.width = "100%";
  $("stage").textContent = m.cached ? "Already compiled: opened from the cache, for free" : `Compiled for $${(m.cost_usd ?? 0).toFixed(2)}`;
  const box = $("result");
  box.hidden = false;
  box.textContent = "";
  const title = document.createElement("b");
  title.textContent = m.title ?? "Tutorial";
  const steps = document.createElement("span");
  steps.className = "ok";
  steps.textContent = `${m.steps} steps ready`;
  box.append(title, steps);
  if (m.score?.length) {
    const score = document.createElement("div");
    score.className = "score";
    score.id = "score";
    score.textContent = m.score.join("\n");
    box.append(score);
  }
  if (m.warnings?.length) {
    const warn = document.createElement("div");
    warn.className = "score";
    warn.textContent = m.warnings.join("\n");
    box.append(warn);
  }
  $("play").hidden = false;
}

bridge.on(m => (m.type === "compile_progress" ? progress(m) : done(m)));
$("go").addEventListener("click", start);
$("close").addEventListener("click", () => bridge.close());
$("close2").addEventListener("click", () => bridge.close());
$("again").addEventListener("click", () => { chosen = undefined; $("drop").textContent = "Drop a saved web page, video or text file here, or click to choose"; show(true); });
$("play").addEventListener("click", () => {
  if (compiled) bridge.send({ type: "open_tutorial", path: compiled });
  bridge.close();
});
$("link").addEventListener("keydown", e => { if ((e as KeyboardEvent).key === "Enter") start(); });

const drop = $("drop");
drop.addEventListener("click", async () => choose(await bridge.pickFile()));
for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); });
for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); });
drop.addEventListener("drop", e => {
  const f = (e as DragEvent).dataTransfer?.files[0];
  if (f) choose(bridge.pathOf(f));
});
// A file dropped anywhere else mustn't navigate the window away.
for (const ev of ["dragover", "drop"]) document.addEventListener(ev, e => e.preventDefault());
