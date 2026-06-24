# adorn Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generic, manifest-driven adorn engine: a Python CLI that compiles a wallpaper into a role palette and renders it across arbitrary app configs, then applies + reloads them.

**Architecture:** A small Python package that orchestrates external CLIs (an extractor — ImageMagick by default — and `pastel` for color math) and Jinja2 templates. It knows nothing about specific apps: everything app-specific comes from a user manifest (`adorn.toml`) and a theme catalog. The engine is developed and tested entirely against *fake* manifests/templates/themes in temp dirs, so it never depends on the user's real configs.

**Tech Stack:** Python ≥3.11 (stdlib `tomllib`, `argparse`, `subprocess`, `pathlib`), `jinja2`, the `pastel` CLI, the `magick` (ImageMagick) CLI. Packaged with hatchling, installed via pipx.

## Global Constraints

- Python ≥ 3.11 (required for stdlib `tomllib`). `requires-python = ">=3.11"`.
- Runtime CLI deps: `pastel` (color math) and an extractor command (default ImageMagick `magick`). Both are invoked via `subprocess`.
- Src layout: package code under `src/adorn/`, tests under `tests/`.
- Every color value produced/stored is a lowercase `#rrggbb` string. Ramp roles are lists of such strings.
- `subprocess` calls use `shell=True` where the command is a user-authored manifest string (reload hooks, wallpaper command, extract command) or an internal `pastel` pipeline — these are shell commands by contract and cannot be arg-lists. **Any value interpolated into such a string (notably `{path}` from a wallpaper filename, and palette values in `preview`) MUST be passed through `shlex.quote()`** to prevent shell injection from a filename/override containing metacharacters. Color values adorn generates are a fixed `#rrggbb`/numeric charset and are also quoted defensively.
- TDD: write the failing test first, every task. Commit after each task with a `feat:`/`test:`/`chore:` message.
- Run tests with the project venv: `.venv/bin/pytest`.
- `pastel` and `magick` are present in the dev environment; color/extraction tests run against the real tools (they are deterministic).

---

### Task 1: Project scaffold + CLI entry stub

**Files:**
- Create: `pyproject.toml`
- Create: `src/adorn/__init__.py`
- Create: `src/adorn/cli.py`
- Create: `README.md`
- Modify: `.gitignore`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: `adorn.__version__` (str); `adorn.cli.main(argv: list[str] | None = None) -> int`; console script `adorn`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
import subprocess
import sys

import adorn


def test_version_constant():
    assert adorn.__version__ == "0.1.0"


def test_cli_version_runs():
    out = subprocess.run(
        [sys.executable, "-m", "adorn", "--version"],
        capture_output=True, text=True,
    )
    assert "0.1.0" in out.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn'` (package not built yet).

- [ ] **Step 3: Create the package and packaging files**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "adorn"
version = "0.1.0"
description = "Automated Desktop Ornamentation & Recoloring eNgine — wallpaper-driven multi-surface desktop theming"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["jinja2>=3.0"]

[project.scripts]
adorn = "adorn.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7"]

[tool.hatch.build.targets.wheel]
packages = ["src/adorn"]
```

```python
# src/adorn/__init__.py
__version__ = "0.1.0"
```

```python
# src/adorn/cli.py
"""adorn command-line entry point (stub; subcommands added in Task 10)."""
import argparse

from . import __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="adorn",
        description="Automated Desktop Ornamentation & Recoloring eNgine",
    )
    parser.add_argument("--version", action="version", version=f"adorn {__version__}")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```markdown
<!-- README.md -->
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
```

Append to `.gitignore`:

```gitignore
# Python
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
dist/
```

- [ ] **Step 4: Create venv and install editable**

Run:
```bash
cd ~/projects/adorn
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
Expected: installs adorn + jinja2 + pytest with no errors.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/adorn/__init__.py src/adorn/cli.py README.md .gitignore tests/test_smoke.py
git commit -m "chore: scaffold adorn package + CLI version stub"
```

---

### Task 2: Color helpers (`pastel` wrappers)

**Files:**
- Create: `src/adorn/color.py`
- Test: `tests/test_color.py`

**Interfaces:**
- Produces:
  - `color.hsl(c: str) -> tuple[float, float, float]` — (hue 0–360, sat 0–1, light 0–1)
  - `color.make_hsl(h: float, s: float, l: float) -> str` — build `#rrggbb`
  - `color.lighten(c: str, amount: float) -> str`
  - `color.gradient(stops: list[str], n: int) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_color.py
from adorn import color


def approx(a, b, tol):
    return abs(a - b) <= tol


def test_hsl_parses_components():
    h, s, l = color.hsl("#3a9d23")
    assert approx(h, 109, 3)
    assert approx(s, 0.635, 0.05)
    assert approx(l, 0.376, 0.05)


def test_make_hsl_round_trips():
    c = color.make_hsl(120, 0.5, 0.5)
    h, s, l = color.hsl(c)
    assert approx(h, 120, 3)
    assert approx(s, 0.5, 0.05)
    assert approx(l, 0.5, 0.05)


def test_make_hsl_returns_hex():
    c = color.make_hsl(0, 1.0, 0.5)
    assert c.startswith("#") and len(c) == 7


def test_lighten_increases_lightness():
    base = "#404040"
    out = color.lighten(base, 0.2)
    assert color.hsl(out)[2] > color.hsl(base)[2]


def test_gradient_returns_n_colors():
    g = color.gradient(["#000000", "#ffffff"], 5)
    assert len(g) == 5
    assert all(x.startswith("#") for x in g)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_color.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.color'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/color.py
"""Thin wrappers around the `pastel` CLI for color math.

Every transform shells out to pastel and returns a #rrggbb string, keeping
adorn a tiny orchestrator with the color math in one well-tested tool. Inputs
are colors adorn generates, so shell=True is acceptable here.
"""
import re
import subprocess

_HSL_RE = re.compile(r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)")


def _run(cmd: str) -> str:
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()


def _to_hex(pipeline: str) -> str:
    """Run a pastel pipeline yielding one color; return it as #rrggbb."""
    return _run(f"{pipeline} | pastel format hex").strip().lower()


def hsl(c: str) -> tuple[float, float, float]:
    """Return (hue 0-360, saturation 0-1, lightness 0-1)."""
    out = _run(f"pastel format hsl {c}")
    m = _HSL_RE.match(out)
    if not m:
        raise ValueError(f"could not parse pastel hsl output: {out!r}")
    return float(m.group(1)), float(m.group(2)) / 100, float(m.group(3)) / 100


def make_hsl(h: float, s: float, l: float) -> str:
    """Build a #rrggbb color from HSL (h degrees, s/l in 0-1)."""
    spec = f"hsl({h:.0f}, {s * 100:.1f}%, {l * 100:.1f}%)"
    return _to_hex(f"pastel color '{spec}'")


def lighten(c: str, amount: float) -> str:
    return _to_hex(f"pastel lighten {amount} {c}")


def gradient(stops: list[str], n: int) -> list[str]:
    """Return n #rrggbb colors interpolated across the given stops."""
    out = _run(f"pastel gradient -n {n} {' '.join(stops)} | pastel format hex")
    return [line.strip().lower() for line in out.splitlines() if line.strip()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_color.py -v`
Expected: PASS (5 passed). If `gradient` fails, confirm pastel is installed: `pastel --version`.

- [ ] **Step 5: Commit**

```bash
git add src/adorn/color.py tests/test_color.py
git commit -m "feat: pastel-backed color helpers (hsl/make_hsl/lighten/gradient)"
```

---

### Task 3: Palette load / merge / dump

**Files:**
- Create: `src/adorn/palette.py`
- Test: `tests/test_palette.py`

**Interfaces:**
- Produces:
  - `palette.load(path) -> dict` — returns `{}` if file is missing
  - `palette.merge(base: dict, override: dict) -> dict`
  - `palette.dump(palette: dict, path) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_palette.py
import tomllib

from adorn import palette


def test_load_missing_returns_empty(tmp_path):
    assert palette.load(tmp_path / "nope.toml") == {}


def test_merge_override_wins():
    base = {"bg": "#111111", "fg": "#cccccc"}
    over = {"bg": "#000000"}
    assert palette.merge(base, over) == {"bg": "#000000", "fg": "#cccccc"}


def test_dump_round_trips_strings_and_lists(tmp_path):
    p = {"bg": "#111111", "grad": ["#aaaaaa", "#bbbbbb", "#cccccc"]}
    path = tmp_path / "palette.toml"
    palette.dump(p, path)
    reloaded = tomllib.loads(path.read_text())
    assert reloaded == p


def test_load_reads_dump(tmp_path):
    p = {"accent": "#3a9d23", "grad": ["#aaaaaa"]}
    path = tmp_path / "palette.toml"
    palette.dump(p, path)
    assert palette.load(path) == p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_palette.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.palette'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/palette.py
"""A palette is a flat dict of role -> "#rrggbb", with ramp roles as lists.

Stored as TOML. Reading uses stdlib tomllib; writing uses a tiny serializer
(values are only strings or lists of strings) to avoid a write-side dependency.
"""
import tomllib
from pathlib import Path


def load(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return tomllib.loads(p.read_text())


def merge(base: dict, override: dict) -> dict:
    """Layer override on top of base; override keys win."""
    return {**base, **override}


def dump(palette: dict, path) -> None:
    lines = []
    for key, value in palette.items():
        if isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{items}]")
        else:
            lines.append(f'{key} = "{value}"')
    Path(path).write_text("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_palette.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/palette.py tests/test_palette.py
git commit -m "feat: palette load/merge/dump (TOML, stdlib-only)"
```

---

### Task 4: Manifest loading + validation

**Files:**
- Create: `src/adorn/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Produces:
  - `manifest.Target` dataclass: `name: str`, `output: Path`, `template: str | None`, `reload: str | None`
  - `manifest.Manifest` dataclass: `root: Path`, `templates_dir: Path`, `themes_dir: Path`, `extract_command: str`, `wallpaper_command: str | None`, `mood: dict`, `ramp: dict | None`, `hues: dict`, `targets: tuple[Target, ...]`
  - `manifest.load(path) -> Manifest`
  - `manifest.DEFAULT_EXTRACT: str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_manifest.py
from pathlib import Path

import pytest

from adorn import manifest

MANIFEST = """
[mood]
saturation_strength = 1.0
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 215, 175, 120, 40]

[wallpaper]
command = "swaymsg output '*' bg {path} fill"

[[target]]
name = "kitty"
template = "kitty.conf.tmpl"
output = "~/.config/kitty/colors.conf"
reload = "kitty @ set-colors --all ~/.config/kitty/colors.conf"
"""


def _write(tmp_path, text):
    p = tmp_path / "adorn.toml"
    p.write_text(text)
    return p


def test_load_parses_targets_and_sections(tmp_path):
    m = manifest.load(_write(tmp_path, MANIFEST))
    assert m.root == tmp_path
    assert m.templates_dir == tmp_path / "templates"
    assert m.themes_dir == tmp_path / "themes"
    assert m.ramp == {"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]}
    assert m.mood["bg_lightness"] == 0.07
    assert len(m.targets) == 1
    t = m.targets[0]
    assert t.name == "kitty"
    assert t.template == "kitty.conf.tmpl"
    assert t.reload.startswith("kitty @ set-colors")
    assert str(t.output) == str(Path.home() / ".config/kitty/colors.conf")


def test_extract_defaults_when_absent(tmp_path):
    m = manifest.load(_write(tmp_path, MANIFEST))
    assert m.extract_command == manifest.DEFAULT_EXTRACT
    assert "magick" in m.extract_command


def test_custom_extract_command(tmp_path):
    text = MANIFEST + '\n[extract]\ncommand = "wallust export {path}"\n'
    m = manifest.load(_write(tmp_path, text))
    assert m.extract_command == "wallust export {path}"


def test_no_targets_raises(tmp_path):
    with pytest.raises(ValueError, match="no .*target"):
        manifest.load(_write(tmp_path, "[mood]\nbg_lightness = 0.07\n"))


def test_target_missing_output_raises(tmp_path):
    text = '[[target]]\nname = "x"\ntemplate = "x.tmpl"\n'
    with pytest.raises(ValueError, match="output"):
        manifest.load(_write(tmp_path, text))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.manifest'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/manifest.py
"""Load and validate adorn.toml into typed Manifest/Target objects."""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXTRACT = (
    "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"
)


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p))


@dataclass(frozen=True)
class Target:
    name: str
    output: Path
    template: str | None = None
    reload: str | None = None


@dataclass(frozen=True)
class Manifest:
    root: Path
    templates_dir: Path
    themes_dir: Path
    extract_command: str
    wallpaper_command: str | None
    mood: dict
    ramp: dict | None
    hues: dict
    targets: tuple[Target, ...]


def load(path) -> Manifest:
    path = Path(path)
    data = tomllib.loads(path.read_text())
    root = path.parent

    raw_targets = data.get("target", [])
    if not raw_targets:
        raise ValueError("manifest defines no [[target]] entries")

    targets = []
    for t in raw_targets:
        if "name" not in t:
            raise ValueError(f"target missing name: {t!r}")
        if "output" not in t:
            raise ValueError(f"target {t['name']!r} missing output")
        targets.append(
            Target(
                name=t["name"],
                output=_expand(t["output"]),
                template=t.get("template"),
                reload=t.get("reload"),
            )
        )

    return Manifest(
        root=root,
        templates_dir=root / "templates",
        themes_dir=root / "themes",
        extract_command=data.get("extract", {}).get("command", DEFAULT_EXTRACT),
        wallpaper_command=data.get("wallpaper", {}).get("command"),
        mood=data.get("mood", {}),
        ramp=data.get("ramp"),
        hues=data.get("hues", {}),
        targets=tuple(targets),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manifest.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/manifest.py tests/test_manifest.py
git commit -m "feat: manifest loader (targets, mood/ramp/hues, pluggable extract)"
```

---

### Task 5: Theme catalog (directories + `current` symlink)

**Files:**
- Create: `src/adorn/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `catalog.ThemePaths` namedtuple: `dir, wallpaper, palette, overrides, files`
  - `catalog.list_themes(root) -> list[str]`
  - `catalog.current_theme(root) -> str | None`
  - `catalog.set_current(root, name) -> None`
  - `catalog.theme_paths(root, name) -> ThemePaths`
  - `catalog.new_theme_dir(root, name) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalog.py
import pytest

from adorn import catalog


def _mk(root, name):
    d = root / "themes" / name
    d.mkdir(parents=True)
    return d


def test_list_empty(tmp_path):
    assert catalog.list_themes(tmp_path) == []


def test_list_sorted(tmp_path):
    _mk(tmp_path, "oceanic")
    _mk(tmp_path, "succulents")
    assert catalog.list_themes(tmp_path) == ["oceanic", "succulents"]


def test_current_none_then_set_and_switch(tmp_path):
    _mk(tmp_path, "a")
    _mk(tmp_path, "b")
    assert catalog.current_theme(tmp_path) is None
    catalog.set_current(tmp_path, "a")
    assert catalog.current_theme(tmp_path) == "a"
    catalog.set_current(tmp_path, "b")
    assert catalog.current_theme(tmp_path) == "b"


def test_theme_paths(tmp_path):
    d = _mk(tmp_path, "x")
    (d / "wallpaper.jpg").write_bytes(b"")
    tp = catalog.theme_paths(tmp_path, "x")
    assert tp.dir == d
    assert tp.wallpaper == d / "wallpaper.jpg"
    assert tp.palette == d / "palette.toml"
    assert tp.overrides == d / "overrides.toml"
    assert tp.files == d / "files"


def test_new_theme_dir_creates_then_conflicts(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "fresh")
    assert d.is_dir()
    with pytest.raises(FileExistsError):
        catalog.new_theme_dir(tmp_path, "fresh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.catalog'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/catalog.py
"""Theme catalog: theme directories and the `current` symlink."""
import os
from collections import namedtuple
from pathlib import Path

ThemePaths = namedtuple("ThemePaths", "dir wallpaper palette overrides files")


def themes_dir(root) -> Path:
    return Path(root) / "themes"


def current_link(root) -> Path:
    return Path(root) / "current"


def list_themes(root) -> list[str]:
    d = themes_dir(root)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def current_theme(root):
    link = current_link(root)
    if link.is_symlink():
        return Path(os.readlink(link)).name
    return None


def set_current(root, name) -> None:
    link = current_link(root)
    target = themes_dir(root) / name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def theme_paths(root, name) -> ThemePaths:
    d = themes_dir(root) / name
    wallpaper = next(iter(sorted(d.glob("wallpaper.*"))), d / "wallpaper")
    return ThemePaths(
        dir=d,
        wallpaper=wallpaper,
        palette=d / "palette.toml",
        overrides=d / "overrides.toml",
        files=d / "files",
    )


def new_theme_dir(root, name) -> Path:
    d = themes_dir(root) / name
    d.mkdir(parents=True, exist_ok=False)
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_catalog.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/catalog.py tests/test_catalog.py
git commit -m "feat: theme catalog (list/current/set_current/theme_paths)"
```

---

### Task 6: Extraction (run command, parse hex)

**Files:**
- Create: `src/adorn/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `manifest.DEFAULT_EXTRACT` (the default command string).
- Produces: `extract.extract(command: str, wallpaper) -> list[str]` (lowercase `#rrggbb`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract.py
import subprocess

import pytest

from adorn import extract
from adorn.manifest import DEFAULT_EXTRACT


def test_parses_hex_from_command_output(tmp_path):
    # command ignores {path} and prints two colors
    cmd = "printf '12: (1,2,3) #AABBCC\\n34: (4,5,6) #DDEEFF\\n'"
    cmd_with_path = cmd + " # {path}"
    colors = extract.extract(cmd_with_path, tmp_path / "img.png")
    assert colors == ["#aabbcc", "#ddeeff"]


def test_substitutes_path(tmp_path):
    cmd = "echo {path}"  # echoes the path; no hex -> should raise
    with pytest.raises(ValueError, match="no colors"):
        extract.extract(cmd, tmp_path / "abc.png")


def test_real_imagemagick_on_solid_image(tmp_path):
    img = tmp_path / "solid.png"
    subprocess.run(
        f"magick -size 16x16 xc:#3a9d23 {img}", shell=True, check=True
    )
    colors = extract.extract(DEFAULT_EXTRACT, img)
    assert "#3a9d23" in colors


def test_path_with_shell_metachars_does_not_inject(tmp_path):
    # a filename that would run `touch PWNED` if the path were not quoted
    sentinel = tmp_path / "PWNED"
    evil = tmp_path / f"a; touch {sentinel} #.png"
    with pytest.raises(ValueError):  # echo emits no hex
        extract.extract("echo {path}", evil)
    assert not sentinel.exists()  # injection did NOT execute
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.extract'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/extract.py
"""Run the manifest's extract command and parse #rrggbb colors from stdout."""
import re
import shlex
import subprocess

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def extract(command: str, wallpaper) -> list[str]:
    cmd = command.format(path=shlex.quote(str(wallpaper)))
    out = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout
    colors = [m.group(0).lower() for m in _HEX_RE.finditer(out)]
    if not colors:
        raise ValueError(f"extract command produced no colors: {cmd!r}")
    return colors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_extract.py -v`
Expected: PASS (3 passed). If the IM test fails, confirm `magick -version`.

- [ ] **Step 5: Commit**

```bash
git add src/adorn/extract.py tests/test_extract.py
git commit -m "feat: pluggable extraction (run command, parse #rrggbb)"
```

---

### Task 7: Compile — the semantic algorithm

**Files:**
- Create: `src/adorn/compile.py`
- Test: `tests/test_compile.py`

**Interfaces:**
- Consumes: `color.*`, `extract.extract`, `palette.dump`, `catalog.theme_paths`, a `Manifest`.
- Produces:
  - `compile.DEFAULT_HUES: dict`, `compile.HUE_LIGHTNESS: float`
  - `compile.mood_saturation(raw: list[str]) -> float`
  - `compile.build_palette(raw: list[str], manifest) -> dict`
  - `compile.compile_theme(root, name, manifest) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compile.py
import subprocess
import types

from adorn import catalog, color, compile as compile_mod
from adorn.manifest import DEFAULT_EXTRACT


def fake_manifest(**over):
    base = dict(
        root=None, templates_dir=None, themes_dir=None,
        extract_command=DEFAULT_EXTRACT, wallpaper_command=None,
        mood={"saturation_strength": 1.0, "bg_lightness": 0.07},
        ramp={"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]},
        hues={}, targets=(),
    )
    base.update(over)
    return types.SimpleNamespace(**base)


def approx(a, b, tol):
    return abs(a - b) <= tol


RAW = ["#2d2d30", "#9b9e61", "#403f3c", "#595b57"]  # green is most saturated


def test_accent_is_most_saturated_raw():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert p["accent"] == "#9b9e61"


def test_background_is_very_dark():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert color.hsl(p["bg"])[2] < 0.15


def test_hue_roles_anchored():
    p = compile_mod.build_palette(RAW, fake_manifest())
    red_h = color.hsl(p["red"])[0]
    assert red_h < 10 or red_h > 350
    assert approx(color.hsl(p["green"])[0], 120, 8)
    assert approx(color.hsl(p["blue"])[0], 215, 8)


def test_semantic_aliases_and_ramp():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert p["urgent"] == p["red"]
    assert p["success"] == p["green"]
    assert p["warning"] == p["yellow"]
    assert isinstance(p["grad"], list) and len(p["grad"]) == 7


def test_custom_hue_override():
    p = compile_mod.build_palette(RAW, fake_manifest(hues={"red": 10}))
    assert approx(color.hsl(p["red"])[0], 10, 8)


def test_compile_theme_writes_palette(tmp_path):
    # build a minimal catalog with a real solid wallpaper
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    m = fake_manifest()
    p = compile_mod.compile_theme(tmp_path, "t", m)
    assert (d / "palette.toml").exists()
    assert "accent" in p and "bg" in p and "grad" in p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_compile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.compile'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/compile.py
"""The semantic algorithm: raw extracted colors -> a role palette.

Hue roles are anchored to canonical angles with saturation borrowed from the
wallpaper's "mood" (average saturation). `accent` is the most-saturated raw
color (the wallpaper's signature). `bg` is pinned near-black, tinted by the
dominant hue.
"""
from . import catalog, color
from . import extract as extract_mod
from . import palette as palette_mod

DEFAULT_HUES = {
    "red": 0,
    "yellow": 50,
    "green": 120,
    "cyan": 175,
    "blue": 215,
    "magenta": 300,
}
HUE_LIGHTNESS = 0.62  # legibility target for the 6 hue roles on a dark bg


def mood_saturation(raw: list[str]) -> float:
    sats = [color.hsl(c)[1] for c in raw]
    return sum(sats) / len(sats)


def build_palette(raw: list[str], manifest) -> dict:
    hues = {**DEFAULT_HUES, **manifest.hues}
    strength = manifest.mood.get("saturation_strength", 1.0)
    bg_l = manifest.mood.get("bg_lightness", 0.07)

    sat = min(1.0, mood_saturation(raw) * strength)
    accent = max(raw, key=lambda c: color.hsl(c)[1])
    dom_h = color.hsl(accent)[0]

    pal: dict = {}
    pal["bg"] = color.make_hsl(dom_h, 0.06, bg_l)
    pal["bg_alt"] = color.lighten(pal["bg"], 0.04)
    pal["bg_highlight"] = color.lighten(pal["bg"], 0.10)
    pal["bg_visual"] = color.lighten(pal["bg"], 0.14)
    pal["fg"] = color.make_hsl(dom_h, 0.08, 0.82)
    pal["fg_dim"] = color.make_hsl(dom_h, 0.06, 0.60)
    pal["muted"] = color.make_hsl(dom_h, 0.05, 0.45)
    pal["comment"] = pal["muted"]
    pal["accent"] = accent

    for role, h in hues.items():
        pal[role] = color.make_hsl(h, sat, HUE_LIGHTNESS)
    pal["urgent"] = pal["red"]
    pal["success"] = pal["green"]
    pal["warning"] = pal["yellow"]

    ramp = manifest.ramp
    if ramp:
        stops = [color.make_hsl(h, sat, HUE_LIGHTNESS) for h in ramp["hues"]]
        pal[ramp["name"]] = color.gradient(stops, ramp["length"])

    return pal


def compile_theme(root, name, manifest) -> dict:
    tp = catalog.theme_paths(root, name)
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    pal = build_palette(raw, manifest)
    palette_mod.dump(pal, tp.palette)
    return pal
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_compile.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/compile.py tests/test_compile.py
git commit -m "feat: semantic palette compile (hue-anchored, theme-tinted)"
```

---

### Task 8: Render (Jinja2 + verbatim files + atomic write)

**Files:**
- Create: `src/adorn/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: a `Manifest` (uses `templates_dir`, `targets`), a palette dict, a `files_dir` path.
- Produces:
  - `render.make_env(templates_dir) -> jinja2.Environment`
  - `render.render_all(manifest, palette: dict, files_dir) -> dict[Path, str]`
  - `render.write_all(outputs: dict) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
import types
from pathlib import Path

import jinja2
import pytest

from adorn import render
from adorn.manifest import Target


def manifest_with(tmp_path, targets):
    (tmp_path / "templates").mkdir(exist_ok=True)
    return types.SimpleNamespace(
        templates_dir=tmp_path / "templates", targets=tuple(targets)
    )


def test_renders_template_with_palette(tmp_path):
    (tmp_path / "templates" / "kitty.conf.tmpl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "kitty.conf.tmpl").write_text("background {{ bg }}\n")
    out = tmp_path / "out" / "colors.conf"
    m = manifest_with(tmp_path, [Target("kitty", out, "kitty.conf.tmpl", None)])
    outputs = render.render_all(m, {"bg": "#111111"}, tmp_path / "files")
    assert outputs[out] == "background #111111\n"


def test_ramp_list_indexing(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "g.tmpl").write_text("{{ grad[0] }}|{{ grad[1] }}")
    out = tmp_path / "g.out"
    m = manifest_with(tmp_path, [Target("g", out, "g.tmpl", None)])
    outputs = render.render_all(m, {"grad": ["#aaaaaa", "#bbbbbb"]}, tmp_path / "files")
    assert outputs[out] == "#aaaaaa|#bbbbbb"


def test_missing_role_raises(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "x.tmpl").write_text("{{ missing }}")
    m = manifest_with(tmp_path, [Target("x", tmp_path / "x.out", "x.tmpl", None)])
    with pytest.raises(jinja2.UndefinedError):
        render.render_all(m, {"bg": "#111111"}, tmp_path / "files")


def test_files_override_used_verbatim(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "wofi.tmpl").write_text("TEMPLATED {{ bg }}")
    override_dir = tmp_path / "files" / "wofi"
    override_dir.mkdir(parents=True)
    (override_dir / "style.css").write_text("VERBATIM CONTENT")
    out = tmp_path / "wofi.out"
    m = manifest_with(tmp_path, [Target("wofi", out, "wofi.tmpl", None)])
    outputs = render.render_all(m, {"bg": "#111111"}, tmp_path / "files")
    assert outputs[out] == "VERBATIM CONTENT"


def test_write_all_creates_dirs_and_files(tmp_path):
    out = tmp_path / "deep" / "nested" / "colors.conf"
    render.write_all({out: "hello\n"})
    assert out.read_text() == "hello\n"


def test_no_template_no_override_raises(tmp_path):
    m = manifest_with(tmp_path, [Target("bad", tmp_path / "b.out", None, None)])
    with pytest.raises(ValueError, match="no template"):
        render.render_all(m, {}, tmp_path / "files")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.render'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/render.py
"""Render targets to outputs (Jinja2 or verbatim files/), then write atomically."""
import os
from pathlib import Path

import jinja2


def make_env(templates_dir) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


def render_all(manifest, palette: dict, files_dir) -> dict:
    """Return {output_path: content} for every target. Raises before any write."""
    env = make_env(manifest.templates_dir)
    outputs: dict = {}
    for target in manifest.targets:
        override = Path(files_dir) / target.name
        if override.is_dir():
            inner = next((p for p in sorted(override.iterdir()) if p.is_file()), None)
            if inner is None:
                raise ValueError(f"files/{target.name}/ exists but is empty")
            outputs[target.output] = inner.read_text()
        elif target.template:
            outputs[target.output] = env.get_template(target.template).render(**palette)
        else:
            raise ValueError(
                f"target {target.name!r} has no template and no files/ override"
            )
    return outputs


def write_all(outputs: dict) -> None:
    """Write each output atomically (temp file + os.replace)."""
    for path, content in outputs.items():
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".adorn-tmp")
        tmp.write_text(content)
        os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/render.py tests/test_render.py
git commit -m "feat: render (Jinja2 strict, files/ override, atomic write)"
```

---

### Task 9: Reload hooks + wallpaper

**Files:**
- Create: `src/adorn/reload.py`
- Test: `tests/test_reload.py`

**Interfaces:**
- Consumes: a `Manifest` (uses `targets`, `wallpaper_command`), `Target.reload`.
- Produces:
  - `reload.run_reload(target) -> None`
  - `reload.run_reloads(manifest) -> None`
  - `reload.set_wallpaper(manifest, wallpaper_path) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reload.py
import types

from adorn import reload as reload_mod
from adorn.manifest import Target


def test_run_reload_executes_command(tmp_path):
    marker = tmp_path / "reloaded"
    t = Target("x", tmp_path / "out", None, f"touch {marker}")
    reload_mod.run_reload(t)
    assert marker.exists()


def test_run_reload_none_is_noop(tmp_path):
    reload_mod.run_reload(Target("x", tmp_path / "out", None, None))  # no error


def test_run_reloads_all(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    m = types.SimpleNamespace(
        targets=(
            Target("a", tmp_path / "oa", None, f"touch {a}"),
            Target("b", tmp_path / "ob", None, f"touch {b}"),
        )
    )
    reload_mod.run_reloads(m)
    assert a.exists() and b.exists()


def test_set_wallpaper_substitutes_path(tmp_path):
    rec = tmp_path / "rec"
    m = types.SimpleNamespace(wallpaper_command=f"echo {{path}} > {rec}")
    reload_mod.set_wallpaper(m, tmp_path / "wall.jpg")
    assert str(tmp_path / "wall.jpg") in rec.read_text()


def test_set_wallpaper_none_is_noop():
    m = types.SimpleNamespace(wallpaper_command=None)
    reload_mod.set_wallpaper(m, "/whatever.jpg")  # no error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reload.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adorn.reload'`.

- [ ] **Step 3: Write the implementation**

```python
# src/adorn/reload.py
"""Run target reload hooks and set the wallpaper."""
import shlex
import subprocess


def run_reload(target) -> None:
    if target.reload:
        subprocess.run(target.reload, shell=True, check=False)


def run_reloads(manifest) -> None:
    for target in manifest.targets:
        run_reload(target)


def set_wallpaper(manifest, wallpaper_path) -> None:
    if manifest.wallpaper_command:
        cmd = manifest.wallpaper_command.format(path=shlex.quote(str(wallpaper_path)))
        subprocess.run(cmd, shell=True, check=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_reload.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/reload.py tests/test_reload.py
git commit -m "feat: reload hooks + wallpaper command"
```

---

### Task 10: Commands + CLI wiring + end-to-end test

**Files:**
- Create: `src/adorn/commands.py`
- Modify: `src/adorn/cli.py` (replace the stub `main` with full subcommands)
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `commands.effective_palette(root, name) -> dict`
  - `commands.cmd_list/cmd_current/cmd_apply/cmd_recompile/cmd_preview(root, ...) -> None`
  - `commands.cmd_new(root, name, wallpaper, do_apply=True) -> None`
  - `cli.main(argv=None) -> int` dispatching `list/current/apply/new/recompile/preview` with a `--root` option (default `~/.config/adorn`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commands.py
import subprocess

from adorn import catalog, cli, commands, palette


def build_catalog(root):
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "kitty.conf.tmpl").write_text(
        "background {{ bg }}\naccent {{ accent }}\n"
    )
    marker = root / "reloaded"
    (root / "adorn.toml").write_text(
        f"""
[mood]
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 215, 175, 120, 40]

[wallpaper]
command = "true {{path}}"

[[target]]
name = "kitty"
template = "kitty.conf.tmpl"
output = "{root / 'kitty-colors.conf'}"
reload = "touch {marker}"
"""
    )
    return marker


def make_wallpaper(path):
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {path}", shell=True, check=True)


def test_new_compiles_and_applies(tmp_path):
    marker = build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp))

    tp = catalog.theme_paths(tmp_path, "test")
    assert tp.palette.exists()
    assert tp.overrides.exists()
    out = (tmp_path / "kitty-colors.conf").read_text()
    assert out.startswith("background #")
    assert catalog.current_theme(tmp_path) == "test"
    assert marker.exists()


def test_overrides_win_on_apply(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp), do_apply=True)
    # pin bg via overrides, re-apply
    tp = catalog.theme_paths(tmp_path, "test")
    palette.dump({"bg": "#000000"}, tp.overrides)
    commands.cmd_apply(tmp_path, "test")
    assert "background #000000" in (tmp_path / "kitty-colors.conf").read_text()


def test_effective_palette_merges(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp), do_apply=False)
    tp = catalog.theme_paths(tmp_path, "test")
    palette.dump({"bg": "#000000"}, tp.overrides)
    eff = commands.effective_palette(tmp_path, "test")
    assert eff["bg"] == "#000000"
    assert "accent" in eff


def test_cli_list_and_current(tmp_path, capsys):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "test", str(wp), "--no-apply"])
    cli.main(["--root", str(tmp_path), "apply", "test"])
    capsys.readouterr()
    cli.main(["--root", str(tmp_path), "list"])
    assert "* test" in capsys.readouterr().out
    cli.main(["--root", str(tmp_path), "current"])
    assert "test" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_commands.py -v`
Expected: FAIL — `ImportError: cannot import name 'commands'` (module absent).

- [ ] **Step 3: Write `commands.py`**

```python
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
    compile_mod.compile_theme(root, name, manifest)
    (theme_dir / "overrides.toml").write_text("# per-theme color/role overrides\n")
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
```

- [ ] **Step 4: Replace `cli.py` with full subcommand dispatch**

```python
# src/adorn/cli.py
"""adorn command-line entry point."""
import argparse
import os
from pathlib import Path

from . import __version__, commands

DEFAULT_ROOT = Path(os.path.expanduser("~/.config/adorn"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="adorn",
        description="Automated Desktop Ornamentation & Recoloring eNgine",
    )
    parser.add_argument("--root", help="catalog root (default ~/.config/adorn)")
    parser.add_argument("--version", action="version", version=f"adorn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list themes")
    sub.add_parser("current", help="show active theme")
    p_apply = sub.add_parser("apply", help="apply a theme")
    p_apply.add_argument("name")
    p_new = sub.add_parser("new", help="create a theme from a wallpaper")
    p_new.add_argument("name")
    p_new.add_argument("wallpaper")
    p_new.add_argument("--no-apply", action="store_true")
    p_recompile = sub.add_parser("recompile", help="recompile palette from wallpaper")
    p_recompile.add_argument("name")
    p_preview = sub.add_parser("preview", help="print a theme's palette as swatches")
    p_preview.add_argument("name")

    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else DEFAULT_ROOT

    if args.command == "list":
        commands.cmd_list(root)
    elif args.command == "current":
        commands.cmd_current(root)
    elif args.command == "apply":
        commands.cmd_apply(root, args.name)
    elif args.command == "new":
        commands.cmd_new(root, args.name, args.wallpaper, do_apply=not args.no_apply)
    elif args.command == "recompile":
        commands.cmd_recompile(root, args.name)
    elif args.command == "preview":
        commands.cmd_preview(root, args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the full suite to verify everything passes**

Run: `.venv/bin/pytest -v`
Expected: PASS — all tests across every module (smoke, color, palette, manifest, catalog, extract, compile, render, reload, commands).

Then update the smoke test, which previously ran `--version` with no subcommand. The new parser requires a subcommand, but `--version` short-circuits via argparse's version action before the subparser is evaluated, so `test_cli_version_runs` still passes — confirm it does in the run above.

- [ ] **Step 6: Commit**

```bash
git add src/adorn/commands.py src/adorn/cli.py tests/test_commands.py
git commit -m "feat: commands + CLI (list/current/apply/new/recompile/preview)"
```

---

## Self-Review

**Spec coverage:**
- Engine/content split → Tasks 4 (manifest) + 5 (catalog): app-specifics come only from manifest + catalog. ✓
- Pluggable extraction (default ImageMagick) → Task 6, default in Task 4. ✓
- Semantic algorithm (hue-anchored, accent image-derived, bg pinned-dark, ramp) → Task 7. ✓
- Color fragments via templates → Task 8 (render). ✓
- Palette + overrides merge → Tasks 3 + 10 (`effective_palette`). ✓
- `files/` verbatim escape hatch → Task 8. ✓
- Atomic apply → Task 8 (`write_all`) + Task 10 (`cmd_apply` renders all before writing). ✓
- Reload + wallpaper → Task 9. ✓
- Command set (list/new/apply/current/preview/recompile) → Task 10. ✓
- `palette.toml` committed/reused, recompile explicit → Task 7 writes it; `cmd_apply` reads it without recompiling; `cmd_recompile` is the only recompiler. ✓
- Tested against fakes, no dependency on real configs → all tests build temp catalogs/manifests. ✓

*Not in this plan (by design):* nvim's external `palette.lua` path, the `succulents` theme, and wiring real configs to `include` fragments are **rice integration**, covered by a follow-up plan per the spec's build order. The engine renders nvim exactly like any other target (a template → output path); only the *content* of that template and the consuming config live in the rice plan.

**Placeholder scan:** No TBD/TODO; every code and test step contains complete, runnable content. ✓

**Type consistency:** `Manifest`/`Target` field names match across manifest, render, reload, compile, commands. Palette is a plain `dict` everywhere. `theme_paths` field names (`dir/wallpaper/palette/overrides/files`) are used consistently in compile + commands. `effective_palette`, `build_palette`, `compile_theme`, `render_all`, `write_all`, `run_reloads`, `set_wallpaper` names match their call sites. ✓
