---
title: How To Design A YouTube Clone With HTML/CSS (first ~10 min)
app: Visual Studio Code
author_version: "VS Code, Oct 2020"
source: {type: video, url: "https://www.youtube.com/watch?v=rhPSo4_Tgi0", author: Web Dev Simplified (Kyle), published: 2020-10-04,
         segment: "01:28-10:25", chapters: ["Video Section HTML 01:28", "Videos Section CSS 06:26"], hash: TBD}
start_state: >
  VS Code (dark theme) snapped left, Chrome snapped right. Folder youtube-clone open with apps.svg, bell.svg,
  logo.png, magnify.svg, video-plus.svg. Live Server extension installed and already running (status bar "Port : 5501").
verified: 2026-10-30, against frames from the downloaded clip (code, file creation, Live Server, layout)
units: px/rem
gold: true
notes: >
  Ends at 10:25, when the duration badge is styled: a natural "it works" moment.
  Risks: unsplash.it placeholder URLs may no longer resolve (swap for picsum.photos if so; mark as a version difference).
  Code values checked against the video frames (img tags self-close with " />"; Google Fonts URL read off screen).
---

# Part A — HTML for one video card (01:28–06:26)

## Step 1 — New file
```yaml
action: click
target: {label: New File, kind: button, where: "Explorer, YOUTUBE-CLONE folder header (icons appear on hover)"}
why: "Start the page."
check: "Inline filename box in Explorer"
source: {t: "01:39-01:41"}
confidence: high   # seen in frames
```
## Step 2 — Name it index.html
```yaml
action: type
target: {label: filename box, kind: field, where: "Explorer, new file row"}
params: {value: "index.html", then_key: Enter}
check: "index.html open in editor"
source: {t: "01:39-01:44"}
confidence: high
```
## Step 3 — Emmet boilerplate
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, line 1"}
params: {value: "!", then_key: Tab}
why: "Emmet expands ! into a full HTML skeleton."
check: "Document has <!DOCTYPE html>, <head>, <body>"
source: {t: "01:44-01:49"}
confidence: high
```
## Step 4 — Videos wrapper, section and card
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, inside <body>"}
params:
  value: |
    <div class="videos">
      <section class="video-section">
        <article class="video-container">
        </article>
      </section>
    </div>
why: "videos = whole area, video-section = a group between grey lines, video-container = one card."
check: "Markup present inside <body>"
source: {t: "01:49-02:31"}
confidence: high
```
## Step 5 — Thumbnail link and image
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, inside <article class=\"video-container\">"}
params:
  value: |
    <a href="#" class="thumbnail">
      <img class="thumbnail-image" src="http://unsplash.it/250/150?gravity=center" />
    </a>
why: "Placeholder 250×150 image; href=\"#\" since nothing is really linked."
check: "Thumbnail markup inside the article"
source: {t: "02:37-03:34"}
confidence: high
```
## Step 6 — Save
```yaml
action: shortcut
target: {label: Save, kind: button, where: "File menu"}
params: {keys: [Ctrl, S]}
check: "Tab shows no unsaved dot"
source: {t: "03:40"}
confidence: high
```
## Step 7 — Open with Live Server
```yaml
action: menu_path
target: {label: Open with Live Server, kind: menu_item, where: "Explorer, right-click index.html",
         menu_path: [index.html (right-click), Open with Live Server], shortcut: "Alt+L Alt+O"}
params: {click_type: right}
why: "Live Server reloads the browser on every save."
check: "New browser tab at 127.0.0.1:5501/index.html"
source: {t: "03:43-03:46"}
confidence: low   # frames show the new tab opening but not how; server was already running
```
## Step 8 — Wait for the page
```yaml
action: wait
target: {label: Browser, kind: window, where: "right half of screen"}
params: {signals: [new tab, page loaded]}
check: "One 250×150 image visible"
source: {t: "03:46-03:52"}
confidence: high
note: "Author works split-screen, so there's no app switch back; if the user's browser covers VS Code, add switch_app."
```
## Step 9 — Bottom section with channel icon
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, after the thumbnail </a>"}
params:
  value: |
    <div class="video-bottom-section">
      <a href="#">
        <img class="channel-icon" src="http://unsplash.it/36/36?gravity=center" />
      </a>
    </div>
why: "Two columns: channel icon left, details right. 36×36 is YouTube's icon size."
check: "Markup present; after save, a small icon under the thumbnail"
source: {t: "03:58-04:48"}
confidence: high
```
## Step 10 — Video details
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, inside .video-bottom-section after the icon link"}
params:
  value: |
    <div class="video-details">
      <a href="#" class="video-title">Video Title</a>
      <a href="#" class="video-channel-name">Channel Name</a>
      <div class="video-metadata">
        <span>12K views</span>
        •
        <span>1 week ago</span>
      </div>
    </div>
why: "Title and channel are links because they're clickable on YouTube."
check: "Markup present"
source: {t: "04:54-06:21"}
confidence: high
simplified: "Author copies the • from YouTube via DevTools (05:50-06:15); we ghost-type it directly."
```
## Step 11 — Save and check
```yaml
action: shortcut
target: {label: Save, kind: button, where: "File menu"}
params: {keys: [Ctrl, S]}
check: "Browser shows title, channel name, '12K views • 1 week ago' (unstyled)"
source: {t: "06:15-06:26"}
repeat_of: 6
```

# Part B — Start the CSS (06:26–10:25)

## Step 12 — New file
```yaml
action: click
target: {label: New File..., kind: button, where: "Explorer view header"}
check: "Inline filename box"
source: {t: "06:33"}
repeat_of: 1
```
## Step 13 — Name it styles.css
```yaml
action: type
target: {label: filename box, kind: field, where: "Explorer, new file row"}
params: {value: "styles.css", then_key: Enter}
check: "styles.css open"
source: {t: "06:33-06:39"}
repeat_of: 2
```
## Step 14 — Switch to index.html
```yaml
action: click
target: {label: index.html, kind: tab, where: "editor tab bar"}
check: "index.html active"
source: {t: "06:39"}
confidence: inferred
```
## Step 15 — Link the stylesheet and Roboto
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, inside <head>, before <title>"}
params:
  value: |
    <link rel="stylesheet" href="styles.css">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
why: "Google uses Roboto on its pages."
check: "Both <link> tags in <head>"
source: {t: "06:39-06:56"}
confidence: high   # URL read off screen at 07:00
```
## Step 16 — Switch to styles.css
```yaml
action: click
target: {label: styles.css, kind: tab, where: "editor tab bar"}
check: "styles.css active"
source: {t: "06:56"}
repeat_of: 14
```
## Step 17 — Base styles
```yaml
action: type
target: {label: Editor, kind: field, where: "styles.css, top"}
params:
  value: |
    *, *::before, *::after {
      box-sizing: border-box;
      font-family: Roboto, Arial, Helvetica, sans-serif;
    }

    body {
      margin: 0;
    }
why: "Selects every element and pseudo-element; Roboto with fallbacks."
check: "After save: page uses Roboto, no gap at page edges"
source: {t: "07:02-07:45"}
confidence: high
```
## Step 18 — Card and thumbnail layout
```yaml
action: type
target: {label: Editor, kind: field, where: "styles.css, end"}
params:
  value: |

    .video-container {
      display: flex;
      flex-direction: column;
    }

    .thumbnail {
      position: relative;
      display: flex;
    }
why: "position: relative lets the duration badge sit in the thumbnail's corner."
check: "Rules present"
source: {t: "07:45-08:29"}
confidence: high
```
## Step 19 — Switch to index.html
```yaml
action: click
target: {label: index.html, kind: tab, where: "editor tab bar"}
check: "index.html active"
source: {t: "08:29"}
repeat_of: 14
```
## Step 20 — Add the video duration
```yaml
action: type
target: {label: Editor, kind: field, where: "index.html, in <a href=\"#\" class=\"thumbnail\"> after class attribute"}
params: {value: ' data-duration="12:24"'}
why: "A data attribute CSS can read with attr()."
check: 'Thumbnail link has data-duration="12:24"'
source: {t: "08:29-08:46"}
confidence: high
```
## Step 21 — Switch to styles.css
```yaml
action: click
target: {label: styles.css, kind: tab, where: "editor tab bar"}
check: "styles.css active"
source: {t: "08:46"}
repeat_of: 14
```
## Step 22 — Duration badge
```yaml
action: type
target: {label: Editor, kind: field, where: "styles.css, end"}
params:
  value: |

    .thumbnail::before {
      content: attr(data-duration);
      position: absolute;
      background-color: rgba(0, 0, 0, .85);
      color: white;
      right: 5px;
      bottom: 5px;
      padding: .1em .3em;
      border-radius: .3em;
      font-size: .9rem;
    }
why: "Pulls 12:24 from the HTML into a dark, slightly see-through pill."
check: "Rule present"
source: {t: "08:46-10:25"}
confidence: high
```
## Step 23 — Save and see it
```yaml
action: shortcut
target: {label: Save, kind: button, where: "File menu"}
params: {keys: [Ctrl, S], then: "look at browser"}
check: "Browser: white '12:24' on a dark pill, bottom-right of the (full-width) thumbnail area"
source: {t: "10:19-10:25"}
repeat_of: 6
```
