// The source window: the step's clip, its section of the text, or why neither is on this PC. It only shows what the
// engine sends. The tutorial's words go in as text, never as HTML. The one thing that loads from the web is a picture a
// saved page didn't keep, from the address the page gives for it, with no referrer.
import type { SourceBlock, SourceBridge, SourceViewMsg } from "../../shared/messages";

declare global { interface Window { ghostSource: SourceBridge } }

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const bridge = window.ghostSource;
const player = $<HTMLVideoElement>("player");
let view: SourceViewMsg | undefined;
let doc: string | undefined;
let stopAt: number | undefined;         // pause here, unless you've moved past it yourself

function shown(id: "video" | "text" | "none") {
  for (const k of ["video", "text", "none"] as const) $(k).hidden = k !== id;
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
      p.textContent = "A picture goes here, but the site didn't send it. Open in the browser to see it.";
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
  $("note").hidden = !m.note;
  $("note").textContent = m.note ?? "";
  const pic = m.figure?.image ?? m.figure?.web_image;
  $("figure").hidden = !pic;
  if (pic && $("figureimg").getAttribute("src") !== pic) $<HTMLImageElement>("figureimg").src = pic;
  $("replay").hidden = m.kind !== "video";
  $("link").hidden = !m.link;
  $("link").textContent = m.link_label ?? "Open in the browser";
  $("link").classList.toggle("pri", m.kind === "none");
  $("choose").hidden = !m.choose;
  if (m.kind === "video") {
    shown("video");
    cue(m, !m.follow || before === undefined);
  } else {
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

$("figureimg").addEventListener("error", () => { $("figure").hidden = true; });
bridge.on(render);
$("replay").addEventListener("click", () => { if (view?.video) cue(view, true); });
$("link").addEventListener("click", () => { if (view?.link) bridge.openLink(view.link); });
$("choose").addEventListener("click", () => { if (view?.choose) bridge.choose(view.choose); });
$("close").addEventListener("click", () => bridge.close());
document.addEventListener("keydown", e => { if (e.key === "Escape") bridge.close(); });
