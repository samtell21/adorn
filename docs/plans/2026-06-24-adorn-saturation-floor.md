# adorn — Saturation Floor + Compile Stats (Plan Addendum)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. This addendum continues the engine plan (`2026-06-24-adorn-engine.md`); it assumes Tasks 1–10 are complete on branch `feat/engine`.

**Goal:** Add a per-generation saturation knob (a floor on the hue roles + ramp, default 0.0 = pure mood) and a compile-stats printout, both discovered necessary via real-wallpaper testing.

**Architecture:** `build_palette` clamps hue saturation to a floor; `compile_theme` returns a `CompileResult` (palette + stats); `cmd_new`/`cmd_recompile` accept a `saturation_floor` override and print a stats block; the CLI exposes `--saturation`.

**Tech Stack:** unchanged (Python ≥3.11, jinja2, pastel, magick).

## Global Constraints

- Python ≥ 3.11. Src layout `src/adorn/`, tests `tests/`. Color values lowercase `#rrggbb`.
- TDD: failing test first, then implement, then pass. Run with `.venv/bin/pytest`.
- Default behavior MUST be unchanged: floor `0.0` ⇒ `clamp(x, 0.0, 1.0)` ≡ the previous `min(1.0, x)`. Existing tests must keep passing.
- Commit messages: `feat:`/`test:`; no co-author trailer.

---

### Task 11: Saturation floor knob, CompileResult stats, `--saturation` flag

**Files:**
- Modify: `src/adorn/compile.py` (build_palette signature + clamp; compile_theme returns CompileResult; add CompileResult + format_stats)
- Modify: `src/adorn/commands.py` (cmd_new/cmd_recompile accept `saturation_floor`, print stats)
- Modify: `src/adorn/cli.py` (`--saturation` on new/recompile)
- Modify: `tests/test_compile.py` (update the existing `test_compile_theme_writes_palette` for the new return type)
- Test: `tests/test_saturation.py` (new)
- Test: `tests/test_commands.py` (add a saturation + stats integration test)

**Interfaces:**
- Produces:
  - `compile.CompileResult` dataclass: `palette: dict`, `raw: list[str]`, `mood_saturation: float`, `saturation_floor: float`, `strength: float`, `effective_saturation: float`, `wallpaper: str`
  - `compile.build_palette(raw, manifest, *, saturation_floor=None) -> dict`
  - `compile.compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult`
  - `compile.format_stats(name: str, result: CompileResult) -> str`
  - `commands.cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None)`
  - `commands.cmd_recompile(root, name, saturation_floor=None)`
  - `cli`: `new`/`recompile` accept `--saturation FLOAT`

- [ ] **Step 1: Write the failing tests (`tests/test_saturation.py`)**

```python
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


# RAW is a muted set: avg saturation is low, so floor 0 stays muted.
RAW = ["#2d2d30", "#9b9e61", "#403f3c", "#595b57"]


def test_floor_zero_is_pure_mood():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.0)
    assert color.hsl(p["red"])[1] < 0.25  # stays muted at floor 0


def test_floor_lifts_hue_saturation():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    for role in ("red", "green", "blue", "yellow", "cyan", "magenta"):
        assert color.hsl(p[role])[1] >= 0.45, f"{role} not lifted to floor"


def test_floor_lifts_ramp_too():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    assert all(color.hsl(c)[1] >= 0.45 for c in p["grad"])


def test_floor_does_not_touch_accent():
    # accent is the most-saturated raw color, passed through unchanged
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    assert p["accent"] == "#9b9e61"


def test_manifest_floor_used_when_no_override():
    m = fake_manifest(mood={"saturation_strength": 1.0, "bg_lightness": 0.07,
                            "hue_saturation_floor": 0.4})
    p = compile_mod.build_palette(RAW, m)  # no explicit override
    assert color.hsl(p["red"])[1] >= 0.35


def test_explicit_override_beats_manifest():
    m = fake_manifest(mood={"saturation_strength": 1.0, "bg_lightness": 0.07,
                            "hue_saturation_floor": 0.2})
    p = compile_mod.build_palette(RAW, m, saturation_floor=0.6)
    assert color.hsl(p["red"])[1] >= 0.55


def test_compile_theme_returns_result_with_stats(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    result = compile_mod.compile_theme(tmp_path, "t", fake_manifest(), saturation_floor=0.5)
    assert (d / "palette.toml").exists()
    assert "accent" in result.palette
    assert result.saturation_floor == 0.5
    assert result.effective_saturation >= 0.5
    assert len(result.raw) >= 1
    assert 0.0 <= result.mood_saturation <= 1.0


def test_format_stats_contains_key_fields():
    result = compile_mod.CompileResult(
        palette={"accent": "#9b9e61", "bg": "#131311", "fg": "#d4d5cd",
                 "red": "#cc6666", "yellow": "#ccbb66", "green": "#66cc66",
                 "blue": "#6691cc", "cyan": "#66ccc3", "magenta": "#cc66cc"},
        raw=["#9b9e61", "#2d2d30"], mood_saturation=0.11, saturation_floor=0.30,
        strength=1.0, effective_saturation=0.30, wallpaper="/x/wall.png",
    )
    s = compile_mod.format_stats("succ", result)
    assert "succ" in s
    assert "/x/wall.png" in s
    assert "mood sat" in s and "0.11" in s
    assert "sat floor" in s and "0.30" in s
    assert "hue sat" in s
    assert "#9b9e61" in s  # accent shown
    assert "red" in s and "#cc6666" in s
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_saturation.py -v`
Expected: FAIL — `build_palette()` has no `saturation_floor` kwarg / `CompileResult`/`format_stats` undefined / `compile_theme` returns a dict not a result.

- [ ] **Step 3: Update `src/adorn/compile.py`**

Add the import at the top (with the existing imports):
```python
from dataclasses import dataclass
```

Add the dataclass after the constants (`HUE_LIGHTNESS = 0.62`):
```python
@dataclass
class CompileResult:
    palette: dict
    raw: list[str]
    mood_saturation: float
    saturation_floor: float
    strength: float
    effective_saturation: float
    wallpaper: str
```

Change `build_palette` to accept the floor and clamp. Replace its current signature and the saturation line:
```python
def build_palette(raw: list[str], manifest, *, saturation_floor=None) -> dict:
    if not raw:
        raise ValueError("build_palette requires at least one raw color")
    hues = {**DEFAULT_HUES, **manifest.hues}
    strength = manifest.mood.get("saturation_strength", 1.0)
    bg_l = manifest.mood.get("bg_lightness", 0.07)
    if saturation_floor is None:
        saturation_floor = manifest.mood.get("hue_saturation_floor", 0.0)

    sat = max(saturation_floor, min(1.0, mood_saturation(raw) * strength))
    ...
```
(Everything below the `sat = ...` line is unchanged — accent, bg/fg derivation, the hue loop, aliases, ramp.)

Replace `compile_theme` with the result-returning version:
```python
def compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult:
    tp = catalog.theme_paths(root, name)
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    strength = manifest.mood.get("saturation_strength", 1.0)
    if saturation_floor is None:
        saturation_floor = manifest.mood.get("hue_saturation_floor", 0.0)
    mood_sat = mood_saturation(raw)
    effective = max(saturation_floor, min(1.0, mood_sat * strength))
    pal = build_palette(raw, manifest, saturation_floor=saturation_floor)
    palette_mod.dump(pal, tp.palette)
    return CompileResult(
        palette=pal, raw=raw, mood_saturation=mood_sat,
        saturation_floor=saturation_floor, strength=strength,
        effective_saturation=effective, wallpaper=str(tp.wallpaper),
    )
```

Add `format_stats` at the end of the module:
```python
def format_stats(name: str, result: CompileResult) -> str:
    def hsl_str(hexv):
        h, s, l = color.hsl(hexv)
        return f"H{h:.0f} S{s * 100:.0f}% L{l * 100:.0f}%"

    p = result.palette
    return "\n".join([
        f"✓ compiled '{name}'",
        f"  wallpaper   {result.wallpaper}",
        f"  raw colors  {len(result.raw)} extracted",
        f"  mood sat    {result.mood_saturation:.2f}   (avg saturation of the wallpaper)",
        f"  sat floor   {result.saturation_floor:.2f}   (--saturation)",
        f"  hue sat     {result.effective_saturation:.2f}   (effective = clamp(mood*strength, floor, 1.0))",
        f"  accent      {p['accent']}   {hsl_str(p['accent'])}   (image-derived)",
        f"  bg {p['bg']}   fg {p['fg']}",
        f"  red {p['red']}  yellow {p['yellow']}  green {p['green']}",
        f"  blue {p['blue']}  cyan {p['cyan']}  magenta {p['magenta']}",
    ])
```

- [ ] **Step 4: Update `tests/test_compile.py` for the new `compile_theme` return type**

The existing `test_compile_theme_writes_palette` does `p = compile_mod.compile_theme(...)` then `assert "accent" in p and "bg" in p and "grad" in p`. Change it to use `.palette`:
```python
def test_compile_theme_writes_palette(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    m = fake_manifest()
    result = compile_mod.compile_theme(tmp_path, "t", m)
    assert (d / "palette.toml").exists()
    assert "accent" in result.palette and "bg" in result.palette and "grad" in result.palette
```
(Leave all other tests in the file unchanged — `build_palette` still returns a dict and floor defaults to 0.0, so they pass as-is.)

- [ ] **Step 5: Update `src/adorn/commands.py`**

`cmd_new` and `cmd_recompile` gain a `saturation_floor` param, capture the result, and print stats:
```python
def cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None) -> None:
    manifest = load_manifest(root)
    theme_dir = catalog.new_theme_dir(root, name)
    dest = theme_dir / ("wallpaper" + Path(wallpaper).suffix)
    shutil.copy(wallpaper, dest)
    (theme_dir / "overrides.toml").write_text(
        "# per-theme color/role overrides\n", encoding="utf-8"
    )
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    print(compile_mod.format_stats(name, result))
    if do_apply:
        cmd_apply(root, name)


def cmd_recompile(root, name, saturation_floor=None) -> None:
    manifest = load_manifest(root)
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    print(compile_mod.format_stats(name, result))
```
(`cmd_apply` is unchanged — it reads the palette from disk via `effective_palette`, independent of `compile_theme`'s return.)

- [ ] **Step 6: Update `src/adorn/cli.py`**

Add `--saturation` to the `new` and `recompile` subparsers and thread it through. In the parser setup:
```python
    p_new = sub.add_parser("new", help="create a theme from a wallpaper")
    p_new.add_argument("name")
    p_new.add_argument("wallpaper")
    p_new.add_argument("--no-apply", action="store_true")
    p_new.add_argument("--saturation", type=float, default=None,
                       help="hue saturation floor 0..1 (default: manifest [mood] or 0.0)")
    p_recompile = sub.add_parser("recompile", help="recompile palette from wallpaper")
    p_recompile.add_argument("name")
    p_recompile.add_argument("--saturation", type=float, default=None,
                             help="hue saturation floor 0..1")
```
And in dispatch:
```python
    elif args.command == "new":
        commands.cmd_new(root, args.name, args.wallpaper,
                         do_apply=not args.no_apply, saturation_floor=args.saturation)
    elif args.command == "recompile":
        commands.cmd_recompile(root, args.name, saturation_floor=args.saturation)
```

- [ ] **Step 7: Add a commands integration test (`tests/test_commands.py`)**

Append (the file already has `build_catalog`, `make_wallpaper`, imports `cli`, `commands`, `catalog`, `palette`):
```python
def test_new_with_saturation_floor_and_stats(tmp_path, capsys):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "pop", str(wp), saturation_floor=0.5)
    out = capsys.readouterr().out
    assert "compiled 'pop'" in out
    assert "sat floor   0.50" in out
    # the floor lifted the hue roles in the saved palette
    from adorn import color
    pal = palette.load(catalog.theme_paths(tmp_path, "pop").palette)
    assert color.hsl(pal["red"])[1] >= 0.45


def test_cli_new_saturation_flag(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "v", str(wp), "--no-apply", "--saturation", "0.4"])
    from adorn import color
    pal = palette.load(catalog.theme_paths(tmp_path, "v").palette)
    assert color.hsl(pal["red"])[1] >= 0.35
```

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: PASS — all prior tests (54) plus the new saturation + commands tests, and the updated `test_compile_theme_writes_palette`. No regressions.

- [ ] **Step 9: Manual smoke (real wallpaper, two variants)**

Run (verifies stats output + that the floor visibly changes saturation):
```bash
DEMO=/tmp/claude-1000/-home-samtell-rice/189b0989-c976-495e-a9aa-a18ac4f2ae38/scratchpad/adorn-demo
rm -rf "$DEMO/themes" "$DEMO/current"
.venv/bin/adorn --root "$DEMO" new succ      /home/samtell/Pictures/Wallpapers/succulents.jpg --no-apply
.venv/bin/adorn --root "$DEMO" new succ-pop  /home/samtell/Pictures/Wallpapers/succulents.jpg --no-apply --saturation 0.4
```
Expected: each prints a stats block; `succ` shows `sat floor 0.00`, `succ-pop` shows `sat floor 0.40` with a higher `hue sat`.

- [ ] **Step 10: Commit**

```bash
git add src/adorn/compile.py src/adorn/commands.py src/adorn/cli.py tests/test_saturation.py tests/test_compile.py tests/test_commands.py
git commit -m "feat: saturation floor knob + --saturation flag + compile stats"
```

## Self-Review

- Floor knob (default 0.0, manifest + per-generation override) → Steps 3,5,6; tested Step 1. ✓
- Default behavior unchanged (floor 0 ≡ old min) → `test_floor_zero_is_pure_mood` + existing tests pass. ✓
- Accent/bg/fg untouched by floor → `test_floor_does_not_touch_accent`. ✓
- Ramp also floored → `test_floor_lifts_ramp_too`. ✓
- Stats printout on new/recompile → Steps 3,5; tested `test_format_stats_contains_key_fields`, `test_new_with_saturation_floor_and_stats`. ✓
- CLI `--saturation` → Step 6; tested `test_cli_new_saturation_flag`. ✓
- No placeholders; all code complete. Types consistent: `CompileResult` fields used identically in compile_theme, format_stats, and tests.
