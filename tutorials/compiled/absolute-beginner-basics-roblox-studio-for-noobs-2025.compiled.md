---
title: ABSOLUTE Beginner Basics.. Roblox Studio For Noobs 2025
app: Roblox Studio
author_version: '2025'
source:
  type: video
  url: https://www.youtube.com/watch?v=-5OOovmkJss
  hash: 1fe4b8f1a7a7aa2b
  author: RoBuilder
  published: '2025-12-11'
start_state: Roblox account created and logged in, Roblox Studio installed, Google Chrome open on Roblox Home page
units: studs
compiled:
  model: muse-spark-1.3
  prompts: b1c6dde207cb
---

# Opening

## Step 1 — Open Create page
```yaml
app: Google Chrome
action: click
target:
  label: Create
  kind: tab
  where: top navigation bar on Roblox Home page
why: to go to page where you will download Roblox Studio
check: Creator Hub page opens
source:
  t: 00:13-00:15
confidence: high
```
## Step 2 — Open experience in Studio
```yaml
app: Google Chrome
action: click
target:
  label: Create Experience
  kind: button
  where: Creations page in Creator Hub
why: to open up a project in Roblox Studio
check: '"Checking For Roblox Studio" dialog appears and Roblox Studio opens'
source:
  t: 00:23-00:25
confidence: high
```
## Step 3 — Switch to Roblox Studio
```yaml
action: switch_app
target:
  label: Roblox Studio
  kind: window
check: Roblox Studio window is active
verify:
  uia:
    name_contains: Roblox Studio
    type: Window
    exists: true
source:
  t: 00:23-00:29
confidence: inferred
```
## Step 4 — Create Baseplate template
```yaml
action: click
target:
  label: Baseplate
  kind: button
  where: Open a Template section on Studio start screen
  menu_path:
  - New
  - Baseplate
why: to keep things very simple and not overwhelm the newcomer
check: Baseplate place opens in Studio viewport
verify:
  uia:
    name: Baseplate
    type: TabItem
    window: Roblox Studio
    exists: true
source:
  t: 00:29-00:35
confidence: high
```

# Navigating

## Step 5 — Move with WASD keys
```yaml
action: shortcut
target:
  label: WASD
  kind: window
  where: 3D viewport
params:
  keys:
  - W
  - A
  - S
  - D
why: to move around in the Roblox Studio engine
check: camera moves around the baseplate
source:
  t: 00:47-01:04
confidence: high
```
## Step 6 — Look around by dragging
```yaml
action: drag
target:
  label: Viewport
  kind: canvas
  where: 3D viewport, while holding right-click
params:
  direction: in whatever direction you are trying to go
why: to move camera in whatever direction you're trying to go
check: camera turns in drag direction
source:
  t: 01:06-01:12
confidence: high
```
## Step 7 — Select SpawnLocation
```yaml
action: click
target:
  label: SpawnLocation
  kind: tree_item
  where: Explorer panel under Workspace
check: SpawnLocation is highlighted and its properties show in Properties panel
verify:
  uia:
    name: SpawnLocation
    type: TreeItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 01:14-01:17
confidence: high
```
## Step 8 — Focus camera on selection
```yaml
action: shortcut
target:
  label: F
  kind: window
  where: 3D viewport with part selected
params:
  keys:
  - F
why: to automatically zoom into that part
check: camera automatically zooms into that part
source:
  t: 01:16-01:18
confidence: high
```

# Exploring

## Step 9 — Select SpawnLocation in viewport
```yaml
action: pick
target:
  label: SpawnLocation
  kind: face
  where: 3D viewport
check: SpawnLocation is selected in Explorer and viewport, Properties shows SpawnLocation
source:
  t: 02:00-02:03
confidence: high
```
## Step 10 — Duplicate SpawnLocation
```yaml
action: shortcut
target:
  label: Ctrl+D
  kind: window
  where: 3D viewport
params:
  keys:
  - Ctrl
  - D
check: second SpawnLocation appears in Explorer and two spawn pads in viewer
source:
  t: 02:02-02:05
confidence: high
```
## Step 11 — Select ServerStorage
```yaml
action: click
target:
  label: ServerStorage
  kind: tree_item
  where: Explorer panel
check: ServerStorage is selected, Properties shows ServerStorage
verify:
  uia:
    name: ServerStorage
    type: TreeItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 02:18-02:20
confidence: high
```
## Step 12 — Select Workspace
```yaml
action: click
target:
  label: Workspace
  kind: tree_item
  where: Explorer panel
check: Workspace is highlighted in Explorer
verify:
  uia:
    name: Workspace
    type: TreeItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 02:24-02:26
confidence: high
```
## Step 13 — Select Lighting
```yaml
action: click
target:
  label: Lighting
  kind: tree_item
  where: Explorer panel
check: Lighting is selected, Properties shows Lighting
verify:
  uia:
    name: Lighting
    type: TreeItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 02:28-02:32
confidence: high
```
## Step 14 — Select SpawnLocation again
```yaml
action: click
target:
  label: SpawnLocation
  kind: tree_item
  where: Explorer panel
check: Properties shows SpawnLocation properties
source:
  t: 02:38-02:40
confidence: high
repeat_of: 7
```
## Step 15 — Deselect by clicking background
```yaml
action: click
target:
  label: viewport background
  kind: canvas
  where: 3D viewport
check: Properties panel is blank
source:
  t: 02:41-02:43
confidence: high
```
## Step 16 — Select Lighting again
```yaml
action: click
target:
  label: Lighting
  kind: tree_item
  where: Explorer panel
check: Lighting is selected, Properties shows Lighting properties
source:
  t: 02:46-02:49
confidence: high
repeat_of: 13
```
## Step 17 — Open Ambient color picker
```yaml
action: click
target:
  label: Ambient
  kind: field
  where: Properties panel under Appearance
check: Select Color dialog opens
verify:
  uia:
    name_contains: Select Color
    type: Window
    window: Roblox Studio
    exists: true
source:
  t: 02:53-02:55
confidence: high
```
## Step 18 — Choose red color
```yaml
action: click
target:
  label: Red
  kind: button
  where: Select Color dialog in Basic colors
why: Tints all light red so the change is dramatic, showing what the Ambient light setting controls.
check: red is previewed in Select Color dialog
source:
  t: 02:55-02:57
confidence: high
```
## Step 19 — Confirm color choice
```yaml
action: click
target:
  label: OK
  kind: button
  where: Select Color dialog
check: Ambient becomes red and viewport is tinted red
verify:
  uia:
    name_contains: Select Color
    type: Window
    window: Roblox Studio
    exists: false
source:
  t: 02:55-02:57
confidence: high
```

# Editing SpawnLocation

## Step 20 — Select SpawnLocation
```yaml
action: click
target:
  label: SpawnLocation
  kind: tree_item
  where: Explorer panel
check: SpawnLocation is highlighted and Properties shows SpawnLocation
source:
  t: 03:07-03:07
confidence: high
repeat_of: 7
```
## Step 21 — Set BrickColor to Deep blue
```yaml
action: menu_path
target:
  label: Deep blue
  kind: menu_item
  where: Properties panel, Appearance section
  menu_path:
  - BrickColor
  - Deep blue
why: Changes the spawn pad's color, showing how appearance settings instantly change how an object looks.
check: Spawn pad turns blue
verify:
  uia:
    name_contains: BrickColor
    type: Edit
    value_contains: Deep blue
    window: Roblox Studio
    exists: true
source:
  t: 03:08-03:10
confidence: high
```
## Step 22 — Set Material to Glass
```yaml
action: menu_path
target:
  label: Glass
  kind: menu_item
  where: Properties panel, Appearance section
  menu_path:
  - Material
  - Glass
why: Gives the pad a glassy see-through look, showing materials change texture as well as color.
check: Material shows Glass
verify:
  uia:
    name_contains: Material
    type: Edit
    value_contains: Glass
    window: Roblox Studio
    exists: true
source:
  t: 03:12-03:16
confidence: high
```
## Step 23 — Start playtest
```yaml
action: click
target:
  label: Play
  kind: button
  where: Top toolbar, Test tab
  menu_path:
  - Home
  - Play
  shortcut: F5
why: to show player spawns on top of the part
check: Play mode starts with avatar on spawn
verify:
  uia:
    name: Stop
    type: Button
    window: Roblox Studio
    exists: true
source:
  t: 03:36-03:38
confidence: high
```
## Step 24 — Stop playtest
```yaml
action: click
target:
  label: Stop
  kind: button
  where: Top toolbar
  menu_path:
  - Home
  - Stop
  shortcut: Shift+F5
why: must end playtest to return to edit mode for next edit
check: Editor view returns
verify:
  uia:
    name: Stop
    type: Button
    window: Roblox Studio
    exists: false
source:
  t: 03:38-03:44
confidence: high
```
## Step 25 — Scale SpawnLocation taller
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: Viewport
params:
  direction: up
  from: scale handle on SpawnLocation
check: Size becomes 12, 6.25, 12
source:
  t: 03:38-03:44
confidence: high
```
## Step 26 — Disable CanCollide
```yaml
action: click
target:
  label: CanCollide
  kind: button
  where: Properties panel, Collision section
why: Lets players fall through the part instead of standing on it, so it works as a zone not a floor.
check: CanCollide checkbox is unchecked
source:
  t: 03:43-03:45
confidence: high
```
## Step 27 — Scale SpawnLocation flatter
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: Viewport
params:
  direction: down
  from: scale handle on SpawnLocation
check: Size becomes 12, 0.75, 12
source:
  t: 03:50-03:56
confidence: high
```
## Step 28 — Activate Select tool
```yaml
action: click
target:
  label: Select
  kind: button
  where: Top toolbar
  menu_path:
  - Model
  - Select
  shortcut: '1'
check: Select tool is active
source:
  t: 04:12-04:16
confidence: high
```
## Step 29 — Select SpawnLocation
```yaml
action: click
target:
  label: SpawnLocation
  kind: tree_item
  where: Explorer panel
check: SpawnLocation is selected again
source:
  t: 04:16-04:16
confidence: high
repeat_of: 7
```
## Step 30 — Activate Move tool
```yaml
action: click
target:
  label: Move
  kind: button
  where: Top toolbar
  menu_path:
  - Model
  - Move
  shortcut: '2'
check: move arrows appear on part
source:
  t: 04:18-04:20
confidence: high
```
## Step 31 — Move SpawnLocation
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: Viewport
params:
  direction: along ground plane
  from: move arrow on SpawnLocation
check: Position changes to 0.25, 0.375, 4.25
source:
  t: 04:18-04:22
confidence: high
```
## Step 32 — Activate Scale tool
```yaml
action: click
target:
  label: Scale
  kind: button
  where: Top toolbar
  menu_path:
  - Model
  - Scale
  shortcut: '3'
check: scale handles appear on part
source:
  t: 04:22-04:24
confidence: high
```
## Step 33 — Scale SpawnLocation wider
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: Viewport
params:
  direction: sideways
  from: scale handle on SpawnLocation
check: Size becomes 23.25, 0.75, 12
source:
  t: 04:22-04:25
confidence: high
```
## Step 34 — Activate Rotate tool
```yaml
action: click
target:
  label: Rotate
  kind: button
  where: Top toolbar
  menu_path:
  - Model
  - Rotate
  shortcut: '4'
check: rotation ring appears on part
source:
  t: 04:28-04:30
confidence: high
```
## Step 35 — Rotate SpawnLocation
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: Viewport
params:
  direction: around vertical axis
  from: rotation ring handle on SpawnLocation
check: part rotates with rotation gizmo showing
source:
  t: 04:30-04:32
confidence: high
```

# Transform and terrain

## Step 36 — Activate Transform tool
```yaml
action: click
target:
  label: Transform
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Transform
  shortcut: '5'
why: Combines moving, rotating and scaling in one tool, so you can edit without switching tools.
check: transform handles appear on SpawnLocation
source:
  t: 04:32-04:36
confidence: high
```
## Step 37 — Move with Transform
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: viewport
params:
  from: center of SpawnLocation
check: SpawnLocation moves in viewport
source:
  t: 04:36-04:38
confidence: high
```
## Step 38 — Rotate with Transform
```yaml
action: drag
target:
  label: rotation handle
  kind: canvas
  where: viewport
params:
  from: rotation handle
check: SpawnLocation rotates in viewport
source:
  t: 04:38-04:43
confidence: high
```
## Step 39 — Scale with Transform
```yaml
action: drag
target:
  label: scale handle
  kind: canvas
  where: viewport
params:
  from: scale handle
check: SpawnLocation scales showing 14.50 studs and 9.75 studs
source:
  t: 04:43-04:44
confidence: high
```
## Step 40 — Open Dragger modes
```yaml
action: click
target:
  label: Dragger modes
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Mode
check: Dragger modes menu with Geometric Physical options appears
source:
  t: 04:47-04:49
confidence: high
```
## Step 41 — Activate Move tool
```yaml
action: click
target:
  label: Move
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Move
  shortcut: '2'
check: move arrows appear on SpawnLocation
source:
  t: 04:54-04:57
confidence: high
repeat_of: 30
```
## Step 42 — Set Move snap to 10
```yaml
action: type
target:
  label: Move snap increment
  kind: field
  where: Home tab toolbar
params:
  value: '10'
why: Sets movement to jump 10 studs at a time, so parts line up evenly instead of drifting.
check: field shows 10 studs
verify:
  uia:
    name_contains: Move
    type: Edit
    value_contains: '10'
    window: Roblox Studio
    exists: true
source:
  t: 04:59-05:01
confidence: high
```
## Step 43 — Move with snap
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: viewport
check: drag label shows -10
source:
  t: 05:01-05:03
confidence: high
```
## Step 44 — Set Rotate snap to 10
```yaml
action: type
target:
  label: Rotate snap increment
  kind: field
  where: Home tab toolbar
params:
  value: '10'
why: Sets rotation to snap in 10-degree steps, so turns stay neat and easy to repeat.
check: field shows 10 degrees
verify:
  uia:
    name_contains: Rotate
    type: Edit
    value_contains: '10'
    window: Roblox Studio
    exists: true
source:
  t: 05:06-05:09
confidence: high
```
## Step 45 — Rotate with snap
```yaml
action: drag
target:
  label: SpawnLocation
  kind: canvas
  where: viewport
check: rotation indicator shows 30
source:
  t: 05:11-05:14
confidence: high
```
## Step 46 — Open Terrain Editor
```yaml
action: click
target:
  label: Terrain
  kind: button
  where: Home tab toolbar
  menu_path:
  - Home
  - Editor
check: Terrain Editor panel opens on left
verify:
  uia:
    name_contains: Terrain Editor
    type: Window
    window: Roblox Studio
    exists: true
source:
  t: 05:23-05:29
confidence: high
```
## Step 47 — Draw rock terrain
```yaml
action: drag
target:
  label: terrain
  kind: canvas
  where: viewport, use Draw with Add mode to add rock terrain
why: Adds solid rock ground you can walk on, showing how to build landscape instead of only parts.
check: small gray rock appears near SpawnLocation
source:
  t: 05:23-05:29
confidence: high
```
## Step 48 — Activate Paint tool
```yaml
action: click
target:
  label: Paint
  kind: button
  where: Terrain Editor panel
  menu_path:
  - Home
  - Terrain Editor
  - Edit
  - Paint
check: Paint tool active with Material Mode Paint Replace
source:
  t: 05:29-05:35
confidence: high
```
## Step 49 — Paint grass material
```yaml
action: drag
target:
  label: terrain
  kind: canvas
  where: viewport, paint grass material onto rock
why: Recolors the rock surface as grass without changing its shape, showing paint only changes looks.
check: rock becomes covered with green grass
source:
  t: 05:35-05:41
confidence: high
```
## Step 50 — Insert Part
```yaml
action: click
target:
  label: Part
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Part
why: Adds a basic block for building, the simplest object you can shape into anything else.
check: new Part block appears in viewport and in Explorer under Workspace
verify:
  uia:
    name: Part
    type: TreeItem
    window: Roblox Studio
    exists: true
source:
  t: 05:49-05:59
confidence: high
```

# Parts and Toolbox

## Step 51 — Lock Part
```yaml
action: click
target:
  label: Lock
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Lock
  shortcut: Alt+L
why: so you can hover over the other parts on your floor without moving the ground
check: Part stays selected and becomes locked
source:
  t: 06:02-06:06
confidence: high
```
## Step 52 — Anchor Part
```yaml
action: click
target:
  label: Anchor
  kind: button
  where: Home tab toolbar
  menu_path:
  - Model
  - Anchor
  shortcut: Alt+A
why: to make the ground immovable by physics
check: Part becomes anchored
source:
  t: 06:09-06:13
confidence: high
```
## Step 53 — Insert Sphere Part
```yaml
action: menu_path
target:
  label: Sphere
  kind: menu_item
  where: Home tab toolbar, Part dropdown
  menu_path:
  - Part
  - Sphere
check: Second Part appears in Explorer and white ball appears on green ground
verify:
  uia:
    name_contains: Sphere
    type: TreeItem
    window: Roblox Studio
    exists: true
source:
  t: 06:11-06:11
confidence: high
```
## Step 54 — Start playtest
```yaml
action: click
target:
  label: Play
  kind: button
  where: Test play controls at top
  menu_path:
  - Home
  - Play
  shortcut: F5
check: Play mode starts with avatar on green ground
source:
  t: 06:14-06:17
confidence: high
repeat_of: 23
```
## Step 55 — Stop playtest
```yaml
action: click
target:
  label: Stop
  kind: button
  where: Play mode controls at top
  menu_path:
  - Home
  - Stop
  shortcut: Shift+F5
check: Editor view returns
source:
  t: 06:29-06:35
confidence: high
repeat_of: 24
```
## Step 56 — Open Toolbox
```yaml
action: click
target:
  label: Toolbox
  kind: button
  where: Home tab toolbar
  menu_path:
  - View
  - Toolbox
check: Toolbox panel appears on left
verify:
  uia:
    name_contains: Toolbox
    type: Window
    window: Roblox Studio
    exists: true
source:
  t: 06:31-06:35
confidence: high
```
## Step 57 — Open Creator Store tab
```yaml
action: click
target:
  label: Creator Store
  kind: tab
  where: Toolbox panel header
  menu_path:
  - View
  - Toolbox
  - Creator Store
check: Creator Store assets including Road are visible
verify:
  uia:
    name: Creator Store
    type: TabItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 06:40-06:41
confidence: high
```
## Step 58 — Insert Road model
```yaml
action: click
target:
  label: Road
  kind: button
  where: Toolbox panel, Creator Store tab, Essential section
why: Adds a ready-made road, showing you can reuse free models instead of building everything.
check: Road model appears in viewport and in Explorer as Road
verify:
  uia:
    name: Road
    type: TreeItem
    window: Roblox Studio
    exists: true
source:
  t: 06:40-06:47
confidence: high
```
## Step 59 — Close Toolbox
```yaml
action: click
target:
  label: Toolbox
  kind: button
  where: Home tab toolbar
  menu_path:
  - View
  - Toolbox
check: Toolbox panel is closed
verify:
  uia:
    name_contains: Toolbox
    type: Window
    window: Roblox Studio
    exists: false
source:
  t: 07:07-07:10
confidence: high
repeat_of: 56
```
## Step 60 — Open Model tab
```yaml
action: click
target:
  label: Model
  kind: tab
  where: top ribbon tabs
  menu_path:
  - Model
  - Model
check: Model tab toolbar appears
verify:
  uia:
    name: Model
    type: TabItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 07:13-07:18
confidence: high
```
## Step 61 — Open Effects list
```yaml
action: click
target:
  label: Effect
  kind: button
  where: Model tab toolbar
  menu_path:
  - Model
  - Effects
why: Shows addable visuals like fire and lights, which make parts glow, sparkle or shine.
check: Effects list appears showing Beam, Explosion, Fire, Highlight, ParticleEmitter, Smoke, Sparkles, Trail, PointLight,
  SpotLight, SurfaceLight
source:
  t: 07:20-07:25
confidence: high
```

# Plugins

## Step 62 — Open Plugins tab
```yaml
action: click
target:
  label: Plugins
  kind: tab
  where: top ribbon
  menu_path:
  - Plugins
check: Plugins toolbar with plugin icons appears
verify:
  uia:
    name: Plugins
    type: TabItem
    window: Roblox Studio
    selected: true
    exists: true
source:
  t: 07:36-07:38
confidence: high
```
## Step 63 — Run Magic Wand
```yaml
action: click
target:
  label: Magic Wand
  kind: button
  where: Plugins toolbar
why: instead of grabbing all of them individually
check: Magic Wand window opens and all green parts become selected
verify:
  uia:
    name_contains: Magic Wand
    type: Window
    window: Roblox Studio
    exists: true
source:
  t: 08:04-08:06
confidence: high
```
## Step 64 — Recolor selection
```yaml
action: click
target:
  label: Color
  kind: field
  where: Properties panel in Appearance section
why: to make all of them the same color
check: parts turn light blue Pastel Blue
source:
  t: 08:09-08:11
confidence: high
```
## Step 65 — Open Part to Terrain
```yaml
action: click
target:
  label: Part to Terrain
  kind: button
  where: Plugins toolbar
why: to make them terrain
check: Part to Terrain window opens
verify:
  uia:
    name_contains: Part to Terrain
    type: Window
    window: Roblox Studio
    exists: true
source:
  t: 08:15-08:17
confidence: high
```
## Step 66 — Select Cobblestone material
```yaml
action: click
target:
  label: Cobblestone
  kind: button
  where: Part to Terrain window in Materials grid
check: cobblestone material is selected
source:
  t: 08:17-08:19
confidence: high
```
## Step 67 — Convert part to terrain
```yaml
action: pick
target:
  label: Part
  kind: face
  where: viewport
  menu_path:
  - Model
  - Part
why: Turns the built block into natural ground, so it blends with terrain instead of staying separate.
check: clicked part becomes cobblestone terrain
source:
  t: 08:19-08:23
confidence: high
```
