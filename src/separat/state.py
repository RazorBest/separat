import json
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import get_args, get_origin, Optional


STATE_FILE = Path(sys.path[0]) / "state.json"
LOCAL_DATA = Path(sys.path[0]) / "data"
SESSIONS_DIR = LOCAL_DATA / "sessions"


def dataclass_from_dict(cls, data):
    kwargs = {}

    for field in fields(cls):
        value = data[field.name]
        field_type = field.type

        if is_dataclass(field_type):
            value = from_dict(field_type, value)
        elif get_origin(field_type) is list:
            item_type = get_args(field_type)[0]
            if is_dataclass(item_type):
                value = [dataclass_from_dict(item_type, x) for x in value]
        elif get_origin(field_type) is dict:
            _key_type, value_type = get_args(field_type)
            if is_dataclass(value_type):
                value = {key: dataclass_from_dict(value_type, x) for key, x in value.items()}

        kwargs[field.name] = value

    return cls(**kwargs)


@dataclass
class ProfileData:
    uuid: str
    name: str
    tmux_session_name: str
    firefox_profile: str
    firefox_pgid: Optional[int] = None


@dataclass
class AppState:
    current_profile_uuid: Optional[str] = None
    profiles: dict[str, ProfileData] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "AppState":
        if path is None:
            path = STATE_FILE
        path = Path(path)

        if not path.exists():
            return cls()

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return dataclass_from_dict(cls, data)

    def save(self, path: Optional[str | Path] = None):
        if path is None:
            path = STATE_FILE
        path = Path(path)

        with path.open("w", encoding="utf-8") as file:
            json.dump(asdict(self), file, indent=2)

    def current_profile(self) -> ProfileData:
        return self.profiles[self.current_profile_uuid]

    def profile_by_name(self, name: str) -> Optional[ProfileData]:
        return next((p for p in self.profiles.values() if p.name == name), None)
