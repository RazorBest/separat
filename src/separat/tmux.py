import os
import subprocess
from pathlib import Path
from typing import Optional

import separat.state as state_mod
from separat.util import filter_resurrect_file_no_session, copy_to_temp


DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
TMUX_RESSURECT_DIR = DATA_HOME / "tmux" / "resurrect"


def run_tmux(args: list[str]): 
    p = subprocess.run(["tmux", *args], capture_output=True, check=True, text=True)

    return p.stdout


def remove_session_from_resurrect(session_name: str):
    session_path = state_mod.SESSIONS_DIR / session_name
    last_link = TMUX_RESSURECT_DIR / "last"

    real_file = last_link.resolve()
    tmpcopy = copy_to_temp(real_file)

    filter_resurrect_file_no_session(tmpcopy.name, session_name)
    real_file.write_bytes(Path(tmpcopy.name).read_bytes())


class TmuxManager:
    def __init__(self):
        self.continuum_save_interval = None
        self.local_continuum_enabled: Optional[bool] = None

    def disable_continuum(self):
        try:
            output = run_tmux(["show-options", "-g", "@continuum-save-interval"])
            value = output.strip().split(" ")[1]
            if value == "0":
                return

            self.continuum_save_interval = value

            run_tmux(["set", "-g", "@continuum-save-interval", "0"])
        except:
            self.local_continuum_enabled = False


    def enable_continuum(self):
        try:
            output = run_tmux(["show-options", "-g", "@continuum-save-interval"])
            prev_value = output.strip().split(" ")[1]
            if prev_value != "0":
                self.local_continuum_enabled = True
                return

            value = self.continuum_save_interval
            if value is None:
                raise ValueError("Continuum can't be enabled without knowing the previous @continuum-save-interval")

            run_tmux(["set", "-g", "@continuum-save-interval", value])
            self.continuum_save_interval = None
            self.local_continuum_enabled = True
        except:
            self.local_continuum_enabled = True

    def start_tmux_session(self, session: str):
        run_tmux(["new-session", "-s", session, "-d"])

        if not self.local_continuum_enabled:
            self.disable_continuum()

    def replace_tmux_session(self, old_session: str, new_session: str):
        # Create detached new session
        self.start_tmux_session(new_session)

        # Switch all the clients to the new session
        output = run_tmux(["list-clients", "-t", old_session])
        lines = output.strip().split("\n")
        ptys = [line.split(" ")[0] for line in lines]
        for pty in ptys:
            run_tmux(["switch-client", "-c", pty, "-t", new_session])

        stop_tmux_session(old_session) 


def stop_tmux_session(session: str):
    try:
        return run_tmux(["kill-session", "-t", session])
    except:
        return None


def resurrect_restore_tmux(session: str):
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

    run_tmux(["run-shell", "-t", session, restore_script_path])
