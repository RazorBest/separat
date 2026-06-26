import argparse
import os
from pathlib import Path

import separat.state as state_mod
from separat.core import create_profile, exec_into_tmux_current_session, launch_profile, stop_profile, switch_profile
from separat.state import AppState


BASE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))


def get_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="separat",
        description="Workflow separator with firefox and tmux",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subp = subparsers.add_parser("switch", help="switch to a workspace")
    # subp.add_argument(metavar="workspace", dest="switch")
    subp.add_argument("workspace")

    subp = subparsers.add_parser("stop", help="stop the current workspace")

    subp = subparsers.add_parser("create", help="create a workspace")
    # subp.add_argument(metavar="workspace", dest="create")
    subp.add_argument("workspace")

    subp = subparsers.add_parser("remove", help="remove a workspace")
    # subp.add_argument(metavar="workspace", dest="remove")
    subp.add_argument("workspace")

    subp = subparsers.add_parser("list", help="list all available workspaces")

    return parser.parse_args()


def do_switch(workspace: str):
    state = AppState.load()

    if state.profile_by_name(workspace) is None:
        print(f"Workspace {workspace} doesn't exist")
        return 1

    if state.current_profile_uuid is not None:
        curr = state.current_profile()
        if curr.name == workspace:
            print(f"Workspace {workspace} is already active")
            return 0
        switch_profile(state, worksapce)
    else:
        launch_profile(state, workspace)
        # This doens't return
        exec_into_tmux_current_session(state)

    return 0


def do_create(workspace: str) -> int:
    state = AppState.load()
    try:
        create_profile(state, workspace)
    except ValueError:
        print(f"Profile with {workspace} already exists")
        return 1

    return 0


def do_stop():
    state = AppState.load()
    # If already exists, return error
    if state.current_profile_uuid is None:
        print(f"No active profile to stop")
        return 0

    stop_profile(state) 
    return 0


def do_remove():
    state = AppState.load()
    if state.current_profile_uuid is not None:
        do_stop()

    # If active, stop. hard
    pass


def do_list():
    state = AppState.load()
    names = [p.name for p in state.profiles.values()]
    print(f"Profiles: {' '.join(names)}")


CMD_DISPATCH = {"switch": do_switch, "create": do_create, "stop": do_stop, "remove": do_remove, "list": do_list}


def main():
    args = get_args()

    do_func = CMD_DISPATCH[args.command]
    kwargs = (vars(args))
    del kwargs["command"]

    ret = do_func(**kwargs)

    return ret

if __name__ == "__main__":
    exit(main())
