// What marks a step on the tutorial's real page. It changes nothing on the page: the browser's highlight ranges draw over the
// text, and no element is added, moved or hidden. Going by words, so it's a best guess: words that aren't there mark nothing.

export const MARK_CSS = "::highlight(ghost-section){background-color:rgba(167,139,250,.16)}" +
  "::highlight(ghost-word){background-color:rgba(124,58,237,.42)}";

/** Pure, and run in the page: the section whose heading says `section`, tinted, and `words` in order inside it. */
function mark(section: string | null, words: string[]) {
  const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLowerCase();
  const highlights = (CSS as unknown as { highlights: Map<string, unknown> }).highlights;
  highlights.delete("ghost-section");
  highlights.delete("ghost-word");
  const want = section ? norm(section) : "";
  const heads = [...document.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5")];
  const at = want ? heads.findIndex(h => { const t = norm(h.textContent ?? ""); return !!t && (t === want || t.includes(want) || (t.length > 8 && want.includes(t))); }) : -1;
  if (at < 0) return { section: false, words: 0 };
  const head = heads[at];
  const level = Number(head.tagName[1]);
  const next = heads.slice(at + 1).find(h => Number(h.tagName[1]) <= level);
  const range = document.createRange();
  range.setStartBefore(head);
  if (next) range.setEndBefore(next);
  else range.setEndAfter(document.body.lastChild ?? document.body);
  const Hl = (window as unknown as { Highlight: new (...r: Range[]) => unknown }).Highlight;
  highlights.set("ghost-section", new Hl(range));

  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  for (let n = walk.nextNode(); n; n = walk.nextNode()) if (range.intersectsNode(n) && n.textContent?.trim()) texts.push(n as Text);
  const found: Range[] = [];
  let i = 0, from = 0;                       // each word is looked for after the one before: "View Orientation", then its "Front"
  for (const word of words) {
    const re = new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    for (let j = i, start = from; j < texts.length; j++, start = 0) {
      const hit = re.exec(texts[j].data.slice(start));
      if (hit) {
        const r = document.createRange();
        r.setStart(texts[j], start + hit.index);
        r.setEnd(texts[j], start + hit.index + hit[0].length);
        found.push(r);
        i = j;
        from = start + hit.index + hit[0].length;
        break;
      }
    }
  }
  if (found.length) highlights.set("ghost-word", new Hl(...found));
  const first = found[0]?.startContainer.parentElement;
  (first ?? head).scrollIntoView({ block: first ? "center" : "start" });
  return { section: true, words: found.length };
}

export const markScript = (section: string | undefined, words: string[] = []) =>
  `(${mark.toString()})(${JSON.stringify(section ?? null)}, ${JSON.stringify(words)})`;
