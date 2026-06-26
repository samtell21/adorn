# adorn

**Automated Desktop Ornamentation & Recoloring eNgine** — compile a wallpaper
into a coherent color palette and render it across your whole desktop with one
command. Generic and manifest-driven: adorn knows nothing about your apps; you
declare them.

```sh
adorn new oceanic ~/Pictures/oceanic.jpg   # extract a palette, render every app, apply
adorn apply succulents                      # switch themes (symlink flip + reload)
adorn alter oceanic -c accent -w mix +magenta   # tweak a color and save it
```

## How it works

- **Extract** a palette from the wallpaper (ImageMagick by default; pluggable),
  then **reshape** it with [`pastel`](https://github.com/sharkdp/pastel) into
  semantic roles (`bg`, `fg`, `accent`, `red`/`green`/`yellow`/…, a rainbow
  `grad` ramp) — hue-anchored and tinted to the wallpaper's mood.
- A **theme** is `palette.toml` + `overrides.toml` + an `apps/` directory of
  **materialized, editable per-app color fragments**. `render` writes them from
  the palette; you can hand-edit any of them and they're saved with the theme.
- `apply` points a `current` symlink at the active theme and runs each target's
  reload. Your real app configs stay in `~/.config/<app>/` and just `include`
  the active fragment via `current/` — so switching themes is a symlink flip,
  and adorn never overwrites your structural config.
- **Schemes** (`schemes/<name>/`) own both the templates *and* the color
  derivation (`scheme.toml`), so one wallpaper can yield different color systems.
- Apps that can't `include` a file (e.g. swaylock) use a **plugin** — just a
  shell command in the target's `reload` field.

## Layout

```
~/.config/adorn/
  adorn.toml            # manifest: [extract] + one [[target]] per app
  schemes/default/      # templates (*.tmpl) + scheme.toml (color derivation)
  themes/<name>/        # wallpaper, palette.toml, overrides.toml, apps/<app>/…
  plugins/              # optional per-app delivery scripts
  current -> themes/…   # the active theme
```

Templates are Jinja2 and can derive colors inline with pastel-backed filters:
`{{ bg | mix(green, 0.2) }}`, `{{ fg | darken(0.1) }}`, `{{ accent | rgb }}`.

## Commands

| | |
|---|---|
| `adorn init` | scaffold `~/.config/adorn` |
| `adorn new <name> <wallpaper> [--scheme S] [--saturation F]` | create + apply a theme |
| `adorn apply <name>` | make a theme active |
| `adorn render <name>` | re-derive `apps/` from palette + overrides |
| `adorn alter <name> [-c roles] [-w] <pastel cmd…>` | run a pastel pipeline over colors |
| `adorn preview <name>` | print the palette as terminal swatches |
| `adorn list` / `current` | catalog / active theme |

## Requirements

- Python ≥ 3.11
- [`pastel`](https://github.com/sharkdp/pastel) — color math
- An extractor: ImageMagick (`magick`) by default; any command that prints
  `#RRGGBB` colors works (e.g. `wallust`)

## Install

```sh
pipx install git+https://github.com/samtell21/adorn
# or, from a clone:
git clone https://github.com/samtell21/adorn && pipx install ./adorn
```

Then `adorn init`, declare your apps in `adorn.toml`, and `adorn new`.
