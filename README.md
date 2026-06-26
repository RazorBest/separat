# Separat: workspace isolation for Linux

Organize your work into workspaces: a Firefox profile, a tmux session and a Desktop. Keep them after restart and resume your work with minimal friction.

## Installation

Separat ships with a CLI. Since most Linux distros noew enforce externally managed environments, you will need to install this module under an environment.

Here are multiple alternatives:

1. Use pipx (which automatically creates an environment):
```
pipx install git+https://github.com/RazorBest/separat.git
```

2. With uv as a persistent tool:
```
uv tool install git+https://github.com/RazorBest/separat.git
```

3. In an self-managed environment:
```
python -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/RazorBest/separat.git
```

## Getting started

Create and enter in a workspace:
```
separat create <workspace name>
separat switch <workspace name>
```

Stop the current workspace:
```
separat stop
```

Only one workspace is active at a time. To change the workspace:
```
separat switch <another workspace name>
```

All commands:
```
$ separat --help
usage: separat [-h] {switch,stop,create,remove,list} ...

Workflow separator with firefox and tmux

positional arguments:
  {switch,stop,create,remove,list}
    switch              switch to a workspace
    stop                stop the current workspace
    create              create a workspace
    remove              remove a workspace
    list                list all available workspaces

options:
  -h, --help            show this help message and exit
```
