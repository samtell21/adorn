# adorn

**Automated Desktop Ornamentation & Recoloring eNgine.**

Compile a wallpaper into a coherent color palette and render it across your
desktop configs (kitty, waybar, sway, …) with one command. Generic and
manifest-driven: adorn knows nothing about your apps — you declare them.

## Requirements
- Python ≥ 3.11
- [`pastel`](https://github.com/sharkdp/pastel) (color math)
- An extractor: ImageMagick (`magick`) by default; any command that prints
  `#RRGGBB` colors works (e.g. `wallust`).

## Install
```sh
pipx install adorn
```
