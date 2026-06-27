# theme.toml overrides scheme.toml — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a theme's `theme.toml` a per-key override layer over its scheme's `scheme.toml` color derivation (`[mood]`/`[hues]`/`[fixed]`/`[[list]]`).

**Architecture:** Add `catalog.theme_overrides()` (theme.toml minus `scheme`) and `compile.merge_scheme_config()` (per-key deep merge; lists by `name`). `compile_theme` merges the theme's overrides onto the scheme config before `build_palette` and the stat computation. Compile-time only — `overrides.toml` (render-time hex pins) is untouched.

**Tech Stack:** Python ≥ 3.11 stdlib (`tomllib`), pytest.

## Global Constraints

- Python ≥ 3.11. Src layout. `encoding="utf-8"` on every file read/write.
- TDD: write the failing test first. Run with `.venv/bin/pytest`.
- Commit `feat:`/`refactor:`. **No co-author trailer** (matches repo history).
- `default` scheme + all existing themes must behave byte-identically (a `theme.toml` with only `scheme = "..."` yields an empty override).
- Spec: `docs/specs/2026-06-27-theme-overrides-design.md`.

---

### Task 1: `catalog.theme_overrides()` — read theme.toml's override sections

**Files:**
- Modify: `src/adorn/catalog.py` (add `theme_overrides`; `tomllib` already imported)
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `catalog.theme_paths(root, name) -> ThemePaths` (existing; `.meta` is `theme.toml`).
- Produces: `catalog.theme_overrides(theme_paths) -> dict` — parses `theme.toml`, returns it with the `scheme` key removed; `{}` if the file is absent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_catalog.py`:

```python
def test_theme_overrides_absent_is_empty(tmp_path):
    d = _mk(tmp_path, "nometa")
    tp = catalog.theme_paths(tmp_path, "nometa")
    assert catalog.theme_overrides(tp) == {}


def test_theme_overrides_only_scheme_is_empty(tmp_path):
    d = _mk(tmp_path, "bare")
    (d / "theme.toml").write_text('scheme = "default"\n', encoding="utf-8")
    tp = catalog.theme_paths(tmp_path, "bare")
    assert catalog.theme_overrides(tp) == {}


def test_theme_overrides_returns_sections_without_scheme(tmp_path):
    d = _mk(tmp_path, "over")
    (d / "theme.toml").write_text(
        'scheme = "default"\n[mood]\nbg_lightness = 0.03\n[fixed]\naccent = "#abcdef"\n',
        encoding="utf-8",
    )
    tp = catalog.theme_paths(tmp_path, "over")
    ov = catalog.theme_overrides(tp)
    assert "scheme" not in ov
    assert ov == {"mood": {"bg_lightness": 0.03}, "fixed": {"accent": "#abcdef"}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_catalog.py -k theme_overrides -v`
Expected: FAIL with `AttributeError: module 'adorn.catalog' has no attribute 'theme_overrides'`

- [ ] **Step 3: Implement `theme_overrides`**

In `src/adorn/catalog.py`, add after `theme_scheme` (end of file):

```python
def theme_overrides(theme_paths) -> dict:
    """The theme's derivation overrides: theme.toml minus the `scheme` key."""
    meta = theme_paths.meta
    if not meta.exists():
        return {}
    data = tomllib.loads(meta.read_text(encoding="utf-8"))
    data.pop("scheme", None)
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_catalog.py -k theme_overrides -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/adorn/catalog.py tests/test_catalog.py
git commit -m "feat: catalog.theme_overrides reads theme.toml derivation overrides"
```

---

### Task 2: `compile.merge_scheme_config()` — per-key deep merge

**Files:**
- Modify: `src/adorn/compile.py` (add `merge_scheme_config` + `_merge_lists` helper)
- Test: `tests/test_compile.py`

**Interfaces:**
- Produces: `compile.merge_scheme_config(base: dict, override: dict) -> dict` — `[mood]`/`[hues]`/`[fixed]` merge key-wise (override key wins, siblings inherited); `[[list]]` (the `"list"` key, a dict or list of dicts) merges by `name` (same name replaces, new name appends); sections absent from `override` come from `base`; empty `override` returns `base` unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compile.py`:

```python
def test_merge_empty_override_returns_base():
    base = {"mood": {"bg_lightness": 0.07, "saturation_strength": 1.0}, "hues": {"red": 0}}
    assert compile_mod.merge_scheme_config(base, {}) == base


def test_merge_mood_is_per_key():
    base = {"mood": {"bg_lightness": 0.07, "saturation_strength": 1.0}}
    merged = compile_mod.merge_scheme_config(base, {"mood": {"bg_lightness": 0.03}})
    assert merged["mood"] == {"bg_lightness": 0.03, "saturation_strength": 1.0}


def test_merge_hues_is_per_key():
    base = {"hues": {"red": 0, "blue": 215}}
    merged = compile_mod.merge_scheme_config(base, {"hues": {"red": 10}})
    assert merged["hues"] == {"red": 10, "blue": 215}


def test_merge_fixed_is_per_key():
    base = {"fixed": {"bg": "#000000", "accent": "#111111"}}
    merged = compile_mod.merge_scheme_config(base, {"fixed": {"accent": "#abcdef"}})
    assert merged["fixed"] == {"bg": "#000000", "accent": "#abcdef"}


def test_merge_lists_by_name_replace_and_append():
    base = {"list": [
        {"name": "grad", "length": 7, "hues": [300, 120]},
        {"name": "warm", "length": 3, "hues": [10, 40]},
    ]}
    override = {"list": [
        {"name": "grad", "length": 5, "hues": [200]},   # replaces same-name
        {"name": "cool", "length": 2, "hues": [200, 240]},  # appends
    ]}
    merged = compile_mod.merge_scheme_config(base, override)
    by_name = {a["name"]: a for a in merged["list"]}
    assert by_name["grad"]["length"] == 5
    assert by_name["warm"]["length"] == 3
    assert by_name["cool"]["length"] == 2


def test_merge_single_list_dict_normalizes():
    base = {"list": {"name": "grad", "length": 7, "hues": [300, 120]}}
    override = {"list": {"name": "grad", "length": 4, "hues": [200]}}
    merged = compile_mod.merge_scheme_config(base, override)
    by_name = {a["name"]: a for a in merged["list"]}
    assert by_name["grad"]["length"] == 4


def test_merge_does_not_mutate_base():
    base = {"mood": {"bg_lightness": 0.07}}
    compile_mod.merge_scheme_config(base, {"mood": {"bg_lightness": 0.03}})
    assert base["mood"]["bg_lightness"] == 0.07
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_compile.py -k merge -v`
Expected: FAIL with `AttributeError: module 'adorn.compile' has no attribute 'merge_scheme_config'`

- [ ] **Step 3: Implement the merge**

In `src/adorn/compile.py`, add after `load_scheme_config`:

```python
def _merge_lists(base, override):
    """Merge [[list]] arrays by `name`. Accepts a dict (single) or list of dicts."""
    def as_list(v):
        if v is None:
            return []
        return [v] if isinstance(v, dict) else list(v)
    by_name = {a["name"]: a for a in as_list(base)}
    for a in as_list(override):
        by_name[a["name"]] = a   # same name replaces (keeps base position), new appends
    return list(by_name.values())


def merge_scheme_config(base: dict, override: dict) -> dict:
    """Per-key deep merge of a theme's overrides onto a scheme's base config.

    Tables ([mood]/[hues]/[fixed]) merge key-wise; [[list]] arrays merge by
    `name`. Sections absent from `override` are taken from `base`. Does not
    mutate `base`.
    """
    merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, oval in override.items():
        bval = merged.get(key)
        if isinstance(bval, dict) and isinstance(oval, dict):
            merged[key] = {**bval, **oval}
        elif key == "list":
            merged[key] = _merge_lists(bval, oval)
        else:
            merged[key] = oval
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_compile.py -k merge -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/adorn/compile.py tests/test_compile.py
git commit -m "feat: compile.merge_scheme_config (per-key, lists by name)"
```

---

### Task 3: Wire the override into `compile_theme`

**Files:**
- Modify: `src/adorn/compile.py:106-121` (`compile_theme`)
- Test: `tests/test_compile.py`

**Interfaces:**
- Consumes: `catalog.theme_overrides` (Task 1), `merge_scheme_config` (Task 2).
- Produces: `compile_theme` now derives the palette from `merge_scheme_config(scheme_cfg, catalog.theme_overrides(tp))`. Signature unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compile.py`:

```python
def test_compile_theme_applies_theme_override(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    # argv list, no shell — matches the no-shell convention in color.py
    subprocess.run(["magick", "-size", "16x16", "xc:#9b9e61", str(img)], check=True)
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[list]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n',
        encoding="utf-8",
    )
    # theme pins accent on top of the scheme's wallpaper-derived accent
    (d / "theme.toml").write_text(
        'scheme = "default"\n[fixed]\naccent = "#abcdef"\n', encoding="utf-8"
    )
    m = types.SimpleNamespace(extract_command=DEFAULT_EXTRACT, schemes_dir=tmp_path / "schemes")
    result = compile_mod.compile_theme(tmp_path, "t", m)
    assert result.palette["accent"] == "#abcdef"   # theme override reached derivation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_compile.py::test_compile_theme_applies_theme_override -v`
Expected: FAIL — `accent` is the wallpaper-derived color (e.g. `#9b9e61`), not `#abcdef`.

- [ ] **Step 3: Wire the merge into `compile_theme`**

In `src/adorn/compile.py`, in `compile_theme`, change the scheme-config line:

```python
    scheme_cfg = load_scheme_config(manifest.schemes_dir / catalog.theme_scheme(tp))
```

to merge the theme's overrides on top:

```python
    scheme_cfg = load_scheme_config(manifest.schemes_dir / catalog.theme_scheme(tp))
    scheme_cfg = merge_scheme_config(scheme_cfg, catalog.theme_overrides(tp))
```

Everything downstream (`mood`/`strength`/`floor` stats and `build_palette(raw, scheme_cfg, ...)`) already reads from `scheme_cfg`, so no further change.

- [ ] **Step 4: Run the test, then the full suite**

Run: `.venv/bin/pytest tests/test_compile.py::test_compile_theme_applies_theme_override -v`
Expected: PASS

Run: `.venv/bin/pytest -q`
Expected: PASS — entire suite green (back-compat: the existing `test_compile_theme_writes_palette` with only `scheme = "default"` still passes because its override is empty).

- [ ] **Step 5: Commit**

```bash
git add src/adorn/compile.py tests/test_compile.py
git commit -m "feat: compile_theme applies theme.toml overrides over scheme.toml"
```

---

## Self-Review

- **Spec coverage:**
  - `catalog.theme_overrides` (theme.toml minus `scheme`) → Task 1. ✓
  - `merge_scheme_config` per-key mood/hues/fixed + lists-by-name + identity → Task 2. ✓
  - `compile_theme` merges before build + stats → Task 3 (stats read from `scheme_cfg`, now merged). ✓
  - Back-compat (only-`scheme` → identical) → Task 3 Step 4 full-suite gate + `test_merge_empty_override_returns_base`. ✓
  - `overrides.toml`/render untouched → no task modifies them. ✓
- **Placeholder scan:** none — every step has concrete code/commands. ✓
- **Type consistency:** `theme_overrides(theme_paths) -> dict`, `merge_scheme_config(base, override) -> dict`, `_merge_lists(base, override)` used consistently across tasks; `compile_theme` signature unchanged. ✓
- **Note:** Tasks 1 and 2 are independent (different functions/files-of-interest); Task 3 depends on both. Tests for compile-theme use `magick` (already a suite dependency, see `test_compile_theme_writes_palette`).
