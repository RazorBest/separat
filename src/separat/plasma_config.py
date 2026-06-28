"""

The structure of the config file is not very well documented. In this case, the best documentation is an example:

```
...
[Containments][2]
ItemGeometries-1745x982=
ItemGeometriesHorizontal=
activityId=a3b634f3-ad76-4da6-913e-2ddd89cec22c
formfactor=0
immutability=1
lastScreen=1
location=0
plugin=org.kde.plasma.folder
wallpaperplugin=org.kde.image

[Containments][2][ConfigDialog]
DialogHeight=540
DialogWidth=720

[Containments][2][General]
positions={"1527x955":[],"1745x982":[],"1920x1080":[]}

[Containments][2][Wallpaper][org.kde.image][General]
Image=/usr/share/backgrounds/blue-but-somewhere-else.jpg
SlidePaths=/usr/share/wallpapers/
...
```

Containments are some primary units used by KDE. For example, your task bar on the bottom and your time widged on the Desktop are each represented by a Containment.
Similarly, the Desktop is also represented by a containment.

"""

import configparser
import os
import subprocess

from separat.storage import XDG_CONFIG_HOME
from separat.util import copy_to_temp

PLASMA_CONFIG_PATH = XDG_CONFIG_HOME / "plasma-org.kde.plasma.desktop-appletsrc"


def export_plasma_desktops_config() -> dict:
    conf = configparser.ConfigParser()
    # Preserves casing
    conf.optionxform = str  # type: ignore[method-assign,assignment]
    conf.read(PLASMA_CONFIG_PATH)

    desktop_containments: dict[str, dict[str, list[tuple[str, str]]]] = {}

    for section in conf.sections():
        if not section.startswith("Containments"):
            continue

        _, index, *subsec_elems = section.split("][")
        subsec = "][".join(subsec_elems)

        if index in desktop_containments:
            desktop_containments[index][subsec] = list(conf[section].items())
        elif conf[section].get("plugin", None) == "org.kde.plasma.folder" and conf[section].get("wallpaperplugin", None) == "org.kde.image":
            desktop_containments[index] = {}
            desktop_containments[index][""] = list(conf[section].items())

    return desktop_containments


def sort_configparser_sections(conf: configparser.ConfigParser) -> None:
    sections = conf.sections()
    sections = sorted(sections)

    opts = []
    for section in sections:
        opts.append((section, list(conf[section].items())))
        conf.remove_section(section)

    for section, opt in opts:
        conf.add_section(section)
        for key, val in opt:
            conf[section][key] = val


def replace_plasma_desktops_config(desktop_containments: dict) -> None:
    """Removes all the deskstop sections from the config and replaces them with
    the ones given by the arguments."""

    tempconfig = copy_to_temp(PLASMA_CONFIG_PATH)
    conf = configparser.ConfigParser()
    # Preserves casing
    conf.optionxform = str  # type: ignore[method-assign,assignment]
    conf.read(tempconfig.name)

    # First remove the old ones
    old_containments = set()
    for section in conf.sections():
        if not section.startswith("Containments"):
            continue

        index = section.split("][")[1]
        if index in old_containments:
            conf.remove_section(section)

        elif conf[section].get("plugin", None) == "org.kde.plasma.folder" and conf[section].get("wallpaperplugin", None) == "org.kde.image":
            # This is the first section of the Containment with this index
            old_containments.add(index)
            conf.remove_section(section)

    # Now, add the new ones
    for index, subsections in desktop_containments.items():
        for subsec, options in subsections.items():
            section = f"Containments][{index}][{subsec}"
            section = section.removesuffix("][")

            conf.add_section(section)
            for key, val in options:
                conf[section][key] = val

    sort_configparser_sections(conf)

    with open(tempconfig.name, "w") as file:
        conf.write(file, space_around_delimiters=False)

    os.rename(tempconfig.name, PLASMA_CONFIG_PATH)


def restart_plasma() -> None:
    subprocess.Popen(
        ["plasmashell", "--replace"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
