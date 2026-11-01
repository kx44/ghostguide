# The base file

Every source (video, web page, text) is compiled into one Markdown file per tutorial, and the live player only ever reads that file. It describes intent: what to do, which control, what success looks like. It never holds screen positions, because your copy of the app is mapped onto it at run time.

You can write one by hand, or fix what the compiler wrote. `python -m engine validate <file>` checks it, and a file that fails won't play.

## Layout

YAML frontmatter, optional `# Part …` headings, then a `## Step N — title` heading and one YAML block per step. Any other text outside those blocks is refused, so nothing is lost silently when a file is rewritten.

````md
---
title: Titanium camping mug
app: SOLIDWORKS
author_version: "2016"
source: {type: web, url: "https://example.com/mug"}
start_state: SOLIDWORKS open, no document
units: mm
---
## Step 1 — New part
```yaml
action: click
target: {label: New, kind: button, where: "top toolbar, left", shortcut: Ctrl+N}
why: "Every part starts from a new document."
check: "The New SOLIDWORKS Document dialog is open"
verify: {uia: {name: New SOLIDWORKS Document, type: Window}}
source: {anchor: "#step-1"}
confidence: high
```
````

## Frontmatter

| Field | Meaning |
|---|---|
| `title`, `app` | Required. `app` picks the app map and helps find the window: it needn't be in the title, and when nothing goes by that name you choose the window once |
| `author_version` | The version the source used |
| `source` | `type` (video, web, pdf, text), `url` (a web link), `hash`, and for a video `segment: "01:28-10:25"` |
| `start_state` | What must be true before step 1. Short, comma-separated items become a checklist |
| `units` | mm, px… |

## A step

| Field | Meaning |
|---|---|
| `app` | The program this step happens in, when it isn't the tutorial's `app`. The finder, the checks and Do it for me all follow it |
| `action` | `click`, `draw_line`, `drag`, `type`, `shortcut`, `pick`, `menu_path`, `switch_app`, `wait`, `look`. This decides how it's drawn |
| `target.label` | The visible text or tooltip name |
| `target.kind` | `button`, `tab`, `menu_item`, `field`, `tree_item`, `face`, `edge`, `canvas`, `window` |
| `target.where` | The region in plain words: "Features tab, CommandManager" |
| `target.menu_path`, `aliases`, `shortcut` | The route if it's hidden, other names across versions, a shortcut |
| `params` | Depends on the action: `value`, `then_key`, `keys`, `click_type`, `from`, `to`, `length`, `signals`, `suggested` |
| `why` | Plain words: what this does and why. Shown on the card |
| `check` | What's true when it's done, in words a person or a model can judge |
| `verify` | The same fact in a form the engine can test for free (below) |
| `source` | `t: "01:39-01:44"` for a video, or `anchor: "#section"` for a page. It's what the source window opens |
| `confidence` | `high`, `low` or `inferred`. Not `high` shows an "unsure" tag on the card |
| `repeat_of`, `optional`, `simplified`, `note` | A repeat gets a lighter guide; a step may be left out; we took a shorter route than the author; a remark |

`suggested` holds a value the source leaves open, such as a dimension. The card labels it as ours, never as what the tutorial says.

## One step, one change

Each step is one change you can check on screen. That's what lets a step move on by itself.

## `verify`

Every listed fact must hold.

```yaml
verify: {uia: {name_contains: index.html, type: TabItem, selected: true}}
verify: {uia: [{name: New SOLIDWORKS Document, type: Window, exists: false},
               {name_contains: Part, type: Window, window: SOLIDWORKS}]}
verify: {file: {path: index.html, contains: 'class="video-details"'}}
```

- **`uia`** reads Windows UI Automation: `name` (exact) or `name_contains`, `type`, `value` or `value_contains`, `window`, `selected`, `exists`. It needs at least one of name, name_contains and type.
- **`file`** reads a file on disk: `path` relative to the tutorial's working folder (no absolute paths, no `..`), `contains`, `not_contains`, `exists`.

A fact that was already true before the step showed doesn't count as proof, unless you clicked the step's target during it.
