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

### Task 18: Named schemes (deferred — write just-in-time after Task 17)
### Task 19: `adorn alter` (deferred — write just-in-time after Task 18)
