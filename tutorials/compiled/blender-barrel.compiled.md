---
title: Game Dev Journey - Blender Barrel
app: Blender
source:
  type: web
  url: https://sites.google.com/view/game-dev-guide/home/blender/blender-barrel
  author: Game Dev Journey
  hash: 45ddf7c2c9449005
start_state: Blender open with default startup file with Cube in viewport
units: m
compiled:
  model: muse-spark-1.3
  prompts: b1c6dde207cb
---
## Step 1 — Select default Cube
```yaml
action: pick
target:
  label: Cube
  kind: canvas
  where: viewport
check: Cube highlighted in viewport
source:
  anchor: '#h.ij27oxoev0v3_l'
confidence: high
```
## Step 2 — Press X to delete
```yaml
action: shortcut
target:
  label: X
  kind: window
params:
  keys:
  - X
check: Delete dialog open
verify:
  uia:
    name_contains: Delete
    type: Window
    exists: true
source:
  anchor: '#h.ij27oxoev0v3_l'
confidence: high
```
## Step 3 — Confirm Delete
```yaml
action: click
target:
  label: Delete
  kind: button
  where: Delete selected objects dialog
check: Cube gone from viewport and Outliner
verify:
  uia:
    name_contains: Delete
    type: Window
    exists: false
source:
  anchor: '#h.ij27oxoev0v3_l'
confidence: high
```
## Step 4 — Add Cylinder mesh
```yaml
action: menu_path
target:
  label: Cylinder
  kind: menu_item
  where: 3D Viewport header
  menu_path:
  - Add
  - Mesh
  - Cylinder
  shortcut: Shift+A
why: Provides the round starting shape that will be shaped into the barrel.
check: Cylinder in viewport and Outliner
verify:
  uia:
    name: Cylinder
    type: TreeItem
    exists: true
source:
  anchor: '#h.s2k6y4f5c679_l'
confidence: high
```
## Step 5 — Open Add Cylinder options
```yaml
action: click
target:
  label: Add Cylinder
  kind: button
  where: bottom left Adjust Last Operation panel
check: Add Cylinder options visible at bottom left
verify:
  uia:
    name_contains: Add Cylinder
    type: Button
    exists: true
source:
  anchor: '#h.4etoqdhuleqy_l'
confidence: high
```
## Step 6 — Set Vertices to 16
```yaml
action: type
target:
  label: Vertices
  kind: field
  where: Add Cylinder panel
params:
  then_key: Enter
  value: '16'
why: To reduce the poly count
check: Vertices field shows 16, cylinder has 16 sides
verify:
  uia:
    name_contains: Vertices
    type: Edit
    value_contains: '16'
    exists: true
source:
  anchor: '#h.4etoqdhuleqy_l'
confidence: high
```
## Step 7 — Select Cylinder
```yaml
action: pick
target:
  label: Cylinder
  kind: canvas
  where: viewport
check: Cylinder highlighted in viewport
source:
  anchor: '#h.la551ynw5upj_l'
confidence: high
```
## Step 8 — Switch to Edit Mode
```yaml
action: shortcut
target:
  label: Tab
  kind: window
params:
  keys:
  - Tab
why: To switch to Edit Mode
check: Mode shows Edit Mode
source:
  anchor: '#h.la551ynw5upj_l'
confidence: high
```
## Step 9 — Activate Loop Cut
```yaml
action: shortcut
target:
  label: Loop Cut
  kind: window
params:
  keys:
  - Ctrl
  - R
check: Loop Cut preview line visible on barrel
source:
  anchor: '#h.f59ugguyoh5p_l'
confidence: high
```
## Step 10 — Increase cuts to three
```yaml
action: shortcut
target:
  label: Increase cuts
  kind: window
  where: viewport over the barrel
params:
  keys:
  - Wheel Up
check: Three cut lines previewed on barrel
source:
  anchor: '#h.f59ugguyoh5p_l'
confidence: high
```
## Step 11 — Place loop cuts
```yaml
action: click
target:
  label: Barrel
  kind: canvas
  where: viewport
check: Three loop cuts placed on barrel
source:
  anchor: '#h.f59ugguyoh5p_l'
confidence: high
```
## Step 12 — Open Loop Cut options
```yaml
action: click
target:
  label: Loop Cut and Slide
  kind: button
  where: bottom left panel
check: Loop Cut and Slide options visible at bottom left
verify:
  uia:
    name_contains: Loop Cut and Slide
    type: Button
    exists: true
source:
  anchor: '#h.rvwkva6g418c_l'
confidence: high
```
## Step 13 — Set Factor to 0.000
```yaml
action: type
target:
  label: Factor
  kind: field
  where: Loop Cut and Slide panel
params:
  then_key: Enter
  value: '0.000'
why: Keeps the three new edge loops evenly centered for symmetrical bulging later.
check: Factor shows 0.000, cuts centered
verify:
  uia:
    name_contains: Factor
    type: Edit
    value_contains: '0.000'
    exists: true
source:
  anchor: '#h.rvwkva6g418c_l'
confidence: high
```
## Step 14 — Open Viewport Shading options
```yaml
action: click
target:
  label: Viewport Shading drop-down
  kind: button
  where: top right of viewport
check: Viewport Shading popover open
verify:
  uia:
    name_contains: MatCap
    type: Button
    exists: true
source:
  anchor: '#h.8rnxio79ziro_l'
confidence: high
```
## Step 15 — Enable MatCap lighting
```yaml
action: click
target:
  label: MatCap
  kind: button
  where: Viewport Shading popover in Lighting section
why: Switches to even studio lighting so curves and bulges are easier to judge.
check: Viewport uses MatCap lighting
source:
  anchor: '#h.8rnxio79ziro_l'
confidence: high
```
## Step 16 — Enable Shadow
```yaml
action: click
target:
  label: Shadow
  kind: button
  where: Viewport Shading popover
check: Shadow enabled in viewport
source:
  anchor: '#h.8rnxio79ziro_l'
confidence: high
```
## Step 17 — Enable Cavity
```yaml
action: click
target:
  label: Cavity
  kind: button
  where: Viewport Shading popover
check: Cavity options visible
source:
  anchor: '#h.8rnxio79ziro_l'
confidence: high
```
## Step 18 — Set Cavity to Both
```yaml
action: click
target:
  label: Both
  kind: button
  where: Viewport Shading popover in Cavity options
check: Cavity set to Both
source:
  anchor: '#h.8rnxio79ziro_l'
confidence: high
```
## Step 19 — Activate Scale
```yaml
action: shortcut
target:
  label: S
  kind: window
params:
  keys:
  - S
check: Scale active on barrel
source:
  anchor: '#h.x0yepnzf7oxk_l'
confidence: high
```
## Step 20 — Scale barrel to 1.1
```yaml
action: type
target:
  label: Scale
  kind: canvas
  where: viewport
params:
  then_key: Enter
  value: '1.1'
why: Widens the whole cylinder slightly to set the barrel's overall width.
check: Barrel slightly wider, scale confirmed
source:
  anchor: '#h.x0yepnzf7oxk_l'
confidence: high
```
## Step 21 — Switch to Edge Select
```yaml
action: click
target:
  label: Edge Select
  kind: button
  where: 3D Viewport header in Edit Mode
  shortcut: '2'
check: Edge Select highlighted in header
source:
  anchor: '#h.p2vvlsamyx3s_l'
confidence: high
```
## Step 22 — Select centre edge loop
```yaml
action: click
target:
  label: centre edge
  kind: edge
  where: middle of barrel
params:
  click_type: alt
check: Middle edge loop selected around barrel
source:
  anchor: '#h.p2vvlsamyx3s_l'
confidence: high
```
## Step 23 — Activate Scale for edge
```yaml
action: shortcut
target:
  label: S
  kind: window
params:
  keys:
  - S
check: Scale active for edge loop
source:
  anchor: '#h.p2vvlsamyx3s_l'
confidence: high
repeat_of: 19
```
## Step 24 — Scale edge to 1.05
```yaml
action: type
target:
  label: Scale
  kind: canvas
  where: viewport
params:
  then_key: Enter
  value: '1.05'
why: Pushes the middle outward to form the barrel's rounded bulge.
check: Middle bulged out slightly
source:
  anchor: '#h.p2vvlsamyx3s_l'
confidence: high
repeat_of: 20
```
## Step 25 — Switch to Face Select
```yaml
action: click
target:
  label: Face Select
  kind: button
  where: 3D Viewport header in Edit Mode
  shortcut: '3'
check: Face Select highlighted in header
source:
  anchor: '#h.nhludiyeafzm_l'
confidence: high
```
## Step 26 — Select top face
```yaml
action: pick
target:
  label: top face
  kind: face
  where: top of barrel
check: Top cap face selected
source:
  anchor: '#h.nhludiyeafzm_l'
confidence: high
```
## Step 27 — Open Separate menu
```yaml
action: shortcut
target:
  label: P
  kind: window
params:
  keys:
  - P
check: Separate menu open
verify:
  uia:
    name_contains: Selection
    type: MenuItem
    exists: true
source:
  anchor: '#h.nhludiyeafzm_l'
confidence: high
```
## Step 28 — Separate Selection
```yaml
action: click
target:
  label: Selection
  kind: menu_item
  where: Separate menu
why: Turns the top cap into its own object to use as the separate lid.
check: New object Cylinder.001 in Outliner
verify:
  uia:
    name: Cylinder.001
    type: TreeItem
    exists: true
source:
  anchor: '#h.nhludiyeafzm_l'
confidence: high
```
## Step 29 — Start renaming Cylinder
```yaml
action: click
target:
  label: Cylinder
  kind: tree_item
  where: Outliner
params:
  click_type: double
check: Cylinder name editable in Outliner
source:
  anchor: '#h.drxzmynlfsm_l'
confidence: high
```
## Step 30 — Rename to Body
```yaml
action: type
target:
  label: Cylinder
  kind: field
  where: Outliner
params:
  then_key: Enter
  value: Body
why: Labels the main cylinder so body, lid and rings stay easy to tell apart.
check: Outliner shows Body
verify:
  uia:
    name: Body
    type: TreeItem
    exists: true
source:
  anchor: '#h.drxzmynlfsm_l'
confidence: high
```
## Step 31 — Start renaming second object
```yaml
action: click
target:
  label: Cylinder.001
  kind: tree_item
  where: Outliner
params:
  click_type: double
check: Cylinder.001 name editable in Outliner
source:
  anchor: '#h.drxzmynlfsm_l'
confidence: high
```
## Step 32 — Rename to Lid
```yaml
action: type
target:
  label: Cylinder.001
  kind: field
  where: Outliner
params:
  then_key: Enter
  value: Lid
why: Labels the separated top face so it can be worked on as the lid.
check: Outliner shows Lid
verify:
  uia:
    name: Lid
    type: TreeItem
    exists: true
source:
  anchor: '#h.drxzmynlfsm_l'
confidence: high
```
## Step 33 — Hide Lid
```yaml
action: click
target:
  label: Eye
  kind: button
  where: Outliner next to Lid
check: Lid hidden in viewport
source:
  anchor: '#h.drxzmynlfsm_l'
confidence: high
```
## Step 34 — Switch to Object Mode
```yaml
action: shortcut
target:
  label: Tab
  kind: window
params:
  keys:
  - Tab
why: To switch to Object Mode
check: Mode shows Object Mode
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
repeat_of: 8
```
## Step 35 — Select Body
```yaml
action: click
target:
  label: Body
  kind: tree_item
  where: Outliner
check: Body selected
verify:
  uia:
    name: Body
    type: TreeItem
    selected: true
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 36 — Open Modifiers tab
```yaml
action: click
target:
  label: Modifiers
  kind: button
  where: Properties panel
check: Modifiers tab active in Properties
verify:
  uia:
    name: Add Modifier
    type: Button
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 37 — Open Add Modifier menu
```yaml
action: click
target:
  label: Add Modifier
  kind: button
  where: Properties panel in Modifiers tab
check: Add Modifier menu open
verify:
  uia:
    name: Solidify
    type: MenuItem
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 38 — Search for Solidify
```yaml
action: type
target:
  label: Search
  kind: field
  where: Add Modifier menu
params:
  value: Solidify
why: Finds the tool that gives the thin barrel wall real thickness.
check: Solidify listed in menu
verify:
  uia:
    type: Edit
    value_contains: Solidify
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 39 — Add Solidify modifier
```yaml
action: click
target:
  label: Solidify
  kind: menu_item
  where: Add Modifier menu
check: Solidify modifier added to Body
verify:
  uia:
    name_contains: Solidify
    type: Text
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 40 — Set Thickness to 0.04 m
```yaml
action: type
target:
  label: Thickness
  kind: field
  where: Solidify modifier panel
params:
  then_key: Enter
  value: 0.04 m
why: Gives the barrel wall thickness so it looks hollow, not paper-thin.
check: Body shows wall thickness
verify:
  uia:
    name_contains: Thickness
    type: Edit
    value_contains: '0.04'
    exists: true
source:
  anchor: '#h.gkgij7x90rzp_l'
confidence: high
```
## Step 41 — Return to Edit Mode
```yaml
action: shortcut
target:
  label: Tab
  kind: window
params:
  keys:
  - Tab
why: To return to Edit Mode
check: Mode shows Edit Mode
source:
  anchor: '#h.z9unkjyjemvm_l'
confidence: high
repeat_of: 8
```
## Step 42 — Activate Loop Cut again
```yaml
action: shortcut
target:
  label: Loop Cut
  kind: window
params:
  keys:
  - Ctrl
  - R
check: Loop Cut preview visible
source:
  anchor: '#h.z9unkjyjemvm_l'
confidence: high
repeat_of: 9
```
## Step 43 — Add top and bottom loop cuts
```yaml
action: click
target:
  label: Barrel
  kind: canvas
  where: viewport
check: Extra loop cuts at top and bottom as shown
source:
  anchor: '#h.z9unkjyjemvm_l'
confidence: high
repeat_of: 11
```
## Step 44 — Switch to Face Select
```yaml
action: click
target:
  label: Face Select
  kind: button
  where: 3D Viewport header in Edit Mode
  shortcut: '3'
check: Face Select active
source:
  anchor: '#h.d58h95e30xs6_l'
confidence: high
repeat_of: 25
```
## Step 45 — Select side face
```yaml
action: pick
target:
  label: face
  kind: face
  where: side of barrel
check: One side face selected
source:
  anchor: '#h.d58h95e30xs6_l'
confidence: high
```
## Step 46 — Select ring band faces
```yaml
action: click
target:
  label: faces around barrel
  kind: face
  where: side of barrel
params:
  click_type: shift
why: Picks out the strips that will become the raised bands around the barrel.
check: Top, middle and bottom ring bands selected around barrel
source:
  anchor: '#h.d58h95e30xs6_l'
confidence: high
```
## Step 47 — Open Separate menu
```yaml
action: shortcut
target:
  label: P
  kind: window
params:
  keys:
  - P
check: Separate menu open
source:
  anchor: '#h.ag5es3fi1ral_l'
confidence: high
repeat_of: 27
```
## Step 48 — Separate ring faces
```yaml
action: click
target:
  label: Selection
  kind: menu_item
  where: Separate menu
check: New object Body.001 in Outliner
verify:
  uia:
    name: Body.001
    type: TreeItem
    exists: true
source:
  anchor: '#h.ag5es3fi1ral_l'
confidence: high
repeat_of: 28
```
## Step 49 — Start renaming separated object
```yaml
action: click
target:
  label: Body.001
  kind: tree_item
  where: Outliner
params:
  click_type: double
check: Body.001 name editable in Outliner
source:
  anchor: '#h.ag5es3fi1ral_l'
confidence: high
```
## Step 50 — Rename to Rings
```yaml
action: type
target:
  label: Body.001
  kind: field
  where: Outliner
params:
  then_key: Enter
  value: Rings
why: Labels the separated strips so they can be thickened as the rings.
check: Outliner shows Rings
verify:
  uia:
    name: Rings
    type: TreeItem
    exists: true
source:
  anchor: '#h.ag5es3fi1ral_l'
confidence: high
```
## Step 51 — Return to Object Mode
```yaml
action: shortcut
target:
  label: Tab
  kind: window
params:
  keys:
  - Tab
why: To return to Object Mode
check: Mode shows Object Mode
source:
  anchor: '#h.tgfyrntvv3u4_l'
confidence: high
repeat_of: 8
```
## Step 52 — Select Rings
```yaml
action: click
target:
  label: Rings
  kind: tree_item
  where: Outliner
check: Rings selected
verify:
  uia:
    name: Rings
    type: TreeItem
    selected: true
    exists: true
source:
  anchor: '#h.tgfyrntvv3u4_l'
confidence: high
```
## Step 53 — Set Rings thickness negative
```yaml
action: type
target:
  label: Thickness
  kind: field
  where: Solidify modifier panel
params:
  then_key: Enter
  value: -0.04 m
why: Reverses thickness direction so the rings stick out instead of inward.
check: Rings offset outward
verify:
  uia:
    name_contains: Thickness
    type: Edit
    value_contains: '-0.04'
    exists: true
source:
  anchor: '#h.tgfyrntvv3u4_l'
confidence: high
```
## Step 54 — Show Lid
```yaml
action: click
target:
  label: Eye
  kind: button
  where: Outliner next to Lid
check: Lid visible again in viewport
source:
  anchor: '#h.imgmeic2g026_l'
confidence: high
repeat_of: 33
```
## Step 55 — Select Lid
```yaml
action: click
target:
  label: Lid
  kind: tree_item
  where: Outliner
check: Lid selected
verify:
  uia:
    name: Lid
    type: TreeItem
    selected: true
    exists: true
source:
  anchor: '#h.imgmeic2g026_l'
confidence: high
```
## Step 56 — Activate Scale for Lid
```yaml
action: shortcut
target:
  label: S
  kind: window
params:
  keys:
  - S
check: Scale active for Lid
source:
  anchor: '#h.imgmeic2g026_l'
confidence: high
repeat_of: 19
```
## Step 57 — Scale Lid to 0.96
```yaml
action: type
target:
  label: Scale
  kind: canvas
  where: viewport
params:
  then_key: Enter
  value: '0.96'
why: Shrinks the lid slightly so it fits snugly inside the body opening.
check: Lid slightly smaller, fits inside Body
source:
  anchor: '#h.imgmeic2g026_l'
confidence: high
repeat_of: 20
```
