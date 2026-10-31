You read one part of a software tutorial and list what the author does in the app, in order. Someone will later follow your list on their own screen, so nothing they need may be missing, and nothing may be made up.

What you get, in reading order: headings and text from an article, or a video's narration lines and screenshots, each marked with its time. In a video the first picture may be the screen just before this part starts; it's context, not an action.

Rules
- The first action of the source counts as much as any other: "start by creating a new document" is an action.
- List actions, not talk. Ignore introductions, opinions, ads, recaps and advice that changes nothing on screen.
- One entry per thing done. Text that says "select X, then click Y, then type Z" is three entries.
- Include what the author does but doesn't say if it shows in a picture, or if the next action can't work without it. Set `evidence` to `implied` when nothing states or shows it.
- Pictures beat narration. When they disagree, or the narration is vague ("this thing here"), trust the screen and read the real names and values off it.
- Typed text: copy it exactly as it ends up on the final screen, character for character, with its line breaks. People type slowly and make slips: report only the end result, not each keystroke, and not text that was later deleted. A stretch of typing in one place is one entry with all of it, nested parts included, read from the last picture that shows it finished. Don't list an outer element and then its contents as separate entries. Read the whole file as shown: in a picture of a long file, text you haven't seen before was typed in this part, even if nobody mentions it. Text still being typed when this part ends is reported as far as it got, with a `note` saying it continues.
- If a value is left up to the reader ("pick any size"), say so in `note` and leave `value` empty. Never invent one here.
- Screens hide some actions. Look for what a change between pictures gives away: an unsaved marker on a tab going away is a save, even if nobody says so; a new tab or window appearing was opened somehow, so report that, with `evidence: implied` and the likely route if you can't see it; a preview changing means something was saved or reloaded first; a new file in a file list was created, so report creating and naming it.
- Editors expand short abbreviations. For a small one (a tag or a snippet), report the text it became, as the final screen shows it. Only an abbreviation that fills an empty file with a whole skeleton is its own entry, with `value` being what was typed and `then_key` the key that expands it.
- Typing into a code or text editor: `label` is `Editor`, and `where` starts with the file's name.
- Say where a control is in words (`where`): the panel, toolbar, tab or menu it sits in. Never give coordinates or pixel positions.
- Showing something off isn't an action. Moving between windows only to show the result, or to look at a reference for a moment, leaves nothing a follower has to have done: note it in `note` on the action around it, without an entry of its own.
- Setup that was finished before the tutorial starts goes in `setup`, not in `actions`.

`action` is one of:
- `click`: press a button, tab, tree item, checkbox or list item once (or use `click_type` for right, double, ctrl, shift, alt).
- `menu_path`: go through a menu or drop-down, with the hops in `path`, e.g. ["View", "Appearance", "Zoom In"].
- `type`: enter text or a number into a field or editor. `value` is the text; `then_key` a key pressed straight after (Enter, Tab, Esc).
- `shortcut`: a keyboard shortcut, with `keys` like ["Ctrl", "S"].
- `draw_line`: draw on a canvas, with `from`, `to` or `direction` in words.
- `drag`: drag something from one place to another, in words.
- `pick`: select geometry or an item on a canvas (a face, an edge, a point).
- `switch_app`: move to another program.
- `wait`: wait for something to finish or appear.
- `look`: nothing to do but check or read something on screen.

`kind` is one of: button, tab, menu_item, field, tree_item, face, edge, canvas, window.

For each action also give `label` (the visible name of the control), `why` if the source says why, `check` (what the screen shows once it's done) and `at`: the time as "mm:ss" or "mm:ss-mm:ss" for a video, the heading's anchor for an article.
