# Symbol Library

The exhaustive, deduplicated reference of monochrome Unicode glyphs for UI
work. These render in your text font (not as colored emoji), so they stay
single-color, scale with text, and look native in toolbars, buttons, log
lines, status badges, menu items, dialogs, and terminals — across web,
Qt/PySide6, native desktop, and CLI.

**Conventions used in this file**

- Every glyph is listed **exactly once** — no duplicates between sections.
  Cross-references point to canonical entries.
- Every entry has its **codepoint** so you can verify in any font inspector.
- Glyphs that default to color emoji on Apple platforms are flagged
  **(emoji-default)** with the U+FE0E recipe noted.
- Two-codepoint sequences are written as `U+XXXX U+YYYY`.

---

## Contents

1. [JellyRip action map](#1-jellyrip-action-map)
2. [Media & transport](#2-media--transport)
3. [Disc & drive states](#3-disc--drive-states)
4. [File, folder & document](#4-file-folder--document)
5. [List, grid & layout](#5-list-grid--layout)
6. [Action, state & feedback](#6-action-state--feedback)
7. [Edit & input](#7-edit--input)
8. [Direction & navigation arrows](#8-direction--navigation-arrows)
9. [Tools & settings](#9-tools--settings)
10. [Keyboard & shortcuts](#10-keyboard--shortcuts)
11. [Status dots & live indicators](#11-status-dots--live-indicators)
12. [Stars, sparkles & favorites](#12-stars-sparkles--favorites)
13. [Numbered & circled digits](#13-numbered--circled-digits)
14. [Progress, bars & sparklines](#14-progress-bars--sparklines)
15. [Math, logic & sets](#15-math-logic--sets)
16. [Currency, commerce & legal](#16-currency-commerce--legal)
17. [Communication & social](#17-communication--social)
18. [Weather, nature & celestial](#18-weather-nature--celestial)
19. [Hands & gestures](#19-hands--gestures)
20. [Geometric shapes](#20-geometric-shapes)
21. [Hexagons, polygons & decorative](#21-hexagons-polygons--decorative)
22. [Type ornaments & dividers](#22-type-ornaments--dividers)
23. [Quotes & guillemets](#23-quotes--guillemets)
24. [Brackets & fences](#24-brackets--fences)
25. [Box drawing & block elements](#25-box-drawing--block-elements)
26. [Music & audio](#26-music--audio)
27. [Games, dice & cards](#27-games-dice--cards)
28. [Religious, esoteric & cultural](#28-religious-esoteric--cultural)
29. [Astrology & zodiac](#29-astrology--zodiac)
30. [Alchemy & science](#30-alchemy--science)
31. [Phonetic & language](#31-phonetic--language)
32. [APL & technical operators](#32-apl--technical-operators)
33. [Braille](#33-braille)
34. [Roman numerals & ordered lists](#34-roman-numerals--ordered-lists)
35. [Letter-like symbols](#35-letter-like-symbols)
36. [Usage tips](#usage-tips)
37. [Ready-to-paste recipes](#ready-to-paste-recipes)
38. [Font coverage notes](#font-coverage-notes)
39. [Glossary](#glossary)

---

## 1. JellyRip action map

Every action surface in JellyRip with its glyph + reasoning. Each label
keeps the leading glyph as part of the visible button text. Convention:
**two spaces** between glyph and label.

### Primary action row

| Action            | Glyph | Codepoint | Why                                       |
|-------------------|-------|-----------|-------------------------------------------|
| Rip TV Show Disc  | ⏺     | U+23FA    | Record — universal "capture this"         |
| Rip Movie Disc    | ⏵     | U+23F5    | Play triangle — single-shot transport     |
| Dump All Titles   | ⇣     | U+21E3    | Dashed down arrow — pull everything down  |

### Secondary action row

| Action                          | Glyph | Codepoint | Why                              |
|---------------------------------|-------|-----------|----------------------------------|
| Organize Existing MKVs          | ▤     | U+25A4    | Horizontal-fill square — list    |
| Prep MKVs For FFmpeg/HandBrake  | ⚒     | U+2692    | Hammer + pick — tools/build      |

### Drive row

| Action             | Glyph | Codepoint | Why                                       |
|--------------------|-------|-----------|-------------------------------------------|
| Refresh drive list | ↻     | U+21BB    | Clockwise arrow — universal refresh       |
| Eject disc         | ⏏     | U+23CF    | Eject — only correct glyph                |
| Disc inserted      | ◉     | U+25C9    | Fisheye — loaded media                    |
| No disc            | ⊚     | U+229A    | Empty ring — tray empty                   |
| Drive scanning     | ◐     | U+25D0    | Half circle — animate rotation            |

### Utility row

| Action            | Glyph | Codepoint | Why                                        |
|-------------------|-------|-----------|--------------------------------------------|
| Settings          | ⚙     | U+2699    | Gear — universal settings                  |
| Check Updates     | ⇡     | U+21E1    | Dashed up arrow — pull a new version       |
| Copy Log          | ⎘     | U+2398    | Next page — system-typography lineage      |
| Browse Folder     | →     | U+2192    | Arrow — go to                              |
| Open Logs Folder  | ⌕     | U+2315    | Telephone recorder — search/lookup         |
| Help / Docs       | ?     | U+003F    | Plain `?`                                  |
| About             | ⓘ     | U+24D8    | Info circle                                |
| Reset / Clear     | ⌫     | U+232B    | Erase left                                 |

### Session controls

| Action          | Glyph | Codepoint | Notes                                      |
|-----------------|-------|-----------|--------------------------------------------|
| Stop Session    | ⏹     | U+23F9    | Stop square                                |
| Pause Session   | ⏸     | U+23F8    | Pause                                      |
| Resume Session  | ⏵     | U+23F5    | Play                                       |
| Toggle play     | ⏯     | U+23EF    | Play/pause toggle                          |
| Cancel          | ⊗     | U+2297    | Circled cross — soft cancel                |
| Close Dialog    | ✗     | U+2717    | Cross                                      |
| Confirm         | ✓     | U+2713    | Check                                      |

### Log-line prefixes

| Line type        | Glyph | Codepoint | Notes                                      |
|------------------|-------|-----------|--------------------------------------------|
| Info             | ⓘ     | U+24D8    | Info circle                                |
| Success          | ✓     | U+2713    | Check                                      |
| Warning          | ⚠     | U+26A0    | Warning **(emoji-default)**                |
| Error            | ✗     | U+2717    | Cross                                      |
| Critical         | ✘     | U+2718    | Heavy cross                                |
| Prompt (y/n)     | ?     | U+003F    | Plain `?` reads cleanly in monospace       |
| Pending          | ◦     | U+25E6    | Empty bullet                               |
| In progress      | ◐     | U+25D0    | Half circle — animate rotation             |
| Skipped          | ⊘     | U+2298    | Circled slash                              |
| Streaming dot    | ●     | U+25CF    | Pulse with CSS animation                   |
| Idle dot         | ○     | U+25CB    | No animation                               |
| Debug            | ⌬     | U+232C    | Benzene ring — reads as "dev"              |
| Trace            | ›     | U+203A    | Single guillemet — quiet bullet            |

### Status / progress / metadata

| Field          | Glyph | Codepoint | Notes                                       |
|----------------|-------|-----------|---------------------------------------------|
| ETA            | ⏱     | U+23F1    | Stopwatch                                   |
| Countdown      | ⏲     | U+23F2    | Timer                                       |
| Long-running   | ⏳     | U+23F3    | Hourglass flowing                           |
| Disc size      | ⬢     | U+2B22    | Solid hex — title block                     |
| Estimated size | ⬡     | U+2B21    | Empty hex — estimate                        |
| Bitrate        | ▎     | U+258E    | Vertical bar                                |
| Bytes / data   | ≡     | U+2261    | Triple bar                                  |
| Network        | ⇅     | U+21C5    | Up + down — transfer                        |

---

## 2. Media & transport

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⏵     | U+23F5    | Play              | Start, resume                  |
| ⏸     | U+23F8    | Pause             | Pause                          |
| ⏹     | U+23F9    | Stop              | Stop, halt                     |
| ⏺     | U+23FA    | Record            | Rip / capture                  |
| ⏭     | U+23ED    | Skip next         | Next title                     |
| ⏮     | U+23EE    | Skip prev         | Previous title                 |
| ⏩     | U+23E9    | Fast forward      | Seek forward                   |
| ⏪     | U+23EA    | Rewind            | Seek backward                  |
| ⏫     | U+23EB    | Double up         | Top of list / fast up          |
| ⏬     | U+23EC    | Double down       | Bottom of list / fast down     |
| ⏏     | U+23CF    | Eject             | Eject                          |
| ⏯     | U+23EF    | Play / pause      | Single toggle button           |
| ⏱     | U+23F1    | Stopwatch         | ETA, timing                    |
| ⏲     | U+23F2    | Timer             | Countdown                      |
| ⏳     | U+23F3    | Hourglass flowing | Long-running                   |
| ⌛     | U+231B    | Hourglass static  | Wait state                     |
| ▶     | U+25B6    | Solid right tri   | Playhead, dropdown right       |
| ▷     | U+25B7    | Outlined right    | Disabled play                  |
| ◀     | U+25C0    | Solid left tri    | Reverse                        |
| ◁     | U+25C1    | Outlined left     | Disabled reverse               |

## 3. Disc & drive states

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ◉     | U+25C9    | Fisheye           | Disc inserted, "selected"      |
| ◎     | U+25CE    | Bullseye          | Target, focus                  |
| ⊙     | U+2299    | Circled dot       | Active state                   |
| ⊚     | U+229A    | Circled ring      | Inactive / empty tray          |
| ◍     | U+25CD    | Striped circle    | Buffering                      |
| ◌     | U+25CC    | Dotted circle     | Placeholder, not present       |
| ◐     | U+25D0    | Half left filled  | Loading 25%                    |
| ◑     | U+25D1    | Half right filled | Loading 75%                    |
| ◒     | U+25D2    | Half bottom       | Loading 50%                    |
| ◓     | U+25D3    | Half top          | Loading 50% variant            |
| ◔     | U+25D4    | Quarter top-right | 25%                            |
| ◕     | U+25D5    | Three-quarter     | 75%                            |
| ◖     | U+25D6    | Left half black   | Pill cap left                  |
| ◗     | U+25D7    | Right half black  | Pill cap right                 |

## 4. File, folder & document

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⎙     | U+2399    | Print screen      | Snapshot, screenshot           |
| ⎘     | U+2398    | Next page         | Copy, duplicate                |
| ⎗     | U+2397    | Previous page     | Previous version               |
| ⎚     | U+239A    | Clear screen      | Clear log                      |
| ⊞     | U+229E    | Squared plus      | Add file / new                 |
| ⊟     | U+229F    | Squared minus     | Remove file                    |
| ⊠     | U+22A0    | Squared cross     | Mark for deletion              |
| ⊡     | U+22A1    | Squared dot       | Selected file                  |
| ▤     | U+25A4    | Horizontal fill   | List view                      |
| ▥     | U+25A5    | Vertical fill     | Columns                        |
| ▦     | U+25A6    | Square mesh       | Grid view                      |
| ▣     | U+25A3    | Square + dot      | Selected tile                  |
| ▩     | U+25A9    | Cross fill        | Hatched placeholder            |
| ▧     | U+25A7    | Diagonal up       | Striped placeholder            |
| ▨     | U+25A8    | Diagonal down     | Striped placeholder            |
| ⌬     | U+232C    | Benzene ring      | Compound / structure           |

## 5. List, grid & layout

| Glyph | Codepoint | Name                  | Use                        |
|-------|-----------|-----------------------|----------------------------|
| ☰     | U+2630    | Trigram heaven        | Hamburger menu             |
| ☱     | U+2631    | Trigram lake          | Menu variant               |
| ☲     | U+2632    | Trigram fire          | Menu variant               |
| ☳     | U+2633    | Trigram thunder       | Menu variant               |
| ☴     | U+2634    | Trigram wind          | Menu variant               |
| ☵     | U+2635    | Trigram water         | Menu variant               |
| ☶     | U+2636    | Trigram mountain      | Menu variant               |
| ☷     | U+2637    | Trigram earth         | Stack / layered            |
| ⋮     | U+22EE    | Vertical ellipsis     | Overflow menu              |
| ⋯     | U+22EF    | Horizontal ellipsis   | More actions               |
| ⋰     | U+22F0    | Up-right diagonal     | Trends up                  |
| ⋱     | U+22F1    | Down-right diagonal   | Trends down                |
| ⫶     | U+2AF6    | Triple colon          | Strong overflow            |
| ⫼     | U+2AFC    | Quadruple bar         | Heavy divider              |
| ⌗     | U+2317    | Viewdata square       | Tags, channels             |
| ⌸     | U+2338    | APL squish            | Compact / collapse         |
| ⌹     | U+2339    | APL quad divide       | Split view                 |
| ⌺     | U+233A    | APL diamond           | Merge / branch             |

## 6. Action, state & feedback

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ✓     | U+2713    | Check             | Success, done                  |
| ✔     | U+2714    | Heavy check       | Strong success                 |
| ✗     | U+2717    | Ballot X          | Fail, dismiss, close           |
| ✘     | U+2718    | Heavy ballot X    | Strong fail                    |
| ✕     | U+2715    | Multiplication X  | Close button                   |
| ✖     | U+2716    | Heavy mult X      | Strong close                   |
| ✚     | U+271A    | Heavy plus        | Add                            |
| ⚠     | U+26A0    | Warning sign      | Caution **(emoji-default)**    |
| ⛔     | U+26D4    | No entry          | Blocked **(emoji-default)**    |
| ⓘ     | U+24D8    | Circled i         | Info                           |
| ⓧ     | U+24E7    | Circled x         | Cancel                         |
| ⊕     | U+2295    | Circled plus      | Add                            |
| ⊖     | U+2296    | Circled minus     | Remove                         |
| ⊗     | U+2297    | Circled cross     | Cancel                         |
| ⊘     | U+2298    | Circled slash     | Disabled, blocked              |
| ⊛     | U+229B    | Circled asterisk  | Wildcard, special              |
| ⦿     | U+29BF    | Circled bullet    | Strong selected                |
| ☑     | U+2611    | Checkbox checked  | Checkbox state                 |
| ☐     | U+2610    | Checkbox empty    | Checkbox state                 |
| ☒     | U+2612    | Checkbox X        | Rejected                       |
| ⚐     | U+2690    | White flag        | Draft, surrender               |
| ⚑     | U+2691    | Black flag        | Bookmark, marked               |
| ↻     | U+21BB    | Clockwise arrow   | Refresh                        |
| ↺     | U+21BA    | Counter-clockwise | Undo                           |
| ⟲     | U+27F2    | Anticlockwise gap | Reload variant                 |
| ⟳     | U+27F3    | Clockwise gap     | Reload variant                 |
| ↶     | U+21B6    | Curve left        | Undo                           |
| ↷     | U+21B7    | Curve right       | Redo                           |
| ⤺     | U+293A    | Top arc anti      | Undo (alt)                     |
| ⤻     | U+293B    | Bottom arc clk    | Redo (alt)                     |
| ⎌     | U+238C    | Undo control      | Undo (rare font support)       |

## 7. Edit & input

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ✎     | U+270E    | Pencil down-right | Edit                           |
| ✏     | U+270F    | Pencil            | Edit                           |
| ✐     | U+2710    | Pencil up-right   | Edit                           |
| ✑     | U+2711    | Nib               | Write, sign                    |
| ✒     | U+2712    | Black nib         | Write                          |
| ✂     | U+2702    | Scissors          | Cut **(emoji-default)**        |
| ✄     | U+2704    | Scissors open     | Cut                            |
| ⌫     | U+232B    | Erase left        | Backspace                      |
| ⌦     | U+2326    | Erase right       | Forward delete                 |
| ⤴     | U+2934    | Curve up arrow    | Indent                         |
| ⤵     | U+2935    | Curve down arrow  | Outdent                        |
| ⌑     | U+2311    | Square lozenge    | Diamond marker                 |
| ⌖     | U+2316    | Position indicator| Crosshair, target              |

## 8. Direction & navigation arrows

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ←     | U+2190    | Left arrow        | Back                           |
| ↑     | U+2191    | Up arrow          | Up                             |
| →     | U+2192    | Right arrow       | Forward                        |
| ↓     | U+2193    | Down arrow        | Down                           |
| ↔     | U+2194    | Left-right        | Resize horizontal              |
| ↕     | U+2195    | Up-down           | Resize vertical                |
| ↖     | U+2196    | NW arrow          | Home / corner                  |
| ↗     | U+2197    | NE arrow          | External link                  |
| ↘     | U+2198    | SE arrow          | End / corner                   |
| ↙     | U+2199    | SW arrow          | Corner                         |
| ↩     | U+21A9    | Hooked left       | Reply                          |
| ↪     | U+21AA    | Hooked right      | Forward                        |
| ↰     | U+21B0    | Cornered up-left  | Branch                         |
| ↱     | U+21B1    | Cornered up-right | Branch                         |
| ↲     | U+21B2    | Cornered down-l   | Indent return                  |
| ↳     | U+21B3    | Cornered down-r   | Indent return                  |
| ⇐     | U+21D0    | Heavy left        | Strong back                    |
| ⇑     | U+21D1    | Heavy up          | Strong up                      |
| ⇒     | U+21D2    | Heavy right       | Strong forward                 |
| ⇓     | U+21D3    | Heavy down        | Strong down                    |
| ⇔     | U+21D4    | Heavy bi-h        | Resize, swap                   |
| ⇕     | U+21D5    | Heavy bi-v        | Resize, swap                   |
| ⇠     | U+21E0    | Dashed left       | Pull left                      |
| ⇡     | U+21E1    | Dashed up         | Upload                         |
| ⇢     | U+21E2    | Dashed right      | Push right                     |
| ⇣     | U+21E3    | Dashed down       | Download                       |
| ⇤     | U+21E4    | Tab left          | Shift+Tab                      |
| ⇥     | U+21E5    | Tab right         | Tab                            |
| ⇦     | U+21E6    | Hollow left       | Modifier-style                 |
| ⇧     | U+21E7    | Hollow up         | Shift                          |
| ⇨     | U+21E8    | Hollow right      | Modifier-style                 |
| ⇩     | U+21E9    | Hollow down       | Modifier-style                 |
| ⇪     | U+21EA    | Caps lock         | Caps Lock                      |
| ⇄     | U+21C4    | Right over left   | Swap                           |
| ⇅     | U+21C5    | Up over down      | Transfer                       |
| ⇆     | U+21C6    | Left over right   | Swap                           |
| ⇵     | U+21F5    | Down over up      | Transfer reversed              |
| ⇞     | U+21DE    | Page up           | PgUp                           |
| ⇟     | U+21DF    | Page down         | PgDn                           |
| ▴     | U+25B4    | Up small tri      | Sort asc                       |
| ▾     | U+25BE    | Down small tri    | Disclosure                     |
| ◂     | U+25C2    | Left small tri    | Collapse                       |
| ▸     | U+25B8    | Right small tri   | Expand                         |
| ⌃     | U+2303    | Up caret          | macOS chevron                  |
| ⌄     | U+2304    | Down caret        | macOS chevron                  |
| ⤒     | U+2912    | Bar up            | Top                            |
| ⤓     | U+2913    | Bar down          | Bottom                         |
| ⥅     | U+2945    | Plus right        | Insert right                   |
| ⥆     | U+2946    | Plus left         | Insert left                    |
| ⤶     | U+2936    | Curve down-left   | Reply down                     |
| ⤷     | U+2937    | Curve down-right  | Indent reply                   |

## 9. Tools & settings

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⚙     | U+2699    | Gear              | Settings                       |
| ⚒     | U+2692    | Hammer + pick     | Build / prep / tools           |
| ⚓     | U+2693    | Anchor            | Pin                            |
| ⚔     | U+2694    | Crossed swords    | Conflict, merge **(emoji-default)** |
| ⚖     | U+2696    | Balance scale     | Compare / equality             |
| ⚗     | U+2697    | Alembic           | Experiment, beta               |
| ⚛     | U+269B    | Atom              | Science, fundamental           |
| ⚡     | U+26A1    | High voltage      | Power **(emoji-default)**      |
| ⛏     | U+26CF    | Pick              | Mining, extraction             |
| ⛓     | U+26D3    | Chains            | Linked, dependency             |
| ⌕     | U+2315    | Telephone recorder| Search, find                   |

## 10. Keyboard & shortcuts

| Glyph | Codepoint | Name                  | macOS / use                |
|-------|-----------|-----------------------|----------------------------|
| ⌘     | U+2318    | Place of interest     | macOS Command              |
| ⌥     | U+2325    | Option key            | macOS Option               |
| ⎇     | U+2387    | Alternative key       | Linux Alt                  |
| ⏎     | U+23CE    | Return                | Enter                      |
| ⌅     | U+2305    | Projective            | Enter (alt)                |
| ⌤     | U+2324    | Up arrow box          | Apple Extended Enter       |
| ⎋     | U+238B    | Broken circle         | Escape                     |
| ␣     | U+2423    | Open box              | Space                      |
| F1…F12| —         | Function keys         | Use literal text "F1"…     |

## 11. Status dots & live indicators

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ●     | U+25CF    | Filled circle     | Active, online, streaming      |
| ○     | U+25CB    | Empty circle      | Idle, offline                  |
| ◯     | U+25EF    | Large circle      | Empty large dot                |
| ⬤     | U+2B24    | Big filled        | Strong active                  |
| ◆     | U+25C6    | Filled diamond    | Marker                         |
| ◇     | U+25C7    | Empty diamond     | Unselected                     |
| ◈     | U+25C8    | Diamond + dot     | Active marker                  |
| ◦     | U+25E6    | Empty bullet      | Pending                        |
| ▪     | U+25AA    | Small black sq    | Bullet                         |
| ▫     | U+25AB    | Small white sq    | Empty bullet                   |

## 12. Stars, sparkles & favorites

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ★     | U+2605    | Filled star       | Favorite                       |
| ☆     | U+2606    | Empty star        | Unrated                        |
| ✦     | U+2726    | Black 4-pt        | Sparkle                        |
| ✧     | U+2727    | White 4-pt        | Sparkle outline                |
| ✩     | U+2729    | Stress outlined   | Highlight                      |
| ✪     | U+272A    | Circled white     | Featured                       |
| ✫     | U+272B    | Open centre       | Decorative                     |
| ✬     | U+272C    | Black centre      | Decorative                     |
| ✭     | U+272D    | Outlined          | Variant                        |
| ✮     | U+272E    | Heavy outlined    | Variant                        |
| ✯     | U+272F    | Pinwheel          | Loading hint                   |
| ✰     | U+2730    | Shadowed white    | Variant                        |
| ✱     | U+2731    | Heavy asterisk    | Required field                 |
| ✲     | U+2732    | Open asterisk     | Required (lighter)             |
| ✳     | U+2733    | 8-spoked          | Decorative                     |
| ✴     | U+2734    | 8-pointed black   | Decorative                     |
| ✵     | U+2735    | 8-pointed pinwheel| Loading                        |
| ✶     | U+2736    | 6-pointed         | Decorative                     |
| ✷     | U+2737    | 6-pointed bold    | Decorative                     |
| ✸     | U+2738    | Heavy 8-pointed   | Decorative                     |
| ✹     | U+2739    | 12-pointed        | Sun-like                       |
| ✺     | U+273A    | 16-pointed        | Sun-like                       |
| ✻     | U+273B    | Teardrop-spoked   | Decorative                     |
| ✼     | U+273C    | Open teardrop     | Decorative                     |
| ✽     | U+273D    | Heavy teardrop    | Decorative                     |
| ✾     | U+273E    | 6-petalled        | Floral                         |
| ✿     | U+273F    | Black florette    | Floral                         |
| ❀     | U+2740    | White florette    | Floral                         |
| ❁     | U+2741    | 8-petalled        | Floral                         |
| ❂     | U+2742    | Circled open      | Decorative                     |
| ❃     | U+2743    | Heavy teardrop var| Decorative                     |
| ❇     | U+2747    | Sparkle           | Sparkle (text)                 |
| ❈     | U+2748    | Heavy sparkle     | Sparkle bold                   |
| ❉     | U+2749    | Balloon-spoked    | Decorative                     |
| ❊     | U+274A    | 8-teardrop        | Decorative                     |
| ❋     | U+274B    | Heavy 8-teardrop  | Decorative                     |
| ❤     | U+2764    | Heavy heart       | Favorite **(emoji-default)**   |
| ♥     | U+2665    | Black heart suit  | Favorite (text presentation)   |
| ♡     | U+2661    | White heart       | Unfavorited                    |

## 13. Numbered & circled digits

| Range / set         | Codepoints                    | Use                |
|---------------------|-------------------------------|--------------------|
| ⓪①②③④⑤⑥⑦⑧⑨         | U+24EA U+2460–U+2468          | Step indicator 0–9 |
| ⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳        | U+2469–U+2473                 | Step 10–20         |
| ⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴         | U+24EB–U+24F4                 | Negative 11–20     |
| ❶❷❸❹❺❻❼❽❾❿          | U+2776–U+277F                 | Negative 1–10      |
| ⓿                   | U+24FF                        | Negative 0         |
| ⓵⓶⓷⓸⓹⓺⓻⓼⓽⓾          | U+24F5–U+24FE                 | Double-circled     |
| ⒈⒉⒊⒋⒌⒍⒎⒏⒐⒑         | U+2488–U+2491                 | Number period      |
| ⒜⒝⒞⒟⒠⒡⒢⒣⒤⒥⒦⒧⒨⒩⒪⒫⒬⒭⒮⒯⒰⒱⒲⒳⒴⒵ | U+249C–U+24B5     | Parenthesized a–z  |
| ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ | U+24D0–U+24E9     | Circled lowercase  |
| ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ | U+24B6–U+24CF     | Circled uppercase  |

## 14. Progress, bars & sparklines

| Range          | Codepoints              | Use                          |
|----------------|-------------------------|------------------------------|
| ▏▎▍▌▋▊▉█        | U+258F→U+2588           | Vertical progress            |
| ▁▂▃▄▅▆▇█        | U+2581→U+2588           | Sparkline                    |
| ░ ▒ ▓           | U+2591 U+2592 U+2593    | Skeleton fills               |
| ▀ ▄ ▌ ▐         | U+2580 U+2584 U+258C U+2590 | Half blocks            |
| ½ ⅓ ¼ ⅕ ⅙ ⅛     | U+00BD U+2153 U+00BC U+2155 U+2159 U+215B | Vulgar fractions |
| ⅔ ⅖ ⅗ ⅘ ⅚ ⅜ ⅝ ⅞ | U+2154 U+2156 U+2157 U+2158 U+215A U+215C U+215D U+215E | More fractions |
| ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁰ | U+00B9 U+00B2 U+00B3 U+2074–U+2079 U+2070 | Superscript |
| ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ ₀ | U+2081–U+2089 U+2080 | Subscript                |
| ⁺ ⁻ ⁼ ⁽ ⁾       | U+207A–U+207E           | Superscript operators        |
| ₊ ₋ ₌ ₍ ₎       | U+208A–U+208E           | Subscript operators          |
| ⌜ ⌝ ⌞ ⌟         | U+231C–U+231F           | Corner brackets              |

## 15. Math, logic & sets

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ±     | U+00B1    | Plus-minus        | Tolerance                      |
| ∓     | U+2213    | Minus-plus        | Tolerance reversed             |
| ×     | U+00D7    | Times             | Multiply                       |
| ÷     | U+00F7    | Divide            | Divide                         |
| ≈     | U+2248    | Approx equal      | Estimate                       |
| ≅     | U+2245    | Approx congruent  | Similar                        |
| ≠     | U+2260    | Not equal         | Diff                           |
| ≡     | U+2261    | Identical         | Triple bar                     |
| ≢     | U+2262    | Not identical     | Diff identity                  |
| ≤     | U+2264    | Less or equal     | Filter                         |
| ≥     | U+2265    | Greater or equal  | Filter                         |
| ≪     | U+226A    | Much less         | Pagination back                |
| ≫     | U+226B    | Much greater      | Pagination forward             |
| ∝     | U+221D    | Proportional      | Math                           |
| ∞     | U+221E    | Infinity          | Unlimited                      |
| ∅     | U+2205    | Empty set         | No results                     |
| ∈     | U+2208    | Element of        | Membership                     |
| ∉     | U+2209    | Not element       | Non-member                     |
| ∋     | U+220B    | Contains          | Reverse membership             |
| ∪     | U+222A    | Union             | Combine                        |
| ∩     | U+2229    | Intersection      | Filter both                    |
| ⊂     | U+2282    | Subset            | Hierarchy                      |
| ⊃     | U+2283    | Superset          | Hierarchy                      |
| ⊆     | U+2286    | Subset or equal   | Hierarchy                      |
| ⊇     | U+2287    | Superset or equal | Hierarchy                      |
| ∀     | U+2200    | For all           | Filter universal               |
| ∃     | U+2203    | Exists            | Filter existential             |
| ∄     | U+2204    | Does not exist    | Filter negative                |
| ∇     | U+2207    | Nabla             | Math                           |
| ∂     | U+2202    | Partial           | Math                           |
| ∑     | U+2211    | Sum               | Aggregate                      |
| ∏     | U+220F    | Product           | Aggregate                      |
| ∐     | U+2210    | Coproduct         | Math                           |
| √     | U+221A    | Square root       | Math                           |
| ∛     | U+221B    | Cube root         | Math                           |
| ∜     | U+221C    | Fourth root       | Math                           |
| ∫     | U+222B    | Integral          | Math                           |
| ∬     | U+222C    | Double integral   | Math                           |
| ∭     | U+222D    | Triple integral   | Math                           |
| °     | U+00B0    | Degree            | Angle, temperature             |
| ′     | U+2032    | Prime             | Minutes / feet                 |
| ″     | U+2033    | Double prime      | Seconds / inches               |
| ‰     | U+2030    | Per mille         | Stats (1/1000)                 |
| ‱     | U+2031    | Per ten thousand  | Stats                          |
| ¬     | U+00AC    | Not               | Logic NOT                      |
| ∧     | U+2227    | Logical AND       | Logic                          |
| ∨     | U+2228    | Logical OR        | Logic                          |
| ⊻     | U+22BB    | XOR               | Logic                          |
| ⊼     | U+22BC    | NAND              | Logic                          |
| ⊽     | U+22BD    | NOR               | Logic                          |
| ⊢     | U+22A2    | Right tack        | Turnstile                      |
| ⊣     | U+22A3    | Left tack         | Turnstile                      |
| ⊤     | U+22A4    | Down tack (top)   | Top, true                      |
| ⊥     | U+22A5    | Up tack (perp)    | Bottom, false, perpendicular   |
| ∠     | U+2220    | Angle             | Geometry                       |
| ∟     | U+221F    | Right angle       | Geometry                       |

## 16. Currency, commerce & legal

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| $     | U+0024    | Dollar            | USD, AUD, etc.                 |
| €     | U+20AC    | Euro              | EUR                            |
| £     | U+00A3    | Pound             | GBP                            |
| ¥     | U+00A5    | Yen               | JPY / CNY                      |
| ¢     | U+00A2    | Cent              | Sub-dollar                     |
| ₽     | U+20BD    | Ruble             | RUB                            |
| ₹     | U+20B9    | Rupee             | INR                            |
| ₩     | U+20A9    | Won               | KRW                            |
| ₪     | U+20AA    | Shekel            | ILS                            |
| ₺     | U+20BA    | Lira              | TRY                            |
| ฿     | U+0E3F    | Baht              | THB                            |
| ₫     | U+20AB    | Dong              | VND                            |
| ₱     | U+20B1    | Peso              | PHP                            |
| ₦     | U+20A6    | Naira             | NGN                            |
| ₿     | U+20BF    | Bitcoin           | BTC                            |
| ¤     | U+00A4    | Generic currency  | Placeholder                    |
| %     | U+0025    | Percent           | Stats                          |
| ™     | U+2122    | Trademark         | Legal                          |
| ®     | U+00AE    | Registered        | Legal                          |
| ©     | U+00A9    | Copyright         | Legal                          |
| ℠     | U+2120    | Service mark      | Legal                          |
| ℗     | U+2117    | Phonogram         | Music copyright                |
| №     | U+2116    | Numero            | "No. 5"                        |
| ℞     | U+211E    | Prescription      | Medical                        |
| ℅     | U+2105    | Care of           | Address                        |
| ⅍     | U+214D    | Aktieselskab      | Corporation                    |

## 17. Communication & social

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ✉     | U+2709    | Envelope          | Mail                           |
| ✆     | U+2706    | Telephone (text)  | Phone                          |
| ☎     | U+260E    | Black telephone   | Phone **(emoji-default)**      |
| ☏     | U+260F    | White telephone   | Phone outline                  |
| ✍     | U+270D    | Writing hand      | Sign, edit                     |
| ✌     | U+270C    | Victory hand      | Peace                          |

## 18. Weather, nature & celestial

(Most render as emoji on Apple — append U+FE0E for text presentation.)

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ☀     | U+2600    | Black sun         | Light theme **(emoji-default)**|
| ☁     | U+2601    | Cloud             | Storage **(emoji-default)**    |
| ☂     | U+2602    | Umbrella          | Rain                           |
| ☃     | U+2603    | Snowman           | Snow                           |
| ☄     | U+2604    | Comet             | Burst                          |
| ☼     | U+263C    | Sun w/ rays       | Bright                         |
| ☽     | U+263D    | First-quarter moon| Dark theme                     |
| ☾     | U+263E    | Last-quarter moon | Dark theme                     |
| ☉     | U+2609    | Sun (astro)       | Astronomical sun               |
| ☊     | U+260A    | Ascending node    | Astro                          |
| ☋     | U+260B    | Descending node   | Astro                          |
| ☌     | U+260C    | Conjunction       | Astro                          |
| ☍     | U+260D    | Opposition        | Astro                          |
| ❄     | U+2744    | Snowflake         | Cold / cache invalidate        |
| ❅     | U+2745    | Tight snowflake   | Variant                        |
| ❆     | U+2746    | Heavy snowflake   | Variant                        |
| ☘     | U+2618    | Shamrock          | Lucky, randomize               |
| ⚘     | U+2698    | Flower            | Eco                            |
| ☢     | U+2622    | Radioactive       | Danger zone                    |
| ☣     | U+2623    | Biohazard         | Danger zone                    |
| ☮     | U+262E    | Peace             | Decorative                     |

## 19. Hands & gestures

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ☜     | U+261C    | Pointing left     | Note                           |
| ☝     | U+261D    | Index up          | Pointing up                    |
| ☞     | U+261E    | Pointing right    | See also                       |
| ☟     | U+261F    | Index down        | Down                           |
| ☚     | U+261A    | Black left        | Strong direction               |
| ☛     | U+261B    | Black right       | Strong direction               |

## 20. Geometric shapes

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ■     | U+25A0    | Black square      | Solid                          |
| □     | U+25A1    | White square      | Outline                        |
| ▢     | U+25A2    | Rounded square    | Rounded outline                |
| ▬     | U+25AC    | Black rectangle   | Bar                            |
| ▭     | U+25AD    | White rectangle   | Outline bar                    |
| ▮     | U+25AE    | Vertical bar      | Vertical pill                  |
| ▯     | U+25AF    | Vertical outline  | Outline pill                   |
| ▲     | U+25B2    | Solid up tri      | Sort asc                       |
| △     | U+25B3    | White up tri      | Outline                        |
| ▼     | U+25BC    | Solid down tri    | Sort desc                      |
| ▽     | U+25BD    | White down tri    | Outline                        |

## 21. Hexagons, polygons & decorative

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⬢     | U+2B22    | Black hex         | Filled tag, chunk              |
| ⬡     | U+2B21    | White hex         | Empty tag                      |
| ⬣     | U+2B23    | Horizontal hex    | Tag                            |
| ⬟     | U+2B1F    | Black pentagon    | Marker                         |
| ⬠     | U+2B20    | White pentagon    | Outline                        |
| ⬥     | U+2B25    | Black diamond med | Variant marker                 |
| ⬦     | U+2B26    | White diamond med | Variant outline                |
| ⬧     | U+2B27    | Black diamond sm  | Bullet                         |
| ⬨     | U+2B28    | White diamond sm  | Bullet outline                 |
| ⬩     | U+2B29    | Black diamond xs  | Tiny bullet                    |
| ⬪     | U+2B2A    | White diamond xs  | Tiny outline                   |
| ⬫     | U+2B2B    | Tiny diamond xs   | Tiniest bullet                 |
| ⬬     | U+2B2C    | Tiny outline xs   | Tiniest outline                |
| ❖     | U+2756    | Diamond minus     | Decorative                     |
| ❍     | U+274D    | Shadowed circle   | Decorative                     |

## 22. Type ornaments & dividers

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ·     | U+00B7    | Middle dot        | Inline separator               |
| •     | U+2022    | Bullet            | List bullet                    |
| ‣     | U+2023    | Triangular bullet | Sub-bullet                     |
| ⁃     | U+2043    | Hyphen bullet     | Bullet variant                 |
| ・    | U+30FB    | Katakana mid dot  | CJK separator                  |
| —     | U+2014    | Em dash           | Strong dash                    |
| –     | U+2013    | En dash           | Range dash                     |
| ‒     | U+2012    | Figure dash       | Tabular                        |
| ―     | U+2015    | Horizontal bar    | Quotation                      |
| ⎯     | U+23AF    | Light horizontal  | Light divider                  |
| ⎻     | U+23BB    | Top scan-line     | Header rule                    |
| ⎼     | U+23BC    | Mid-low scan-line | Mid rule                       |
| ⎽     | U+23BD    | Bottom scan-line  | Footer rule                    |
| ‖     | U+2016    | Double vertical   | Strong divider                 |
| ∥     | U+2225    | Parallel          | Math divider                   |
| §     | U+00A7    | Section           | Legal section                  |
| ¶     | U+00B6    | Pilcrow           | Paragraph                      |
| †     | U+2020    | Dagger            | Footnote                       |
| ‡     | U+2021    | Double dagger     | Footnote 2                     |
| …     | U+2026    | Ellipsis          | Truncation                     |
| ⁂     | U+2042    | Asterism          | Section break                  |
| ※    | U+203B    | Reference mark    | Note                           |
| ☙     | U+2619    | Reversed florette | Decorative                     |
| ❦     | U+2766    | Floral heart      | Decorative                     |
| ❧     | U+2767    | Rotated florette  | Decorative                     |

## 23. Quotes & guillemets

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| "     | U+201C    | Left double curly | Open quote                     |
| "     | U+201D    | Right double curly| Close quote                    |
| '     | U+2018    | Left single curly | Open inner                     |
| '     | U+2019    | Right single curly| Close inner / apostrophe       |
| „     | U+201E    | Low double quote  | German open                    |
| ‚     | U+201A    | Low single quote  | German open                    |
| ‹     | U+2039    | Single left guill | Subtle nav                     |
| ›     | U+203A    | Single right guill| Subtle nav / trace bullet      |
| «     | U+00AB    | Double left guill | Page step back                 |
| »     | U+00BB    | Double right guill| Page step forward              |
| ❝     | U+275D    | Heavy left quote  | Decorative                     |
| ❞     | U+275E    | Heavy right quote | Decorative                     |
| ❮     | U+276E    | Heavy left angle  | Strong nav                     |
| ❯     | U+276F    | Heavy right angle | Strong nav                     |

## 24. Brackets & fences

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⟨     | U+27E8    | Math left angle   | Tag open                       |
| ⟩     | U+27E9    | Math right angle  | Tag close                      |
| ⟦     | U+27E6    | White square open | Z-notation                     |
| ⟧     | U+27E7    | White square close| Z-notation                     |
| ⟪     | U+27EA    | Double left angle | Strong tag                     |
| ⟫     | U+27EB    | Double right angle| Strong tag                     |
| ⌈     | U+2308    | Left ceiling      | Math ceiling                   |
| ⌉     | U+2309    | Right ceiling     | Math ceiling                   |
| ⌊     | U+230A    | Left floor        | Math floor                     |
| ⌋     | U+230B    | Right floor       | Math floor                     |
| ⦃     | U+2983    | White curly open  | Set notation                   |
| ⦄     | U+2984    | White curly close | Set notation                   |
| ⦅     | U+2985    | White paren open  | Decorative                     |
| ⦆     | U+2986    | White paren close | Decorative                     |
| ⟮     | U+27EE    | Flat paren open   | Math grouping                  |
| ⟯     | U+27EF    | Flat paren close  | Math grouping                  |
| ⸤     | U+2E24    | Top half corner   | Quote bracket                  |
| ⸥     | U+2E25    | Bottom half corner| Quote bracket                  |

## 25. Box drawing & block elements

For terminal layouts, ASCII art, lo-fi previews. Listed by family — not
all individual codepoints since the ranges are dense and self-explanatory.

| Family | Range            | Includes                                   |
|--------|------------------|--------------------------------------------|
| Light  | U+2500–U+253C    | ─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼                      |
| Heavy  | U+2501–U+254B    | ━ ┃ ┏ ┓ ┗ ┛ ┣ ┫ ┳ ┻ ╋                      |
| Double | U+2550–U+256C    | ═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬                      |
| Round  | U+256D–U+2570    | ╭ ╮ ╯ ╰                                    |
| Diag   | U+2571–U+2573    | ╱ ╲ ╳                                      |
| Block  | U+2580–U+2593    | ▀ ▄ ▌ ▐ █ ░ ▒ ▓                            |

## 26. Music & audio

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ♩     | U+2669    | Quarter note      | Music                          |
| ♪     | U+266A    | Eighth note       | Music                          |
| ♫     | U+266B    | Beamed eighth     | Music                          |
| ♬     | U+266C    | Beamed sixteenth  | Music                          |
| ♭     | U+266D    | Flat              | Music accidental               |
| ♮     | U+266E    | Natural           | Music accidental               |
| ♯     | U+266F    | Sharp             | Music accidental               |
| 𝄞     | U+1D11E   | Treble clef       | Music staff                    |
| 𝄢     | U+1D122   | Bass clef         | Music staff                    |

## 27. Games, dice & cards

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ♔     | U+2654    | White king        | Chess                          |
| ♕     | U+2655    | White queen       | Chess                          |
| ♖     | U+2656    | White rook        | Chess                          |
| ♗     | U+2657    | White bishop      | Chess                          |
| ♘     | U+2658    | White knight      | Chess                          |
| ♙     | U+2659    | White pawn        | Chess                          |
| ♚     | U+265A    | Black king        | Chess                          |
| ♛     | U+265B    | Black queen       | Chess                          |
| ♜     | U+265C    | Black rook        | Chess                          |
| ♝     | U+265D    | Black bishop      | Chess                          |
| ♞     | U+265E    | Black knight      | Chess                          |
| ♟     | U+265F    | Black pawn        | Chess                          |
| ♠     | U+2660    | Black spade       | Card                           |
| ♡     | U+2661    | White heart       | Card outline                   |
| ♢     | U+2662    | White diamond     | Card outline                   |
| ♣     | U+2663    | Black club        | Card                           |
| ♤     | U+2664    | White spade       | Card outline                   |
| ♥     | U+2665    | Black heart       | Card                           |
| ♦     | U+2666    | Black diamond     | Card                           |
| ♧     | U+2667    | White club        | Card outline                   |
| ⚀     | U+2680    | Die face 1        | Random                         |
| ⚁     | U+2681    | Die face 2        | Random                         |
| ⚂     | U+2682    | Die face 3        | Random                         |
| ⚃     | U+2683    | Die face 4        | Random                         |
| ⚄     | U+2684    | Die face 5        | Random                         |
| ⚅     | U+2685    | Die face 6        | Random                         |
| ⛀     | U+26C0    | White draughts    | Game                           |
| ⛁     | U+26C1    | White king dr.    | Game                           |
| ⛂     | U+26C2    | Black draughts    | Game                           |
| ⛃     | U+26C3    | Black king dr.    | Game                           |

## 28. Religious, esoteric & cultural

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ☯     | U+262F    | Yin yang          | Theme toggle                   |
| ☸     | U+2638    | Dharma wheel      | Settings (decorative)          |
| ☥     | U+2625    | Ankh              | Decorative                     |
| ☩     | U+2629    | Cross of Jerusalem| Decorative                     |
| ✝     | U+271D    | Latin cross       | Decorative                     |
| ☪     | U+262A    | Star and crescent | Decorative                     |
| ☦     | U+2626    | Orthodox cross    | Decorative                     |
| ☧     | U+2627    | Chi rho           | Decorative                     |
| ✡     | U+2721    | Star of David     | Decorative                     |
| ☬     | U+262C    | Khanda            | Decorative                     |
| ☫     | U+262B    | Farsi symbol      | Decorative                     |
| ☭     | U+262D    | Hammer & sickle   | Decorative                     |

## 29. Astrology & zodiac

| Glyph | Codepoint | Name              |
|-------|-----------|-------------------|
| ♈     | U+2648    | Aries             |
| ♉     | U+2649    | Taurus            |
| ♊     | U+264A    | Gemini            |
| ♋     | U+264B    | Cancer            |
| ♌     | U+264C    | Leo               |
| ♍     | U+264D    | Virgo             |
| ♎     | U+264E    | Libra             |
| ♏     | U+264F    | Scorpio           |
| ♐     | U+2650    | Sagittarius       |
| ♑     | U+2651    | Capricorn         |
| ♒     | U+2652    | Aquarius          |
| ♓     | U+2653    | Pisces            |
| ☿     | U+263F    | Mercury           |
| ♀     | U+2640    | Venus / female    |
| ♁     | U+2641    | Earth             |
| ♂     | U+2642    | Mars / male       |
| ♃     | U+2643    | Jupiter           |
| ♄     | U+2644    | Saturn            |
| ♅     | U+2645    | Uranus            |
| ♆     | U+2646    | Neptune           |
| ♇     | U+2647    | Pluto             |

## 30. Alchemy & science

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| 🜀     | U+1F700   | Quintessence      | Alchemy                        |
| 🜁     | U+1F701   | Air               | Alchemy                        |
| 🜂     | U+1F702   | Fire              | Alchemy                        |
| 🜃     | U+1F703   | Earth             | Alchemy                        |
| 🜄     | U+1F704   | Water             | Alchemy                        |
| 🜔     | U+1F714   | Salt              | Alchemy                        |
| 🝜     | U+1F75C   | Crucible          | Alchemy                        |
| ⚗     | (see §9)  | Alembic           | Experiment / beta              |
| ⚛     | (see §9)  | Atom              | Science                        |

(Alchemy block U+1F700–U+1F773 has many more — limited font support outside Symbola/Noto Sans Symbols.)

## 31. Phonetic & language

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ə     | U+0259    | Schwa             | Phonetic                       |
| ʃ     | U+0283    | Esh               | Phonetic                       |
| ʒ     | U+0292    | Ezh               | Phonetic                       |
| θ     | U+03B8    | Theta             | Phonetic / math                |
| ð     | U+00F0    | Eth               | Phonetic / Old English         |
| ŋ     | U+014B    | Eng               | Phonetic                       |
| ʔ     | U+0294    | Glottal stop      | Phonetic                       |
| ◌     | U+25CC    | Dotted circle     | Combining-mark placeholder     |

## 32. APL & technical operators

Many double as compact UI symbols.

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ⎕     | U+2395    | APL quad          | Generic placeholder            |
| ⌷     | U+2337    | APL squish quad   | Indexed                        |
| ⌽     | U+233D    | APL stile / circle| Reverse                        |
| ⌾     | U+233E    | APL circle stile  | Cycle                          |
| ⍳     | U+2373    | APL iota          | Index                          |
| ⍴     | U+2374    | APL rho           | Reshape                        |
| ⍟     | U+235F    | APL log           | Logarithm                      |
| ⍝     | U+235D    | APL lamp          | Comment marker                 |
| ⌶     | U+2336    | APL i-beam        | I-beam cursor                  |
| ⍱     | U+2371    | APL down caret    | NOR                            |
| ⍲     | U+2372    | APL up caret      | NAND                           |
| ⍻     | U+237B    | Not check         | Approval rejected              |
| ⌘     | (see §10) | Command           | macOS                          |

## 33. Braille

The Braille range U+2800–U+28FF gives 256 dot-patterns. Useful for:
- Custom 8-dot loading spinners
- Compact data viz where each pattern encodes 8 bits
- Decorative monospace mosaics

| Glyph | Codepoint | Pattern    | Use                            |
|-------|-----------|------------|--------------------------------|
| ⠀     | U+2800    | Empty      | Whitespace placeholder         |
| ⠁     | U+2801    | Dot 1      | 1-bit                          |
| ⠂     | U+2802    | Dot 2      | 1-bit                          |
| ⠃     | U+2803    | Dots 1+2   | 2-bit                          |
| ⠿     | U+283F    | All 6 lower| Dense block                    |
| ⡿     | U+287F    | 7 dots     | Dense block                    |
| ⣿     | U+28FF    | All 8 dots | Solid square                   |

Spinner sequence (rotating):  `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏`

## 34. Roman numerals & ordered lists

| Range        | Codepoints         | Notes                          |
|--------------|--------------------|--------------------------------|
| Ⅰ Ⅱ Ⅲ Ⅳ Ⅴ Ⅵ Ⅶ Ⅷ Ⅸ Ⅹ Ⅺ Ⅻ | U+2160–U+216B | Roman 1–12 (uppercase) |
| ⅰ ⅱ ⅲ ⅳ ⅴ ⅵ ⅶ ⅷ ⅸ ⅹ ⅺ ⅻ | U+2170–U+217B | Roman 1–12 (lowercase) |
| Ⅼ Ⅽ Ⅾ Ⅿ      | U+216C–U+216F      | 50, 100, 500, 1000             |
| ↀ ↁ ↂ        | U+2180–U+2182      | 1000, 5000, 10000              |

## 35. Letter-like symbols

| Glyph | Codepoint | Name              | Use                            |
|-------|-----------|-------------------|--------------------------------|
| ℃     | U+2103    | Celsius           | Temperature                    |
| ℉     | U+2109    | Fahrenheit        | Temperature                    |
| K     | U+212A    | Kelvin            | Temperature                    |
| Å     | U+212B    | Angstrom          | Distance                       |
| ℓ     | U+2113    | Script l          | Litre                          |
| ℳ     | U+2133    | Script M          | Stylized                       |
| ℘     | U+2118    | Weierstrass p     | Math                           |
| ℜ     | U+211C    | Real part         | Math                           |
| ℑ     | U+2111    | Imaginary part    | Math                           |
| ℵ     | U+2135    | Aleph             | Set theory                     |
| ℶ     | U+2136    | Beth              | Set theory                     |
| ℷ     | U+2137    | Gimel             | Set theory                     |
| ℸ     | U+2138    | Daleth            | Set theory                     |
| ℎ     | U+210E    | Planck constant   | Physics                        |
| ℏ     | U+210F    | Reduced Planck    | Physics                        |
| ℧     | U+2127    | Mho (inverted Ω)  | Electrical                     |
| Ω     | U+03A9    | Omega             | Resistance / final             |

---

## Usage tips

- **Render in your text font, not a fallback.** Test in your actual font
  stack — Segoe UI, SF Pro, Inter, JetBrains Mono, Fira Code cover most
  glyphs in this document.
- **Force monochrome (text) presentation** by appending **U+FE0E** after
  any glyph the OS wants to render as emoji: `⚙︎` (`U+2699 U+FE0E`),
  `⏵︎`, `⚠︎`, `☀︎`. Append **U+FE0F** to *force* color emoji presentation.
- **Size them up ~10–15%** vs surrounding text — designed for body text,
  they look small on buttons. `font-size: 1.1em` is a good default.
- **Vertical-align: middle** on inline glyphs, or use `display: inline-flex;
  align-items: center;` on the parent.
- **Two-space gap** between glyph and label reads cleaner than one:
  `"⚙  Settings"`, not `"⚙ Settings"`. Apply consistently.
- **Avoid mixing** color emoji and these glyphs in the same UI — colored
  pixmaps break the monochrome rhythm.
- **Tabular-nums** (`font-variant-numeric: tabular-nums`) keeps digits
  aligned next to status glyphs in ETA/progress strings.
- **Accessibility**: wrap decorative glyphs in `<span aria-hidden="true">`
  and put the action name in the button's `aria-label`. For icon-only
  buttons, set `aria-label` directly on the button.
- **Qt/PySide6**: `btn.setText("⚙  Settings")` works directly. Glyph
  spacing is preserved by widget metrics — no extra CSS needed.
- **Terminals** prefer the box-drawing range and block-elements range.
  Modern terminals (Windows Terminal, iTerm2, Alacritty, Kitty) cover
  them via Cascadia Code / SF Mono / JetBrains Mono.
- **RTL languages**: mirror direction-bearing glyphs (← → ↗ etc.) at the
  layout level via `dir="rtl"`, never by swapping codepoints.

## Ready-to-paste recipes

### React/JSX button with leading glyph
```jsx
<button className="btn-go" aria-label="Rip TV Show Disc">
  <span aria-hidden="true">⏺</span>{"  "}Rip TV Show Disc
</button>
```

### CSS pulsing live dot
```css
.live-dot::before {
  content: "●";
  color: #2ea043;
  margin-right: 6px;
  animation: live-pulse 1.6s ease-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
```

### Qt/PySide6 button
```python
self.btn_rip = QPushButton("⏺  Rip TV Show Disc")
self.btn_rip.setProperty("role", "go")
```

### Log-prefix dictionary (JS)
```js
const LOG_PREFIX = {
  info:    "ⓘ",
  success: "✓",
  warn:    "⚠︎",   // U+FE0E forces monochrome
  error:   "✗",
  prompt:  "?",
  pending: "◦",
  running: "◐",
  skipped: "⊘",
  debug:   "⌬",
  trace:   "›",
};
```

### Step indicator
```
①  Insert disc  ▸  ②  Choose titles  ▸  ③  Rip  ▸  ④  Done
```

### ASCII progress bar (8x sub-pixel resolution)
```js
function bar(pct, width = 20) {
  const full = Math.floor((pct / 100) * width);
  const partials = ["", "▏","▎","▍","▌","▋","▊","▉"];
  const remainder = ((pct / 100) * width - full) * 8 | 0;
  return "█".repeat(full) +
         (partials[remainder] ?? "") +
         " ".repeat(width - full - (remainder > 0 ? 1 : 0));
}
// bar(64) → "████████████▊       "
```

### Sparkline from numbers
```js
function spark(values) {
  const blocks = "▁▂▃▄▅▆▇█";
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  return values.map(v =>
    blocks[Math.floor(((v - min) / range) * (blocks.length - 1))]
  ).join("");
}
// spark([1,3,2,5,4,8,6]) → "▁▃▂▅▄█▆"
```

### Box-drawing card
```
╭─────────────────╮
│  Title 02       │
│  44 min · 4.1GB │
╰─────────────────╯
```

### Braille spinner (CLI)
```js
const FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"];
let i = 0;
setInterval(() => process.stdout.write("\r" + FRAMES[i++ % FRAMES.length]), 80);
```

### Required-field marker (form labels)
```html
<label>Email <span aria-hidden="true" class="req">✱</span></label>
<style>.req { color: #c4312f; font-size: 0.9em; vertical-align: super; }</style>
```

### Compact rating widget
```js
function rating(stars, max = 5) {
  return "★".repeat(stars) + "☆".repeat(max - stars);
}
// rating(3) → "★★★☆☆"
```

---

## Font coverage notes

| Font                | Coverage    | Notes                                    |
|---------------------|-------------|------------------------------------------|
| Segoe UI            | Excellent   | Default Windows; covers nearly all       |
| Segoe UI Symbol     | Best        | Bundled fallback for missing on Windows  |
| SF Pro              | Good        | macOS; many media glyphs render as emoji — use U+FE0E |
| Apple Symbols       | Best (mac)  | Apple's bundled symbol fallback          |
| Inter               | Good        | Webfont; pair with Symbols Nerd Font     |
| JetBrains Mono      | Excellent   | Monospace; covers blocks + media + status|
| Cascadia Code       | Excellent   | Modern Windows monospace                 |
| Fira Code           | Excellent   | Programming ligatures + symbols          |
| Consolas            | Good        | Log panels; covers blocks                |
| Menlo / Monaco      | Good        | macOS monospace                          |
| DejaVu Sans         | Excellent   | Linux fallback; very wide coverage       |
| Noto Sans Symbols 2 | Best fallback | Google's universal symbol fallback     |
| Symbola             | Best        | Free font designed to cover everything   |
| Symbols Nerd Font   | Best        | Programming icon set; thousands of glyphs|

If a glyph renders as a tofu box (`□`):
1. Add a webfont fallback: `font-family: "Inter", "Segoe UI Symbol", "Apple Symbols", "Noto Sans Symbols 2", sans-serif;`
2. Force the OS-bundled symbol font.
3. Swap to a covered glyph from the same category.

### Recommended CSS stack (web UI)
```css
font-family:
  "Inter",
  -apple-system, BlinkMacSystemFont,
  "Segoe UI",
  "Segoe UI Symbol", "Apple Symbols",
  "Noto Sans Symbols 2",
  sans-serif;
```

### Recommended CSS stack (monospace / log panels)
```css
font-family:
  "JetBrains Mono", "Cascadia Code", "Fira Code",
  Consolas, "SF Mono", Menlo, monospace,
  "Segoe UI Symbol", "Apple Symbols";
```

### Detecting tofu in JS
```js
// Returns true if the font has a glyph for the given codepoint
function hasGlyph(char, font = "Inter") {
  const c = document.createElement("canvas").getContext("2d");
  c.font = `16px "${font}"`;
  const w1 = c.measureText(char).width;
  c.font = `16px "fakefont-does-not-exist"`;
  const w2 = c.measureText(char).width;
  return w1 !== w2;
}
```

---

## Glossary

- **Codepoint** — a unique number identifying a character in Unicode. Written `U+XXXX` in hex (e.g. `U+2699` for ⚙).
- **U+FE0E** — Variation Selector-15. Forces *text* (monochrome) presentation of an ambiguous glyph.
- **U+FE0F** — Variation Selector-16. Forces *emoji* (color) presentation.
- **Tofu** (`□`) — placeholder rendered when a font has no glyph for a codepoint.
- **Dingbat** — pictographic glyph, traditionally from Zapf Dingbats. Many U+2700-block glyphs originate here.
- **APL symbols** — operators from the APL programming language. Many double as compact UI symbols (⌸ ⌹ ⌺ ⎕ ⌷).
- **Box drawing** — line-art glyphs in U+2500–U+257F for terminal layouts.
- **Block elements** — partial-fill glyphs in U+2580–U+259F. Foundation for sparklines and progress bars.
- **Braille** — U+2800–U+28FF, 256 dot-patterns. Each codepoint encodes 8 bits as filled/empty dots.
- **PUA** (Private Use Area) — U+E000–U+F8FF and supplementary planes. Used by icon fonts (Nerd Fonts, Material Icons). Not in standard Unicode and not portable across fonts — avoid for this reason.
