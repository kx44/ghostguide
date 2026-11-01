Does {app}{version_words} have a built-in way to search for its commands by name, from inside the program? For example a command palette or a search box that finds commands. Look in its official help or documentation.

Report:
- `name`: what the program calls it.
- `keys`: the default key or key combination that opens it, on Windows. Leave it out if there isn't one.
- `how`: one short sentence, only if something more is needed to find or use it, such as where its box is or what to do with a result.
- `source`: the URL of the page that says so.

Search twice at most, and stop as soon as one page answers it: each search costs money, and this is a small fact. Only report what a page you found actually says. Prefer the vendor's own documentation over forums and blogs. A search of the help pages alone doesn't count.

Reply with only a JSON object, no other text: {{"name": "...", "keys": "...", "how": "...", "source": "https://..."}}. If it has no such search, reply {{"none": true}}. If you can't tell, reply {{}}.
