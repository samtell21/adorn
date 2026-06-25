# src/adorn/commands.py
"""High-level commands wiring the modules together."""
import shlex
import shutil
import subprocess
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


def cmd_apply(root, name) -> None:
    manifest = load_manifest(root)
    tp = catalog.theme_paths(root, name)
    palette = effective_palette(root, name)
    outputs = render_mod.render_all(manifest, palette, tp.files)
    render_mod.write_all(outputs)
    reload_mod.run_reloads(manifest)
    reload_mod.set_wallpaper(manifest, tp.wallpaper)
    catalog.set_current(root, name)


def cmd_new(root, name, wallpaper, do_apply=True) -> None:
    manifest = load_manifest(root)
    theme_dir = catalog.new_theme_dir(root, name)
    dest = theme_dir / ("wallpaper" + Path(wallpaper).suffix)
    shutil.copy(wallpaper, dest)
    (theme_dir / "overrides.toml").write_text("# per-theme color/role overrides\n", encoding="utf-8")
    compile_mod.compile_theme(root, name, manifest)
    if do_apply:
        cmd_apply(root, name)


def cmd_recompile(root, name) -> None:
    manifest = load_manifest(root)
    compile_mod.compile_theme(root, name, manifest)


def cmd_preview(root, name) -> None:
    palette = effective_palette(root, name)
    for key, value in palette.items():
        colors = value if isinstance(value, list) else [value]
        for i, c in enumerate(colors):
            label = f"{key}{i}" if isinstance(value, list) else key
            subprocess.run(
                f"printf '%-16s' {shlex.quote(label)}; "
                f"pastel color {shlex.quote(c)} | head -n1",
                shell=True,
            )
