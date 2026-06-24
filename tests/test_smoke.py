import subprocess
import sys

import adorn


def test_version_constant():
    assert adorn.__version__ == "0.1.0"


def test_cli_version_runs():
    out = subprocess.run(
        [sys.executable, "-m", "adorn", "--version"],
        capture_output=True, text=True,
    )
    assert "0.1.0" in out.stdout
