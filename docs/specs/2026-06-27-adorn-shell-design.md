# adorn — interactive shell (design)

> **Status:** design, approved-in-principle 2026-06-27. Target: v0.1.0.
> **Depends on:** `2026-06-27-theme-overrides-design.md` (theme.toml override layer).

## Summary

`adorn` with no subcommand launches an interactive REPL (like `python3`). It is an
**imperative shell over the existing engine**: short verbs drive the same core
functions the CLI calls (`catalog`/`compile`/`render`/`commands`), in-process. The
live desktop is the preview — every mutating command can render/apply to the real
system, so there is no separate TUI to keep in sync. A git repo records every
command so history, `diff`, and `undo`/`redo` come "for free".

`adorn <subcommand …>` keeps working exactly as today; the shell is an additional
frontend, not a replacement.

## Goals / non-goals

- **Goal:** make painful multi-step CLI sequences a few keystrokes; keep the real
  config as the single source of truth; robust undo.
- **Non-goal (v0.1.0):** a command grammar (`;` sequencing, `|` typed pipes),
  tab-completion, a declarative theming DSL. The pipe/sequence grammar is v0.2.

## Architecture

```
            ┌───────────────────────────────────────────────┐
            │  frontends                                     │
            │   cli.py  (one-shot)      shell.py  (REPL)     │
            └───────────────┬───────────────────┬───────────┘
                            │   in-process calls │
            ┌───────────────▼───────────────────▼───────────┐
            │  core: catalog · compile · render · commands · │
            │        palette · color · reload · manifest     │
            └───────────────┬───────────────────────────────┘
                            │ writes
            work-tree  ~/.config/adorn   ◄── git-dir ~/.local/state/adorn/history.git
                            │ apply (symlink + reload + wallpaper)
                       live desktop
```

- **In-process.** No subprocess-per-command. The shell imports and calls core
  functions, getting structured dicts back (needed for `palette`/`status`/`diff`).
- **Evaluator / loop split (testability spine).** The command evaluator is a near-pure
  function `eval_line(state, line) -> (state, output, dirty)` with no terminal I/O.
  The REPL loop (`shell.repl()`) is a thin wrapper: read line → `eval_line` → print
  → commit-if-dirty. This lets the entire command surface be unit-tested by feeding
  strings, with no TTY.
- **New modules:** `src/adorn/shell.py` (prompt, tokenizer, `eval_line`, dispatch,
  REPL loop) and `src/adorn/history.py` (git wrapper). Small additions to
  `color.py`, `catalog.py`, `cli.py` (below).

## State model

Session state persists in `~/.local/state/adorn/session.toml`:

```toml
working_theme = "quux"   # the named theme being edited (the base)
swatch        = "#388cff"  # loaded color, or absent
temp          = true     # mode flag
auto          = false    # mode flag
```

- **Working vs live.** *Working theme* is what the shell edits (prompt: `<scheme>
  <theme>`); *live* is the `current` symlink (`cur`). They diverge until `apply`.
  The scheme shown is read from the working theme's `theme.toml` (not stored
  separately).
- **Active directory.** Operations target `themes/<working_theme>/`, **except** in
  temp mode where they target the hidden temp slot `themes/.temp/` (a copy of the
  working theme made on entering temp). The prompt still displays the base name.
- **Swatch** is a modal sub-context. While loaded, the prompt becomes `#rrggbb >`
  and only `al`/`ad`/`as`/`ads`/`ah`/`set`/`c`(clear) act on it.

### Modes — two orthogonal booleans

`temp` and `auto` are independent flags that compose (`[temp]`, `[auto]`,
`[temp][auto]`).

- **temp:** edits go to `themes/.temp/` instead of the named theme. Renderable and
  appliable; survives shell exit (session + slot persist). Exits:
  - `save` → copy `.temp` over the working theme, drop temp.
  - `save <name>` → copy the active dir to a new theme, switch to it, drop temp.
  - `abandon` → delete `.temp`, drop temp, working theme untouched.
- **auto:** every mutating command immediately applies. Toggle with `auto` /
  `auto on` / `auto off`. `save`/`abandon` do **not** touch auto.
- **auto is command-aware (3 reaction tiers by what got dirtied):**
  | dirtied | trigger | verbs |
  |---|---|---|
  | derivation (`cs`, `e`/`es` on theme.toml/scheme.toml) | recompile → render → apply | `re`+`r`+`go` |
  | colors (`set`) | render → apply | `r`+`go` |
  | selection (`ct`) | apply | `go` |

## Persistence & history (git)

- **Layout:** git-dir `~/.local/state/adorn/history.git`, work-tree `~/.config/adorn`.
  On first launch, init the repo and make a baseline commit if absent.
- **Commit-per-mutation:** after a mutating command succeeds, commit the work-tree
  with the command text as the message. Read-only commands (`lst` `lss` `cur` `p`
  `h` `diff` `status` `apps`) do not commit. Failed commands do not commit.
- **`h`:** list commits newest-first, numbered **backwards** — `1` = previous
  command, `2` = the one before, `0` = now (HEAD).
- **`undo N` / `revert N`:** restore the work-tree to the state `N` commits back.
  It undoes the **render** (files change) but **not the apply** — the live symlink
  and desktop stay until you `go`/`apply`. A position pointer (session) tracks how
  far back you are; a new mutating command commits forward from the current point,
  truncating the redo tail.
- **`redo N`:** re-advance the pointer.
- **`diff A B`:** palette-aware diff between two history points — show role color
  changes (compare the two effective palettes) and note any template/`*.toml`/
  fragment changes. `diff 1 0` = last change → now.
- Because the temp slot lives **inside** the work-tree, history/undo/diff behave
  identically in temp and normal mode.

## Command reference (v0.1.0)

Legend for "core": the function(s) the verb drives.

### Session / shell
| Verb | Meaning | core |
|---|---|---|
| `adorn` (no args) | launch REPL | `shell.repl` |
| `exit` | persist session, quit (`goodbye`) | — |
| `help` / `?` | list commands | — |
| `# …` | comment (ignored) | — |

### Listing & info (read-only)
| Verb | Meaning | core |
|---|---|---|
| `lst` | list themes, `*` = live (hides dotdir slots) | `catalog.list_themes` |
| `lss` | list schemes | `catalog.list_schemes` (new) |
| `apps` | apps in theme/scheme; green = scheme app not yet rendered, red = theme fragment with no scheme template | set-compare scheme tmpls vs theme `apps/` (per manifest targets) |
| `p` / `palette` | working palette swatches; flags roles changed-but-unrendered | `commands.effective_palette` + dirty check |
| `status` / `status <app>` | what scheme/palette aspects are unrendered | compare palette/scheme mtime vs fragments |
| `cur` | live applied theme `<scheme> <theme>` | `catalog.current_theme` |
| `h` | history, numbered backwards | `history.log` |
| `diff A B` | palette-aware diff between history points | `history.diff` |

### Working selection
| Verb | Meaning | core |
|---|---|---|
| `ct <theme>` | change working theme | session + `catalog.theme_paths` |
| `cs <scheme>` | change working theme's scheme (writes `theme.toml`) | writes `theme.toml` `scheme=` |

### Color swatch (modal — requires a loaded swatch except `c`)
| Verb | Meaning | core |
|---|---|---|
| `c <role>` / `c +role` | load a role's effective color | `effective_palette` (flattened) |
| `c #rrggbb` / `c <pastel color>` | load a literal/any-format color | `color` (pastel) |
| `c pick` | pick interactively | `pastel pick` |
| `c ls` | list named colors | `pastel list` |
| `c` (bare) | clear the swatch (`clear` = alias) | — |
| `al <amt>` / `ad <amt>` | lighten / darken | `color.lighten` / `darken` |
| `as <amt>` / `ads <amt>` | saturate / desaturate | `color.saturate` / `desaturate` (new) |
| `ah <deg>` | rotate hue | `color.rotate` (new) |
| `set <role>` | write swatch → role override (`role old -> new`) | `palette` overrides write |

### Render / apply
| Verb | Meaning | core |
|---|---|---|
| `render` / `r` | materialize fragments from palette+overrides | `commands.render_theme` |
| `recompile` / `re` | re-extract wallpaper → re-derive palette | `compile.compile_theme` |
| `apply` / `go` | repoint live symlink + reload + wallpaper | `commands.cmd_apply` |
| `rna` | render then apply | `render_theme` + `cmd_apply` |

### Modes
| Verb | Meaning |
|---|---|
| `temp` | enter temp (snapshot working theme → `.temp`) |
| `auto` / `auto on` / `auto off` | toggle auto-apply |
| `save` | (in temp) copy `.temp` over working theme, drop temp |
| `save <name>` | copy active dir → new theme, switch to it, drop temp (any mode) |
| `abandon` | discard `.temp`, drop temp |

### Theme / scheme management
| Verb | Meaning | core |
|---|---|---|
| `new <name> <wallpaper>` | create theme from a wallpaper | `commands.cmd_new` |
| `cps <src> <dst>` / `cps <dst>` | copy scheme (1-arg = current → dst); `-f` forces over conflict | `shutil.copytree` |
| `cpt <src> <dst>` / `cpt <dst>` | copy theme (same rules) | `shutil.copytree` |
| `rm <theme>` / `rms <scheme>` | delete theme / scheme | `shutil.rmtree` |
| `rma <app>` | remove an app from the scheme (then `r` pushes it through) | scheme tmpl + manifest target |

### Editing ($EDITOR)
| Verb | Meaning | target |
|---|---|---|
| `e <app>` | edit theme's rendered fragment | `themes/<t>/apps/<app>/…` |
| `e` (bare) | edit `theme.toml` (derivation overrides) | `themes/<t>/theme.toml` |
| `ec <app>` | edit the real app config | `~/.config/<app>/…` |
| `es <app>` | edit scheme template | `schemes/<s>/<app>.tmpl` |
| `es` (bare) | edit `scheme.toml` | `schemes/<s>/scheme.toml` |

### History / undo
| Verb | Meaning |
|---|---|
| `undo N` / `revert N` | restore work-tree N back (undoes render, not apply) |
| `redo N` | re-advance |

## Core additions required

- `color.py`: `saturate(c, amt)`, `desaturate(c, amt)`, `rotate(c, deg)` — thin
  `pastel saturate|desaturate|rotate` wrappers matching the existing `lighten`/
  `darken` shape (argv list, no shell).
- `catalog.py`: `list_themes` skips names starting with `.` (hides `.temp`);
  add `list_schemes(schemes_dir) -> list[str]`.
- `cli.py`: bare invocation (no subcommand) calls `shell.repl(root)`; all existing
  subcommands unchanged.
- `palette.py` / a small helper: `set_override(tp, role, hexv)` (factor the write
  block already in `cmd_alter` so the shell's `set` and the CLI share it).

## Error handling

- Unknown verb → `error: unknown command: <x>`; nothing commits.
- Swatch op with no swatch → `error: no color loaded (use c <role>)`.
- Unknown role / theme / scheme → explicit `error: …`; nothing commits.
- `pastel` failures surface stderr (existing pattern in `color`/`cmd_alter`).
- Copy conflicts → error unless `-f`.
- A command either fully succeeds (then commits) or errors (no commit); the
  evaluator returns `dirty=False` on error so the loop skips the commit.

## Testing

- **Evaluator tests** (no TTY): feed lines to `eval_line` against a built catalog
  fixture (reuse `build_catalog` from `test_commands.py`); assert output + the
  resulting files/session. Cover every verb.
- **History tests:** `history.py` against a temp work-tree — baseline init, commit
  per mutation, `log` numbering, `undo`/`redo` round-trip, `diff` role changes.
- **Mode tests:** temp enter → edit → `save`/`save <name>`/`abandon`; `auto`
  tiering picks the right verbs per dirtied class.
- **Swatch tests:** load → `al`/`as`/`ah` → `set` writes the expected override.
- **Back-compat:** existing suite stays green; bare `adorn` launches the REPL while
  `adorn <subcommand>` is unchanged.

## Conventions

Python ≥ 3.11, src layout, `encoding="utf-8"`, TDD with `.venv/bin/pytest`. Commit
`feat:`/`refactor:`, no co-author trailer (matches repo history).

## Deferred to v0.2+

- Command grammar: `;` sequencing and `|` **typed** pipes (value carries a
  `scheme`/`theme`/`color` type; receivers validate, so `cps … | ct` errors).
- Tab-completion; richer `diff`/`status` visualizations.
- Reworking the one-shot CLI to mirror the shell verbs (separate, later effort).
