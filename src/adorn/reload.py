"""Run target reload hooks and set the wallpaper."""
import shlex
import subprocess


def run_reload(target) -> None:
    if target.reload:
        subprocess.run(target.reload, shell=True, check=False)


def run_reloads(manifest) -> None:
    for target in manifest.targets:
        run_reload(target)


def set_wallpaper(manifest, wallpaper_path) -> None:
    if manifest.wallpaper_command:
        cmd = manifest.wallpaper_command.format(path=shlex.quote(str(wallpaper_path)))
        subprocess.run(cmd, shell=True, check=False)
