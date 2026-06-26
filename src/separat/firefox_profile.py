from __future__ import annotations

import configparser
import html
import json
import os
import subprocess
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


from separat.util import copy_to_temp


themes = {
        "Frostlit": "{74da71cc-4d66-48f5-95d1-1f017f18ffab}",
        "Blue & Yellow": "{b2e6a461-610a-4882-8329-9ebc7164115b}",
        "Magical aristocracy": "{32965c32-d2e9-4b17-b9e4-c52b26f9ed08}",
        "Activist – Balanced": "activist-balanced-colorway@mozilla.org",
        "Visionary – Balanced": "visionary-balanced-colorway@mozilla.org",
        "Innovator – Balanced": "innovator-balanced-colorway@mozilla.org",
        "Dream of Waves": "{a07400bb-b55c-4435-906d-5b6d8303f4c1}",
        "Crocus flowerses Easter": "{c66a6c92-ee14-48fc-8814-93ed174f42d1}",
        "Senzune Fractal Luster": "{9904367c-ae9c-4b2d-b0ad-85e676269497}",
}


HOME = Path(os.path.expanduser("~"))
FIREFOX_DIR = HOME / ".config/mozilla/firefox"
COPY_FROM_PROFILE = [
    "user.js",
    "prefs.js",
    "extensions",
    "extensions.json",
    "extensions-settings.json",
    "extensions-preferences.json",
    "browser-extension-data",
    "search.json.mozlz4",
    "xulstore.json",
]


def run(cmd: str):
    p = subprocess.run(cmd, shell="True", capture_output=True, check=True, text=True)

    return p.stdout


def get_default_profile_path() -> Path:
    firefox_profiles_ini = FIREFOX_DIR / "profiles.ini"
    default_profile_file = None
    with open(firefox_profiles_ini) as file:
        install_section = False
        for line in file.readlines():
            if line.startswith("[Install"):
                install_section = True
            elif line[0] == "[":
                install_section = False
            elif install_section and line.startswith("Default="):
                default_profile_file = line.split("Default=")[1].strip()
                break

    default_profile_path = FIREFOX_DIR / default_profile_file

    return Path(default_profile_path)


@dataclass
class Bookmark:
    guid: str = ""
    title: str = ""
    index: int = 0
    dateAdded: int = 0
    lastModified: int = 0
    id_: int = 0
    typeCode: int = -1
    type_: str = field(init=False)
    root: Optional[str] = field(init=False)
    children: list[Bookmark] = field(default_factory=list)
    uri: Optional[str] = None

    def __post_init__(self):
        if self.typeCode == 1:
            self.type_ = "text/x-moz-place"
        elif self.typeCode == 2:
            self.type_ = "text/x-moz-place-container"
        elif self.typeCode == -1:
            # Dummy bookmark
            self.type_ = None
        else:
            raise ValueError(f"Unknown typeCode: {self.typeCode}")

        if self.guid == "root________":
            self.root = "placesRoot"
        elif self.guid == "menu________":
            self.root = "bookmarksMenuFolder"
        elif self.guid == "toolbar_____":
            self.root = "toolbarFolder"
        elif self.guid == "unfiled_____":
            self.root = "unfiledBookmarksFolder"
        elif self.guid == "mobile______":
            self.root = "mobileFolder"
        else:
            self.root = None

    def to_dict(self):
        data = {
            "type": self.type_,
            "id": self.id_,
            "guid": self.guid,
            "title": self.title,
            "index": self.index,
            "dateAdded": self.dateAdded,
            "lastModified": self.lastModified,
            "id": self.id_,
            "typeCode": self.typeCode,
            "type": self.type_,
        }

        if self.root is not None:
            data["root"] = self.root

        if self.uri is not None:
            data["uri"] = self.uri

        if len(self.children) > 0:
            children_data = []
            for child in self.children:
                children_data.append(child.to_dict())

            data["children"] = children_data

        return data


def read_bookmarks(profile_path: str | Path) -> Bookmark:
    profile_path = Path(profile_path)

    db_path = profile_path / "places.sqlite"
    tempfile = copy_to_temp(db_path)
    uri = f"file:{tempfile.name}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()

    """
    From the schema:
    CREATE TABLE moz_bookmarks (
        id INTEGER PRIMARY KEY,
        type INTEGER,
        fk INTEGER DEFAULT NULL,
        parent INTEGER,
        position INTEGER,
        title LONGVARCHAR,
        keyword_id INTEGER,
        folder_type TEXT,
        dateAdded INTEGER,
        lastModified INTEGER,
        guid TEXT,
        syncStatus INTEGER NOT NULL DEFAULT 0,
        syncChangeCounter INTEGER NOT NULL DEFAULT 1
    );
    """
    cursor.execute("""
        SELECT
            moz_bookmarks.id,
            moz_bookmarks.type,
            moz_bookmarks.parent,
            moz_bookmarks.position,
            moz_bookmarks.title, 
            moz_bookmarks.dateAdded,
            moz_bookmarks.lastModified,
            moz_bookmarks.guid,

            moz_places.url
        FROM
            moz_bookmarks
        LEFT JOIN
            -- The actual URLs are stored in a separate moz_places table, which is pointed
            -- at by the moz_bookmarks.fk field.
            moz_places
        ON
            moz_bookmarks.fk = moz_places.id
        WHERE
            moz_bookmarks.title IS NOT NULL
        ;
    """)
    rows = cursor.fetchall()
    conn.close()

    parents = {}
    for line in rows:
        (book_id, typeCode, parent, position, title,
         dateAdded, lastModified, guid, uri) = line

        bookmark = None
        bookmark = Bookmark(
            id_=book_id,
            typeCode=typeCode,
            index=position,
            title=title,
            dateAdded=dateAdded,
            lastModified=lastModified,
            guid=guid,
            uri=uri,
        )

        if book_id in parents:
            bookmark.children = parents[book_id].children

        if typeCode == 2:
            parents[book_id] = bookmark

        # The root has parent 0 (which means no parent)
        if parent > 0:
            # Add the parent if it doesn't exist
            if parent not in parents:
                bparent = Bookmark()
                bparent.id_ = parent
                parents[parent] = bparent
        
            parents[parent].children.append(bookmark)

    # Return the root
    return parents[1]


def parse_bookmark_node_to_html(node: Bookmark):
    lines = []
    title = html.escape(node.title)
    
    # Convert Firefox microseconds timestamps to standard Unix seconds
    add_date = node.dateAdded // 1000000
    last_mod = node.lastModified // 1000000

    # Don't create an actual folder for the root folder
    if node.root == "placesRoot":
        for child in node.children:
            lines.append(parse_bookmark_node_to_html(child))

    # Folders (typeCode 2)
    elif node.typeCode == 2:
        # Don't attach a title to these folders
        if node.root not in ("placesRoot", "bookmarksMenuFolder", "toolbarFolder", "unfiledBookmarksFolder", "mobileFolder"):
            lines.append(f'    <DT><H3 ADD_DATE="{add_date}" LAST_MODIFIED="{last_mod}">{title}</H3>\n')
        lines.append("    <DL><p>\n")
        
        # Recursively process everything inside this folder
        for child in node.children:
            # Indent child elements for clean HTML readability
            child_html = parse_bookmark_node_to_html(child)
            indented_child = "\n".join([f"    {line}" if line else "" for line in child_html.split("\n")])
            lines.append(indented_child.rstrip() + "\n")
            
        lines.append("    </DL><p>\n")

    # Bookmarks (typeCode 1)
    elif node.typeCode == 1:
        uri = html.escape(node.uri)
        lines.append(f'    <DT><A HREF="{uri}" ADD_DATE="{add_date}">{title}</A>\n')

    # Separators (typeCode 3)
    elif node.typeCode == 3:
        lines.append("    <HR>\n")

    return "".join(lines)


def export_bookmarks_to_html_tempfile(profile_path: str | Path):
    bookmark_root = read_bookmarks(profile_path)

    # Classic Netscape bookmark header that Firefox requires to trigger import
    html_header = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "\n"
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n'
        "<TITLE>Bookmarks</TITLE>\n"
        "<H1>Bookmarks</H1>\n\n"
        "<DL><p>\n"
    )
    
    html_body = parse_bookmark_node_to_html(bookmark_root)
    html_footer = "</DL><p>\n"

    tmpfile = tempfile.NamedTemporaryFile("w", delete=False)
    tmpfile.write(html_header + html_body + html_footer)
    tmpfile.flush()
    tmpfile.close()

    return tmpfile


def create_profile(name: str):
    default_profile_path = get_default_profile_path()
    assert(default_profile_path is not None)

    out = run(f"firefox -CreateProfile {name}")
    profile_dir = get_profile_path_with_name(name)
    assert(profile_dir is not None)

    for file in COPY_FROM_PROFILE:
        src = default_profile_path / file
        dst = os.path.join(profile_dir, file)

        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.exists(src):
            raise RuntimeError(f"{src} is not file or directory")

    # Migrate bookmarks
    bookmarks_html_file = export_bookmarks_to_html_tempfile(default_profile_path)
    bookmarks_local_name = "bookmarks_from_default.html"
    bookmarks_profile_path = profile_dir / bookmarks_local_name
    with open(bookmarks_profile_path, "wb") as file:
        file.write(Path(bookmarks_html_file.name).read_bytes())

    # Configure user.js such that it imports the bookmarks
    suffix = f'''
    user_pref("browser.places.importBookmarksHTML", true);
    user_pref("browser.bookmarks.file", "{bookmarks_profile_path.resolve()}");
    '''

    user_js_path = profile_dir / "user.js"
    with user_js_path.open("w+") as file:
        file.write(suffix)


def get_profile_path_with_name(name: str) -> Optional[str]:
    firefox_profiles_ini = FIREFOX_DIR / "profiles.ini"
    profile_file = None
    with open(firefox_profiles_ini) as file:
        profile_section = False
        has_name = False
        for line in file.readlines():
            if line.startswith("[Profile"):
                profile_section = True
            elif line[0] == "[":
                profile_section = False
            elif profile_section and line.startswith(f"Name={name}"):
                has_name = True
            elif profile_section and has_name and line.startswith(f"Path="):
                profile_file = line.split("Path=")[1].strip()
                break

    if profile_file is None:
        return None

    return FIREFOX_DIR / profile_file


def remove_profile(name: str):
    profile_dir = get_profile_path_with_name(name)
    # Remove the profile directory
    shutil.rmtree(profile_dir)

    # Remove the corresponding section in profiles.ini

    # Read
    conf = configparser.RawConfigParser()
    conf.optionxform = str
    firefox_profiles_ini = FIREFOX_DIR / "profiles.ini"
    conf.read(firefox_profiles_ini)

    # Remove
    sections_to_remove = list(filter(lambda sec: conf.has_option(sec, "Name") and conf.get(sec, "Name") == name, conf.sections()))
    for sec in sections_to_remove:
        conf.remove_section(sec)

    # Write
    with open(firefox_profiles_ini, "w") as f:
        conf.write(f, space_around_delimiters=False)

    return True


def update_theme():
    "prefs.js"

    user_pref("extensions.activeThemeID", "{74da71cc-4d66-48f5-95d1-1f017f18ffab}");


def start_with_profile(name: str):
    return subprocess.Popen(
        ["firefox", "-P", name],
        stdin=None,
        stdout=None,
        stderr=None,
        start_new_session=True,
    )
