# src/adorn/commands.py
"""High-level commands wiring the modules together."""
import shutil
from pathlib import Path

from . import catalog
from . import compile as compile_mod
from . import manifest as manifest_mod
from . import palette as palette_mod
from . import reload as reload_mod
from . import render as render_mod


def load_manifest(root):
    return manifest_mod.load(Path(root) / "adorn.toml")


def effective_palette(root, name) -> dict:
    tp = catalog.theme_paths(root, name)
    base = palette_mod.load(tp.palette)
    overrides = palette_mod.load(tp.overrides)
    return palette_mod.merge(base, overrides)


def cmd_list(root) -> None:
    current = catalog.current_theme(root)
    for name in catalog.list_themes(root):
        marker = "*" if name == current else " "
        print(f"{marker} {name}")


def cmd_current(root) -> None:
    print(catalog.current_theme(root) or "(none)")


def render_theme(root, name, manifest) -> None:
    tp = catalog.theme_paths(root, name)
    context = dict(effective_palette(root, name))
    context["wallpaper"] = str(tp.wallpaper)
    render_mod.materialize(manifest, context, tp.dir / "apps")


def cmd_render(root, name) -> None:
    manifest = load_manifest(root)
    render_theme(root, name, manifest)
    print(f"rendered apps/ fragments for '{name}'")


def cmd_apply(root, name) -> None:
    manifest = load_manifest(root)
    tp = catalog.theme_paths(root, name)
    apps_dir = tp.dir / "apps"
    if not apps_dir.exists():
        render_theme(root, name, manifest)
    catalog.set_current(root, name)
    reload_mod.run_reloads(manifest)
    reload_mod.set_wallpaper(manifest, tp.wallpaper)


def cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None) -> None:
    manifest = load_manifest(root)
    theme_dir = catalog.new_theme_dir(root, name)
    dest = theme_dir / ("wallpaper" + Path(wallpaper).suffix)
    shutil.copy(wallpaper, dest)
    (theme_dir / "overrides.toml").write_text(
        "# per-theme color/role overrides\n", encoding="utf-8"
    )
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    render_theme(root, name, manifest)
    print(compile_mod.format_stats(name, result))
    if do_apply:
        cmd_apply(root, name)


def cmd_recompile(root, name, saturation_floor=None) -> None:
    manifest = load_manifest(root)
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    print(compile_mod.format_stats(name, result))
    print(f"palette recompiled; run `adorn render {name}` to update apps/")


STARTER_MANIFEST = '''# adorn manifest — declares which apps adorn themes.

[extract]
command = "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"

[wallpaper]
# command = "swaymsg output '*' bg {path} fill"

[mood]
saturation_strength = 1.0
hue_saturation_floor = 0.0   # raise (e.g. 0.30) for more saturated semantic colors
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 250, 215, 175, 120, 60, 40]

# One [[target]] per app. Example:
# [[target]]
# name = "kitty"
# template = "kitty.conf.tmpl"          # lives in templates/
# output = "~/.config/kitty/colors.conf"
# reload = "kitty @ set-colors --all ~/.config/kitty/colors.conf"
'''


def cmd_init(root) -> None:
    root = Path(root)
    manifest_path = root / "adorn.toml"
    if manifest_path.exists():
        raise FileExistsError(f"adorn config already exists at {manifest_path}")
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "themes").mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(STARTER_MANIFEST, encoding="utf-8")
    print(f"created adorn config at {root}")
    print(f"  edit {manifest_path} — add a [[target]] per app")
    print(f"  put templates in {root / 'templates'}")


def cmd_preview(root, name) -> None:
    palette = effective_palette(root, name)
    for key, value in palette.items():
        colors = value if isinstance(value, list) else [value]
        for i, c in enumerate(colors):
            label = f"{key}{i}" if isinstance(value, list) else key
            try:
                r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
            except (ValueError, IndexError):
                print(f"{label:<16}{c}")
                continue
            swatch = f"\x1b[48;2;{r};{g};{b}m        \x1b[0m"
            print(f"{label:<16}{swatch} {c}")
