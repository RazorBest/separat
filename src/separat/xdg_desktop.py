import subprocess
from pathlib import Path
from typing import Union


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, check=True, text=True)
    return p.stdout


def get_current_desktop() -> str:
    return run(["xdg-user-dir", "DESKTOP"]).strip()


def set_current_desktop(path: Union[str, Path]) -> None:
    run(["xdg-user-dirs-update", "--set", "DESKTOP", str(path)])
