import os
from pathlib import Path

import separat.state as state_mod
from separat.core import TMUX_RESSURECT_DIR
from separat.inotify_simple import INotify, flags
from separat.state import AppState
from separat.util import filter_ressurect_file_for_session, copy_to_temp


def on_tmux_ressurect_change(state):
    last_path = TMUX_RESSURECT_DIR / "last"
    if not last_path.exists():
        return

    session_file = last_path.resolve()
    tmpcopy = copy_to_temp(session_file)

    has_session = filter_ressurect_file_for_session(tmpcopy.name, state.current_profile().tmux_session_name)

    if has_session:
        new_path = state_mod.SESSIONS_DIR / state.current_profile().tmux_session_name
        new_path.write_bytes(Path(tmpcopy.name).read_bytes())


def on_statefile_change():
    return AppState.load()


def watch_changes():
    state = AppState.load()

    inotify = INotify()
    watch_flags = flags.CREATE | flags.MODIFY
    wd_tmux = inotify.add_watch(TMUX_RESSURECT_DIR, watch_flags)
    print(state_mod.STATE_FILE)
    wd_state = inotify.add_watch(state_mod.STATE_FILE, watch_flags)
    
    while True:
        for evt in inotify.read():
            if evt.wd == wd_tmux:
                on_tmux_ressurect_change(state)
            elif evt.wd == wd_state:
                state = on_statefile_change()


def main():
    watch_changes()


if __name__ == "__main__":
    main()
