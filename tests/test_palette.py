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
