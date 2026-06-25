# adorn — Automated Desktop Ornamentation & Recoloring eNgine

**Date:** 2026-06-24
**Status:** Design approved, pending spec review

## Problem

The desktop theme ("Succulents Dark") spans 8 surfaces — kitty, waybar, swayfx
borders, mako, wofi, swaylock, zathura, delta, and nvim — each with colors
hand-tuned in its own config syntax. Changing the theme means hand-editing every
file, which is enough friction that the theme never changes. The goal is to be
able to switch wallpaper + a fully coherent theme every couple of weeks, and
switch back to an old one at will, with near-zero manual work.

## Goals

- One command flips the whole system to a new, coherent, wallpaper-derived theme.
- Switching *back* to a previous theme is instant and reproducible (no recompile).
- Wallpaper-derived colors are pushed toward stable **semantic roles** (red =
  urgent, green = success, etc.) so the result is legible and consistent across
  any wallpaper, with minimal manual tweaking.
- Per-theme manual tweaks are supported and stored *with* the theme.
- The engine itself is **system-agnostic** and publishable to GitHub; nothing
  about the user's specific apps is baked in.

## Non-goals (YAGNI)

- A user-scriptable color-expression DSL. v1 ships a fixed role set + tunable
  knobs. (Revisit only if a concrete need appears.)
- Live-reloading already-running nvim instances (next launch is fine).
- adorn absorbing the extractor/pastel natively — it shells out to them.
- Pixel-perfect *automatic* reproduction of the existing hand-tuned palette
  (the override layer carries those deltas instead).

## Architecture: engine vs. content

Two separate parts:

```
┌─────────────────────────────────────┐     ┌──────────────────────────────────────┐
│  adorn  (the tool — GitHub, generic) │     │  user content  (~/.config/adorn/)     │
│  • knows nothing about the user apps  │◄────│  adorn.toml      ← manifest           │
│  • reads a manifest                   │ rdr │  templates/      ← color fragments    │
│  • extract → reshape → render → reload│     │  themes/<name>/  ← wallpaper+palette  │
│  • catalog mgmt (list/apply/new/...)  │     │  current → themes/succulents          │
└─────────────────────────────────────┘     └──────────────────────────────────────┘
```

**adorn** = mechanism: a generic palette compiler + Jinja2 template renderer +
catalog manager. **The manifest + templates + theme catalog** = policy, living in
the user's rice repo. Anyone can `pipx install adorn`, write their own manifest,
and theme a completely different set of apps.

### Implementation

- **Language:** Python (pipx-installable). Chosen over Rust because the workload
  is occasional, IO/subprocess-bound glue (TOML parse, template render, shell
  out, run hooks) where Rust's speed is irrelevant, and because the audience —
  ricers who tinker — benefit from a hackable, fork-and-tweak source. Matches the
  existing Python alarm CLI.
- **Runtime deps:** an extractor (default ImageMagick `magick`; pluggable — any
  command that prints `#RRGGBB` colors works, e.g. `wallust`), `pastel` (color
  math), `jinja2`, Python stdlib `tomllib`.
- **Extraction is pluggable:** adorn runs a manifest-configured `[extract]
  command` (with `{path}` substituted), parses every `#RRGGBB` from its stdout,
  and uses those as the raw colors. Default is an ImageMagick histogram command.
  Since adorn does all the semantic reshaping itself, the extractor only needs to
  emit raw dominant colors — so the default is simple and already installed, and
  wallust/others can be dropped in via the manifest.

### Catalog layout (`~/.config/adorn/`)

adorn's directory holds **only theme/color material**. The user's structural app
configs stay in `~/.config/<app>/`, each carrying a single `include`/`@import`
line that points at the active theme via the `current` symlink.

```
adorn.toml                      # manifest (targets, knobs, wallpaper hook)
templates/                      # waybar-colors.css.tmpl, kitty-colors.tmpl, ...
themes/
  succulents/
    wallpaper.jpg
    palette.toml                # base palette (extraction) — the starting place
    overrides.toml              # palette-level role tweaks
    apps/                       # MATERIALIZED, editable per-app color fragments,
      waybar/colors.css         #   saved with the theme. Rendered from
      kitty/colors.conf         #   palette+overrides by `new`/`render`, then
      mako/colors               #   freely hand-editable. THIS is the per-app
      wofi/colors.css           #   control layer.
      zathura/colors
      sway/colors
      nvim/palette.lua
current -> themes/succulents    # symlink marks the active theme
```

The `apps/` fragments are the per-app editable layer the whole system exists to
provide: adorn gives a base (palette → rendered fragments), and the user tweaks
the palette, the overrides, AND any individual app fragment — all saved in the
theme. Each app's real config sources the active theme's fragment through
`current`, e.g. `~/.config/adorn/current/apps/nvim/palette.lua`.

## Delivery: source-from-`current`, copy only as a forced fallback

Each app's structural config stays in `~/.config/<app>/` and carries ONE line
that includes the active theme's color fragment via the `current` symlink.
Switching themes is then just repointing `current` + reloading — adorn never
rewrites the user's structural config.

- `kitty.conf`     → `include ~/.config/adorn/current/apps/kitty/colors.conf`
- `waybar/style.css` → `@import "…/current/apps/waybar/colors.css"` (define-color block)
- `sway/config`    → `include ~/.config/adorn/current/apps/sway/colors`
- `mako/config`    → `include=~/.config/adorn/current/apps/mako/colors`
- `wofi/style.css` → `@import "…/current/apps/wofi/colors.css"` (define-color block)
- `zathura/zathurarc` → `include ~/.config/adorn/current/apps/zathura/colors`
- `nvim`           → `dofile`/`require` of `…/current/apps/nvim/palette.lua`

**App-specific delivery via plugins (forced fallback).** swaylock has no include
mechanism, so its colors must be written into its config. Rather than special-case
this in the engine, adorn leans on the `reload` field: a target's `reload` is just
a shell command run (after `current` is flipped) at apply time. For swaylock the
`reload` command IS a plugin script — `~/.config/adorn/plugins/swaylock` — that
reads the active fragment (`current/apps/swaylock/colors`) and rewrites a delimited
block (`# >>> adorn` / `# <<< adorn`) in `~/.config/swaylock/config`, preserving
structural settings.

Plugins live in `~/.config/adorn/plugins/` (user-owned, untouched by `pipx`
upgrades). A plugin defaults its input (`current/apps/<app>/<file>`) and output
(the app's known config path) and accepts overrides as args. adorn ships
`swaylock` as the worked example. The engine has **no** plugin/`via`/block code —
plugins are simply reload commands, so any app needing bespoke write logic is a
user script referenced from `reload`.

**Wallpaper as a render variable.** Templates receive `{{ wallpaper }}` (the
active theme's wallpaper absolute path) alongside the palette roles, so the
wallpaper is managed *in the fragments*: the sway fragment carries
`output * bg {{ wallpaper }} fill` (surviving `swaymsg reload`) and swaylock
carries `image={{ wallpaper }}`. No separate wallpaper-setting command needed.

**Named schemes.** `templates/` becomes `schemes/<scheme>/` (a set of templates =
a role→app mapping). A theme records its scheme in `themes/<name>/theme.toml`
(`scheme = "default"`). `new --scheme X` selects it; `render` reads it to resolve
`schemes/X/`. Unspecified → `default`. Schemes let one role map differently per
scheme (e.g. kitty `color1` = red in one, yellow in another) independent of the
per-theme palette.

## Palette schema (roles)

Derived from what the configs already use (base16-ish + the waybar rainbow):

| Group | Roles | Derivation |
|---|---|---|
| Background | `bg`, `bg_alt`, `bg_highlight`, `bg_visual` | `bg` pinned near-black; variants = `bg` lightened in steps |
| Foreground | `fg`, `fg_dim`, `muted`/`comment` | light, low-sat; hue borrowed from wallpaper |
| Accent | `accent` | the wallpaper's dominant **saturated** color (the only genuinely image-derived role) |
| Hues | `red`, `green`, `yellow`, `blue`, `cyan`, `magenta` | **hue-anchored** to canonical angles; S/L from theme mood |
| Semantic aliases | `urgent`=red, `success`=green, `warning`=yellow | point at the hue roles |
| Rainbow | `grad0..grad6` | hue sweep (magenta→blue→teal→green→warm) at theme S/L |

### Semantic algorithm (hue-anchored, theme-tinted)

- **Mood** = average saturation + a lightness sense computed from the extracted
  raw colors (via pastel). The single knob that makes every derived role *lean
  toward* the wallpaper.
- **6 hues:** hue fixed near the canonical angle for the role; saturation from
  mood; lightness from a per-role legibility target. Guarantees every role is
  present and legible on any wallpaper → fewest manual tweaks.
- **accent:** the wallpaper's signature saturated color, image-derived — gives
  each theme its character while urgent/etc. stay reliably hue-correct.
- **bg (special case):** ignores the mood-saturation rule — lightness pinned very
  low (~L 6–8 %), saturation near-zero, hue from the wallpaper. Reads as black
  with a whisper of theme. Any theme can pin `bg = "#000000"` in `overrides.toml`.
- **Rainbow `grad0..6`:** a configurable ramp — a hue sweep at the theme's S/L so
  it stays colorful but leans toward the theme.
- **Saturation floor (legibility/distinguishability knob):** the hue-role
  saturation is `clamp(mood_sat × saturation_strength, hue_saturation_floor,
  1.0)`. Default floor is `0.0` (pure mood — the preferred muted look on muted
  wallpapers). Raising it (e.g. `0.30`) lifts the 6 hue roles + ramp to a minimum
  saturation so semantic/ANSI colors stay tellable apart on a muted wallpaper,
  *without* touching `accent`/`bg`/`fg`. Discovered via real-wallpaper testing:
  at floor 0 a muted wallpaper makes red≈yellow≈muted (fine as UI, blurry for a
  terminal). The floor is settable per generation (see commands) so one image can
  yield several saved variants at different saturations.

v1 exposes tunable knobs (canonical hues, mood strength + saturation floor, bg
lightness, ramp endpoints/length) in the manifest — not an expression DSL.

## Compile stats

`adorn new` and `adorn recompile` print a stats block to stdout after compiling:
theme name, wallpaper, raw-color count, mood saturation, the saturation floor
used, the effective hue saturation, and the key role swatches with their H/S/L —
so the chosen saturation is visible without re-deriving it via `pastel`. Pipe to
a file to keep a record.

## Manifest (`adorn.toml`) sketch

```toml
[extract]
# {path} substituted; adorn parses every #RRGGBB from stdout. Default if omitted
# is an equivalent ImageMagick histogram command. Swap in wallust here if wanted.
command = "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"

[wallpaper]
command = "swaymsg output '*' bg {path} fill"   # {path} substituted

[mood]
saturation_strength = 1.0      # how hard derived roles lean toward wallpaper mood
hue_saturation_floor = 0.0     # min saturation for the 6 hue roles + ramp (0 = pure mood)
bg_lightness = 0.07

[ramp]                         # the waybar rainbow
name = "grad"
length = 7
hues = [300, 250, 170, 120, 40]   # sweep waypoints; S/L from mood

# A target renders a fragment into themes/<name>/apps/<name>/<fragment>.
# Apps source it via current/; apply just flips the symlink + reloads.
[[target]]
name   = "waybar"
template = "waybar-colors.css.tmpl"
fragment = "colors.css"                  # → apps/waybar/colors.css
reload   = "pkill -SIGUSR2 waybar"

[[target]]
name   = "kitty"
template = "kitty-colors.tmpl"
fragment = "colors.conf"
reload   = "kitty @ set-colors --all ~/.config/adorn/current/apps/kitty/colors.conf"

[[target]]
name   = "nvim"
template = "nvim-palette.lua.tmpl"
fragment = "palette.lua"
# no reload — picked up on next launch

# Forced fallback: swaylock can't include, so apply rewrites a marked block.
[[target]]
name   = "swaylock"
template = "swaylock-colors.tmpl"
fragment = "colors"
via      = "block"                       # managed-block injection
output   = "~/.config/swaylock/config"   # the file whose marked block is rewritten
```

## Mechanics

- **Compile** (`palette.toml`): run the extract command → parse raw `#RRGGBB`
  colors → compute mood → apply per-role rules → write `palette.toml`. Committed,
  so switching to an old theme never
  recompiles; recompiling is an explicit action.
- **Merge:** effective palette = `palette.toml` + `overrides.toml` layered on top.
  Generated and hand-tuned stay separate, so the generated half can be recompiled
  without losing tweaks.
- **Render (materialize):** Jinja2-render each target's template with the
  effective palette → write to `themes/<name>/apps/<target>/<fragment>`.
  Placeholders: `{{ bg }}`, `{{ accent }}`, `{{ grad[0] }}`, etc. This is the
  *only* step that writes the `apps/` fragments, so hand-edits to them persist
  until the user explicitly re-renders. `new` runs render once; `render <name>`
  re-derives them from the (possibly edited) palette+overrides.
- **Apply:** point `current` → `themes/<name>`; for `via="block"` targets
  (swaylock), rewrite the marked color block in the target's real config from the
  theme's fragment; run reload hooks; set wallpaper. Apply does **not** re-render
  — it deploys the already-materialized `apps/` fragments, so apply never clobbers
  hand-edits. Source-from-`current` targets need no copy (their app config already
  includes `current/apps/<target>/<fragment>`). Re-applying is idempotent.

## Command interface

```
adorn list                                # catalog, * marks current
adorn new <name> <wallpaper> [--scheme S] [--saturation F]  # extract palette + render apps/, stats, then apply (--no-apply)
adorn apply <name>                        # current → theme; reload (incl. plugin reloads); deploys apps/ as-is
adorn render <name>                       # re-derive apps/ fragments from palette+overrides (overwrites apps/)
adorn alter <name> [-c roles] [-w] <pastel-cmd…>  # run a pastel pipeline over theme colors (see below)
adorn current                             # show active theme
adorn preview <name>                      # print palette as ANSI truecolor swatches WITHOUT applying
adorn recompile <name> [--saturation F]   # re-run extraction → palette.toml only (keeps overrides; then `render`)
adorn edit <name>                         # open overrides.toml in $EDITOR (optional convenience)
```

### `adorn alter` — pastel pipelines over theme colors

`adorn alter <theme> [-c role[,role…]] [-w] <pastel command…>` runs a `pastel`
pipeline against a theme's effective colors.

- **Selection:** `-c/--color role,role` picks colors; absent ⇒ all palette colors
  (ramp entries as `grad0…gradN`).
- **`+role` sigil:** any `+role` token in the command is replaced with that role's
  hex (so a color can be both piped in *and* referenced as an argument).
- **Execution:** the N selected colors are fed (one hex per line) into the pastel
  command; pastel emits M colors. **Require M == N**, mapping 1:1 back to the
  selected colors. M≠N (e.g. `color #111` yields 1 for N>1) is an error — set
  multiple colors to one value with explicit separate calls.
- **`-w/--write`:** write the N results to the selected roles in
  `themes/<theme>/overrides.toml` (then `render` to push into `apps/`).

Examples: `alter volc -c red saturate .5`; `alter volc -c accent -w mix +magenta`;
`alter volc -w saturate .3` (lift every color).

The key separation: **`render` writes the `apps/` fragments** (from
palette+overrides), **`apply` deploys them** (symlink + reload). Hand-edits to
`apps/<app>/…` survive every `apply` and are only regenerated by an explicit
`render`/`recompile`+`render`.

`--saturation F` overrides `[mood] hue_saturation_floor` for that compile, so one
image can produce several saved variants (e.g. `new succ-muted img`, `new
succ-mid img --saturation 0.30`). `new`/`recompile` print a compile-stats block
(see "Compile stats").

Core = `list / new / apply / current`; `preview` + `recompile` round out v1.

## Build order

1. **adorn engine** — TDD against a *fake* manifest + fake templates (genericity
   makes it fully isolatable): manifest parse → compile → merge → render → atomic
   apply → reload → catalog.
2. **Rice integration** — extract today's Succulents colors into template
   fragments; wire each config to `include` its fragment; create the `succulents`
   theme from the current wallpaper.
3. **Validate** — `adorn apply succulents` reproduces the current look →
   `adorn new <x> <new-wallpaper>` proves a real switch →
   `adorn apply succulents` proves switch-back.

## Acceptance criteria

- `adorn apply succulents` reproduces the current Succulents Dark look across all
  8 surfaces (deltas from the hand-tuned original carried in `succulents/
  overrides.toml`).
- A brand-new wallpaper yields a coherent, legible theme via `adorn new` with no
  more than a couple of override tweaks needed.
- Switching between two existing themes is instant and requires no recompile.
- The engine's test suite passes against fake fixtures with zero dependency on
  the user's real configs.

## Open / deferred

- adorn lives in its own git repo (`~/projects/adorn`); the user content
  (manifest, templates, theme catalog) will live under `~/.config/adorn/` in the
  rice setup (rice itself is not yet under git — see the standing "track configs
  w git?" task).
- Possible later: color-expression DSL; absorbing the extractor/pastel natively
  into a single binary; live nvim reload; wallust as an alternate extract backend.
