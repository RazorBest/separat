import os
import sys
import tarfile

import separat.state as state_mod
from separat.inotify_simple import INotify, flags
from separat.state import AppState
from separat.tmux import TMUX_RESSURECT_DIR
from separat.util import copy_to_temp, filter_resurrect_file_for_session


def on_tmux_resurrect_change(state) -> None:
    if state.current_profile_name is None:
        return None

    last_path = TMUX_RESSURECT_DIR / "last"
    if not last_path.exists():
        return None

    session_file = last_path.resolve()
    tmpcopy = copy_to_temp(session_file)

    has_session = filter_resurrect_file_for_session(tmpcopy.name, state.current_profile().tmux_session_name)

    if has_session:
        new_path = state.current_profile().tmux_session_file()
        os.rename(tmpcopy.name, new_path)

    try:
        profile = state.current_profile()
        session_name = profile.tmux_session_name
        pane_contents_path = TMUX_RESSURECT_DIR / "pane_contents.tar.gz"
        tmpcopy = copy_to_temp(pane_contents_path)

        panes_backup = tarfile.open(profile.tmux_panes_file(), "w:gz")

        tar = tarfile.open(tmpcopy.name, "r:gz")
        for member in tar.getmembers():
            if not member.name.startswith(f"./pane_contents/pane-{session_name}"):
                continue

            file = tar.extractfile(member)
            panes_backup.addfile(member, file)

        panes_backup.close()

    except tarfile.ReadError:
        # tar.gz file is not ready
        pass


def on_statefile_change() -> AppState:
    return AppState.load()


def watch_changes() -> None:
    state = AppState.load()

    inotify = INotify()
    watch_flags = flags.CREATE | flags.MODIFY
    wd_tmux = inotify.add_watch(TMUX_RESSURECT_DIR, watch_flags)
    print(state_mod.STATE_FILE)
    wd_state = inotify.add_watch(state_mod.STATE_FILE, watch_flags)

    while True:
        for evt in inotify.read():
            if evt.wd == wd_tmux:
                on_tmux_resurrect_change(state)
            elif evt.wd == wd_state:
                state = on_statefile_change()


def main() -> int:
    watch_changes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
