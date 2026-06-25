# adorn — Friendly Errors + `init` (Plan Addendum)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Continues the engine plan; assumes Tasks 1–11 complete on `feat/engine`.

**Goal:** Replace the raw traceback when the manifest/config is missing with a clean, actionable error, and add `adorn init` to scaffold a starter `~/.config/adorn` config.

## Global Constraints
- Python ≥ 3.11. Src layout. `encoding="utf-8"` on all file IO. TDD; run `.venv/bin/pytest`. Commit `feat:`/`fix:`, no co-author trailer.

---

### Task 12: Friendly missing-config error + `adorn init`

**Files:**
- Modify: `src/adorn/manifest.py` (clear error when manifest file is absent)
- Modify: `src/adorn/commands.py` (add `cmd_init`)
- Modify: `src/adorn/cli.py` (add `init` subcommand; catch known errors → stderr + exit 1)
- Test: `tests/test_init.py` (new)

**Interfaces:**
- `commands.cmd_init(root) -> None` (creates `<root>/adorn.toml`, `templates/`, `themes/`; raises `FileExistsError` if the manifest already exists)
- `manifest.load` raises `FileNotFoundError` with an actionable message when the file is absent
- `cli`: `adorn init` subcommand; `cli.main` returns `1` and prints `adorn: <msg>` to stderr on `FileNotFoundError`/`ValueError`/`FileExistsError`

- [ ] **Step 1: Write failing tests (`tests/test_init.py`)**

```python
import pytest

from adorn import cli, commands, manifest


def test_load_missing_manifest_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="adorn init"):
        manifest.load(tmp_path / "adorn.toml")


def test_cmd_init_scaffolds_config(tmp_path, capsys):
    commands.cmd_init(tmp_path)
    assert (tmp_path / "adorn.toml").exists()
    assert (tmp_path / "templates").is_dir()
    assert (tmp_path / "themes").is_dir()
    out = capsys.readouterr().out
    assert "created" in out.lower()


def test_cmd_init_refuses_to_clobber(tmp_path):
    commands.cmd_init(tmp_path)
    with pytest.raises(FileExistsError, match="already exists"):
        commands.cmd_init(tmp_path)


def test_cli_init_then_manifest_loads(tmp_path):
    rc = cli.main(["--root", str(tmp_path), "init"])
    assert rc == 0
    # starter manifest parses (has [mood]/[ramp]/[extract]); no targets yet is fine for load? 
    # load() raises on zero targets, so just assert the file exists and is valid TOML.
    import tomllib
    data = tomllib.loads((tmp_path / "adorn.toml").read_text(encoding="utf-8"))
    assert "extract" in data and "mood" in data


def test_cli_missing_manifest_is_clean_error(tmp_path, capsys):
    # new on a root with no manifest -> exit 1 + friendly stderr, no traceback
    rc = cli.main(["--root", str(tmp_path / "nope"), "new", "x", str(tmp_path / "img.png")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("adorn:")
    assert "adorn init" in err
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_init.py -v`
Expected: FAIL — `cmd_init` undefined / no clean error / `init` subcommand missing.

- [ ] **Step 3: `manifest.py` — clear error on missing file**

At the top of `load`, before reading:
```python
def load(path) -> Manifest:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"no adorn manifest at {path} — run 'adorn init' to create one, or pass --root"
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    ...
```

- [ ] **Step 4: `commands.py` — add `cmd_init`**

Add a module-level starter template and the command:
```python
STARTER_MANIFEST = '''# adorn manifest — declares which apps adorn themes.

[extract]
command = "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"

[wallpaper]
# command = "swaymsg output '*' bg {path} fill"

[mood]
saturation_strength = 1.0
hue_saturation_floor = 0.0   # raise (e.g. 0.30) for more saturated semantic colors
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 250, 215, 175, 120, 60, 40]

# One [[target]] per app. Example:
# [[target]]
# name = "kitty"
# template = "kitty.conf.tmpl"          # lives in templates/
# output = "~/.config/kitty/colors.conf"
# reload = "kitty @ set-colors --all ~/.config/kitty/colors.conf"
'''


def cmd_init(root) -> None:
    root = Path(root)
    manifest_path = root / "adorn.toml"
    if manifest_path.exists():
        raise FileExistsError(f"adorn config already exists at {manifest_path}")
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "themes").mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(STARTER_MANIFEST, encoding="utf-8")
    print(f"created adorn config at {root}")
    print(f"  edit {manifest_path} — add a [[target]] per app")
    print(f"  put templates in {root / 'templates'}")
```

- [ ] **Step 5: `cli.py` — `init` subcommand + error handling**

Add `import sys` at the top. Register the subcommand (near the others):
```python
    sub.add_parser("init", help="scaffold a starter ~/.config/adorn config")
```
Wrap the dispatch block in try/except and add the init branch:
```python
    try:
        if args.command == "list":
            commands.cmd_list(root)
        elif args.command == "current":
            commands.cmd_current(root)
        elif args.command == "apply":
            commands.cmd_apply(root, args.name)
        elif args.command == "new":
            commands.cmd_new(root, args.name, args.wallpaper,
                             do_apply=not args.no_apply, saturation_floor=args.saturation)
        elif args.command == "recompile":
            commands.cmd_recompile(root, args.name, saturation_floor=args.saturation)
        elif args.command == "preview":
            commands.cmd_preview(root, args.name)
        elif args.command == "init":
            commands.cmd_init(root)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"adorn: {e}", file=sys.stderr)
        return 1
    return 0
```

- [ ] **Step 6: Run new tests + full suite**

Run: `.venv/bin/pytest tests/test_init.py -v` (pass), then `.venv/bin/pytest -q` (all pass, no regressions — 66 prior + 5 new = 71).

- [ ] **Step 7: Commit**

```bash
git add src/adorn/manifest.py src/adorn/commands.py src/adorn/cli.py tests/test_init.py
git commit -m "feat: adorn init + friendly error when manifest is missing"
```

## Self-Review
- Friendly missing-manifest error (no traceback, exit 1, mentions `adorn init`) → Steps 3,5; tested `test_cli_missing_manifest_is_clean_error`. ✓
- `adorn init` scaffolds config, refuses to clobber → Step 4; tested. ✓
- No placeholder; complete code. CLI catches the three error types the commands raise.
