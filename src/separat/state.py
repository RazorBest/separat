from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, get_args, get_origin, get_type_hints

from separat.storage import STATE_FILE, plasmaconf_dir, sessions_dir

if TYPE_CHECKING:
    from collections.abc import Iterable


def dataclass_from_dict(cls, data):
    kwargs = {}

    dataclass_hints = get_type_hints(cls)

    for fld in fields(cls):
        if not fld.init and fld.name not in data:
            continue
        value = data[fld.name]
        field_type = dataclass_hints[fld.name]

        if is_dataclass(field_type):
            value = dataclass_from_dict(field_type, value)
        elif get_origin(field_type) is list:
            item_type = get_args(field_type)[0]
            if is_dataclass(item_type):
                value = [dataclass_from_dict(item_type, x) for x in value]
        elif get_origin(field_type) is dict:
            _key_type, value_type = get_args(field_type)
            if is_dataclass(value_type):
                value = {key: dataclass_from_dict(value_type, x) for key, x in value.items()}

        kwargs[fld.name] = value

    return cls(**kwargs)


@dataclass
class ProfileData:
    name: str
    tmux_session_name: str
    firefox_profile: str
    firefox_pgid: int | None = None
    tmux_variables: dict[str, str] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def tmux_session_file(self) -> Path:
        return sessions_dir(self.name) / self.tmux_session_name

    def tmux_panes_file(self) -> Path:
        return sessions_dir(self.name) / "pane_contents.tar.gz"

    def plasmaconfig_file(self) -> Path:
        return plasmaconf_dir(self.name) / "plasmaconfig"

    def set_tmux_option(self, option: str, value: str):
        self.tmux_variables[option] = value

    def get_tmux_option(self, option: str) -> str | None:
        return self.tmux_variables.get(option, None)

    def tmux_options(self) -> Iterable[tuple[str, str]]:
        return self.tmux_variables.items()


def default_profile() -> ProfileData:
    profile = ProfileData(name="default", tmux_session_name="", firefox_profile="")
    return profile


@dataclass
class AppState:
    current_profile_name: str | None = None
    profiles: dict[str, ProfileData] = field(default_factory=dict)

    def __post_init__(self):
        has_default = any(p.name == "default" for p in self.profiles.values())
        if not has_default:
            p = default_profile()
            self.profiles[p.name] = p

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppState:
        if path is None:
            path = STATE_FILE
        path = Path(path)

        if not path.exists():
            return cls()

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return dataclass_from_dict(cls, data)

    def save(self, path: str | Path | None = None) -> None:
        if path is None:
            path = STATE_FILE
        path = Path(path)

        with path.open("w", encoding="utf-8") as file:
            json.dump(asdict(self), file, indent=2)

    def current_profile(self) -> ProfileData:
        if self.current_profile_name is None:
            raise RuntimeError("No active current profile")
        return self.profiles[self.current_profile_name]

    def profile_by_name(self, name: str) -> ProfileData | None:
        return self.profiles.get(name, None)

    def default_profile(self) -> ProfileData:
        return self.profiles["default"]

    def add_profile(self, profile: ProfileData):
        if profile.name in self.profiles:
            raise RuntimeError(f"Profile '{profile.name}' already exists")
        self.profiles[profile.name] = profile

    def set_current_profile(self, name: str) -> ProfileData:
        if (profile := self.profiles.get(name, None)) is None:
            raise RuntimeError(f"Profile '{name}' doesn't exist")
        self.current_profile_name = name

        return profile
