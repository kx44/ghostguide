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
target: {label: Centerline, kind: menu_item, where: "Sketch tab, CommandManager",
         menu_path: [Sketch, Line ▾, Centerline]}
why: "The centerline becomes the axis the profile spins around."
check: "Insert Line PropertyManager open, centerline cursor"
source: {anchor: "#step-2"}
confidence: high   # opening the sketch on Front Plane is implied
```
## Step 6 — Draw the centerline up from the origin
```yaml
action: draw_line
target: {label: Origin, kind: canvas, where: "sketch origin, red arrows"}
params: {from: origin, direction: up, to: "just above the plane's boundary box"}
why: "Follow the blue guideline straight up so the axis is vertical."
check: "Vertical centerline segment from origin"
source: {anchor: "#step-2"}
confidence: high
```
## Step 7 — Continue it below the origin, then stop
```yaml
action: draw_line
target: {label: Origin, kind: canvas, where: "graphics area, below origin"}
params: {direction: down, to: "about the same distance below the boundary", then_key: Esc}
why: "Extends the axis through the whole mug height."
check: "Centerline spans above and below origin; line tool released"
source: {anchor: "#step-2"}
confidence: high
```
## Step 8 — Line tool
```yaml
action: click
target: {label: Line, kind: button, where: "Sketch tab, CommandManager", shortcut: L}
why: "Draw the mug wall's cross-section."
check: "Line tool active"
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
## Step 10 — Offset the wall
```yaml
action: click
target: {label: Offset Entities, kind: button, where: "Sketch tab, CommandManager"}
why: "Creates the parallel second wall edge."
check: "Offset Entities PropertyManager open, line selected"
source: {anchor: "#step-3"}
confidence: high
```
## Step 11 — Set wall thickness and side
```yaml
action: type
target: {label: Offset Distance, kind: field, where: "Offset Entities PropertyManager, Parameters"}
params: {suggested: {value: "2", side: inside (use Reverse if preview is outside)}}
why: "Check distance and side in the preview before confirming."
check: "Preview line 2 mm on the inner side"
source: {anchor: "#step-3"}
confidence: high
```
## Step 12 — Confirm the offset
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Two parallel wall lines"
source: {anchor: "#step-3"}
confidence: inferred
```
## Step 13 — Close the top of the wall
```yaml
action: draw_line
target: {label: Line endpoints, kind: canvas, where: "top ends of the two wall lines"}
params: {from: "outer top endpoint", to: "inner top endpoint"}
why: "The profile must be closed to revolve."
check: "Top ends joined"
source: {anchor: "#step-3"}
confidence: high
```
## Step 14 — Close the base
```yaml
action: draw_line
target: {label: Line endpoints, kind: canvas, where: "bottom ends of the wall lines"}
params: {to: centerline, suggested: {base_thickness: 2mm}}
why: "Runs the base to the axis so the mug has a floor; no gaps."
check: "Closed profile (no open endpoints)"
source: {anchor: "#step-3"}
confidence: inferred   # "bottom edges left to the designer"
```
## Step 15 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner, top-right of graphics area"}
check: "Sketch1 in tree, not in edit mode"
source: {anchor: "#step-3"}
confidence: high
```
## Step 16 — Revolve
```yaml
action: click
target: {label: Revolved Boss/Base, kind: button, where: "Features tab, CommandManager",
         menu_path: [Insert, Boss/Base, Revolve]}
why: "Spins the profile around the centerline into a cup."
check: "Revolve PropertyManager open with preview"
source: {anchor: "#step-4"}
confidence: high   # source selects the profile edge first; with one sketch it isn't needed
```
## Step 17 — Full turn
```yaml
action: type
target: {label: Angle, kind: field, where: "Revolve PropertyManager, Direction 1"}
params: {value: "360"}
why: "A full revolution makes a closed cup."
check: "Preview shows a full cup; axis = centerline"
source: {anchor: "#step-4"}
confidence: high   # 360 is the default, so often already set
```
## Step 18 — Confirm the revolve
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Revolve1 in tree; cup-shaped solid. Error → open profile, back to step 13"
source: {anchor: "#step-4"}
confidence: high
repeat_of: 12
```

# Part B — Handle path (source step 5)

## Step 19 — Select the Front Plane again
```yaml
action: click
target: {label: Front Plane, kind: tree_item, where: "FeatureManager design tree"}
check: "Front Plane highlighted"
source: {anchor: "#step-5"}
repeat_of: 3
```
## Step 20 — Front view
```yaml
action: shortcut
target: {label: Front, kind: button, where: "Heads-up View toolbar"}
params: {keys: [Ctrl, "1"]}
check: "View normal to Front Plane"
source: {anchor: "#step-5"}
repeat_of: 4
```
## Step 21 — Show hidden edges
```yaml
action: menu_path
target: {label: Hidden Lines Visible, kind: menu_item, where: "Heads-up View toolbar",
         menu_path: [Display Style, Hidden Lines Visible]}
why: "You need to see the inner wall to start the handle on it."
check: "Both wall edges visible as lines"
source: {anchor: "#step-5"}
confidence: high
```
## Step 22 — New sketch with the Line tool
```yaml
action: click
target: {label: Line, kind: button, where: "Sketch tab, CommandManager", shortcut: L}
check: "Sketch open on Front Plane, Line tool active"
source: {anchor: "#step-5"}
repeat_of: 8
```
## Step 23 — Draw the handle path
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
## Step 24 — Round the corners (optional)
```yaml
action: click
target: {label: Sketch Fillet, kind: button, where: "Sketch tab, CommandManager"}
params: {suggested: {radius: 8mm}, optional: true}
check: "Sharp corners of the path rounded"
source: {anchor: "#step-5"}
confidence: high
```
## Step 25 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner"}
check: "Sketch2 in tree"
source: {anchor: "#step-5"}
repeat_of: 15
```

# Part C — Handle cross-section (source steps 6–7)

## Step 26 — Select the Right Plane
```yaml
action: click
target: {label: Right Plane, kind: tree_item, where: "FeatureManager design tree"}
check: "Right Plane highlighted"
source: {anchor: "#step-6"}
confidence: high
```
## Step 27 — Insert a reference plane
```yaml
action: menu_path
target: {label: Plane, kind: menu_item, where: "menu bar (hover the SOLIDWORKS logo if hidden)",
         menu_path: [Insert, Reference Geometry, Plane]}
why: "The handle's cross-section needs a plane at the handle's start point."
check: "Plane PropertyManager open, Right Plane as first reference"
source: {anchor: "#step-6"}
confidence: high   # menu-bar-behind-logo is 2016 UI; version mapping may pin it
```
## Step 28 — Pick the handle's first point
```yaml
action: pick
target: {label: Handle start point, kind: canvas, where: "where the handle path meets the inner wall"}
why: "Puts the new plane exactly where the handle starts."
check: "Second reference = that point; preview plane through it"
source: {anchor: "#step-6"}
confidence: high
```
## Step 29 — Confirm the plane
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
params: {click_type: right, note: "source right-clicks first, then clicks the check"}
check: "Plane1 in tree"
source: {anchor: "#step-6"}
repeat_of: 12
```
## Step 30 — Rename it MugEdge
```yaml
action: type
target: {label: Plane1, kind: tree_item, where: "FeatureManager design tree"}
params: {value: "MugEdge", then_key: Enter, how: "slow double-click or F2 to rename"}
why: "A clear name makes the sweep easier to set up."
check: "Tree shows MugEdge"
source: {anchor: "#step-6"}
confidence: high
```
## Step 31 — Look at MugEdge straight on
```yaml
action: shortcut
target: {label: Normal To, kind: button, where: "Heads-up View toolbar › View Orientation"}
params: {keys: [Ctrl, "8"], precondition: "MugEdge selected"}
check: "View normal to MugEdge"
source: {anchor: "#step-7"}
confidence: high
```
## Step 32 — Centerpoint Straight Slot
```yaml
action: menu_path
target: {label: Centerpoint Straight Slot, kind: menu_item, where: "Sketch tab, CommandManager",
         menu_path: [Sketch, Straight Slot ▾, Centerpoint Straight Slot]}
why: "A slot gives the handle a rounded, comfortable cross-section."
check: "Slot PropertyManager open, sketch on MugEdge"
source: {anchor: "#step-7"}
confidence: high
```
## Step 33 — Slot centre and half-length
```yaml
action: drag
target: {label: Handle start point, kind: canvas, where: "handle start point (turns orange)"}
params: {from: "handle start point", suggested: {half_length: 6mm}}
check: "Slot centre on the point, first click placed"
source: {anchor: "#step-7"}
confidence: high
```
## Step 34 — Slot width
```yaml
action: drag
target: {label: Slot preview, kind: canvas, where: "around the handle start point"}
params: {suggested: {width: 5mm}}
why: "Keep it narrow enough to hold comfortably."
check: "Closed slot profile"
source: {anchor: "#step-7"}
confidence: high
```
## Step 35 — Exit the sketch
```yaml
action: click
target: {label: Exit Sketch, kind: button, where: "confirmation corner"}
check: "Sketch3 in tree"
source: {anchor: "#step-7"}
repeat_of: 15
```

# Part D — Sweep and finish (source steps 8–10)

## Step 36 — Swept Boss/Base
```yaml
action: click
target: {label: Swept Boss/Base, kind: button, where: "Features tab, CommandManager",
         menu_path: [Insert, Boss/Base, Sweep]}
check: "Sweep PropertyManager open"
source: {anchor: "#step-8"}
confidence: high
```
## Step 37 — Profile = the slot
```yaml
action: pick
target: {label: Sketch3, kind: tree_item, where: "flyout FeatureManager tree, or the slot in graphics"}
params: {field: "Profile (blue box)"}
check: "Profile box shows Sketch3"
source: {anchor: "#step-8"}
confidence: high
```
## Step 38 — Path = the handle line
```yaml
action: pick
target: {label: Sketch2, kind: tree_item, where: "flyout FeatureManager tree, or the handle path in graphics"}
params: {field: "Path (pink box)"}
check: "Path box shows Sketch2; yellow handle preview"
source: {anchor: "#step-8"}
confidence: high
```
## Step 39 — Confirm the sweep
```yaml
action: click
target: {label: OK (green check), kind: button, where: "top of PropertyManager"}
check: "Sweep1 in tree; mug has a handle"
source: {anchor: "#step-8"}
repeat_of: 12
```
## Step 40 — Check proportions
```yaml
action: look
target: {label: Mug, kind: canvas, where: "graphics area"}
why: "Edit Sketch1/Sketch2 from the tree if it looks off; the model updates."
check: "User presses Next"
source: {anchor: "#step-9"}
confidence: high
```
## Step 41 — Fillet
```yaml
action: click
target: {label: Fillet, kind: button, where: "Features tab, CommandManager"}
check: "Fillet PropertyManager open"
source: {anchor: "#step-10"}
confidence: high
```
## Step 42 — Pick the sharp edges
```yaml
action: pick
target: {label: Rim and handle edges, kind: edge, where: "mug rim; handle-to-wall joins"}
check: "Edges listed in Items To Fillet"
source: {anchor: "#step-10"}
confidence: inferred   # source doesn't name edges
```
## Step 43 — Radius and confirm
```yaml
action: type
target: {label: Radius, kind: field, where: "Fillet PropertyManager"}
params: {suggested: {value: "1"}, then: "OK (green check)"}
why: "Real parts have small fillets from manufacturing."
check: "Fillet1 in tree; no sharp edges on rim"
source: {anchor: "#step-10"}
confidence: high
```
