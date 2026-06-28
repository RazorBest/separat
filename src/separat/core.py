import json
import os
import random
import shutil
import signal
import string
import tarfile
import time
from pathlib import Path
from typing import Union

import separat.firefox_profile as firefox
from separat.plasma_config import (
    export_plasma_desktops_config,
    replace_plasma_desktops_config,
    restart_plasma,
)
from separat.state import AppState, ProfileData
from separat.storage import desktop_dir
from separat.tmux import (
    TMUX_RESSURECT_DIR,
    TmuxManager,
    remove_session_from_panes,
    remove_session_from_resurrect,
    resurrect_restore_tmux,
    stop_tmux_session,
    sync_panes_with_session,
    sync_resurrect_with_session,
)
from separat.util import copy_to_temp, filter_resurrect_file_no_session
from separat.xdg_desktop import get_current_desktop, set_current_desktop


def create_profile(state: AppState, name: str) -> None:
    if state.profile_by_name(name) is not None:
        raise ValueError(f"Profile with {name} already exists")

    tmux_session_name = name
    firefox_profile = f"{name}_separat"

    firefox.create_profile(firefox_profile)

    os.makedirs(
        desktop_dir(name),
    )

    # TODO: change theme of profile

    profile = ProfileData(
        name=name,
        tmux_session_name=tmux_session_name,
        firefox_profile=firefox_profile,
    )

    # Plasma state
    if not state.default_profile().plasmaconfig_file().exists():
        if state.current_profile_name is not None:
            raise RuntimeError("Invalid state. Can't have a current profile without a default saved plasma config")
        default_plasmaconfig = export_plasma_desktops_config()
        store_default_plasmaconfig(state, default_plasmaconfig)
    src = state.default_profile().plasmaconfig_file()
    dst = profile.plasmaconfig_file()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

    state.add_profile(profile)
    state.save()


def set_active_profile(state: AppState, name: str) -> ProfileData:
    profile = state.set_current_profile(name)
    state.save()

    return profile


def set_current_profile_firefox_pgid(state: AppState, pgid: int) -> None:
    state.current_profile().firefox_pgid = pgid
    state.save()


def merge_saved_profile_with_resurrect(profile: ProfileData, tmux_session_name: str) -> None:
    session_path = profile.tmux_session_file()
    profile_panes_file = profile.tmux_panes_file()
    if session_path.exists():
        last_link = TMUX_RESSURECT_DIR / "last"
        real_file = last_link.resolve()
        tmpcopy = copy_to_temp(real_file)
        filter_resurrect_file_no_session(tmpcopy.name, tmux_session_name)

        with open(tmpcopy.name, "wb+") as file:
            file.write(b"\n")
            file.write(Path(session_path).read_bytes())

        os.rename(tmpcopy.name, real_file)

    if profile_panes_file.exists():
        # Pane contents
        pane_contents_path = TMUX_RESSURECT_DIR / "pane_contents.tar.gz"
        tmpcopy1 = copy_to_temp(pane_contents_path)
        tmpcopy2 = copy_to_temp(tmpcopy1.name)

        src1 = tarfile.open(tmpcopy1.name, "r:gz")
        src2 = tarfile.open(profile_panes_file, "r:gz")
        dst = tarfile.open(tmpcopy2.name, "w:gz")

        for member in src1.getmembers():
            if member.name.startswith(f"./pane_contents/pane-{tmux_session_name}"):
                continue
            filetmp = src1.extractfile(member)
            dst.addfile(member, filetmp)

        for member in src2.getmembers():
            filetmp = src2.extractfile(member)
            dst.addfile(member, filetmp)

        dst.close()
        os.rename(tmpcopy2.name, pane_contents_path)


def set_default_profile_desktop(state: AppState, desktop_path: Union[str, Path]) -> None:
    state.default_profile().extra["desktop_path"] = desktop_path
    state.save()


def store_plasmaconfig_for_profile(profile: ProfileData, plasma_config: dict) -> None:
    conf_file = profile.plasmaconfig_file()
    conf_file.parent.mkdir(parents=True, exist_ok=True)
    with open(conf_file, "w") as file:
        json.dump(plasma_config, file)


def replace_plasmaconfig_from_profile(profile: ProfileData) -> None:
    with open(profile.plasmaconfig_file()) as file:
        data = json.load(file)
        replace_plasma_desktops_config(data)


def store_default_plasmaconfig(state: AppState, plasma_config: dict) -> None:
    profile = state.default_profile()
    store_plasmaconfig_for_profile(profile, plasma_config)


def launch_profile(state: AppState, name: str) -> None:
    if state.current_profile_name is not None:
        raise ValueError("A different profile is active")

    profile = set_active_profile(state, name)

    # Firefox
    proc = firefox.start_with_profile(profile.firefox_profile)
    set_current_profile_firefox_pgid(state, proc.pid)

    # Tmux
    tmux_manager = TmuxManager()
    tmux_manager.disable_continuum()
    try:
        merge_saved_profile_with_resurrect(profile, profile.tmux_session_name)
        rand_session = "".join(random.choices(string.ascii_letters, k=16))
        # Use a dummy session to be able to run resurrect
        # We should use the profile session, because the contents of existing panes are not restored
        tmux_manager.start_tmux_session(rand_session)
        resurrect_restore_tmux()
        stop_tmux_session(rand_session)
    finally:
        tmux_manager.enable_continuum()

    # WARNING: The plasma config file is changed when we change the desktop.
    # That's why we have to save it before changing the Desktop.
    # Plasma state
    default_plasmaconfig = export_plasma_desktops_config()
    store_default_plasmaconfig(state, default_plasmaconfig)
    # restart_plasma()

    # Desktop directory
    if (prev_desktop := get_current_desktop()) != "":
        set_default_profile_desktop(state, prev_desktop)
        set_current_desktop(desktop_dir(name))

    time.sleep(0.5)
    replace_plasmaconfig_from_profile(profile)
    restart_plasma()


def stop_profile(state: AppState) -> None:
    profile = state.current_profile()

    try:
        if profile.firefox_pgid is not None:
            os.killpg(profile.firefox_pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    profile.firefox_pgid = None

    tmux_session_name = profile.tmux_session_name
    sync_resurrect_with_session(profile.tmux_session_file(), tmux_session_name)
    sync_panes_with_session(profile.tmux_panes_file(), tmux_session_name)
    remove_session_from_resurrect(tmux_session_name)
    remove_session_from_panes(tmux_session_name)

    # WARNING: The plasma config file is changed when we change the desktop.
    # That's why we have to save it before changing the Desktop.
    # Plasma state
    plasmaconfig = export_plasma_desktops_config()
    store_plasmaconfig_for_profile(profile, plasmaconfig)

    if get_current_desktop() != "":
        default_desktop = state.default_profile().extra["desktop_path"]
        set_current_desktop(default_desktop)

    time.sleep(0.5)
    replace_plasmaconfig_from_profile(state.default_profile())
    restart_plasma()

    state.current_profile_name = None
    state.save()

    # This can stop this process if it was launched from the tmux session that we're about to kill
    stop_tmux_session(tmux_session_name)


def switch_profile(state: AppState, name: str) -> None:
    old_profile = state.current_profile()
    old_tmux_session = old_profile.tmux_session_name
    if (new_profile := state.profile_by_name(name)) is None:
        raise RuntimeError("Profile {name} doesn't exist")
    new_tmux_session = new_profile.tmux_session_name

    # Firefox
    try:
        if old_profile.firefox_pgid is not None:
            os.killpg(old_profile.firefox_pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    old_profile.firefox_pgid = None
    proc = firefox.start_with_profile(new_profile.firefox_profile)

    # Tmux
    tmux_manager = TmuxManager()
    tmux_manager.disable_continuum()
    try:
        sync_resurrect_with_session(old_profile.tmux_session_file(), old_tmux_session)
        remove_session_from_resurrect(old_tmux_session)
        sync_panes_with_session(old_profile.tmux_panes_file(), old_tmux_session)
        remove_session_from_panes(old_tmux_session)

        merge_saved_profile_with_resurrect(new_profile, new_tmux_session)

        resurrect_restore_tmux()
        stop_tmux_session(old_tmux_session)
    finally:
        tmux_manager.enable_continuum()

    # WARNING: The plasma config file is changed when we change the desktop.
    # That's why we have to save it before changing the Desktop.
    # Plasma state
    plasmaconfig = export_plasma_desktops_config()
    store_plasmaconfig_for_profile(old_profile, plasmaconfig)

    # Desktop
    if get_current_desktop() != "":
        default_desktop = state.default_profile().extra["desktop_path"]
        set_current_desktop(default_desktop)

    if (prev_desktop := get_current_desktop()) != "":
        if state.current_profile_name is None or old_profile.name == "default":
            set_default_profile_desktop(state, prev_desktop)
        set_current_desktop(desktop_dir(name))

    time.sleep(0.5)
    replace_plasmaconfig_from_profile(new_profile)
    restart_plasma()

    state.current_profile_name = None

    set_active_profile(state, name)
    set_current_profile_firefox_pgid(state, proc.pid)

    state.save()


def exec_into_tmux_current_session(state: AppState) -> None:
    session_name = state.current_profile().tmux_session_name
    os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])
