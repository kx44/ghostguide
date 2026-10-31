---
title: Titanium camping mug (10 steps to your first product)
app: SOLIDWORKS
author_version: "2016 (not stated; inferred from publish date)"
source: {type: web, url: "https://www.engineersrule.com/10-steps-creating-first-product-solidworks/", author: Simon Martin, published: 2016-07-28, hash: TBD}
start_state: SOLIDWORKS open, no document
units: mm
gold: true   # hand-written reference; the compiler's output is scored against this
notes: >
  The source gives NO dimensions ("left to the designer"). Values under `suggested` are ours,
  so the demo runs the same every time; the overlay shows them as "suggested", not "tutorial says".
  Screenshots exist after the intro and Steps 1–9 but have no captions; crops TBD.
---

# Part A — Mug body (source steps 1–4)

## Step 1 — Create a new part
```yaml
action: click
target: {label: New, kind: button, where: "top toolbar, left", shortcut: Ctrl+N}
why: "Starts a blank document."
check: "New SOLIDWORKS Document dialog open"
verify: {uia: {name: New SOLIDWORKS Document, type: Window}}
source: {anchor: "#step-1"}
confidence: inferred   # source just says "start a new part"
```
## Step 2 — Choose Part
```yaml
action: click
target: {label: Part, kind: button, where: "New SOLIDWORKS Document dialog"}
params: {click_type: double}
why: "The mug is a single solid part."
check: "Empty part window; FeatureManager shows Front/Top/Right Plane"
verify: {uia: [{name: New SOLIDWORKS Document, type: Window, exists: false}, {name_contains: "Part", type: Window, window: SOLIDWORKS}]}
source: {anchor: "#step-1"}
confidence: inferred
```
## Step 3 — Select the Front Plane
```yaml
action: click
target: {label: Front Plane, kind: tree_item, where: "FeatureManager design tree, left"}
why: "The mug's profile is drawn on this plane."
check: "Front Plane highlighted in tree and graphics area"
source: {anchor: "#step-1"}
confidence: high
```
## Step 4 — View from the front
```yaml
action: menu_path
target: {label: Front, kind: menu_item, where: "Heads-up View toolbar, top of graphics area",
         menu_path: [View Orientation, Front], shortcut: Ctrl+1}
why: "Looking straight at the plane makes the sketch accurate."
check: "View is normal to Front Plane"
source: {anchor: "#step-1"}
confidence: high
```
## Step 5 — Pick the Centerline tool
```yaml
action: menu_path
target: {label: Centerline, kind: menu_item, where: "Sketch tab, CommandManager. Line is a small icon with no text, a diagonal line, the first in the top row of small icons, with its dropdown arrow right beside it",
         menu_path: [Sketch, Line ▾, Centerline]}
why: "The centerline becomes the axis the profile spins around."
check: "Insert Line PropertyManager open, centerline cursor"
verify: {uia: {name: Insert Line, type: Button}}
source: {anchor: "#step-2"}
confidence: high   # opening the sketch on Front Plane is implied
```
## Step 6 — Draw the centerline through the origin
```yaml
action: draw_line
target: {label: Origin, kind: canvas, where: "sketch origin, red arrows"}
params: {from: "above the plane's boundary box, straight above the origin", direction: "down, through the origin", to: "about the same distance below it"}
why: "One straight line, so Revolve knows it's the axis. Two would leave it asking which one."
check: "Vertical centerline through the origin"
source: {anchor: "#step-2"}
confidence: high   # the source draws up, then down; in 2026 that's two lines and no automatic axis
```
## Step 7 — Release the tool
```yaml
action: shortcut
target: {label: Esc, kind: button, where: "keyboard"}
params: {keys: [Esc]}
why: "Stops the line where it is."
check: "Line tool released"
verify: {uia: [{name: Insert Line, type: Button, exists: false}, {name: Line Properties, type: Button, exists: false}]}
source: {anchor: "#step-2"}
confidence: high
```
## Step 8 — Line tool
```yaml
action: click
target: {label: Line, kind: button, where: "Sketch tab, CommandManager. A small icon with no text, a diagonal line, the first in the top row of small icons", shortcut: L}
why: "Draw the mug wall's cross-section."
check: "Line tool active"
verify: {uia: {name: Insert Line, type: Button}}
source: {anchor: "#step-3"}
confidence: high
```
## Step 9 — Draw one wall edge
```yaml
action: draw_line
target: {label: Centerline, kind: canvas, where: "right of centerline"}
params: {from: "near bottom, right of centerline", direction: "up, slight outward taper",
         suggested: {length: 100mm, radius_at_base: 40mm}}
why: "One edge of the wall; the offset makes the other."
check: "Single line right of centerline"
source: {anchor: "#step-3"}
confidence: high   # shape is the designer's choice
```
## Step 10 — Select the wall line
```yaml
action: pick
target: {label: Wall line, kind: edge, where: "the line right of the centerline"}
why: "Offset Entities works on what's selected."
check: "The line is highlighted"
source: {anchor: "#step-3"}
confidence: inferred   # the source implies it
```
## Step 11 — Offset the wall
```yaml
action: click
target: {label: Offset Entities, kind: button, where: "Sketch tab, CommandManager"}
why: "Creates the parallel second wall edge."
check: "Offset Entities PropertyManager open, line selected"
verify: {uia: {name: Offset Entities, type: Button}}
source: {anchor: "#step-3"}
confidence: high
```
## Step 12 — Set wall thickness and side
```yaml
action: type
target: {label: Offset Distance, kind: field, where: "Offset Entities PropertyManager, Parameters"}
params: {suggested: {value: "2", side: inside (use Reverse if preview is outside)}}
why: "Check distance and side in the preview before confirming."
check: "Preview line 2 mm on the inner side"
verify: {uia: {type: Edit, value_contains: "2.00mm"}}
source: {anchor: "#step-3"}
confidence: high
```
## Step 13 — Confirm the offset
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Two parallel wall lines"
verify: {uia: {name: Offset Entities, type: Button, exists: false}}
source: {anchor: "#step-3"}
confidence: inferred
```
## Step 14 — Close the top of the wall
```yaml
action: draw_line
target: {label: Line endpoints, kind: canvas, where: "top ends of the two wall lines"}
params: {from: "outer top endpoint", to: "inner top endpoint"}
why: "Pick the Line tool again (L). The profile must be closed to revolve."
check: "Top ends joined"
source: {anchor: "#step-3"}
confidence: high
```
## Step 15 — Close the base
```yaml
action: draw_line
target: {label: Line endpoints, kind: canvas, where: "bottom ends of the wall lines"}
params: {to: centerline, suggested: {base_thickness: 2mm}}
why: "Runs the base to the axis so the mug has a floor; no gaps."
check: "Closed profile (no open endpoints)"
source: {anchor: "#step-3"}
confidence: inferred   # "bottom edges left to the designer"
```
## Step 16 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner, top-right of graphics area"}
check: "Sketch1 in tree, not in edit mode"
verify: {uia: [{name_contains: Sketch1, type: TreeItem, window: SOLIDWORKS}, {name_contains: "Sketch1 of", type: Window, exists: false}]}
source: {anchor: "#step-3"}
confidence: high
```
## Step 17 — Select the sketch
```yaml
action: click
target: {label: Sketch1, kind: tree_item, where: "FeatureManager design tree"}
why: "Revolve only shows its preview with the sketch selected; otherwise it asks for a plane or a sketch."
check: "Sketch1 highlighted in the tree"
source: {anchor: "#step-4"}
confidence: high   # source selects the profile first
```
## Step 18 — Revolve
```yaml
action: click
target: {label: Revolved Boss/Base, kind: button, where: "Features tab, CommandManager",
         menu_path: [Insert, Boss/Base, Revolve]}
why: "Spins the profile around the centerline into a cup."
check: "Revolve PropertyManager open with preview"
verify: {uia: {name: Revolve, type: Button}}
source: {anchor: "#step-4"}
confidence: high
```
## Step 19 — Full turn
```yaml
action: type
target: {label: Angle, kind: field, where: "Revolve PropertyManager, Direction 1"}
params: {value: "360"}
why: "A full revolution makes a closed cup."
check: "Preview shows a full cup; axis = centerline"
verify: {uia: {type: Edit, value_contains: "360"}}
source: {anchor: "#step-4"}
confidence: high   # 360 is the default, so often already set
```
## Step 20 — Confirm the revolve
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Revolve1 in tree; cup-shaped solid. Error → open profile, back to step 14"
verify: {uia: {name: Revolve1, type: TreeItem, window: SOLIDWORKS}}
source: {anchor: "#step-4"}
confidence: high
repeat_of: 13
```

# Part B — Handle path (source step 5)

## Step 21 — Select the Front Plane again
```yaml
action: click
target: {label: Front Plane, kind: tree_item, where: "FeatureManager design tree"}
check: "Front Plane highlighted"
source: {anchor: "#step-5"}
repeat_of: 3
```
## Step 22 — Front view
```yaml
action: shortcut
target: {label: Front, kind: button, where: "Heads-up View toolbar"}
params: {keys: [Ctrl, "1"]}
check: "View normal to Front Plane"
source: {anchor: "#step-5"}
repeat_of: 4
```
## Step 23 — Show hidden edges
```yaml
action: menu_path
target: {label: Hidden Lines Visible, kind: menu_item, where: "Heads-up View toolbar across the top of the graphics area. Display Style is an icon with no text: a small shaded box, the third icon from the right end of the toolbar, with a dropdown arrow. The next one along, two half boxes, is Section View: not that. In its dropdown of five icons, Hidden Lines Visible is the fourth",
         menu_path: [Display Style, Hidden Lines Visible]}
why: "You need to see the inner wall to start the handle on it."
check: "The model shows as lines, with its hidden inner edges dashed"
source: {anchor: "#step-5"}
confidence: high
```
## Step 24 — New sketch with the Line tool
```yaml
action: click
target: {label: Line, kind: button, where: "Sketch tab, CommandManager. A small icon with no text, a diagonal line, the first in the top row of small icons", shortcut: L}
check: "Sketch open on Front Plane, Line tool active"
source: {anchor: "#step-5"}
repeat_of: 8
```
## Step 25 — Draw the handle path
```yaml
action: draw_line
target: {label: Inner wall, kind: edge, where: "right wall, upper half"}
params: {from: "point on inner wall (turns orange on hover)", to: "same wall, lower",
         segments: "out → down → back", suggested: {reach: 30mm, drop: 60mm}}
why: "This is the path the handle follows; start and end must touch the wall."
check: "Open polyline starting and ending on the inner wall edge"
source: {anchor: "#step-5"}
confidence: high
```
## Step 26 — Round the corners (optional)
```yaml
action: click
target: {label: Sketch Fillet, kind: button, where: "Sketch tab, CommandManager"}
params: {suggested: {radius: 8mm}, optional: true}
check: "Sharp corners of the path rounded"
source: {anchor: "#step-5"}
confidence: high
```
## Step 27 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner"}
check: "Sketch2 in tree"
verify: {uia: [{name_contains: Sketch2, type: TreeItem, window: SOLIDWORKS}, {name_contains: "Sketch2 of", type: Window, exists: false}]}
source: {anchor: "#step-5"}
repeat_of: 16
```

# Part C — Handle cross-section (source steps 6–7)

## Step 28 — Select the Right Plane
```yaml
action: click
target: {label: Right Plane, kind: tree_item, where: "FeatureManager design tree"}
check: "Right Plane highlighted"
source: {anchor: "#step-6"}
confidence: high
```
## Step 29 — Insert a reference plane
```yaml
action: menu_path
target: {label: Plane, kind: menu_item, where: "Features tab, CommandManager. Reference Geometry is a big button with text and a dropdown",
         menu_path: [Features, Reference Geometry ▾, Plane]}
why: "The handle's cross-section needs a plane at the handle's start point."
check: "Plane PropertyManager open, Right Plane as first reference"
verify: {uia: {name: Plane, type: Text}}
source: {anchor: "#step-6"}
confidence: high   # the source uses the menu bar, which 2026 folds away behind the logo
```
## Step 30 — Pick the handle's first point
```yaml
action: pick
target: {label: Handle start point, kind: canvas, where: "where the handle path meets the inner wall"}
why: "Puts the new plane exactly where the handle starts."
check: "Second reference = that point; preview plane through it"
verify: {uia: {name_contains: "@Sketch2", type: Text}}
source: {anchor: "#step-6"}
confidence: high
```
## Step 31 — Confirm the plane
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
params: {click_type: right, note: "source right-clicks first, then clicks the check"}
check: "Plane1 in tree"
verify: {uia: {name: Plane1, type: TreeItem, window: SOLIDWORKS}}
source: {anchor: "#step-6"}
repeat_of: 13
```
## Step 32 — Rename it MugEdge
```yaml
action: type
target: {label: Plane1, kind: tree_item, where: "FeatureManager design tree"}
params: {value: "MugEdge", then_key: Enter, how: "F2 to rename"}
why: "A clear name makes the sweep easier to set up."
check: "Tree shows MugEdge"
verify: {uia: {name: MugEdge, type: TreeItem, window: SOLIDWORKS}}
source: {anchor: "#step-6"}
confidence: high
```
## Step 33 — Look at MugEdge straight on
```yaml
action: shortcut
target: {label: Normal To, kind: button, where: "Heads-up View toolbar › View Orientation"}
params: {keys: [Ctrl, "8"], precondition: "MugEdge selected"}
check: "View normal to MugEdge"
source: {anchor: "#step-7"}
confidence: high
```
## Step 34 — Centerpoint Straight Slot
```yaml
action: menu_path
target: {label: Centerpoint Straight Slot, kind: menu_item, where: "Sketch tab, CommandManager. Straight Slot is a small icon with no text, a rounded slot with two dots, the first in the bottom row of small icons, with its dropdown arrow right beside it",
         menu_path: [Sketch, Straight Slot ▾, Centerpoint Straight Slot]}
why: "A slot gives the handle a rounded, comfortable cross-section."
check: "Slot PropertyManager open, sketch on MugEdge"
verify: {uia: {name_contains: "Sketch3 of", type: Window}}
source: {anchor: "#step-7"}
confidence: high
```
## Step 35 — Slot centre and half-length
```yaml
action: drag
target: {label: Handle start point, kind: canvas, where: "handle start point (turns orange)"}
params: {from: "handle start point", suggested: {half_length: 6mm}}
check: "Slot centre on the point, first click placed"
source: {anchor: "#step-7"}
confidence: high
```
## Step 36 — Slot width
```yaml
action: drag
target: {label: Slot preview, kind: canvas, where: "around the handle start point"}
params: {suggested: {width: 5mm}}
why: "Keep it narrow enough to hold comfortably."
check: "Closed slot profile"
source: {anchor: "#step-7"}
confidence: high
```
## Step 37 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner"}
check: "Sketch3 in tree"
verify: {uia: [{name_contains: Sketch3, type: TreeItem, window: SOLIDWORKS}, {name_contains: "Sketch3 of", type: Window, exists: false}]}
source: {anchor: "#step-7"}
repeat_of: 16
```

# Part D — Sweep and finish (source steps 8–10)

## Step 38 — Swept Boss/Base
```yaml
action: click
target: {label: Swept Boss/Base, kind: button, where: "Features tab, CommandManager",
         menu_path: [Insert, Boss/Base, Sweep]}
check: "Sweep PropertyManager open"
verify: {uia: {name: Sweep, type: Button}}
source: {anchor: "#step-8"}
confidence: high
```
## Step 39 — Profile = the slot
```yaml
action: pick
target: {label: Sketch3, kind: tree_item, where: "flyout FeatureManager tree, or the slot in graphics"}
params: {field: "Profile (blue box)"}
check: "Profile box shows Sketch3"
verify: {uia: {name: Sketch3, type: ListItem}}
source: {anchor: "#step-8"}
confidence: high
```
## Step 40 — Path = the handle line
```yaml
action: pick
target: {label: Sketch2, kind: tree_item, where: "flyout FeatureManager tree, or the handle path in graphics"}
params: {field: "Path (pink box)"}
check: "Path box shows Sketch2; yellow handle preview"
verify: {uia: {name: Sketch2, type: ListItem}}
source: {anchor: "#step-8"}
confidence: high
```
## Step 41 — Confirm the sweep
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Sweep1 in tree; mug has a handle"
verify: {uia: {name: Sweep1, type: TreeItem, window: SOLIDWORKS}}
source: {anchor: "#step-8"}
repeat_of: 13
```
## Step 42 — Check proportions
```yaml
action: look
target: {label: Mug, kind: canvas, where: "graphics area"}
why: "Edit Sketch1/Sketch2 from the tree if it looks off; the model updates."
check: "User presses Next"
source: {anchor: "#step-9"}
confidence: high
```
## Step 43 — Fillet
```yaml
action: click
target: {label: Fillet, kind: button, where: "Features tab, CommandManager"}
check: "Fillet PropertyManager open"
verify: {uia: {name: Fillet, type: Button}}
source: {anchor: "#step-10"}
confidence: high
```
## Step 44 — Pick the sharp edges
```yaml
action: pick
target: {label: Rim edge, kind: edge, where: "the top edge of the mug's rim"}
check: "Edges listed in Items To Fillet"
verify: {uia: {name_contains: "Edge<", type: ListItem}}
source: {anchor: "#step-10"}
confidence: inferred   # source doesn't name edges
```
## Step 45 — Radius and confirm
```yaml
action: type
target: {label: Radius, kind: field, where: "Fillet PropertyManager"}
params: {suggested: {value: "1"}, then: "OK (green check)"}
why: "Real parts have small fillets from manufacturing."
check: "Fillet1 in tree; no sharp edges on rim"
verify: {uia: {name: Fillet1, type: TreeItem, window: SOLIDWORKS}}
source: {anchor: "#step-10"}
confidence: high
```
