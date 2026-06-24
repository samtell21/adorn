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


def test_eight_digit_rgba_returns_rgb(tmp_path):
    # ImageMagick can emit #RRGGBBAA for alpha images; we want the RGB only
    cmd = "printf '#3A9D23FF #11223344\\n' # {path}"
    colors = extract.extract(cmd, tmp_path / "x.png")
    assert colors == ["#3a9d23", "#112233"]
