import tempfile
from pathlib import Path
from typing import Union

from separat.storage import TEMP_DATA


def filter_resurrect_file_for_session(path: Union[str, Path], session: str) -> bool:
    path = Path(path)
    selected = []
    with path.open("r", encoding="utf-8") as file:
        for line in file.readlines():
            if line.strip() == "":
                continue
            if line.split("\t")[1] == session:
                selected.append(line)

    with path.open("w", encoding="utf-8") as file:
        if len(selected) == 0:
            return False

        file.writelines(selected)

    return True


def filter_resurrect_file_no_session(path: Union[str, Path], session: str) -> bool:
    path = Path(path)
    selected = []
    with path.open("r", encoding="utf-8") as file:
        for line in file.readlines():
            if line.strip() == "":
                continue
            if line.split("\t")[1] != session:
                selected.append(line)

    with path.open("w", encoding="utf-8") as file:
        if len(selected) == 0:
            return False

        file.writelines(selected)

    return True


def copy_to_temp(path: Union[Union[str, Path]]) -> tempfile._TemporaryFileWrapper:
    path = Path(path)

    tmpcopy = tempfile.NamedTemporaryFile("wb", dir=TEMP_DATA, delete=False)
    tmpcopy.write(path.read_bytes())
    tmpcopy.flush()
    tmpcopy.close()

    return tmpcopy
