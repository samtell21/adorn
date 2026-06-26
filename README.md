# adorn

**Automated Desktop Ornamentation & Recoloring eNgine** — compile a wallpaper
into a coherent color palette and render it across your whole desktop with one
command. Generic and manifest-driven: adorn knows nothing about your apps; you
declare them once, then switch coordinated themes instantly.

```sh
adorn new oceanic ~/Pictures/oceanic.jpg   # extract a palette, render every app, apply it
adorn apply succulents                      # switch themes (instant)
adorn alter oceanic -c accent -w mix +magenta   # nudge a color and save it
```

---

## Mental model

- A **palette** is a set of named *roles* (`bg`, `fg`, `accent`, `red`, `green`,
  …) — see [the roles table](#template-context-roles--filters). adorn derives
  them from a wallpaper.
- A **scheme** (`schemes/<name>/`) owns the **templates** (one per app) *and* the
  **color derivation** (`scheme.toml`). It's a reusable color *system*.
- A **theme** (`themes/<name>/`) is one scheme applied to one wallpaper:
  `palette.toml` (the derived colors) + `overrides.toml` (your tweaks) + an
  `apps/` directory of **rendered, editable per-app color fragments**.
- Your real app configs **stay in `~/.config/<app>/`** and `include` the active
  theme's fragment through a `current` symlink. `adorn apply` just repoints that
  symlink and reloads — it never rewrites your structural config.

```
~/.config/adorn/
  adorn.toml              # manifest: [extract] + one [[target]] per app
  schemes/default/
    scheme.toml           # color derivation (mood, ramp, hues, fixed)
    kitty-colors.tmpl     # a template per app
    waybar-colors.css.tmpl
  themes/
    oceanic/
      wallpaper.jpg
      palette.toml        # derived roles (generated)
      overrides.toml      # your per-role tweaks
      theme.toml          # which scheme this theme uses
      apps/
        kitty/colors.conf       # rendered fragment — editable, saved here
        waybar/colors.css
  current -> themes/oceanic     # the active theme
```

---

## Install

```sh
pipx install git+https://github.com/samtell21/adorn
```

Requires Python ≥ 3.11, [`pastel`](https://github.com/sharkdp/pastel) (color
math), and an extractor — ImageMagick (`magick`) by default, or any command
that prints `#RRGGBB` colors (e.g. `wallust`).

---

## Walkthrough: theme kitty end to end

**1. Scaffold.**

```sh
adorn init                 # creates ~/.config/adorn/{adorn.toml, schemes/default/, themes/}
```

**2. Declare kitty as a target** in `~/.config/adorn/adorn.toml`:

```toml
[extract]
command = "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"

[[target]]
name     = "kitty"
template = "kitty-colors.tmpl"     # lives in the scheme dir
fragment = "colors.conf"           # rendered to themes/<t>/apps/kitty/colors.conf
reload   = "kitty @ set-colors --all ~/.config/adorn/current/apps/kitty/colors.conf"
```

**3. Write the template** `~/.config/adorn/schemes/default/kitty-colors.tmpl`.
It's Jinja2; the palette roles are the variables:

```jinja
background {{ bg }}
foreground {{ fg }}
cursor     {{ accent }}

color0 {{ bg_highlight }}
color1 {{ red }}
color2 {{ green }}
color3 {{ yellow }}
color4 {{ blue }}
color5 {{ magenta }}
color6 {{ cyan }}
color7 {{ fg }}
```

**4. Wire kitty to source it** — one line in your `~/.config/kitty/kitty.conf`
(your real config stays put; this just pulls in the active theme's colors):

```conf
include ~/.config/adorn/current/apps/kitty/colors.conf
```

**5. Create a theme from a wallpaper:**

```sh
adorn new oceanic ~/Pictures/oceanic.jpg
```

That extracts a palette, renders `themes/oceanic/apps/kitty/colors.conf`, points
`current` → `themes/oceanic`, and runs kitty's reload. kitty is now themed.

**6. Switch.** Make another (`adorn new forest ~/Pictures/forest.jpg`), then:

```sh
adorn apply oceanic        # current -> oceanic, reload
adorn apply forest         # instant switch
```

Add more apps by repeating steps 2–4 (a target, a template, one `include` line).

---

## Template context (roles + filters)

Every template is rendered with these variables:

| Role | Meaning |
|---|---|
| `bg`, `bg_alt`, `bg_highlight`, `bg_visual` | backgrounds (near-black → lighter surfaces) |
| `fg`, `fg_dim`, `muted`, `comment` | foreground / dimmed / secondary text |
| `accent` | the wallpaper's signature color |
| `red` `green` `yellow` `blue` `cyan` `magenta` | the six semantic hues |
| `urgent` `success` `warning` | aliases of `red` / `green` / `yellow` |
| `grad` | the ramp — a **list**, e.g. `{{ grad[0] }}` … `{{ grad[6] }}` |
| `wallpaper` | absolute path to the theme's wallpaper |

All values are `#rrggbb`. Derive colors inline with pastel-backed **filters**:

```jinja
{{ bg | mix(green, 0.2) }}     {# blend bg 20% toward green — e.g. a diff wash #}
{{ fg | darken(0.1) }}         {# darken / lighten by an amount #}
{{ accent | rgb }}             {# "#9fb06a" -> "159;176;106" (ANSI 24-bit triple) #}
```

---

## Manifest (`adorn.toml`)

Just `[extract]` and one `[[target]]` per app:

| Field | Required | Purpose |
|---|---|---|
| `name` | yes | target id; fragment lands in `apps/<name>/` |
| `template` | yes | template filename inside the scheme dir |
| `fragment` | yes | output filename (e.g. `colors.conf`) |
| `reload` | no | shell command run after `current` flips (re-read signal, **or** a plugin) |

`[extract] command` runs with `{path}` = the wallpaper; adorn parses every
`#RRGGBB` from its stdout.

---

## Scheme color derivation (`schemes/<name>/scheme.toml`)

Controls how the wallpaper becomes roles:

```toml
[mood]
saturation_strength  = 1.0    # how hard hues lean toward the wallpaper's mood
hue_saturation_floor = 0.0    # raise (e.g. 0.30) so muted wallpapers stay legible
bg_lightness         = 0.07   # how dark the background is

[ramp]                        # the `grad` rainbow
name   = "grad"
length = 7
hues   = [300, 250, 215, 175, 120, 60, 40]   # waypoints; sweeps at theme S/L

[hues]                        # optional: override a role's canonical hue angle
red = 5

[fixed]                       # optional: pin a role to a literal hex, ignoring the wallpaper
bg = "#000000"
```

A theme picks its scheme via `adorn new <name> <wallpaper> --scheme <scheme>`
(recorded in `themes/<name>/theme.toml`; defaults to `default`).

---

## Tweaking a theme

- **Per-role**, regenerable: edit `themes/<t>/overrides.toml` (e.g.
  `accent = "#88c0d0"`), then `adorn render <t>` to push it into the fragments.
- **Per-app**, free-form: edit any `themes/<t>/apps/<app>/…` fragment directly —
  it's saved with the theme and survives `apply` (only `render` overwrites it).
- **From the CLI** with pastel:

  ```sh
  adorn alter forest -c red saturate 0.4        # preview a change (with swatches)
  adorn alter forest -c accent -w mix +magenta  # mix accent with magenta, write to overrides
  adorn alter forest -w lighten 0.05            # lift every color, save
  ```

  The selected colors are piped through the pastel command; `+role` expands to
  that role's hex; `-w` writes results to `overrides.toml`.

---

## Plugins (apps that can't `include`)

If an app can't include an arbitrary file, its delivery is just a script in its
target's `reload` field. Example — swaylock can't include, so a plugin writes a
managed color block into its config:

```toml
[[target]]
name     = "swaylock"
template = "swaylock-colors.tmpl"
fragment = "colors"
reload   = "~/.config/adorn/plugins/swaylock"   # reads current/apps/swaylock/colors, edits the config
```

Plugins live in `~/.config/adorn/plugins/` (untouched by upgrades). adorn runs
`reload` after flipping `current`, so the plugin sees the active fragment at
`~/.config/adorn/current/apps/<name>/<fragment>`.

---

## Commands

| Command | Does |
|---|---|
| `adorn init` | scaffold `~/.config/adorn` |
| `adorn new <name> <wallpaper> [--scheme S] [--saturation F]` | extract, render, apply |
| `adorn apply <name>` | make a theme active (symlink flip + reload) |
| `adorn render <name>` | re-derive `apps/` from palette + overrides |
| `adorn recompile <name> [--saturation F]` | re-extract the palette from the wallpaper |
| `adorn alter <name> [-c roles] [-w] <pastel cmd…>` | run a pastel pipeline over colors |
| `adorn preview <name>` | print the palette as terminal swatches |
| `adorn list` / `adorn current` | catalog / active theme |
