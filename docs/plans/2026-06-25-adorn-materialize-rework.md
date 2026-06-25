# adorn — Materialize-into-theme + source-from-current (Plan Addendum)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Continues the engine; assumes Tasks 1–13 complete on `feat/engine`.

**Goal:** Rework the engine so every theme materializes editable per-app color fragments under `apps/`, apps source the active theme via the `current` symlink, and `apply` deploys without re-rendering (hand-edits persist). `render` materializes; `apply` flips the symlink + reloads; swaylock is the one managed-block fallback.

**Architecture change:** Today `apply` renders templates straight to live config outputs. New: `render` writes templates into `themes/<name>/apps/<target>/<fragment>` (materialize); `apply` points `current` → theme, rewrites the swaylock managed-block, and reloads — it does NOT re-render.

## Global Constraints
- Python ≥ 3.11. Src layout. `encoding="utf-8"` on all file IO. TDD; run `.venv/bin/pytest`. Commit `feat:`/`refactor:`, no co-author trailer.
- Atomic writes (temp + `os.replace`).
- Existing tests that assumed the old `apply`-renders-to-output model WILL change — the brief names exactly which to update; do not silently delete coverage, port it to the new behavior.

---

### Task 14: Target fields + render.materialize + managed-block writer

**Files:**
- Modify: `src/adorn/manifest.py` (Target: add `fragment`, `via`; make `output` optional)
- Modify: `src/adorn/render.py` (replace `render_all`/`write_all` with `materialize` + `write_block`; keep `make_env`)
- Modify: `tests/test_manifest.py` (Target field assertions)
- Replace: `tests/test_render.py` (test `materialize` + `write_block`)

**Interfaces:**
- `manifest.Target(name, template=None, fragment=None, via="current", output=None, reload=None)`
- `render.make_env(templates_dir)` (unchanged)
- `render.materialize(manifest, palette: dict, apps_dir) -> dict[str, Path]` — renders each target with a `template` into `apps_dir/<target.name>/<target.fragment>`; returns `{target_name: written_path}`
- `render.MARKER_BEGIN`, `render.MARKER_END` (str)
- `render.write_block(config_path, fragment_text) -> None` — replaces the marked block in `config_path` (appends a block if markers absent; creates the file if missing)

- [ ] **Step 1: Write failing tests**

Replace `tests/test_render.py` entirely:
```python
import types
from pathlib import Path

from adorn import render
from adorn.manifest import Target


def manifest_with(tmp_path, targets):
    (tmp_path / "templates").mkdir(exist_ok=True)
    return types.SimpleNamespace(templates_dir=tmp_path / "templates", targets=tuple(targets))


def test_materialize_renders_into_apps_dir(tmp_path):
    (tmp_path / "templates" / "waybar.tmpl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "waybar.tmpl").write_text("bg {{ bg }}\n")
    m = manifest_with(tmp_path, [Target("waybar", template="waybar.tmpl", fragment="colors.css")])
    apps = tmp_path / "apps"
    written = render.materialize(m, {"bg": "#111111"}, apps)
    dest = apps / "waybar" / "colors.css"
    assert dest.read_text() == "bg #111111\n"
    assert written["waybar"] == dest


def test_materialize_ramp_indexing(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "g.tmpl").write_text("{{ grad[0] }}|{{ grad[1] }}")
    m = manifest_with(tmp_path, [Target("g", template="g.tmpl", fragment="c")])
    render.materialize(m, {"grad": ["#aaaaaa", "#bbbbbb"]}, tmp_path / "apps")
    assert (tmp_path / "apps" / "g" / "c").read_text() == "#aaaaaa|#bbbbbb"


def test_materialize_missing_role_raises(tmp_path):
    import jinja2
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "x.tmpl").write_text("{{ missing }}")
    m = manifest_with(tmp_path, [Target("x", template="x.tmpl", fragment="c")])
    import pytest
    with pytest.raises(jinja2.UndefinedError):
        render.materialize(m, {"bg": "#111111"}, tmp_path / "apps")


def test_write_block_appends_when_absent(tmp_path):
    cfg = tmp_path / "swaylock.conf"
    cfg.write_text("font=Foo\nindicator-radius=110\n", encoding="utf-8")
    render.write_block(cfg, "ring-color=aabbcc")
    text = cfg.read_text()
    assert "font=Foo" in text                      # structural config preserved
    assert render.MARKER_BEGIN in text and render.MARKER_END in text
    assert "ring-color=aabbcc" in text


def test_write_block_replaces_existing(tmp_path):
    cfg = tmp_path / "swaylock.conf"
    render.write_block(cfg, "ring-color=oldold")    # creates file + block
    render.write_block(cfg, "ring-color=newnew")    # replaces block
    text = cfg.read_text()
    assert "ring-color=newnew" in text
    assert "ring-color=oldold" not in text
    assert text.count(render.MARKER_BEGIN) == 1     # exactly one block


def test_write_block_preserves_surrounding(tmp_path):
    cfg = tmp_path / "c"
    cfg.write_text(f"A=1\n{render.MARKER_BEGIN}\nold\n{render.MARKER_END}\nB=2\n", encoding="utf-8")
    render.write_block(cfg, "new=val")
    text = cfg.read_text()
    assert "A=1" in text and "B=2" in text and "new=val" in text and "old" not in text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_render.py -v` → FAIL (`materialize`/`write_block` undefined).

- [ ] **Step 3: Rewrite `src/adorn/render.py`**

```python
"""Render target templates into a theme's apps/ fragments, and manage the
swaylock-style delimited color block for apps that cannot include a file."""
import os
from pathlib import Path

import jinja2

MARKER_BEGIN = "# >>> adorn (managed) >>>"
MARKER_END = "# <<< adorn (managed) <<<"


def make_env(templates_dir) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".adorn-tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def materialize(manifest, palette: dict, apps_dir) -> dict:
    """Render each target with a template into apps_dir/<target>/<fragment>.

    Returns {target_name: written_path}. Raises (before writing anything more)
    on a missing role, so a bad template can't leave a half-materialized set.
    """
    env = make_env(manifest.templates_dir)
    rendered = {}
    for target in manifest.targets:
        if not target.template:
            continue
        content = env.get_template(target.template).render(**palette)
        dest = Path(apps_dir) / target.name / target.fragment
        rendered[target.name] = (dest, content)
    written = {}
    for name, (dest, content) in rendered.items():
        _atomic_write(dest, content)
        written[name] = dest
    return written


def write_block(config_path, fragment_text: str) -> None:
    """Replace the adorn-managed block in config_path with fragment_text.

    Appends a fresh block if the markers are absent; creates the file if missing.
    The user's surrounding (structural) config is preserved untouched.
    """
    path = Path(config_path)
    block = f"{MARKER_BEGIN}\n{fragment_text.rstrip(chr(10))}\n{MARKER_END}\n"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if MARKER_BEGIN in text and MARKER_END in text:
            pre = text[: text.index(MARKER_BEGIN)]
            post = text[text.index(MARKER_END) + len(MARKER_END):].lstrip("\n")
            new = pre + block + post
        else:
            new = text.rstrip("\n") + "\n\n" + block
    else:
        new = block
    _atomic_write(path, new)
```

- [ ] **Step 4: Update `src/adorn/manifest.py` Target**

Replace the `Target` dataclass and the target-construction in `load`:
```python
@dataclass(frozen=True)
class Target:
    name: str
    template: str | None = None
    fragment: str | None = None
    via: str = "current"
    output: Path | None = None
    reload: str | None = None
```
In `load`, build each target:
```python
    for t in raw_targets:
        if "name" not in t:
            raise ValueError(f"target missing name: {t!r}")
        out = t.get("output")
        targets.append(
            Target(
                name=t["name"],
                template=t.get("template"),
                fragment=t.get("fragment"),
                via=t.get("via", "current"),
                output=_expand(out) if out else None,
                reload=t.get("reload"),
            )
        )
```
(Remove the old "missing output" ValueError — `output` is now optional.)

- [ ] **Step 5: Update `tests/test_manifest.py`**

The happy-path fixture's `[[target]]` uses `output`. Add `fragment` + assert new fields. Change the kitty target block in the `MANIFEST` string to include `fragment = "colors.conf"`, and update `test_load_parses_targets_and_sections` to also assert:
```python
    assert t.fragment == "colors.conf"
    assert t.via == "current"
```
Delete `test_target_missing_output_raises` (output is no longer required) and replace it with:
```python
def test_target_defaults_via_current_and_optional_output(tmp_path):
    text = '[[target]]\nname = "x"\ntemplate = "x.tmpl"\nfragment = "c"\n'
    m = manifest.load(_write(tmp_path, text))
    assert m.targets[0].via == "current"
    assert m.targets[0].output is None
```
Keep `test_no_targets_raises` (still valid).

- [ ] **Step 6: Run tests**

`.venv/bin/pytest tests/test_render.py tests/test_manifest.py -v` → all pass.

- [ ] **Step 7: Commit**

```bash
git add src/adorn/render.py src/adorn/manifest.py tests/test_render.py tests/test_manifest.py
git commit -m "refactor: render.materialize into apps/ + managed-block writer; Target fragment/via"
```

---

### Task 15: commands + CLI rework (render verb, apply = symlink + block + reload)

**Files:**
- Modify: `src/adorn/commands.py` (`render_theme`, `cmd_render`; rework `cmd_new`, `cmd_apply`, `cmd_recompile`)
- Modify: `src/adorn/cli.py` (add `render` subcommand)
- Modify: `tests/test_commands.py` (rewrite integration tests for the new model)

**Interfaces:**
- `commands.render_theme(root, name, manifest) -> None` (materialize apps/)
- `commands.cmd_render(root, name) -> None`
- `commands.cmd_new(root, name, wallpaper, do_apply=True, saturation_floor=None)` — now also materializes apps/
- `commands.cmd_apply(root, name)` — set current; for `via="block"` targets rewrite the block from `apps/<t>/<fragment>`; reload; set wallpaper; render apps/ first only if missing
- `commands.cmd_recompile(root, name, saturation_floor=None)` — palette only; prints a "run render" hint
- `cli`: `adorn render <name>`

- [ ] **Step 1: Rewrite the integration tests (`tests/test_commands.py`)**

Replace the file's tests with ones for the new model. Helper builds a manifest with a source-from-current target (waybar) and a block target (swaylock):
```python
import subprocess

from adorn import catalog, cli, commands, palette


def build_catalog(root):
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "waybar.tmpl").write_text("bg {{ bg }}\naccent {{ accent }}\n")
    (root / "templates" / "swaylock.tmpl").write_text("ring={{ accent[1:] }}\n")
    swaycfg = root / "swaylock.conf"
    swaycfg.write_text("font=Foo\nindicator-radius=110\n", encoding="utf-8")
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
name = "waybar"
template = "waybar.tmpl"
fragment = "colors.css"
reload = "true"
[[target]]
name = "swaylock"
template = "swaylock.tmpl"
fragment = "colors"
via = "block"
output = "{swaycfg}"
"""
    )
    return swaycfg


def make_wallpaper(path):
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {path}", shell=True, check=True)


def test_new_materializes_editable_fragments(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp))
    tp = catalog.theme_paths(tmp_path, "t")
    waybar_frag = tp.dir / "apps" / "waybar" / "colors.css"
    assert waybar_frag.exists()
    assert waybar_frag.read_text().startswith("bg #")
    # editable + saved: hand-edit survives apply
    waybar_frag.write_text("bg #deadbe\naccent #c0ffee\n", encoding="utf-8")
    commands.cmd_apply(tmp_path, "t")
    assert (tp.dir / "apps" / "waybar" / "colors.css").read_text() == "bg #deadbe\naccent #c0ffee\n"


def test_apply_sets_current_symlink(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    commands.cmd_apply(tmp_path, "t")
    assert catalog.current_theme(tmp_path) == "t"


def test_apply_writes_swaylock_block(tmp_path):
    swaycfg = build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp))
    text = swaycfg.read_text()
    assert "font=Foo" in text                      # structural preserved
    assert "ring=" in text                          # color block injected
    from adorn import render
    assert render.MARKER_BEGIN in text


def test_render_redramatizes_from_palette(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    frag = catalog.theme_paths(tmp_path, "t").dir / "apps" / "waybar" / "colors.css"
    frag.write_text("HAND EDIT\n", encoding="utf-8")
    commands.cmd_render(tmp_path, "t")              # regenerate from palette
    assert frag.read_text().startswith("bg #")      # edit overwritten by render
    assert "HAND EDIT" not in frag.read_text()


def test_overrides_flow_to_fragment_on_render(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    tp = catalog.theme_paths(tmp_path, "t")
    palette.dump({"bg": "#000000"}, tp.overrides)
    commands.cmd_render(tmp_path, "t")
    assert "bg #000000" in (tp.dir / "apps" / "waybar" / "colors.css").read_text()


def test_cli_render_subcommand(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "t", str(wp), "--no-apply"])
    assert cli.main(["--root", str(tmp_path), "render", "t"]) == 0
```

- [ ] **Step 2: Run to verify failure**

`.venv/bin/pytest tests/test_commands.py -v` → FAIL (`render_theme`/`cmd_render` undefined; cmd_apply old behavior).

- [ ] **Step 3: Rewrite the relevant parts of `src/adorn/commands.py`**

Keep `load_manifest`, `effective_palette`, `cmd_list`, `cmd_current`, `cmd_preview`. Replace `cmd_apply`, `cmd_new`, `cmd_recompile` and add `render_theme`/`cmd_render`:
```python
def render_theme(root, name, manifest) -> None:
    palette = effective_palette(root, name)
    apps_dir = catalog.theme_paths(root, name).dir / "apps"
    render_mod.materialize(manifest, palette, apps_dir)


def cmd_render(root, name) -> None:
    manifest = load_manifest(root)
    render_theme(root, name, manifest)
    print(f"rendered apps/ fragments for '{name}'")


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


def cmd_apply(root, name) -> None:
    manifest = load_manifest(root)
    tp = catalog.theme_paths(root, name)
    apps_dir = tp.dir / "apps"
    if not apps_dir.exists():
        render_theme(root, name, manifest)   # bootstrap a theme that has no apps/ yet
    catalog.set_current(root, name)
    for target in manifest.targets:
        if target.via == "block" and target.output is not None:
            frag = apps_dir / target.name / target.fragment
            render_mod.write_block(target.output, frag.read_text(encoding="utf-8"))
    reload_mod.run_reloads(manifest)
    reload_mod.set_wallpaper(manifest, tp.wallpaper)


def cmd_recompile(root, name, saturation_floor=None) -> None:
    manifest = load_manifest(root)
    result = compile_mod.compile_theme(root, name, manifest, saturation_floor=saturation_floor)
    print(compile_mod.format_stats(name, result))
    print(f"palette recompiled; run `adorn render {name}` to update apps/")
```
(`render_mod` is the existing `from . import render as render_mod` import.)

- [ ] **Step 4: Add `render` to `src/adorn/cli.py`**

Register the subcommand and dispatch:
```python
    p_render = sub.add_parser("render", help="re-derive apps/ fragments from palette+overrides")
    p_render.add_argument("name")
```
In the try/except dispatch:
```python
        elif args.command == "render":
            commands.cmd_render(root, args.name)
```

- [ ] **Step 5: Run the full suite**

`.venv/bin/pytest -v` → all pass. Note: `test_compile.py`'s `test_compile_theme_writes_palette` still uses `.palette` (compile_theme unchanged) — confirm it passes. If any other older test references the removed `render.render_all`/`write_all` or `cmd_apply`-writes-to-config behavior, port it to the new model (don't delete coverage).

- [ ] **Step 6: Commit**

```bash
git add src/adorn/commands.py src/adorn/cli.py tests/test_commands.py
git commit -m "feat: render materializes apps/, apply = current symlink + block + reload"
```

## Self-Review
- Per-app editable fragments materialized per theme → `materialize` + `cmd_new`; tested `test_new_materializes_editable_fragments`. ✓
- Hand-edits persist across apply (apply doesn't re-render) → tested (edit→apply→unchanged). ✓
- `render` regenerates from palette+overrides → `cmd_render`; tested. ✓
- apply = current symlink + reload; source-from-current targets need no copy → `cmd_apply`; tested `test_apply_sets_current_symlink`. ✓
- swaylock managed-block, structural preserved → `write_block`; tested `test_apply_writes_swaylock_block`, `test_write_block_*`. ✓
- overrides flow into fragments on render → tested. ✓
- No placeholders; types consistent (`Target.fragment/via/output`, `materialize`/`write_block`/`render_theme` signatures match call sites).
