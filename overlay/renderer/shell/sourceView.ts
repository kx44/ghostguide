// The source window: the step's clip, its section of the text, or why neither is on this PC. It only shows what the
// engine sends. The tutorial's words go in as text, never as HTML. The one thing that loads from the web is a picture a
// saved page didn't keep, from the address the page gives for it, with no referrer. A web tutorial's real page is what shows
// first, drawn by the main process over #pagearea; this text is the fallback when the page won't load, or when you ask for it.
import type { SourceBlock, SourceBridge, SourceViewMsg } from "../../shared/messages";

declare global { interface Window { ghostSource: SourceBridge } }

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const bridge = window.ghostSource;
const player = $<HTMLVideoElement>("player");
let view: SourceViewMsg | undefined;
let doc: string | undefined;
let stopAt: number | undefined;         // pause here, unless you've moved past it yourself

let useCopy = false;                    // our copy of the text: you asked for it, or the page wouldn't load
let pageFailed = false;

function shown(id: "video" | "text" | "none" | "pagearea") {
  for (const k of ["video", "text", "none", "pagearea"] as const) $(k).hidden = k !== id;
  if (id === "pagearea") reportArea();
}

function reportArea() {
  const r = $("pagearea").getBoundingClientRect();
  if (r.width && r.height) bridge.pageArea({ x: r.left, y: r.top, width: r.width, height: r.height });
}

function cue(m: SourceViewMsg, play: boolean) {
  const start = m.start ?? 0;
  stopAt = m.end;
  const go = () => {
    player.currentTime = start;
    if (play) void player.play().catch(() => {});     // the controls still work if autoplay is refused
    else player.pause();
  };
  if (player.getAttribute("src") !== m.video) {
    player.setAttribute("src", m.video!);
    player.addEventListener("loadedmetadata", go, { once: true });
  } else go();
}

player.addEventListener("timeupdate", () => {
  if (stopAt !== undefined && player.currentTime >= stopAt) { player.pause(); stopAt = undefined; }
});
player.addEventListener("seeking", () => {
  if (stopAt !== undefined && player.currentTime > stopAt + 0.5) stopAt = undefined;
});

function block(b: SourceBlock): HTMLElement {
  if (b.kind === "image" && (b.image || b.web_image)) {
    const img = document.createElement("img");
    img.referrerPolicy = "no-referrer";
    img.src = (b.image ?? b.web_image)!;
    img.alt = b.text;
    img.addEventListener("error", () => {
      const p = document.createElement("p");
      p.textContent = "A picture goes here, but the site didn't send it. It's on the page itself.";
      img.replaceWith(p);
    }, { once: true });
    return img;
  }
  const e = document.createElement(b.kind === "heading" ? "h2" : "p");
  e.textContent = b.text;
  return e;
}

/** The whole text, one group per section, so the section you're on can be marked. */
function renderText(blocks: SourceBlock[]) {
  const box = $("text");
  box.textContent = "";
  let sec: HTMLElement | undefined, at: string | undefined;
  for (const b of blocks) {
    if (!sec || b.anchor !== at) {
      sec = document.createElement("div");
      sec.className = "sec";
      sec.dataset.anchor = b.anchor ?? "";
      box.append(sec);
      at = b.anchor;
    }
    sec.append(block(b));
  }
}

function markSection(anchor: string | undefined) {
  const box = $("text");
  let first: HTMLElement | undefined;
  box.querySelectorAll<HTMLElement>(".sec").forEach(s => {
    const here = !!anchor && s.dataset.anchor === anchor;
    s.classList.toggle("here", here);
    if (here && !first) first = s;
  });
  if (first) first.scrollIntoView({ block: "start" });
}

function render(m: SourceViewMsg) {
  const before = view;
  view = m;
  $("meta").textContent = `Step ${m.n} of ${m.of} · ${m.tutorial}`;
  $("title").textContent = m.title;
  $("where").hidden = !m.where;
  $("where").textContent = m.where ?? "";
  const note = pageFailed && useCopy ? "The page didn't load, so this is our copy of its text." : m.note;
  $("note").hidden = !note;
  $("note").textContent = note ?? "";
  $("replay").hidden = m.kind !== "video";
  const realPage = !!m.page && m.kind !== "video" && !useCopy;
  $("page").hidden = !m.page || realPage;
  $("copy").hidden = !realPage;
  $("link").hidden = !m.link;
  $("link").textContent = m.link_label ?? "Open in the browser";
  $("link").classList.toggle("pri", m.kind === "none");
  $("choose").hidden = !m.choose;
  $("choose").textContent = m.choose === "video" ? "Choose the video file…" : "Choose a saved copy…";
  if (realPage) {
    player.pause();
    shown("pagearea");
    bridge.showPage(m.page!, m.section, m.words);
  } else if (m.kind === "video") {
    bridge.hidePage();
    shown("video");
    cue(m, !m.follow || before === undefined);
  } else {
    bridge.hidePage();
    player.pause();
    if (m.kind === "text") {
      shown("text");
      if (m.doc !== doc || !$("text").childElementCount) { renderText(m.blocks ?? []); doc = m.doc; }
      markSection(m.anchor);
    } else {
      shown("none");
      $("message").textContent = m.message ?? "";
    }
  }
}

bridge.on(render);
$("replay").addEventListener("click", () => { if (view?.video) cue(view, true); });
$("page").addEventListener("click", () => { useCopy = false; pageFailed = false; if (view) render(view); });
$("copy").addEventListener("click", () => { useCopy = true; if (view) render(view); });
bridge.onPage(state => {
  if (state === "failed") { useCopy = true; pageFailed = true; if (view) render(view); }
});
new ResizeObserver(reportArea).observe($("pagearea"));
$("link").addEventListener("click", () => { if (view?.link) bridge.openLink(view.link); });
$("choose").addEventListener("click", () => { if (view?.choose) bridge.choose(view.choose); });
$("close").addEventListener("click", () => bridge.close());
document.addEventListener("keydown", e => { if (e.key === "Escape") bridge.close(); });
