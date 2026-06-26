import os
import signal
from pathlib import Path
from uuid import uuid4

import separat.state as state_mod
import separat.firefox_profile as firefox
from separat.state import AppState, ProfileData
from separat.tmux import remove_session_from_resurrect, resurrect_restore_tmux, stop_tmux_session, TMUX_RESSURECT_DIR, TmuxManager
from separat.util import copy_to_temp, filter_resurrect_file_no_session, filter_resurrect_file_for_session


def create_profile(state: AppState, name: str):
    if state.profile_by_name(name) is not None:
        raise ValueError(f"Profile with {name} already exists")

    tmux_session_name = name
    firefox_profile= f"{name}_separat"
    uuid = str(uuid4())

    firefox.create_profile(firefox_profile)

    # TODO: change theme of profile

    profile = ProfileData(
        uuid=uuid,
        name=name,
        tmux_session_name=tmux_session_name,
        firefox_profile=firefox_profile
    )

    state.profiles[uuid] = profile
    state.save()


def set_active_profile(state: AppState, name: str) -> ProfileData:
    if (profile := state.profile_by_name(name)) is None:
        raise ValueError(f"Profile with {name} doesn't exist")

    state.current_profile_uuid = profile.uuid
    state.save()

    return profile


def set_current_profile_firefox_pgid(state: AppState, pgid: int):
    state.current_profile().firefox_pgid = pgid
    state.save()


"""
def link_resurrect_last_session_to_profile(state: AppState, name: str):
    session_path = state_mod.SESSIONS_DIR / state.profile_by_name(name).tmux_session_name
    last_link = TMUX_RESSURECT_DIR / "last"

    if last_link.is_symlink() or last_link.exists():
        last_link.unlink()

    last_link.symlink_to(session_path)
"""


def merge_saved_profile_with_resurrect(tmux_session_name: str):
    session_path = state_mod.SESSIONS_DIR / tmux_session_name
    if not session_path.exists():
        return

    last_link = TMUX_RESSURECT_DIR / "last"
    real_file = last_link.resolve()
    tmpcopy = copy_to_temp(real_file)
    filter_resurrect_file_no_session(tmpcopy.name, tmux_session_name)

    with open(tmpcopy.name, "wb+") as file:
        file.write(b"\n")
        file.write(Path(session_path).read_bytes())

    real_file.write_bytes(Path(tmpcopy.name).read_bytes())


def sync_resurrect_with_session(tmux_session_name: str):
    last_link = TMUX_RESSURECT_DIR / "last"
    if not last_link.exists():
        return
    real_file = last_link.resolve()
    tmpcopy = copy_to_temp(real_file)
    has_session = filter_resurrect_file_for_session(tmpcopy.name, tmux_session_name)

    if has_session:
        session_path = state_mod.SESSIONS_DIR / tmux_session_name
        session_path.write_bytes(Path(tmpcopy.name).read_bytes())


def launch_profile(state: AppState, name: str):
    if state.current_profile_uuid is not None:
        raise ValueError("A different profile is active")

    profile = set_active_profile(state, name)

    # Firefox
    proc = firefox.start_with_profile(profile.firefox_profile)
    set_current_profile_firefox_pgid(state, proc.pid)

    # Tmux
    tmux_manager = TmuxManager()
    tmux_manager.disable_continuum()
    try:
        merge_saved_profile_with_resurrect(profile.tmux_session_name)
        tmux_manager.start_tmux_session(profile.tmux_session_name)
        resurrect_restore_tmux(profile.tmux_session_name)
    finally:
        tmux_manager.enable_continuum()


def stop_profile(state: AppState):
    profile = state.current_profile()
    try:
        os.killpg(profile.firefox_pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    profile.firefox_pgid = None

    tmux_session_name = profile.tmux_session_name
    sync_resurrect_with_session(profile.tmux_session_name)
    remove_session_from_resurrect(tmux_session_name)

    state.current_profile_uuid = None
    state.save()

    stop_tmux_session(tmux_session_name)


def switch_profile(state: AppState, name: str):
    old_profile = state.current_profile()
    old_tmux_session = old_profile.tmux_session_name
    new_profile = state.profile_by_name(name)
    new_tmux_session = new_profile.tmux_session_name

    # Firefox
    try:
        os.killpg(old_profile.firefox_pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    old_profile.firefox_pgid = None
    proc = firefox.start_with_profile(new_profile.firefox_profile)

    # Tmux
    tmux_manager = TmuxManager()
    tmux_manager.disable_continuum()
    try:
        sync_resurrect_with_session(profile.tmux_session_name)
        remove_session_from_resurrect(old_tmux_session)
        merge_saved_profile_with_resurrect(profile.tmux_session_name)
        tmux_manager.replace_tmux_session(old_tmux_session, new_tmux_session)
        resurrect_restore_tmux(new_tmux_session)
    finally:
        tmux_manager.enable_continuum()

    state.current_profile_uuid = None

    set_active_profile(state, name)
    set_current_profile_firefox_pgid(state, proc.pid)

    state.save()


def exec_into_tmux_current_session(state: AppState):
    session_name = state.current_profile().tmux_session_name
    os.execvp(
        "tmux",
        ["tmux", "attach-session", "-t", session_name]
    )
