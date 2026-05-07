# Symbol Library

A reusable reference of Unicode glyphs for UI work. These render in your text
font (not as emoji), so they look native in toolbars, buttons, log lines,
status badges, and labels — across web, native, and terminal UIs.

Copy-paste any symbol directly. All are single Unicode codepoints unless noted.

---

## Media / disc / transport

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| ⏵     | Play              | Start, resume                  |
| ⏸     | Pause             | Pause                          |
| ⏹     | Stop              | Stop session, halt             |
| ⏺     | Record            | Rip / record                   |
| ⏭     | Skip next         | Next title                     |
| ⏮     | Skip prev         | Previous title                 |
| ⏩     | Fast forward      | Seek                           |
| ⏪     | Rewind            | Seek back                      |
| ⏏     | Eject             | Eject disc                     |
| ◉     | Fisheye           | Disc, "selected"               |
| ◎     | Bullseye          | Target, focus                  |
| ⊙     | Circled dot       | Active state                   |
| ⊚     | Circled ring      | Inactive state                 |

## File / list / grid

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| ▤     | Horizontal fill   | List view                      |
| ▦     | Square mesh       | Grid view                      |
| ▣     | Square + dot      | Selected tile                  |
| ▥     | Vertical fill     | Columns                        |
| ▧ ▨   | Diagonal fills    | Striped placeholders           |
| ▩     | Cross fill        | Hatched placeholder            |
| ⬢     | Black hex         | Title / track                  |
| ⬡     | White hex         | Empty title slot               |
| ☰     | Trigram           | Menu / list / hamburger        |
| ⋮     | Vertical ellipsis | Overflow menu                  |
| ⋯     | Horizontal ellip. | More actions                   |

## Action / state

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| ✓     | Check             | Success, done                  |
| ✔     | Heavy check       | Strong success                 |
| ✗     | Cross             | Fail, dismiss                  |
| ✘     | Heavy cross       | Strong fail                    |
| ⚠     | Warning           | Caution, prep                  |
| ⓘ     | Circled i         | Info                           |
| ⊕     | Circled plus      | Add                            |
| ⊖     | Circled minus     | Remove                         |
| ⊘     | Circled slash     | Disabled, blocked              |
| ⊗     | Circled cross     | Cancel, close                  |
| ↻     | Clockwise arrow   | Refresh                        |
| ↺     | Counter-clockwise | Undo, revert                   |
| ⟲ ⟳   | Curved arrows     | Reload variants                |
| ⌫     | Erase left        | Backspace, delete              |
| ⌦     | Erase right       | Forward delete                 |

## Direction / navigation

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| → ← ↑ ↓     | Arrows      | Navigation                     |
| ↗ ↘ ↙ ↖     | Diagonal    | External, expand               |
| ↔ ↕         | Bidirectional | Resize                       |
| ⇒ ⇐ ⇑ ⇓     | Heavy arrows | Strong direction              |
| ⇡ ⇣ ⇠ ⇢     | Dashed arrows | Upload / download             |
| ▸ ▾ ▴ ◂     | Small tris  | Combobox arrow, disclosure    |
| ▶ ◀ ▲ ▼     | Solid tris  | Playhead, dropdown            |

## Tools / settings / keyboard

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| ⚙     | Gear              | Settings                       |
| ⚒     | Hammer + pick     | Build, prep, tools             |
| ⌘     | Command key       | Keyboard shortcut              |
| ⎇     | Option key        | Keyboard shortcut              |
| ⏎     | Return            | Enter, submit                  |
| ⇧     | Shift             | Keyboard shortcut              |
| ⌕     | Search            | Find                           |
| ⌗     | Hash / number     | Tags, channels                 |
| ⎘     | Copy / page       | Copy log, duplicate            |
| ⎗     | Page back         | Previous page                  |

## Status indicators (pair with color)

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| ●     | Filled circle     | Active, online                 |
| ○     | Empty circle      | Idle, offline                  |
| ◐ ◑ ◒ ◓ | Half circles   | Loading phases                 |
| ◆     | Filled diamond    | Marker, selected               |
| ◇     | Empty diamond     | Unselected                     |
| ◈     | Diamond + dot     | Active marker                  |
| ★ ☆   | Stars             | Favorite, rating               |
| ⬤     | Big filled circle | Strong active dot              |

## Type ornaments / dividers

| Glyph | Name              | Good for                       |
|-------|-------------------|--------------------------------|
| · • ‣ ◦ ⁃ ・ | Bullets    | Lists, separators              |
| — – ‒        | Em/en dashes | Inline punctuation           |
| ⌜ ⌝ ⌞ ⌟      | Corner brackets | Log groupings, quotes      |
| ⎯ ⎻ ⎼ ⎽      | Horizontal rules | Varying-weight dividers   |
| ▏▎▍▌▋▊▉█     | Vertical bar widths | Custom progress bars   |

---

## Suggested mappings for JellyRip-style apps

| Action            | Glyph |
|-------------------|-------|
| Rip TV Show       | ⏺     |
| Rip Movie         | ⏵     |
| Dump All Titles   | ⇣     |
| Organize MKVs     | ▤     |
| Prep for FFmpeg   | ⚒     |
| Settings          | ⚙     |
| Check Updates     | ⇡     |
| Copy Log          | ⎘     |
| Browse Folder     | →     |
| Refresh           | ↻     |
| Stop Session      | ⏹     |
| Eject Disc        | ⏏     |
| Disc detected     | ◉     |
| Confirm prompt    | ⓘ     |
| Warning prompt    | ⚠     |
| Success log line  | ✓     |
| Error log line    | ✗     |
| Streaming dot     | ●     |
| Idle dot          | ○     |

---

## Tips for using these in UIs

- **Render in your text font, not a fallback.** If your font lacks a glyph
  the OS will substitute (often badly). Test in the actual font stack —
  Segoe UI, SF Pro, Inter, JetBrains Mono all cover most of these.
- **Size them up ~10–15%** relative to surrounding text. They're designed
  for body text and look small on buttons. `font-size: 1.1em` works.
- **Vertical-align: middle** on inline icons next to text labels.
- **Avoid mixing emoji and these glyphs** in the same UI — emoji are full
  color and will break the monochrome rhythm.
- **Tabular-nums** (`font-variant-numeric: tabular-nums`) keeps digits
  aligned next to status glyphs.
- **For accessibility**, wrap decorative glyphs in `<span aria-hidden="true">`
  and put the action name in the button's accessible label.
