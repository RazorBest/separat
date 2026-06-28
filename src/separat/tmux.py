import os
import subprocess
import tarfile
from pathlib import Path
from typing import Optional, Union

from separat.util import (
    copy_to_temp,
    filter_resurrect_file_for_session,
    filter_resurrect_file_no_session,
)

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
TMUX_RESSURECT_DIR = DATA_HOME / "tmux" / "resurrect"


def run_tmux(args: list[str]) -> str:
    p = subprocess.run(["tmux", *args], capture_output=True, check=True, text=True)

    return p.stdout


def remove_session_from_panes(session_name: str) -> None:
    pane_contents_path = TMUX_RESSURECT_DIR / "pane_contents.tar.gz"
    if not pane_contents_path.exists():
        return None

    tmpcopy1 = copy_to_temp(pane_contents_path)
    tmpcopy2 = copy_to_temp(tmpcopy1.name)

    src = tarfile.open(tmpcopy1.name, "r:gz")
    dst = tarfile.open(tmpcopy2.name, "w:gz")
    for member in src.getmembers():
        if member.name.startswith(f"./pane_contents/pane-{session_name}"):
            continue

        file = src.extractfile(member)
        dst.addfile(member, file)

    dst.close()
    os.rename(tmpcopy2.name, pane_contents_path)


def remove_session_from_resurrect(session_name: str) -> None:
    last_link = TMUX_RESSURECT_DIR / "last"

    real_file = last_link.resolve()
    tmpcopy = copy_to_temp(real_file)

    filter_resurrect_file_no_session(tmpcopy.name, session_name)
    os.rename(tmpcopy.name, real_file)


def sync_panes_with_session(profile_panels_file: Union[str, Path], session_name: str) -> None:
    profile_panels_file = Path(profile_panels_file)
    pane_contents_path = TMUX_RESSURECT_DIR / "pane_contents.tar.gz"
    if not pane_contents_path.exists():
        return None

    tmpcopy1 = copy_to_temp(pane_contents_path)
    tmpcopy2 = copy_to_temp(tmpcopy1.name)

    src = tarfile.open(tmpcopy1.name, "r:gz")
    dst = tarfile.open(tmpcopy2.name, "w:gz")
    for member in src.getmembers():
        if not member.name.startswith(f"./pane_contents/pane-{session_name}"):
            continue

        file = src.extractfile(member)
        dst.addfile(member, file)

    dst.close()
    os.rename(tmpcopy2.name, profile_panels_file)


def sync_resurrect_with_session(profile_session_file: Union[str, Path], session_name: str) -> None:
    profile_session_file = Path(profile_session_file)
    last_link = TMUX_RESSURECT_DIR / "last"
    if not last_link.exists():
        return None
    real_file = last_link.resolve()
    tmpcopy = copy_to_temp(real_file)
    has_session = filter_resurrect_file_for_session(tmpcopy.name, session_name)

    if has_session:
        profile_session_file.parent.mkdir(parents=True, exist_ok=True)
        os.rename(tmpcopy.name, profile_session_file)


class TmuxManager:
    def __init__(self) -> None:
        self.continuum_save_interval: Optional[str] = None
        self.local_continuum_enabled: Optional[bool] = None

    def disable_continuum(self) -> None:
        try:
            output = run_tmux(["show-options", "-g", "@continuum-save-interval"])
            value = output.strip().split(" ")[1]
            if value == "0":
                return None

            self.continuum_save_interval = value

            run_tmux(["set", "-g", "@continuum-save-interval", "0"])
        except subprocess.CalledProcessError:
            self.local_continuum_enabled = False

    def enable_continuum(self) -> None:
        try:
            output = run_tmux(["show-options", "-g", "@continuum-save-interval"])
            prev_value = output.strip().split(" ")[1]
            if prev_value != "0":
                self.local_continuum_enabled = True
                return None

            value = self.continuum_save_interval
            if value is None:
                raise ValueError("Continuum can't be enabled without knowing the previous @continuum-save-interval")

            run_tmux(["set", "-g", "@continuum-save-interval", value])
            self.continuum_save_interval = None
            self.local_continuum_enabled = True
        except subprocess.CalledProcessError:
            self.local_continuum_enabled = True

    def start_tmux_session(self, session: str) -> None:
        run_tmux(["new-session", "-s", session, "-d"])

        if not self.local_continuum_enabled:
            self.disable_continuum()

    def replace_tmux_session(self, old_session: str, new_session: str) -> None:
        # Create detached new session
        self.start_tmux_session(new_session)

        # Switch all the clients to the new session
        output = run_tmux(["list-clients", "-t", old_session])
        lines = output.strip().split("\n")
        ptys = [line.split(" ")[0] for line in lines]
        for pty in ptys:
            run_tmux(["switch-client", "-c", pty, "-t", new_session])

        stop_tmux_session(old_session)


def stop_tmux_session(session: str) -> Optional[str]:
    try:
        return run_tmux(["kill-session", "-t", session])
    except subprocess.CalledProcessError:
        return None


def resurrect_restore_tmux() -> None:
    output = run_tmux(["list-keys"])

    lines = output.strip().split("\n")
    restore_script_path = None
    for line in lines:
        if "tmux-resurrect/scripts/restore.sh" not in line:
            continue

        words = line.strip().split()
        restore_script_path = words[5]
        if "tmux-resurrect/scripts/restore.sh" not in restore_script_path:
            raise RuntimeError("Restore command has an unexpected format")
        break

    if restore_script_path is None:
        raise RuntimeError("Can't find the restore command. Is resurrect installed?")

    run_tmux(["run-shell", restore_script_path])


def already_in_tmux_environment() -> bool:
    # TODO
    return False
