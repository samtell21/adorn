# src/adorn/commands.py
"""High-level commands wiring the modules together."""
import re
import shutil
import subprocess
from pathlib import Path

from . import catalog
from . import compile as compile_mod
from . import manifest as manifest_mod
from . import palette as palette_mod
from . import reload as reload_mod
from . import render as render_mod


def _swatch(hexv: str) -> str:
    """Render a 4-space ANSI truecolor swatch background."""
    try:
        r, g, b = int(hexv[1:3], 16), int(hexv[3:5], 16), int(hexv[5:7], 16)
    except (ValueError, IndexError):
        return "    "
    return f"\x1b[48;2;{r};{g};{b}m    \x1b[0m"


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
    scheme_dir = manifest.schemes_dir / catalog.theme_scheme(tp)
    context = dict(effective_palette(root, name))
    context["wallpaper"] = str(tp.wallpaper)
    render_mod.materialize(manifest, context, tp.dir / "apps", scheme_dir)


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


def cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None, scheme="default") -> None:
    manifest = load_manifest(root)
    if not (manifest.schemes_dir / scheme).is_dir():
        raise ValueError(f"no such scheme: {scheme!r} (looked in {manifest.schemes_dir})")
    theme_dir = catalog.new_theme_dir(root, name)
    dest = theme_dir / ("wallpaper" + Path(wallpaper).suffix)
    shutil.copy(wallpaper, dest)
    (theme_dir / "overrides.toml").write_text(
        "# per-theme color/role overrides\n", encoding="utf-8"
    )
    (theme_dir / "theme.toml").write_text(f'scheme = "{scheme}"\n', encoding="utf-8")
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


STARTER_MANIFEST = '''# adorn manifest — which apps adorn themes. Color derivation lives per-scheme
# in schemes/<scheme>/scheme.toml (see schemes/default/scheme.toml).

[extract]
command = "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"

# One [[target]] per app. Example:
# [[target]]
# name = "kitty"
# template = "kitty-colors.tmpl"   # lives in schemes/<scheme>/
# fragment = "colors.conf"          # materialized at themes/<t>/apps/kitty/colors.conf
# reload = "kitty @ set-colors --all ~/.config/adorn/current/apps/kitty/colors.conf"
'''


STARTER_SCHEME = '''# default scheme — color derivation. Copy this dir to make a new scheme.
[mood]
saturation_strength = 1.0
hue_saturation_floor = 0.0   # raise (e.g. 0.30) for more saturated semantic colors
bg_lightness = 0.07

[[list]]
name = "grad"
length = 7
hues = [300, 250, 215, 175, 120, 60, 40]

# [hues]   # override canonical hue per role, e.g.  red = 5
# [fixed]  # pin roles to a literal hex regardless of wallpaper, e.g.  bg = "#000000"
'''


def cmd_init(root) -> None:
    root = Path(root)
    manifest_path = root / "adorn.toml"
    if manifest_path.exists():
        raise FileExistsError(f"adorn config already exists at {manifest_path}")
    (root / "schemes" / "default").mkdir(parents=True, exist_ok=True)
    (root / "themes").mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(STARTER_MANIFEST, encoding="utf-8")
    (root / "schemes" / "default" / "scheme.toml").write_text(STARTER_SCHEME, encoding="utf-8")
    print(f"created adorn config at {root}")
    print(f"  edit {manifest_path} — add a [[target]] per app")
    print(f"  color derivation: {root / 'schemes' / 'default' / 'scheme.toml'}")
    print(f"  put templates in {root / 'schemes' / 'default'}")


def cmd_alter(root, name, colors, write, command) -> None:
    if not command:
        raise ValueError("no pastel command given")
    pal = effective_palette(root, name)

    # flatten palette into selectable colors (array -> grad0..gradN-1)
    selectable = {}
    for k, v in pal.items():
        if isinstance(v, list):
            for i, c in enumerate(v):
                selectable[f"{k}{i}"] = c
        else:
            selectable[k] = v

    if colors:
        for c in colors:
            if c not in selectable:
                raise ValueError(f"unknown color role: {c}")
        selected = list(colors)
    else:
        selected = list(selectable.keys())

    # expand +role sigils in the command
    expanded = []
    for tok in command:
        if tok.startswith("+"):
            role = tok[1:]
            if role not in selectable:
                raise ValueError(f"unknown color role in +{role}")
            expanded.append(selectable[role])
        else:
            expanded.append(tok)

    stdin = "".join(selectable[s] + "\n" for s in selected)
    # run `pastel <expanded>` then normalize via `pastel format hex`.
    # argv lists + NO shell: user tokens can't inject (a token like ";rm" is just
    # a literal pastel argument, which pastel rejects).
    try:
        step = subprocess.run(
            ["pastel", *expanded], input=stdin, capture_output=True, text=True, check=True
        )
        norm = subprocess.run(
            ["pastel", "format", "hex"], input=step.stdout, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"pastel failed: {(e.stderr or '').strip()}") from e
    results = [ln.strip().lower() for ln in norm.stdout.splitlines() if ln.strip()]
    if len(results) != len(selected):
        raise ValueError(
            f"pastel produced {len(results)} color(s) for {len(selected)} selected — "
            f"refusing an ambiguous mapping (set multiple colors with separate calls)"
        )

    for role, newc in zip(selected, results):
        before = selectable[role]
        print(f"{role:<14} {_swatch(before)} {before}  ->  {_swatch(newc)} {newc}")

    if write:
        tp = catalog.theme_paths(root, name)
        overrides = palette_mod.load(tp.overrides)
        array_name, array_vals = None, None
        for role, newc in zip(selected, results):
            m = re.fullmatch(r"([a-zA-Z_]+)(\d+)", role)
            if m and isinstance(pal.get(m.group(1)), list):
                base, idx = m.group(1), int(m.group(2))
                if array_vals is None:
                    array_name, array_vals = base, list(pal[base])
                array_vals[idx] = newc
            else:
                overrides[role] = newc
        if array_vals is not None:
            overrides[array_name] = array_vals
        palette_mod.dump(overrides, tp.overrides)
        print(f"wrote {len(selected)} override(s) to {tp.overrides}")


def cmd_preview(root, name) -> None:
    palette = effective_palette(root, name)
    for key, value in palette.items():
        colors = value if isinstance(value, list) else [value]
        for i, c in enumerate(colors):
            label = f"{key}{i}" if isinstance(value, list) else key
            swatch = _swatch(c)
            if swatch == "    ":
                print(f"{label:<16}{c}")
            else:
                print(f"{label:<16}{swatch} {c}")
