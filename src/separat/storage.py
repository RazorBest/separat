import os
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# Reference: https://specifications.freedesktop.org/basedir/latest/
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share").strip()).expanduser()
XDG_STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state").strip()).expanduser()
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config").strip()).expanduser()
XDG_CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache").strip()).expanduser()

TEMP_DATA = ensure_dir(XDG_CACHE_HOME / "separat_python")
LOCAL_DATA = ensure_dir(XDG_DATA_HOME / "separat_python")
STATE_FILE = LOCAL_DATA / "state.json"
PROFILES_DIR = ensure_dir(LOCAL_DATA / "profiles")


def sessions_dir(profile_name: str) -> Path:
    return PROFILES_DIR / profile_name / "sessions"


def desktop_dir(profile_name: str) -> Path:
    return PROFILES_DIR / profile_name / "Desktop"


def plasmaconf_dir(profile_name: str) -> Path:
    return PROFILES_DIR / profile_name / "plasma_config"
