# adorn — Per-scheme color definitions (Plan Addendum)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Assumes Tasks 1–19 complete on `feat/engine` (91 tests).

**Goal:** Move the color-derivation config (`[mood]`/`[ramp]`/`[hues]`) out of the global manifest and into per-scheme `schemes/<scheme>/scheme.toml`, plus a `[fixed]` section for roles pinned to a literal hex. A scheme becomes a full color *system*; a theme instantiates it via its wallpaper. The `default` scheme carries today's values.

## Global Constraints
- Python ≥ 3.11. Src layout. `encoding="utf-8"`. TDD; `.venv/bin/pytest`. Commit `feat:`/`refactor:`, no co-author trailer.
- `default` scheme reproduces current behavior exactly.

---

### Task 20: scheme-owned color derivation

**Files:**
- Modify: `src/adorn/manifest.py` (drop `mood`/`ramp`/`hues` from `Manifest`)
- Modify: `src/adorn/catalog.py` (add `theme_scheme(theme_paths) -> str`)
- Modify: `src/adorn/compile.py` (`load_scheme_config`; `build_palette(raw, scheme_config, …)`; `compile_theme` resolves scheme config; `[fixed]` overlay)
- Modify: `src/adorn/commands.py` (`render_theme` uses `catalog.theme_scheme`; remove the old `theme_scheme` here)
- Modify tests: `test_manifest.py`, `test_compile.py`, `test_saturation.py`, `test_commands.py`

**Interfaces:**
- `manifest.Manifest(root, schemes_dir, themes_dir, extract_command, wallpaper_command, targets)` (no mood/ramp/hues)
- `catalog.theme_scheme(theme_paths) -> str` (reads `theme.toml` `scheme`, default `"default"`)
- `compile.load_scheme_config(scheme_dir) -> dict` (reads `scheme.toml`; `{}` if absent)
- `compile.build_palette(raw, scheme_config: dict, *, saturation_floor=None) -> dict` — reads `scheme_config["mood"|"ramp"|"hues"|"fixed"]`; `[fixed]` roles overlay the derived palette
- `compile.compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult` (resolves the theme's scheme config)

- [ ] **Step 1: Tests first (RED).**

`test_saturation.py` / `test_compile.py`: replace the `fake_manifest(**over)` helper with a scheme-config dict builder, and update every `build_palette(RAW, fake_manifest(...))` call to pass a config dict:
```python
def fake_scheme(**over):
    cfg = {
        "mood": {"saturation_strength": 1.0, "bg_lightness": 0.07},
        "ramp": {"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]},
        "hues": {},
    }
    cfg.update(over)
    return cfg
```
Update calls: `build_palette(RAW, fake_manifest())` → `build_palette(RAW, fake_scheme())`; `fake_manifest(hues={"red":10})` → `fake_scheme(hues={"red":10})`; `fake_manifest(mood={...})` → `fake_scheme(mood={...})`. Keep the assertions.

Add to `test_compile.py`:
```python
def test_fixed_roles_override_derivation():
    p = compile_mod.build_palette(RAW, fake_scheme(fixed={"bg": "#000000", "accent": "#abcdef"}))
    assert p["bg"] == "#000000"
    assert p["accent"] == "#abcdef"


def test_load_scheme_config(tmp_path):
    sd = tmp_path / "s"; sd.mkdir()
    (sd / "scheme.toml").write_text('[mood]\nbg_lightness=0.05\n[hues]\nred=10\n', encoding="utf-8")
    cfg = compile_mod.load_scheme_config(sd)
    assert cfg["mood"]["bg_lightness"] == 0.05 and cfg["hues"]["red"] == 10


def test_load_scheme_config_missing_is_empty(tmp_path):
    assert compile_mod.load_scheme_config(tmp_path / "nope") == {}
```
The `compile_theme` test (`test_compile_theme_returns_result_with_stats`) must now create a scheme config. Before the `compile_theme(...)` call, write the scheme config and theme meta:
```python
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[ramp]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n', encoding="utf-8")
    (d / "theme.toml").write_text('scheme = "default"\n', encoding="utf-8")
```
and use a real `Manifest`-like object exposing `schemes_dir = tmp_path / "schemes"` and `extract_command = DEFAULT_EXTRACT` (a `types.SimpleNamespace` is fine).

`test_manifest.py`: the `MANIFEST` fixture has `[mood]`/`[ramp]`; remove the assertions on `m.mood`/`m.ramp` (the fields no longer exist). Keep targets/extract assertions.

`test_commands.py`: `build_catalog` must write `schemes/default/scheme.toml` (the color config) in addition to the templates, and each theme created gets `theme.toml`. Add to `build_catalog`:
```python
    (root / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[ramp]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n', encoding="utf-8")
```
Add a per-scheme-color test:
```python
def test_scheme_changes_color_derivation(tmp_path):
    build_catalog(tmp_path)
    alt = tmp_path / "schemes" / "alt"; alt.mkdir(parents=True)
    (alt / "waybar.tmpl").write_text("bg {{ bg }}\naccent {{ accent }}\n")
    (alt / "sway.tmpl").write_text("output * bg {{ wallpaper }} fill\n")
    (alt / "scheme.toml").write_text('[fixed]\naccent="#abcdef"\n', encoding="utf-8")
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False, scheme="alt")
    from adorn import palette
    pal = palette.load(catalog.theme_paths(tmp_path, "t").palette)
    assert pal["accent"] == "#abcdef"   # scheme's fixed role won
```

- [ ] **Step 2: Run (RED).**

- [ ] **Step 3: `manifest.py`** — remove `mood`, `ramp`, `hues` from the `Manifest` dataclass and from `load()` (delete the `data.get("mood"…)/ramp/hues` lines). Keep `extract_command`, `wallpaper_command`, `schemes_dir`, `themes_dir`, `targets`.

- [ ] **Step 4: `catalog.py`** — move `theme_scheme` here:
```python
import tomllib  # add at top

def theme_scheme(theme_paths) -> str:
    meta = theme_paths.meta
    if meta.exists():
        return tomllib.loads(meta.read_text(encoding="utf-8")).get("scheme", "default")
    return "default"
```

- [ ] **Step 5: `compile.py`** — add `from pathlib import Path` and `import tomllib` if missing.
```python
def load_scheme_config(scheme_dir) -> dict:
    p = Path(scheme_dir) / "scheme.toml"
    if p.exists():
        return tomllib.loads(p.read_text(encoding="utf-8"))
    return {}
```
Change `build_palette` to read from `scheme_config`:
```python
def build_palette(raw, scheme_config: dict, *, saturation_floor=None) -> dict:
    if not raw:
        raise ValueError("build_palette requires at least one raw color")
    mood = scheme_config.get("mood", {})
    hues = {**DEFAULT_HUES, **scheme_config.get("hues", {})}
    ramp = scheme_config.get("ramp")
    fixed = scheme_config.get("fixed", {})
    strength = mood.get("saturation_strength", 1.0)
    bg_l = mood.get("bg_lightness", 0.07)
    if saturation_floor is None:
        saturation_floor = mood.get("hue_saturation_floor", 0.0)
    if not 0.0 <= saturation_floor <= 1.0:
        raise ValueError(f"saturation floor must be in [0.0, 1.0], got {saturation_floor}")
    sat = max(saturation_floor, min(1.0, mood_saturation(raw) * strength))
    # ... (unchanged: accent pick + lightness clamp, bg/fg/variants, hue loop,
    #      aliases, ramp using `ramp`) ...
    pal.update(fixed)   # scheme's fixed roles win over derivation
    return pal
```
Change `compile_theme` to resolve the scheme config:
```python
def compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult:
    tp = catalog.theme_paths(root, name)
    scheme_cfg = load_scheme_config(manifest.schemes_dir / catalog.theme_scheme(tp))
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    mood = scheme_cfg.get("mood", {})
    strength = mood.get("saturation_strength", 1.0)
    floor = saturation_floor if saturation_floor is not None else mood.get("hue_saturation_floor", 0.0)
    mood_sat = mood_saturation(raw)
    effective = max(floor, min(1.0, mood_sat * strength))
    pal = build_palette(raw, scheme_cfg, saturation_floor=saturation_floor)
    palette_mod.dump(pal, tp.palette)
    return CompileResult(palette=pal, raw=raw, mood_saturation=mood_sat,
                         saturation_floor=floor, strength=strength,
                         effective_saturation=effective, wallpaper=str(tp.wallpaper))
```

- [ ] **Step 6: `commands.py`** — `render_theme` uses `catalog.theme_scheme(tp)` (remove the local `theme_scheme` def + its `tomllib` import if now unused). Keep everything else.

- [ ] **Step 7: Full suite green.** `.venv/bin/pytest -q`.

- [ ] **Step 8: Commit** `git commit -am "feat: per-scheme color derivation (scheme.toml [mood]/[ramp]/[hues]/[fixed])"`

## Self-Review (Task 20)
- color knobs moved manifest → per-scheme scheme.toml; build_palette reads scheme_config → tested. ✓
- `[fixed]` roles overlay derivation → tested (build_palette + cmd_new via scheme). ✓
- default scheme reproduces current behavior (same values) → existing property tests pass. ✓
- theme_scheme in catalog; compile + render both resolve the theme's scheme. ✓