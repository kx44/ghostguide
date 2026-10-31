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
start_state: Visual Studio Code open with YOUTUBE-CLONE folder open containing apps.svg, bell.svg, logo.png, magnify.svg,
  video-plus.svg
compiled:
  model: muse-spark-1.3
  prompts: 716bb2afd62b
---

# Create video markup

## Step 1 — Click New File
```yaml
action: click
target:
  label: New File
  kind: button
  where: Explorer panel header
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
  where: Explorer panel
params:
  then_key: Enter
  value: index.html
check: index.html appears in Explorer and editor
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
check: HTML boilerplate with DOCTYPE, html, head and body appears
verify:
  uia:
    type: Edit
    value_contains: <!DOCTYPE
    window: index.html
    exists: true
source:
  t: 01:46-01:46
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
check: videos section with thumbnail, channel icon, Video Title, Channel Name and 12K views • 1 week ago appears
  in code
verify:
  uia:
    type: Edit
    value_contains: 12K views
    window: index.html
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
params:
  keys:
  - Ctrl
  - S
check: live preview shows thumbnail, channel icon and video metadata
verify:
  file:
    path: index.html
    contains: 12K views
    exists: true
source:
  t: 06:22-06:22
confidence: high
```

# Link CSS and font

## Step 6 — Click New File for stylesheet
```yaml
action: click
target:
  label: New File
  kind: button
  where: Explorer panel header
check: file name input appears
source:
  t: 06:34-06:40
confidence: high
```
## Step 7 — Name file styles.css
```yaml
action: type
target:
  label: File name field
  kind: field
  where: Explorer panel
params:
  then_key: Enter
  value: styles.css
check: styles.css appears in Explorer
verify:
  uia:
    name: styles.css
    type: TreeItem
    exists: true
source:
  t: 06:34-06:40
confidence: inferred
```
## Step 8 — Activate index.html
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
  t: 06:40-06:46
confidence: inferred
```
## Step 9 — Type stylesheet link
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, inside <head>
params:
  value: <link rel="stylesheet" href="styles.css">
check: stylesheet link appears in head
verify:
  uia:
    type: Edit
    value_contains: href="styles.css"
    window: index.html
    exists: true
source:
  t: 06:40-06:46
confidence: high
```
## Step 10 — Type Roboto font link
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, inside <head> after stylesheet link
params:
  value: <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
check: Roboto font link appears below stylesheet link
verify:
  uia:
    type: Edit
    value_contains: fonts.googleapis.com
    window: index.html
    exists: true
source:
  t: 06:46-06:52
confidence: high
```
## Step 11 — Save index.html links
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
params:
  keys:
  - Ctrl
  - S
check: index.html is saved
verify:
  file:
    path: index.html
    contains: fonts.googleapis.com
    exists: true
source:
  t: 06:52-07:04
confidence: high
```

# Add base styles

## Step 12 — Activate styles.css
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
## Step 13 — Type universal font rule
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
check: universal selector rule with box-sizing and font-family is in styles.css
verify:
  uia:
    type: Edit
    value_contains: box-sizing
    window: styles.css
    exists: true
source:
  t: 07:04-07:28
confidence: high
```
## Step 14 — Save universal rule
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
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
check: body margin rule is in styles.css
verify:
  uia:
    type: Edit
    value_contains: 'margin: 0'
    window: styles.css
    exists: true
source:
  t: 07:36-07:42
confidence: high
```
## Step 16 — Save body rule
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
params:
  keys:
  - Ctrl
  - S
check: preview content moves to top and sides with no margin
verify:
  file:
    path: styles.css
    contains: 'margin: 0'
    exists: true
source:
  t: 07:42-07:42
confidence: high
```
## Step 17 — Type video-container rule
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
check: .video-container rule with display flex and column direction is in styles.css
verify:
  uia:
    type: Edit
    value_contains: .video-container
    window: styles.css
    exists: true
source:
  t: 07:42-08:00
confidence: high
```
## Step 18 — Type thumbnail rule
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
check: .thumbnail rule with position relative and display flex is in styles.css
verify:
  uia:
    type: Edit
    value_contains: 'position: relative'
    window: styles.css
    exists: true
source:
  t: 08:12-08:27
confidence: high
```

# Add duration badge

## Step 19 — Activate index.html
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
## Step 20 — Type duration attribute
```yaml
action: type
target:
  label: Editor
  kind: field
  where: index.html, in <a class="thumbnail"> after the class attribute
params:
  value: data-duration="12:24"
check: thumbnail anchor reads <a href="#" class="thumbnail" data-duration="12:24">
verify:
  uia:
    type: Edit
    value_contains: data-duration="12:24"
    window: index.html
    exists: true
source:
  t: 08:33-08:45
confidence: high
```
## Step 21 — Activate styles.css again
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
check: 12:24 badge appears bottom-right of thumbnail with white text on dark background
verify:
  uia:
    type: Edit
    value_contains: thumbnail::before
    window: styles.css
    exists: true
source:
  t: 08:51-10:24
confidence: high
```
## Step 23 — Save badge rule
```yaml
action: shortcut
target:
  label: Save
  kind: menu_item
params:
  keys:
  - Ctrl
  - S
check: preview shows 12:24 badge on thumbnail
verify:
  file:
    path: styles.css
    contains: thumbnail::before
    exists: true
source:
  t: 08:51-09:15
confidence: high
```
