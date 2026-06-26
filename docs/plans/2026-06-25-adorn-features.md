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

### Task 19: `adorn alter` — pastel pipelines over theme colors

**Files:**
- Modify: `src/adorn/commands.py` (`cmd_alter`)
- Modify: `src/adorn/cli.py` (`alter` subcommand)
- Test: `tests/test_alter.py` (new)

**Interfaces:**
- `commands.cmd_alter(root, name, colors, write, command) -> None`
  - `colors`: list[str] of role names, or `None` for all
  - `write`: bool
  - `command`: list[str] — the pastel command tokens (`+role` tokens expand to that role's hex)
- `cli`: `adorn alter <name> [-c roles] [-w] <pastel cmd…>`

- [ ] **Step 1: Write failing tests (`tests/test_alter.py`)**

```python
import subprocess
import pytest
from adorn import catalog, cli, commands, palette


def setup_theme(tmp_path):
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "w.tmpl").write_text("bg {{ bg }}\n")
    (tmp_path / "adorn.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[ramp]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n'
        '[[target]]\nname="waybar"\ntemplate="w.tmpl"\nfragment="colors.css"\n'
    )
    wp = tmp_path / "src.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {wp}", shell=True, check=True)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    return tmp_path


def test_alter_saturate_single_prints_mapping(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["red"], False, ["saturate", "0.5"])
    out = capsys.readouterr().out
    assert "red" in out and "->" in out
    # not written
    assert "red" not in palette.load(catalog.theme_paths(tmp_path, "t").overrides)


def test_alter_write_scalar_to_overrides(tmp_path):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["accent"], True, ["lighten", "0.1"])
    over = palette.load(catalog.theme_paths(tmp_path, "t").overrides)
    assert "accent" in over and over["accent"].startswith("#")


def test_alter_plus_sigil_references_role(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["accent"], False, ["mix", "+magenta"])
    assert "accent" in capsys.readouterr().out


def test_alter_all_colors_saturate(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", None, False, ["saturate", "0.1"])
    assert capsys.readouterr().out.count("->") >= 10   # one per palette color incl grad0..6


def test_alter_mismatch_is_error(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(ValueError, match="produced"):
        commands.cmd_alter(tmp_path, "t", None, False, ["color", "#111111"])  # 1 out for N>1


def test_alter_unknown_role_errors(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(ValueError, match="unknown"):
        commands.cmd_alter(tmp_path, "t", ["nope"], False, ["saturate", "0.1"])


def test_alter_write_ramp_entry_rebuilds_list(tmp_path):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["grad0"], True, ["saturate", "0.2"])
    over = palette.load(catalog.theme_paths(tmp_path, "t").overrides)
    assert isinstance(over["grad"], list) and len(over["grad"]) == 7


def test_cli_alter(tmp_path):
    setup_theme(tmp_path)
    assert cli.main(["--root", str(tmp_path), "alter", "t", "-c", "red", "saturate", "0.3"]) == 0
```

- [ ] **Step 2: Run (RED).** `.venv/bin/pytest tests/test_alter.py -v` → `cmd_alter` undefined.

- [ ] **Step 3: `commands.py` — add `cmd_alter`** (add `import re` and `import subprocess` at top — re-add subprocess; NO shell, so no `shlex` needed):

```python
def cmd_alter(root, name, colors, write, command) -> None:
    if not command:
        raise ValueError("no pastel command given")
    palette = effective_palette(root, name)

    # flatten palette into selectable colors (ramp -> grad0..gradN)
    selectable = {}
    for k, v in palette.items():
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
    step = subprocess.run(
        ["pastel", *expanded], input=stdin, capture_output=True, text=True, check=True
    )
    norm = subprocess.run(
        ["pastel", "format", "hex"], input=step.stdout, capture_output=True, text=True, check=True
    )
    results = [ln.strip().lower() for ln in norm.stdout.splitlines() if ln.strip()]
    if len(results) != len(selected):
        raise ValueError(
            f"pastel produced {len(results)} color(s) for {len(selected)} selected — "
            f"refusing an ambiguous mapping (set multiple colors with separate calls)"
        )

    for role, newc in zip(selected, results):
        print(f"{role:<14} {selectable[role]} -> {newc}")

    if write:
        tp = catalog.theme_paths(root, name)
        overrides = palette_mod.load(tp.overrides)
        ramp_name, ramp_list = None, None
        for role, newc in zip(selected, results):
            m = re.fullmatch(r"([a-zA-Z_]+)(\d+)", role)
            if m and isinstance(palette.get(m.group(1)), list):
                base, idx = m.group(1), int(m.group(2))
                if ramp_list is None:
                    ramp_name, ramp_list = base, list(palette[base])
                ramp_list[idx] = newc
            else:
                overrides[role] = newc
        if ramp_list is not None:
            overrides[ramp_name] = ramp_list
        palette_mod.dump(overrides, tp.overrides)
        print(f"wrote {len(selected)} override(s) to {tp.overrides}")
```

- [ ] **Step 4: `cli.py` — `alter` subcommand**

```python
    p_alter = sub.add_parser("alter", help="run a pastel pipeline over a theme's colors")
    p_alter.add_argument("name")
    p_alter.add_argument("-c", "--color", default=None,
                         help="comma-separated roles (default: all)")
    p_alter.add_argument("-w", "--write", action="store_true",
                         help="write results to the theme's overrides.toml")
    p_alter.add_argument("command", nargs=argparse.REMAINDER,
                         help="pastel command; use +role to reference a color")
```
Dispatch:
```python
        elif args.command == "alter":
            roles = args.color.split(",") if args.color else None
            commands.cmd_alter(root, args.name, roles, args.write, args.command)
```
(`args.command` here is the subparser dest for `alter`'s positional REMAINDER. NOTE the top-level subparser dest is also `command` — rename the alter REMAINDER dest to avoid collision: use `p_alter.add_argument("pastel", nargs=argparse.REMAINDER, ...)` and dispatch with `args.pastel`. Verify the top-level `dest="command"` from `add_subparsers(dest="command")` isn't shadowed.)

- [ ] **Step 5: Run full suite.** `.venv/bin/pytest -q` → all pass (80 + 8 new = 88). If REMAINDER captures `-c/-w` when they appear before the command, confirm the test `test_cli_alter` (options before command) passes; if argparse mis-binds, document and adjust (e.g. require options before the command, which the tests follow).

- [ ] **Step 6: Commit** `git commit -am "feat: adorn alter — pastel pipelines over theme colors (+role sigil, -c/-w, 1:1 mapping)"`

## Self-Review (Task 19)
- pastel pipeline over selected/all colors, +role expansion, 1:1 M==N enforcement, -w to overrides (incl ramp rebuild) → tested across 8 cases. ✓
- unknown role + ambiguous-mapping errors → tested. ✓
- CLI -c/-w/REMAINDER → tested. ✓
