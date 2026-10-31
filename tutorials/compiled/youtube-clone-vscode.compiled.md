---
title: How To Design A YouTube Clone With HTML/CSS
app: Visual Studio Code
author_version: '2020'
source:
  type: video
  url: https://www.youtube.com/watch?v=rhPSo4_Tgi0
  hash: 51c026032b0046fd
  author: Web Dev Simplified
  published: '2020-10-03'
  segment: 01:28-10:25
start_state: YOUTUBE-CLONE folder open in Visual Studio Code containing apps.svg, bell.svg, logo.png, magnify.svg,
  video-plus.svg
compiled:
  model: muse-spark-1.3
  prompts: e729c706c779
---

# Create video markup

## Step 1 — Create new file
```yaml
action: click
target:
  label: New File
  kind: button
  where: Explorer panel header in Visual Studio Code
check: file name input appears
source:
  t: 01:40-01:40
confidence: high
```
## Step 2 — Name file index.html
```yaml
action: type
target:
  label: File name field
  kind: field
  where: Explorer panel in Visual Studio Code
params:
  then_key: Enter
  value: index.html
why: Gives the page the standard homepage name, so it opens as a website in the browser preview.
check: index.html appears in OPEN EDITORS and YOUTUBE-CLONE folder
verify:
  uia:
    name: index.html
    type: TreeItem
    exists: true
source:
  t: 01:40-01:46
confidence: high
```
## Step 3 — Insert HTML boilerplate
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, empty file
params:
  then_key: Tab
  value: '!'
why: to get boilerplate emmet code
check: HTML boilerplate with DOCTYPE, html, head and body appears
verify:
  uia:
    type: Edit
    value_contains: DOCTYPE
    exists: true
source:
  t: 01:46-01:53
confidence: high
```
## Step 4 — Type video card markup
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, inside <body>
params:
  value: |-
    <div class="videos">
      <section class="video-section">
        <article class="video-container">
          <a href="#" class="thumbnail">
            <img class="thumbnail-image" src="http://unsplash.it/250/150?gravity=center" />
          </a>
          <div class="video-bottom-section">
            <a href="#">
              <img class="channel-icon" src="http://unsplash.it/36/36?gravity=center" />
            </a>
            <div class="video-details">
              <a href="#" class="video-title">Video Title</a>
              <a href="#" class="video-channel-name">Channel Name</a>
              <div class="video-metadata">
                <span>12K views</span>
                •
                <span>1 week ago</span>
              </div>
            </div>
          </div>
        </article>
      </section>
    </div>
why: Builds one video card with thumbnail, channel icon, title and view info. Later steps style it like YouTube.
check: code shows videos div with thumbnail, channel icon, title, channel name and 12K views • 1 week ago
verify:
  uia:
    type: Edit
    value_contains: video-metadata
    exists: true
source:
  t: 01:53-06:22
confidence: high
```
## Step 5 — Save index.html
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
  where: Visual Studio Code
params:
  keys:
  - Ctrl
  - S
check: live preview shows thumbnail, channel icon, title and metadata
verify:
  file:
    path: index.html
    contains: video-metadata
    exists: true
source:
  t: 06:22-06:22
confidence: high
```

# Link stylesheet

## Step 6 — Create new file for styles
```yaml
action: click
target:
  label: New File
  kind: button
  where: Explorer panel
check: file name input appears
source:
  t: 06:34-06:40
confidence: high
repeat_of: 1
```
## Step 7 — Name file styles.css
```yaml
action: type
target:
  label: File name field
  kind: field
  where: Explorer panel in Visual Studio Code
params:
  then_key: Enter
  value: styles.css
why: Creates the separate style file the page will use, keeping design rules out of the HTML.
check: styles.css appears in Explorer under YOUTUBE-CLONE and in OPEN EDITORS
verify:
  uia:
    name: styles.css
    type: TreeItem
    exists: true
source:
  t: 06:34-06:40
confidence: inferred
```
## Step 8 — Open index.html
```yaml
action: click
target:
  label: index.html
  kind: tab
  where: editor tab bar
check: index.html is showing in the editor
verify:
  uia:
    name_contains: index.html
    type: TabItem
    selected: true
    exists: true
source:
  t: 06:40-06:46
confidence: inferred
```
## Step 9 — Link stylesheet in head
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, inside <head>
params:
  value: <link rel="stylesheet" href="styles.css">
why: Connects styles.css to the page, so rules written there change how the video card looks.
check: link tag appears in head in index.html
verify:
  uia:
    type: Edit
    value_contains: href="styles.css"
    exists: true
source:
  t: 06:40-06:46
confidence: high
```
## Step 10 — Add Roboto font link
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, inside <head>, after stylesheet link
params:
  value: <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
why: Loads the Roboto typeface for the page, so all text shares the same clean style.
check: Google Fonts Roboto link appears below styles.css link
verify:
  uia:
    type: Edit
    value_contains: Roboto
    exists: true
source:
  t: 06:46-06:52
confidence: high
```
## Step 11 — Save index.html
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
  where: index.html
params:
  keys:
  - Ctrl
  - S
check: index.html saved with stylesheet links
verify:
  file:
    path: index.html
    contains: Roboto
    exists: true
source:
  t: 06:52-07:04
confidence: high
```

# Add base styles

## Step 12 — Open styles.css editor
```yaml
action: click
target:
  label: styles.css
  kind: tab
  where: Editor tab bar
check: styles.css editor is active and empty
verify:
  uia:
    name: styles.css
    type: TabItem
    selected: true
    exists: true
source:
  t: 07:00-07:04
confidence: high
```
## Step 13 — Type universal box-sizing rule
```yaml
action: type
target:
  label: Editor
  kind: field
  where: styles.css, empty file
params:
  value: |-
    *, *::before, *::after {
      box-sizing: border-box;
      font-family: Roboto, Arial, Helvetica, sans-serif;
    }
why: Makes sizes include padding and borders, and sets the same default text style everywhere.
check: universal selector rule with box-sizing and font-family is in styles.css
verify:
  uia:
    type: Edit
    value_contains: box-sizing
    exists: true
source:
  t: 07:04-07:28
confidence: high
```
## Step 14 — Save styles.css
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
  where: styles.css file
params:
  keys:
  - Ctrl
  - S
check: preview text changes to Roboto font
verify:
  file:
    path: styles.css
    contains: box-sizing
    exists: true
source:
  t: 07:28-07:34
confidence: high
```
## Step 15 — Type body margin rule
```yaml
action: type
target:
  label: Editor
  kind: field
  where: styles.css, end
params:
  value: |-
    body {
      margin: 0;
    }
why: Removes the browser's default blank space around the edges, so content reaches the top and sides.
check: body margin rule is in styles.css
verify:
  uia:
    type: Edit
    value_contains: 'margin: 0'
    exists: true
source:
  t: 07:36-07:42
confidence: high
```
## Step 16 — Save styles.css
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
  where: styles.css file
params:
  keys:
  - Ctrl
  - S
check: browser preview content is pushed to top and sides with no margin
verify:
  file:
    path: styles.css
    contains: 'margin: 0'
    exists: true
source:
  t: 07:42-07:42
confidence: high
```
## Step 17 — Type video-container flex rule
```yaml
action: type
target:
  label: Editor
  kind: field
  where: styles.css, end
params:
  value: |-
    .video-container {
      display: flex;
      flex-direction: column;
    }
why: Stacks the thumbnail above its details in a column, so the card reads top to bottom.
check: .video-container rule with display flex and flex-direction column is in styles.css
verify:
  uia:
    type: Edit
    value_contains: .video-container
    exists: true
source:
  t: 07:42-08:00
confidence: high
```
## Step 18 — Type thumbnail positioning rule
```yaml
action: type
target:
  label: Editor
  kind: field
  where: styles.css, end
params:
  value: |-
    .thumbnail {
      position: relative;
      display: flex;
    }
why: Lets items be placed on top of the thumbnail, so the video length badge can sit in its corner.
check: .thumbnail rule with position relative and display flex is in styles.css
verify:
  uia:
    type: Edit
    value_contains: 'position: relative'
    exists: true
source:
  t: 08:12-08:27
confidence: high
```

# Add duration badge

## Step 19 — Open index.html editor
```yaml
action: click
target:
  label: index.html
  kind: tab
  where: Editor tab bar
check: index.html editor is active
verify:
  uia:
    name: index.html
    type: TabItem
    selected: true
    exists: true
source:
  t: 08:27-08:33
confidence: high
```
## Step 20 — Add duration attribute to thumbnail
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, in <a class="thumbnail"> after the class attribute
params:
  value: data-duration="12:24"
why: Stores the video length on the thumbnail, so it can be shown as an overlay without extra markup.
check: thumbnail anchor reads <a href="#" class="thumbnail" data-duration="12:24">
verify:
  uia:
    type: Edit
    value_contains: data-duration
    exists: true
source:
  t: 08:33-08:45
confidence: high
```
## Step 21 — Open styles.css editor
```yaml
action: click
target:
  label: styles.css
  kind: tab
  where: Editor tab bar
check: styles.css editor is active again
verify:
  uia:
    name: styles.css
    type: TabItem
    selected: true
    exists: true
source:
  t: 08:45-08:51
confidence: high
repeat_of: 12
```
## Step 22 — Type duration badge rule
```yaml
action: type
target:
  label: Editor
  kind: field
  where: styles.css, end
params:
  value: |-
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
why: to pull data-duration into before element as content
check: duration badge shows 12:24 at bottom right with white text on dark background, padded and rounded
verify:
  uia:
    type: Edit
    value_contains: attr(data-duration)
    exists: true
source:
  t: 08:51-10:24
confidence: high
```
## Step 23 — Save styles.css
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
  where: Visual Studio Code
params:
  keys:
  - Ctrl
  - S
check: 12:24 text appears on thumbnail in preview
verify:
  file:
    path: styles.css
    contains: attr(data-duration)
    exists: true
source:
  t: 08:51-09:15
confidence: high
```
