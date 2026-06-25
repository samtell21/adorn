# adorn — Feature batch: wallpaper var, schemes, plugin-via-reload, alter

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Continues the engine; assumes Tasks 1–16 complete on `feat/engine`.

**Goal:** (17) `{{ wallpaper }}` render variable + drop the `via`/`output`/`write_block` delivery code (plugins are now just `reload` commands). (18) Named schemes. (19) `adorn alter`.

## Global Constraints
- Python ≥ 3.11. Src layout. `encoding="utf-8"`. TDD; `.venv/bin/pytest`. Commit `feat:`/`refactor:`, no co-author trailer.

---

### Task 17: `{{ wallpaper }}` render var + remove via/output/write_block

**Files:**
- Modify: `src/adorn/manifest.py` (Target: drop `via`, `output`)
- Modify: `src/adorn/render.py` (remove `write_block`, `MARKER_BEGIN/END`)
- Modify: `src/adorn/commands.py` (`render_theme` adds `wallpaper` to context; `cmd_apply` drops the via="block" branch)
- Modify: `tests/test_render.py` (drop write_block tests; add wallpaper-context test)
- Modify: `tests/test_manifest.py` (Target no longer has via/output)
- Modify: `tests/test_commands.py` (drop swaylock-block test; rewrite build_catalog without via/output; add wallpaper-in-fragment test)

**Interfaces:**
- `manifest.Target(name, template=None, fragment=None, reload=None)`
- `render.materialize(manifest, context: dict, apps_dir) -> dict` (unchanged behavior; `context` may carry non-color keys like `wallpaper`)
- `commands.render_theme(root, name, manifest)` — context = effective palette + `{"wallpaper": str(theme wallpaper path)}`
- `commands.cmd_apply(root, name)` — bootstrap-if-missing + set_current + run_reloads + set_wallpaper (no block handling)

- [ ] **Step 1: Update tests first (RED)**

In `tests/test_render.py`: DELETE `test_write_block_appends_when_absent`, `test_write_block_replaces_existing`, `test_write_block_preserves_surrounding`, `test_write_block_keeps_blank_separator_on_reapply` (write_block is removed). ADD:
```python
def test_materialize_passes_nonpalette_context(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "w.tmpl").write_text("wp {{ wallpaper }}")
    m = manifest_with(tmp_path, [Target("sway", template="w.tmpl", fragment="colors")])
    render.materialize(m, {"wallpaper": "/x/wall.jpg"}, tmp_path / "apps")
    assert (tmp_path / "apps" / "sway" / "colors").read_text() == "wp /x/wall.jpg"
```

In `tests/test_manifest.py`: the manifest fixture's kitty target has `fragment`. Update `test_target_defaults_via_current_and_optional_output` → rename to and replace with:
```python
def test_target_fields(tmp_path):
    text = '[[target]]\nname = "x"\ntemplate = "x.tmpl"\nfragment = "c"\nreload = "true"\n'
    m = manifest.load(_write(tmp_path, text))
    t = m.targets[0]
    assert (t.name, t.template, t.fragment, t.reload) == ("x", "x.tmpl", "c", "true")
    assert not hasattr(t, "via")
```
And in `test_load_parses_targets_and_sections`, remove the `t.via == "current"` assertion if present.

In `tests/test_commands.py`: rewrite `build_catalog` to drop the swaylock via="block" target and add a `{{ wallpaper }}`-using target; DELETE `test_apply_writes_swaylock_block`. New `build_catalog` + a wallpaper test:
```python
def build_catalog(root):
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "waybar.tmpl").write_text("bg {{ bg }}\naccent {{ accent }}\n")
    (root / "templates" / "sway.tmpl").write_text("output * bg {{ wallpaper }} fill\n")
    (root / "adorn.toml").write_text(
        """
[mood]
bg_lightness = 0.07
[ramp]
name = "grad"
length = 7
hues = [300, 215, 175, 120, 40]
[[target]]
name = "waybar"
template = "waybar.tmpl"
fragment = "colors.css"
reload = "true"
[[target]]
name = "sway"
template = "sway.tmpl"
fragment = "colors"
reload = "true"
"""
    )


def test_render_puts_wallpaper_in_fragment(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    frag = catalog.theme_paths(tmp_path, "t").dir / "apps" / "sway" / "colors"
    text = frag.read_text()
    assert "output * bg" in text
    assert str(catalog.theme_paths(tmp_path, "t").wallpaper) in text  # theme's wallpaper path
```
(Keep all other test_commands.py tests; they used build_catalog which no longer has a swaylock/block target — that's fine, none of the kept tests asserted on swaylock.)

- [ ] **Step 2: Run to verify failures**

`.venv/bin/pytest tests/test_render.py tests/test_manifest.py tests/test_commands.py -v` → failures for the new wallpaper tests + any references to removed write_block/via.

- [ ] **Step 3: `manifest.py` — drop via/output**

Replace the `Target` dataclass:
```python
@dataclass(frozen=True)
class Target:
    name: str
    template: str | None = None
    fragment: str | None = None
    reload: str | None = None
```
In `load`, simplify target construction (remove via/output/`_expand(out)`):
```python
    for t in raw_targets:
        if "name" not in t:
            raise ValueError(f"target missing name: {t!r}")
        targets.append(
            Target(
                name=t["name"],
                template=t.get("template"),
                fragment=t.get("fragment"),
                reload=t.get("reload"),
            )
        )
```
(Leave `_expand` in the module — still used for the manifest's own paths if any; if now unused, remove it. Check and remove if unused.)

- [ ] **Step 4: `render.py` — remove write_block + markers**

Delete `MARKER_BEGIN`, `MARKER_END`, and the entire `write_block` function. Keep `make_env`, `_atomic_write`, `materialize`. Rename `materialize`'s second parameter from `palette` to `context` for clarity (it renders `**context`); body unchanged otherwise.

- [ ] **Step 5: `commands.py` — wallpaper in context, drop block branch**

`render_theme`:
```python
def render_theme(root, name, manifest) -> None:
    tp = catalog.theme_paths(root, name)
    context = dict(effective_palette(root, name))
    context["wallpaper"] = str(tp.wallpaper)
    render_mod.materialize(manifest, context, tp.dir / "apps")
```
`cmd_apply` (remove the `for target … via == "block"` loop entirely):
```python
def cmd_apply(root, name) -> None:
    manifest = load_manifest(root)
    tp = catalog.theme_paths(root, name)
    apps_dir = tp.dir / "apps"
    if not apps_dir.exists():
        render_theme(root, name, manifest)
    catalog.set_current(root, name)
    reload_mod.run_reloads(manifest)
    reload_mod.set_wallpaper(manifest, tp.wallpaper)
```

- [ ] **Step 6: Full suite green**

`.venv/bin/pytest -q` → all pass (80 minus 4 removed write_block tests minus 1 removed block test plus 2 new = 77).

- [ ] **Step 7: Commit**

```bash
git add src/adorn/manifest.py src/adorn/render.py src/adorn/commands.py tests/test_render.py tests/test_manifest.py tests/test_commands.py
git commit -m "refactor: {{wallpaper}} render var; drop via/output/write_block (plugins are reload commands)"
```

## Self-Review (Task 17)
- `{{ wallpaper }}` in render context → `render_theme`; tested `test_render_puts_wallpaper_in_fragment`, `test_materialize_passes_nonpalette_context`. ✓
- via/output/write_block removed; Target simplified → tested `test_target_fields`. ✓
- cmd_apply no longer block-handles; still bootstraps + symlink + reload + wallpaper. ✓

---

### Task 18: Named schemes

**Files:**
- Modify: `src/adorn/manifest.py` (`Manifest.templates_dir` → `schemes_dir`)
- Modify: `src/adorn/render.py` (`materialize` takes an explicit `templates_dir`)
- Modify: `src/adorn/catalog.py` (`ThemePaths` gains `meta` = `theme.toml`)
- Modify: `src/adorn/commands.py` (`theme_scheme` helper; `render_theme` resolves the scheme dir; `cmd_new` writes `theme.toml`)
- Modify: `src/adorn/cli.py` (`new --scheme`)
- Modify tests accordingly.

**Interfaces:**
- `manifest.Manifest(... schemes_dir ...)` (replaces `templates_dir`; `schemes_dir = root/"schemes"`)
- `render.materialize(manifest, context, apps_dir, templates_dir) -> dict`
- `catalog.ThemePaths(dir, wallpaper, palette, overrides, files, meta)`
- `commands.theme_scheme(theme_paths) -> str` (reads `theme.toml` `scheme`, default `"default"`)
- `commands.cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None, scheme="default")`
- `cli`: `new --scheme S`

- [ ] **Step 1: Tests first (RED)** — add to `tests/test_render.py`:
```python
def test_materialize_uses_given_templates_dir(tmp_path):
    sdir = tmp_path / "schemes" / "alt"; sdir.mkdir(parents=True)
    (sdir / "k.tmpl").write_text("c1 {{ red }}")
    m = manifest_with(tmp_path, [Target("kitty", template="k.tmpl", fragment="colors.conf")])
    render.materialize(m, {"red": "#ff0000"}, tmp_path / "apps", sdir)
    assert (tmp_path / "apps" / "kitty" / "colors.conf").read_text() == "c1 #ff0000"
```
Update the OTHER `materialize(...)` calls in test_render.py to pass a 4th arg `tmp_path / "templates"` (the existing fixture dir). Update `manifest_with` to also expose `schemes_dir = tmp_path / "schemes"` (harmless extra attr).

Add to `tests/test_commands.py`:
```python
def test_new_records_scheme_and_uses_it(tmp_path):
    build_catalog(tmp_path)
    # add an alternate scheme that maps waybar bg to {{ accent }} instead of {{ bg }}
    alt = tmp_path / "schemes" / "alt"; alt.mkdir(parents=True)
    (alt / "waybar.tmpl").write_text("bg {{ accent }}\n")
    (alt / "sway.tmpl").write_text("output * bg {{ wallpaper }} fill\n")
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False, scheme="alt")
    import tomllib
    meta = tomllib.loads((catalog.theme_paths(tmp_path, "t").dir / "theme.toml").read_text())
    assert meta["scheme"] == "alt"
    frag = (catalog.theme_paths(tmp_path, "t").dir / "apps" / "waybar" / "colors.css").read_text()
    pal = palette.load(catalog.theme_paths(tmp_path, "t").palette)
    assert pal["accent"] in frag        # used the alt scheme's template


def test_default_scheme_when_unspecified(tmp_path):
    from adorn import commands as C
    build_catalog(tmp_path)
    # build_catalog's templates live in tmp_path/"templates"; move them to schemes/default
    import shutil
    (tmp_path / "schemes").mkdir(exist_ok=True)
    shutil.move(str(tmp_path / "templates"), str(tmp_path / "schemes" / "default"))
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    C.cmd_new(tmp_path, "t", str(wp), do_apply=False)   # no scheme -> default
    assert (catalog.theme_paths(tmp_path, "t").dir / "apps" / "waybar" / "colors.css").exists()
```
NOTE: `build_catalog` currently writes templates to `tmp_path/"templates"`. Update `build_catalog` to write them to `tmp_path/"schemes"/"default"` instead (since schemes replace templates). Adjust the two new tests accordingly (the `shutil.move` in the second becomes unnecessary — remove it once build_catalog writes to schemes/default).

- [ ] **Step 2: Run (RED).** `.venv/bin/pytest tests/test_render.py tests/test_commands.py -v`.

- [ ] **Step 3: `manifest.py`** — rename `templates_dir` to `schemes_dir`:
```python
        templates_dir=root / "templates",   # DELETE this line
```
becomes (in the Manifest(...) construction):
```python
        schemes_dir=root / "schemes",
```
and in the dataclass replace `templates_dir: Path` with `schemes_dir: Path`.

- [ ] **Step 4: `render.py`** — `materialize` takes `templates_dir`:
```python
def materialize(manifest, context: dict, apps_dir, templates_dir) -> dict:
    env = make_env(templates_dir)
    rendered = {}
    for target in manifest.targets:
        if not target.template:
            continue
        content = env.get_template(target.template).render(**context)
        rendered[target.name] = (Path(apps_dir) / target.name / target.fragment, content)
    written = {}
    for name, (dest, content) in rendered.items():
        _atomic_write(dest, content)
        written[name] = dest
    return written
```

- [ ] **Step 5: `catalog.py`** — add `meta` to ThemePaths:
```python
ThemePaths = namedtuple("ThemePaths", "dir wallpaper palette overrides files meta")
```
and in `theme_paths(...)` add `meta=d / "theme.toml"` to the returned tuple.

- [ ] **Step 6: `commands.py`** — scheme helper + wire it:
```python
import tomllib  # add near the top imports


def theme_scheme(theme_paths) -> str:
    meta = theme_paths.meta
    if meta.exists():
        return tomllib.loads(meta.read_text(encoding="utf-8")).get("scheme", "default")
    return "default"


def render_theme(root, name, manifest) -> None:
    tp = catalog.theme_paths(root, name)
    scheme_dir = manifest.schemes_dir / theme_scheme(tp)
    context = dict(effective_palette(root, name))
    context["wallpaper"] = str(tp.wallpaper)
    render_mod.materialize(manifest, context, tp.dir / "apps", scheme_dir)
```
`cmd_new` writes `theme.toml` (add `scheme` param, write meta before render):
```python
def cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None, scheme="default") -> None:
    manifest = load_manifest(root)
    theme_dir = catalog.new_theme_dir(root, name)
    dest = theme_dir / ("wallpaper" + Path(wallpaper).suffix)
    shutil.copy(wallpaper, dest)
    (theme_dir / "overrides.toml").write_text("# per-theme color/role overrides\n", encoding="utf-8")
    (theme_dir / "theme.toml").write_text(f'scheme = "{scheme}"\n', encoding="utf-8")
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    render_theme(root, name, manifest)
    print(compile_mod.format_stats(name, result))
    if do_apply:
        cmd_apply(root, name)
```

- [ ] **Step 7: `cli.py`** — `new --scheme`:
```python
    p_new.add_argument("--scheme", default="default")
```
and pass `scheme=args.scheme` in the `cmd_new(...)` dispatch call.

- [ ] **Step 8: Full suite green.** `.venv/bin/pytest -q`.

- [ ] **Step 9: Commit** `git commit -am "feat: named schemes (schemes/<name>/ template sets + per-theme theme.toml)"`

## Self-Review (Task 18)
- schemes_dir replaces templates_dir; materialize uses explicit dir → tested. ✓
- theme.toml records scheme; render resolves it; default when absent → tested (alt + default). ✓
- new --scheme wired → CLI dispatch. ✓

---

### Task 19: `adorn alter` (write just-in-time after Task 18)
