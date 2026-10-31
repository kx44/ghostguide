---
title: 10 Steps to Creating Your First Product in SOLIDWORKS - Engineers Rule
app: SOLIDWORKS
author_version: '2016'
source:
  type: web
  url: https://www.engineersrule.com/10-steps-creating-first-product-solidworks/
  hash: 90f61d03161b01ef
  author: Simon Martin
  published: '2016-07-28'
start_state: SOLIDWORKS open with New document dialog open
compiled:
  model: muse-spark-1.3
  prompts: 716bb2afd62b
---

# Create a new part

## Step 1 — Create new Part document
```yaml
action: click
target:
  label: Part
  kind: button
  where: New document dialog
check: New Part document opens with Feature Tree showing Front Plane
verify:
  uia:
    name: Front Plane
    type: TreeItem
    exists: true
source:
  anchor: '#1-create-a-new-part'
confidence: high
```
## Step 2 — Select Front Plane
```yaml
action: click
target:
  label: Front Plane
  kind: tree_item
  where: Feature Tree to the left of workspace
check: Front Plane highlights as selected in Feature Tree
verify:
  uia:
    name: Front Plane
    type: TreeItem
    selected: true
    exists: true
source:
  anchor: '#1-create-a-new-part'
confidence: high
```
## Step 3 — Orient view to Front
```yaml
action: menu_path
target:
  label: Front
  kind: menu_item
  where: icons above the working area
  menu_path:
  - View Orientation
  - Front
check: View is square to Front Plane
source:
  anchor: '#1-create-a-new-part'
confidence: high
```

# Draw a centerline

## Step 4 — Select Centerline tool
```yaml
action: menu_path
target:
  label: Centerline
  kind: menu_item
  where: Sketch Toolbar
  menu_path:
  - Line
  - Centerline
check: Centerline tool is active in Sketch Toolbar
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```
## Step 5 — Draw vertical centerline
```yaml
action: draw_line
target:
  label: Centerline
  kind: canvas
  where: Front Plane sketch
why: to reference revolve axis and mug profile
check: Vertical centerline appears through Front Plane boundary box
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```
## Step 6 — Exit Centerline tool
```yaml
action: shortcut
target:
  label: Escape
  kind: button
params:
  keys:
  - Escape
why: to drop the Centerline tool
check: Centerline tool drops, cursor returns to select
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```

# Sketch mug profile

## Step 7 — Select Line tool
```yaml
action: click
target:
  label: Line
  kind: button
  where: Sketch Toolbar
check: Line tool is active in Sketch Toolbar
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 8 — Sketch outer wall profile
```yaml
action: draw_line
target:
  label: outer wall profile
  kind: canvas
  where: Front Plane sketch using Centerline as reference
check: Outer wall profile line appears beside Centerline
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 9 — Select outer wall profile
```yaml
action: pick
target:
  label: outer wall profile sketch
  kind: edge
  where: Front Plane sketch
check: Outer wall profile highlights as selected
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 10 — Open Offset Entities
```yaml
action: click
target:
  label: Offset Entities
  kind: button
  where: Sketch toolbar
check: Offset Entities PropertyManager opens on left
verify:
  uia:
    name_contains: Offset Entities
    type: Window
    exists: true
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 11 — Enter offset distance
```yaml
action: type
target:
  label: Offset Distance
  kind: field
  where: Offset Entities PropertyManager
params:
  suggested:
    note: any small value works
    value: '3'
why: to duplicate to inner-wall side
check: Offset distance value appears in PropertyManager
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: inferred
```
## Step 12 — Confirm offset
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
check: Inner-wall parallel line appears and Offset dialog closes
verify:
  uia:
    name_contains: Offset
    type: Window
    exists: false
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: inferred
```
## Step 13 — Draw top closing line
```yaml
action: draw_line
target:
  label: top closing line
  kind: canvas
  where: Front Plane sketch at one end of parallel lines
check: Top gap between parallel lines is closed
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 14 — Draw bottom closing line
```yaml
action: draw_line
target:
  label: bottom closing line
  kind: canvas
  where: Front Plane sketch at other end of parallel lines
check: Closed mug-wall cross-section profile appears
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 15 — Exit sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand corner of workspace
check: Sketch mode exits, profile remains in workspace
verify:
  uia:
    name: Exit Sketch
    type: Button
    exists: false
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```

# Revolve the profile

## Step 16 — Select profile outer edge
```yaml
action: pick
target:
  label: outer edge of profile sketch
  kind: edge
  where: workspace sketch
check: Outer edge of profile highlights
source:
  anchor: '#4-revolve-the-profile'
confidence: high
```
## Step 17 — Start Revolved Boss Base
```yaml
action: click
target:
  label: Revolved Boss/Base
  kind: button
  where: Features toolbar
check: Revolve PropertyManager opens
verify:
  uia:
    name_contains: Revolve
    type: Window
    exists: true
source:
  anchor: '#4-revolve-the-profile'
confidence: high
```
## Step 18 — Confirm revolve
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
check: Mug body solid appears and Revolve dialog closes
verify:
  uia:
    name_contains: Revolve
    type: Window
    exists: false
source:
  anchor: '#4-revolve-the-profile'
confidence: inferred
repeat_of: 12
```

# Sketch handle profile

## Step 19 — Select Front Plane for handle
```yaml
action: click
target:
  label: Front Plane
  kind: tree_item
  where: Feature Tree on left side of screen
check: Front Plane highlights as selected
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
repeat_of: 2
```
## Step 20 — Orient view to Front for handle
```yaml
action: menu_path
target:
  label: Front
  kind: menu_item
  where: View Orientation icon at top of workspace
  menu_path:
  - View Orientation
  - Front
check: View is square to Front
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
repeat_of: 3
```
## Step 21 — Show hidden lines
```yaml
action: menu_path
target:
  label: Hidden Lines Visible
  kind: menu_item
  where: Display Style icon at top of workspace
  menu_path:
  - Display Style
  - Hidden Lines Visible
why: to see both inner and outer edges of the mug
check: Inner and outer mug edges show as dashed hidden lines
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
```
## Step 22 — Select Line tool for handle
```yaml
action: click
target:
  label: Line
  kind: button
  where: Sketch toolbar
check: Line tool is active
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
repeat_of: 7
```
## Step 23 — Draw handle profile
```yaml
action: draw_line
target:
  label: handle profile
  kind: canvas
  where: Front Plane sketch
check: Handle loop sketch appears attached to inner wall
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
```
## Step 24 — Round handle corners
```yaml
action: click
target:
  label: Sketch Fillet
  kind: button
  where: Sketch toolbar
check: Handle corners appear rounded
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
optional: true
```
## Step 25 — Exit handle sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand corner of workspace
check: Handle sketch exits, loop remains visible
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: inferred
repeat_of: 15
```

# Create a new plane

## Step 26 — Select Right Plane
```yaml
action: click
target:
  label: Right Plane
  kind: tree_item
  where: Feature Tree
check: Right Plane highlights as selected
verify:
  uia:
    name: Right Plane
    type: TreeItem
    selected: true
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 27 — Insert new Plane
```yaml
action: menu_path
target:
  label: Plane
  kind: menu_item
  where: Insert menu after hovering SOLIDWORKS logo in upper left
  menu_path:
  - Insert
  - Reference Geometry
  - Plane
check: Plane PropertyManager opens
verify:
  uia:
    name_contains: Plane
    type: Window
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 28 — Select handle endpoint reference
```yaml
action: pick
target:
  label: first point of handle profile sketch
  kind: canvas
  where: workspace where point turns orange
check: Handle endpoint highlights orange as plane reference
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 29 — Confirm new plane
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
why: to create new working plane on edge of mug parallel to Right Plane
check: New working plane parallel to Right Plane appears on mug edge
source:
  anchor: '#6-create-a-new-plane'
confidence: high
repeat_of: 12
```
## Step 30 — Rename plane to MugEdge
```yaml
action: type
target:
  label: plane name
  kind: field
  where: Feature Tree
params:
  value: MugEdge
check: Feature Tree shows plane named MugEdge
verify:
  uia:
    name: MugEdge
    type: TreeItem
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```

# Sketch handle body profile

## Step 31 — Orient view Normal To
```yaml
action: menu_path
target:
  label: Normal To
  kind: menu_item
  where: View Orientation icon
  menu_path:
  - View Orientation
  - Normal To
why: to place view directly over the MugEdge plane
check: View looks directly at MugEdge plane
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 32 — Select Centerpoint Straight Slot tool
```yaml
action: menu_path
target:
  label: Centerpoint Straight Slot
  kind: menu_item
  where: Sketch toolbar
  menu_path:
  - Straight Slot
  - Centerpoint Straight Slot
check: Centerpoint Straight Slot tool is active
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 33 — Select slot center point
```yaml
action: pick
target:
  label: first sketch point of handle
  kind: canvas
  where: MugEdge plane sketch where line turns orange
check: Slot centerpoint attaches to handle point with orange highlight
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 34 — Drag slot width
```yaml
action: drag
target:
  label: slot width
  kind: canvas
  where: MugEdge plane sketch
check: Narrow slot width preview appears
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 35 — Drag slot length
```yaml
action: drag
target:
  label: slot length
  kind: canvas
  where: MugEdge plane sketch
check: Straight slot profile appears at mug height
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 36 — Exit slot sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand area of workspace
check: Slot sketch exits, profile remains
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
repeat_of: 15
```

# Sweep the handle body

## Step 37 — Start Swept Boss Base
```yaml
action: click
target:
  label: Swept Boss/Base
  kind: button
  where: Features toolbar
check: Sweep PropertyManager opens with Profile and Path boxes
verify:
  uia:
    name_contains: Sweep
    type: Window
    exists: true
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 38 — Select sweep profile
```yaml
action: pick
target:
  label: handle body profile created with Centerpoint Straight Slot
  kind: face
  where: blue Profile dialog box / workspace
check: Slot profile fills blue Profile box
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 39 — Select sweep path
```yaml
action: pick
target:
  label: handle profile sketch
  kind: edge
  where: pink Path dialog box / workspace
check: Handle loop fills pink Path box with sweep preview
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 40 — Confirm sweep
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
why: to confirm Sweep and create yellow handle
check: Yellow handle solid appears and Sweep dialog closes
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
repeat_of: 12
```

# Add fillets

## Step 41 — Start Fillet
```yaml
action: click
target:
  label: Fillet
  kind: button
  where: Features toolbar
check: Fillet PropertyManager opens
verify:
  uia:
    name_contains: Fillet
    type: Window
    exists: true
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: high
```
## Step 42 — Select fillet edges
```yaml
action: pick
target:
  label: sharp mug edges
  kind: edge
  where: workspace model
check: Sharp mug and handle edges highlight for fillet
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
```
## Step 43 — Enter fillet radius
```yaml
action: type
target:
  label: Fillet Radius
  kind: field
  where: Fillet PropertyManager
params:
  suggested:
    note: any small value works
    value: '2'
check: Fillet radius value appears in PropertyManager
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
```
## Step 44 — Confirm fillet
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
check: Sharp edges appear rounded and Fillet dialog closes
verify:
  uia:
    name_contains: Fillet
    type: Window
    exists: false
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
repeat_of: 12
```
