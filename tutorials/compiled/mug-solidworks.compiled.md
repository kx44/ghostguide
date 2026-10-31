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
start_state: SOLIDWORKS open with no document open
compiled:
  model: muse-spark-1.3
  prompts: e729c706c779
---

# Mug body

## Step 1 — Open New document dialog
```yaml
action: click
target:
  label: New
  kind: button
  where: Standard toolbar at top of window
check: New dialog opens showing document types
verify:
  uia:
    name_contains: New
    type: Window
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#1-create-a-new-part'
confidence: inferred
```
## Step 2 — Create new Part document
```yaml
action: click
target:
  label: Part
  kind: button
  where: New document dialog
params:
  click_type: double
check: New Part document opens with Feature Tree showing Front Plane
verify:
  uia:
    name: Front Plane
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#1-create-a-new-part'
confidence: high
```
## Step 3 — Select Front Plane
```yaml
action: click
target:
  label: Front Plane
  kind: tree_item
  where: Feature Tree to the left of workspace
check: Front Plane is highlighted in Feature Tree
verify:
  uia:
    name: Front Plane
    type: TreeItem
    window: SOLIDWORKS
    selected: true
    exists: true
source:
  anchor: '#1-create-a-new-part'
confidence: high
```
## Step 4 — Orient view to Front
```yaml
action: menu_path
target:
  label: Front
  kind: menu_item
  where: icons above the working area
  menu_path:
  - View Orientation
  - Front
check: View faces Front Plane straight on
source:
  anchor: '#1-create-a-new-part'
confidence: high
```
## Step 5 — Start sketch on Front Plane
```yaml
action: click
target:
  label: Sketch
  kind: button
  where: Sketch toolbar
why: sketch must be active to draw centerline
check: Sketch editing starts on Front Plane
source:
  anchor: '#2-draw-a-centerline'
confidence: inferred
```
## Step 6 — Open Centerline tool
```yaml
action: menu_path
target:
  label: Centerline
  kind: menu_item
  where: Sketch Toolbar
  menu_path:
  - Line
  - Centerline
check: Centerline tool is active
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```
## Step 7 — Draw vertical centerline
```yaml
action: draw_line
target:
  label: Centerline
  kind: canvas
  where: Front Plane sketch
params:
  from: center over the red arrows straight up along blue dotted guideline to just above the Front Plane boundary
    box
  to: just as far below the Front Plane boundary box over the red arrow
why: Creates the spin axis for the mug body, which later steps revolve the wall profile around.
check: Vertical centerline crosses Front Plane boundary box
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```
## Step 8 — Drop Centerline tool
```yaml
action: shortcut
target:
  label: Escape
  kind: button
params:
  keys:
  - Escape
why: to drop the Centerline tool
check: Centerline tool is dropped
source:
  anchor: '#2-draw-a-centerline'
confidence: high
```
## Step 9 — Open Line tool
```yaml
action: click
target:
  label: Line
  kind: button
  where: Sketch Toolbar
check: Line tool is active
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 10 — Sketch outer wall profile
```yaml
action: draw_line
target:
  label: outer wall profile
  kind: canvas
  where: Front Plane sketch using Centerline as reference
params:
  suggested:
    note: exact shape, bottom edges and outer wall angle are up to you
    value: outer wall profile offset from centerline
why: Draws the side shape of the cup that will be spun into a solid wall.
check: Outer wall profile line appears beside centerline
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 11 — Select outer wall profile
```yaml
action: pick
target:
  label: outer wall profile sketch
  kind: edge
  where: Front Plane sketch
check: Outer wall profile is selected
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 12 — Open Offset Entities
```yaml
action: click
target:
  label: Offset Entities
  kind: button
  where: Sketch toolbar
why: Makes a parallel copy of the outer wall to form the inner wall thickness.
check: Offset Entities PropertyManager opens
verify:
  uia:
    name_contains: Offset
    type: Text
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 13 — Enter offset distance
```yaml
action: type
target:
  label: Offset Distance
  kind: field
  where: Offset Entities PropertyManager
params:
  suggested:
    note: any small wall thickness works
    value: '3'
why: to duplicate to inner-wall side
check: Inner-wall preview appears on inner side
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: inferred
```
## Step 14 — Confirm offset
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: Offset Entities PropertyManager
check: Parallel inner-wall line is created and dialog closes
verify:
  uia:
    name_contains: Offset
    type: Text
    window: SOLIDWORKS
    exists: false
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: inferred
```
## Step 15 — Draw top closing line
```yaml
action: draw_line
target:
  label: top closing line
  kind: canvas
  where: Front Plane sketch at one end of parallel lines
params:
  suggested:
    note: exact position follows your profile
    value: line closing inner and outer wall at one end
why: Seals one end of the walls to help make a closed loop that can become solid.
check: Gap at one end of parallel lines is closed
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 16 — Draw bottom closing line
```yaml
action: draw_line
target:
  label: bottom closing line
  kind: canvas
  where: Front Plane sketch at other end of parallel lines
params:
  suggested:
    note: exact position follows your profile
    value: line closing inner and outer wall at other end
why: Seals the other end, finishing the closed wall loop needed for the solid body.
check: Profile is a closed loop between inner and outer walls
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 17 — Exit sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand corner of workspace
check: Sketch mode ends
verify:
  uia:
    name: Exit Sketch
    type: Button
    window: SOLIDWORKS
    exists: false
source:
  anchor: '#3-sketch-a-camping-mug-profile'
confidence: high
```
## Step 18 — Select profile outer edge
```yaml
action: pick
target:
  label: outer edge of profile sketch
  kind: edge
  where: workspace sketch
why: Tells the revolve tool which closed loop to spin into the mug body.
check: Outer edge of profile is highlighted
source:
  anchor: '#4-revolve-the-profile'
confidence: high
```
## Step 19 — Open Revolved Boss/Base
```yaml
action: click
target:
  label: Revolved Boss/Base
  kind: button
  where: Features toolbar
why: Spins the wall loop around the centerline to form the round mug body.
check: Revolve PropertyManager opens
verify:
  uia:
    name_contains: Revolve
    type: Text
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#4-revolve-the-profile'
confidence: high
```
## Step 20 — Select axis of revolution
```yaml
action: pick
target:
  label: Centerline
  kind: edge
  where: workspace
params:
  field: Axis of Revolution
why: revolve needs centerline as axis
check: Centerline fills Axis of Revolution
source:
  anchor: '#4-revolve-the-profile'
confidence: inferred
```
## Step 21 — Confirm revolve
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: Revolve PropertyManager
check: Mug body solid appears and Revolve closes
verify:
  uia:
    name_contains: Revolve
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#4-revolve-the-profile'
confidence: inferred
repeat_of: 14
```

# Handle path and plane

## Step 22 — Select Front Plane
```yaml
action: click
target:
  label: Front Plane
  kind: tree_item
  where: Feature Tree on left side of screen
check: Front Plane is highlighted in Feature Tree
verify:
  uia:
    name: Front Plane
    type: TreeItem
    window: SOLIDWORKS
    selected: true
    exists: true
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
repeat_of: 3
```
## Step 23 — Orient view to Front
```yaml
action: menu_path
target:
  label: Front
  kind: menu_item
  where: View Orientation icon at top of workspace
  menu_path:
  - View Orientation
  - Front
check: View faces Front straight on
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
repeat_of: 4
```
## Step 24 — Show hidden lines
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
check: Inner and outer edges of mug show as hidden lines
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
```
## Step 25 — Open Line tool
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
repeat_of: 9
```
## Step 26 — Draw handle profile
```yaml
action: draw_line
target:
  label: handle profile
  kind: canvas
  where: Front Plane sketch
params:
  from: first point on inner edge of mug where highlight turns orange
  suggested:
    note: exact handle shape up to you
    value: natural handle loop out from wall and back
  to: last point on same inner wall
why: Draws the curve the handle will follow from top to bottom of the mug.
check: Handle loop sketch connects back to same inner wall
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
```
## Step 27 — Round handle corners
```yaml
action: click
target:
  label: Sketch Fillet
  kind: button
  where: Sketch toolbar
why: Rounds the handle corners so the swept handle flows smoothly without sharp kinks.
check: Handle corners are rounded
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: high
optional: true
```
## Step 28 — Exit sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand corner of workspace
check: Handle sketch closes so plane can be created
source:
  anchor: '#5-sketch-the-handle-profile'
confidence: inferred
repeat_of: 17
```
## Step 29 — Select Right Plane
```yaml
action: click
target:
  label: Right Plane
  kind: tree_item
  where: Feature Tree
check: Right Plane is highlighted in Feature Tree
verify:
  uia:
    name: Right Plane
    type: TreeItem
    window: SOLIDWORKS
    selected: true
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 30 — Open Plane dialog
```yaml
action: menu_path
target:
  label: Plane
  kind: menu_item
  where: Insert menu after hovering SOLIDWORKS logo in upper left to show File, Edit, View, etc.
  menu_path:
  - Insert
  - Reference Geometry
  - Plane
why: Creates a new flat drawing surface placed at the edge of the mug for the handle shape.
check: Plane PropertyManager opens
verify:
  uia:
    name_contains: Plane
    type: Text
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 31 — Select handle endpoint for plane
```yaml
action: pick
target:
  label: first point of handle profile sketch
  kind: canvas
  where: workspace where point turns orange
why: Anchors the new surface at the handle end, so the handle shape lines up with its path.
check: Handle endpoint highlights orange as plane reference
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```
## Step 32 — Confirm new plane
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
why: to create new working plane on edge of mug parallel to Right Plane
check: New working plane parallel to Right Plane appears at mug edge
verify:
  uia:
    name_contains: Plane
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
repeat_of: 14
```
## Step 33 — Rename plane to MugEdge
```yaml
action: type
target:
  label: plane name
  kind: field
  where: Feature Tree
params:
  value: MugEdge
why: Gives the plane a clear name so it is easy to find as the handle sketch surface.
check: Feature Tree shows MugEdge plane name
verify:
  uia:
    name: MugEdge
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#6-create-a-new-plane'
confidence: high
```

# Handle body and finish

## Step 34 — Orient view Normal To
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
## Step 35 — Start sketch on MugEdge plane
```yaml
action: click
target:
  label: Sketch
  kind: button
  where: Sketch toolbar
check: Sketch editing starts on MugEdge plane
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: inferred
repeat_of: 5
```
## Step 36 — Open Centerpoint Straight Slot tool
```yaml
action: menu_path
target:
  label: Centerpoint Straight Slot
  kind: menu_item
  where: Sketch toolbar
  menu_path:
  - Straight Slot
  - Centerpoint Straight Slot
why: Makes the rounded cross-section shape that gives the handle its thickness.
check: Centerpoint Straight Slot tool is active
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 37 — Place slot centerpoint
```yaml
action: pick
target:
  label: first sketch point of handle
  kind: canvas
  where: MugEdge plane sketch where line turns orange
why: Centers that cross-section on the handle path so the handle starts in the right place.
check: Slot centerpoint is placed at handle endpoint
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 38 — Drag slot width
```yaml
action: drag
target:
  label: slot width
  kind: canvas
  where: MugEdge plane sketch
params:
  from: slot centerpoint
  suggested:
    note: keep narrow, any small width works
    value: narrow width
  to: width position using guidelines
why: Sets how thick the handle feels when gripped.
check: Narrow slot width preview appears
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 39 — Drag slot length
```yaml
action: drag
target:
  label: slot length
  kind: canvas
  where: MugEdge plane sketch
params:
  from: slot width position
  suggested:
    note: height up to you, avoid design requiring too much material
    value: short length up or down to mug height
  to: up or down to mug height position
why: Sets how wide the handle face is where it meets the mug.
check: Slot length extends to mug height
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
```
## Step 40 — Exit sketch
```yaml
action: click
target:
  label: Exit Sketch
  kind: button
  where: upper right-hand area of workspace
check: Sketch mode ends with slot profile saved
verify:
  uia:
    name: Exit Sketch
    type: Button
    window: SOLIDWORKS
    exists: false
source:
  anchor: '#7-sketch-a-handle-body-profile'
confidence: high
repeat_of: 17
```
## Step 41 — Open Swept Boss/Base
```yaml
action: click
target:
  label: Swept Boss/Base
  kind: button
  where: Features toolbar
why: Builds the solid handle by pushing the slot shape along the handle curve.
check: Sweep PropertyManager opens
verify:
  uia:
    name_contains: Sweep
    type: Text
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 42 — Select sweep profile
```yaml
action: pick
target:
  label: handle body profile created with Centerpoint Straight Slot
  kind: face
  where: blue Profile dialog box / workspace
params:
  field: Profile
why: Tells the tool which cross-section shape to push to form the handle.
check: Slot profile fills Profile box
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 43 — Select sweep path
```yaml
action: pick
target:
  label: handle profile sketch
  kind: edge
  where: pink Path dialog box / workspace
params:
  field: Path
why: Tells the tool which curve to follow to place the handle.
check: Handle sketch fills Path box with preview
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
```
## Step 44 — Confirm sweep
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: upper right-hand corner of workspace
why: to confirm Sweep and create yellow handle
check: Yellow handle solid appears and Sweep closes
verify:
  uia:
    name_contains: Sweep
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#8-sweep-the-handle-body'
confidence: high
repeat_of: 14
```
## Step 45 — Open Fillet tool
```yaml
action: click
target:
  label: Fillet
  kind: button
  where: Features toolbar
why: Smooths sharp joins where the handle meets the mug into rounded, comfortable edges.
check: Fillet PropertyManager opens
verify:
  uia:
    name_contains: Fillet
    type: Text
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: high
```
## Step 46 — Select edges to fillet
```yaml
action: pick
target:
  label: sharp edges
  kind: edge
  where: mug and handle
check: Sharp edges highlight for fillet
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
```
## Step 47 — Enter fillet radius
```yaml
action: type
target:
  label: Radius
  kind: field
  where: Fillet PropertyManager
params:
  suggested:
    note: any small radius works
    value: '2'
why: Sets how rounded the smoothed edges become.
check: Fillet preview updates
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
```
## Step 48 — Confirm fillet
```yaml
action: click
target:
  label: green check mark
  kind: button
  where: Fillet PropertyManager
check: Sharp edges are refined and Fillet closes
verify:
  uia:
    name_contains: Fillet
    type: TreeItem
    window: SOLIDWORKS
    exists: true
source:
  anchor: '#10-add-fillets-and-design-details'
confidence: inferred
repeat_of: 14
```
