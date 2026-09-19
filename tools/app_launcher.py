import os
import re
import shlex
import shutil
import subprocess
from typing import Dict, List, Optional, Any

SEARCH_DIRECTORIES = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications")
]

# In-memory application index cache
_APP_INDEX: Optional[Dict[str, Dict[str, Any]]] = None


def parse_desktop_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Parses a Linux .desktop file and extracts metadata from [Desktop Entry].
    Returns a dictionary of properties or None if invalid or not a GUI application.
    """
    if not os.path.isfile(filepath) or not filepath.endswith(".desktop"):
        return None

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return None

    in_desktop_entry = False
    properties: Dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if section_name == "Desktop Entry":
                in_desktop_entry = True
            else:
                if in_desktop_entry:
                    # End of [Desktop Entry] section
                    break
            continue

        if in_desktop_entry and "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Only store first encountered un-localized or main key
            if key not in properties:
                properties[key] = val

    if not properties:
        return None

    # Validate Type (must be Application if present)
    app_type = properties.get("Type", "Application").strip()
    if app_type != "Application":
        return None

    # Check NoDisplay and Hidden
    no_display = properties.get("NoDisplay", "false").lower() == "true"
    hidden = properties.get("Hidden", "false").lower() == "true"
    if no_display or hidden:
        return None

    # Check Terminal (exclude CLI/terminal applications)
    terminal = properties.get("Terminal", "false").lower() == "true"
    if terminal:
        return None

    name = properties.get("Name", "").strip()
    exec_str = properties.get("Exec", "").strip()
    if not name or not exec_str:
        return None

    desktop_id = os.path.basename(filepath)

    return {
        "Name": name,
        "GenericName": properties.get("GenericName", "").strip(),
        "Exec": exec_str,
        "Icon": properties.get("Icon", "").strip(),
        "NoDisplay": no_display,
        "Hidden": hidden,
        "Terminal": terminal,
        "Categories": properties.get("Categories", "").strip(),
        "filepath": filepath,
        "desktop_id": desktop_id
    }


def discover_apps(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Scans standard Linux application directories and returns an index of discovered GUI apps.
    Keyed by desktop_id.
    """
    global _APP_INDEX
    if _APP_INDEX is not None and not force_refresh:
        return _APP_INDEX

    apps: Dict[str, Dict[str, Any]] = {}

    for directory in SEARCH_DIRECTORIES:
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except Exception:
            continue

        for filename in entries:
            if not filename.endswith(".desktop"):
                continue
            filepath = os.path.join(directory, filename)
            parsed = parse_desktop_file(filepath)
            if parsed:
                apps[filename] = parsed

    _APP_INDEX = apps
    return _APP_INDEX


def refresh_app_index() -> Dict[str, Dict[str, Any]]:
    """Forces a rescan of application directories and returns the updated index."""
    return discover_apps(force_refresh=True)


def normalize_string(s: str) -> str:
    """Normalizes string for robust deterministic matching."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def resolve_app(name: str) -> Optional[Any]:
    """
    Deterministically resolves an application name against the discovered desktop applications.
    Returns:
      - Single app dict if unique match found.
      - Dict with {"ambiguous": True, "matches": [...]} if multiple matches found.
      - None if no match found.
    """
    if not name or not isinstance(name, str):
        return None

    query = name.strip()
    if not query:
        return None

    # Exclude explicit shell commands, metacharacters, scripts, or dangerous operations
    lowered_query = query.lower()
    if re.search(r"[;&|`$><\n]", query):
        return None
    if lowered_query in {"bash", "sh", "zsh", "sudo", "cmd"} or lowered_query.startswith("sudo ") or lowered_query.startswith("bash ") or lowered_query.startswith("rm "):
        return None

    apps_index = discover_apps()
    if not apps_index:
        return None

    norm_query = normalize_string(query)

    # Alias mappings for canonical desktop app requests
    canonical_aliases = {
        "brave": ["brave-browser.desktop", "brave.desktop"],
        "browser": ["brave-browser.desktop", "brave.desktop"],
        "terminal": ["xfce4-terminal.desktop", "org.gnome.Terminal.desktop", "x-terminal-emulator.desktop"],
        "console": ["xfce4-terminal.desktop", "org.gnome.Terminal.desktop"],
        "file_manager": ["thunar.desktop", "org.gnome.Nautilus.desktop"],
        "file manager": ["thunar.desktop", "org.gnome.Nautilus.desktop"],
        "files": ["thunar.desktop", "org.gnome.Nautilus.desktop"],
        "text_editor": ["mousepad.desktop", "xed.desktop", "xedit.desktop"],
        "text editor": ["mousepad.desktop", "xed.desktop", "xedit.desktop"],
        "calculator": ["gnome-calculator.desktop", "galculator.desktop", "xcalc.desktop"]
    }

    if lowered_query in canonical_aliases:
        for target_id in canonical_aliases[lowered_query]:
            if target_id in apps_index:
                return apps_index[target_id]

    # Strategy 1: Exact match on desktop_id (stem or full), Name, or GenericName
    exact_matches = []
    for desktop_id, app in apps_index.items():
        stem = desktop_id.rsplit(".desktop", 1)[0].lower()
        app_name = app["Name"].lower()
        generic = app.get("GenericName", "").lower()

        if lowered_query in (stem, app_name, generic, desktop_id.lower()):
            exact_matches.append(app)

    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) > 1:
        names = sorted(list({a["Name"] for a in exact_matches}))
        if len(names) == 1:
            return exact_matches[0]
        return {"ambiguous": True, "matches": names}

    # Strategy 2: Normalized exact match
    norm_matches = []
    for desktop_id, app in apps_index.items():
        stem_norm = normalize_string(desktop_id.rsplit(".desktop", 1)[0])
        name_norm = normalize_string(app["Name"])
        generic_norm = normalize_string(app.get("GenericName", ""))

        if norm_query in (stem_norm, name_norm, generic_norm):
            norm_matches.append(app)

    if len(norm_matches) == 1:
        return norm_matches[0]
    elif len(norm_matches) > 1:
        names = sorted(list({a["Name"] for a in norm_matches}))
        if len(names) == 1:
            return norm_matches[0]
        return {"ambiguous": True, "matches": names}

    # Strategy 3: Substring / Word Match
    partial_matches = []
    for desktop_id, app in apps_index.items():
        stem_norm = normalize_string(desktop_id.rsplit(".desktop", 1)[0])
        name_norm = normalize_string(app["Name"])

        if norm_query and (norm_query in name_norm or norm_query in stem_norm):
            partial_matches.append(app)

    unique_by_name: Dict[str, Dict[str, Any]] = {}
    for a in partial_matches:
        unique_by_name[a["Name"]] = a

    unique_matches = list(unique_by_name.values())

    # If multiple partial matches exist, filter out nightly/beta/dev variants if a stable version exists
    if len(unique_matches) > 1:
        stable_matches = [
            a for a in unique_matches
            if not any(v in a["desktop_id"].lower() or v in a["Name"].lower() for v in ["nightly", "beta", "dev", "debug"])
        ]
        if len(stable_matches) == 1:
            return stable_matches[0]
        elif len(stable_matches) > 1:
            unique_matches = stable_matches

    if len(unique_matches) == 1:
        return unique_matches[0]
    elif len(unique_matches) > 1:
        names = sorted([a["Name"] for a in unique_matches])
        return {"ambiguous": True, "matches": names}

    return None


def clean_exec_args(exec_str: str) -> List[str]:
    """
    Strips Freedesktop Exec field codes (%f, %F, %u, %U, %i, %c, %k) and returns command args list.
    """
    cleaned = re.sub(r"%[fFuUiIckK]", "", exec_str).strip()
    return shlex.split(cleaned)


def _launch_backend(app_entry: Dict[str, Any]) -> bool:
    """
    Low-level launcher backend. Launches the app process safely without shell=True.
    Supports BRAIN_MOCK_GUI for testing environments.
    """
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return True

    filepath = app_entry.get("filepath", "")
    desktop_id = app_entry.get("desktop_id", "")
    exec_str = app_entry.get("Exec", "")

    # Attempt 1: gio launch
    if shutil.which("gio") and filepath and os.path.exists(filepath):
        try:
            subprocess.Popen(["gio", "launch", filepath], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    # Attempt 2: gtk-launch
    if shutil.which("gtk-launch") and desktop_id:
        try:
            subprocess.Popen(["gtk-launch", desktop_id], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    # Attempt 3: Direct execution of Exec binary (NO shell=True)
    if exec_str:
        try:
            cmd_args = clean_exec_args(exec_str)
            if cmd_args and shutil.which(cmd_args[0]):
                subprocess.Popen(cmd_args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        except Exception:
            pass

    return False


def launch_app(name: str) -> Dict[str, Any]:
    """
    Resolves and launches an application deterministically by name.
    Returns structured result dict.
    """
    resolved = resolve_app(name)

    if resolved is None:
        return {
            "success": False,
            "tool": "OPEN_APP",
            "error": f"Error: Application '{name}' is not in the approved safety allowlist or not found."
        }

    if isinstance(resolved, dict) and resolved.get("ambiguous"):
        return {
            "success": False,
            "tool": "OPEN_APP",
            "error": "Multiple applications match",
            "matches": resolved.get("matches", [])
        }

    app_entry = resolved
    app_name = app_entry.get("Name", name)
    desktop_id = app_entry.get("desktop_id", "")

    launched = _launch_backend(app_entry)
    if not launched:
        return {
            "success": False,
            "tool": "OPEN_APP",
            "error": f"Failed to launch application '{app_name}'"
        }

    try:
        from tools.apps import default_app_tracker
        default_app_tracker.register_app(app_name)
        if name:
            default_app_tracker.register_app(name)
        if desktop_id:
            default_app_tracker.register_app(desktop_id.rsplit(".desktop", 1)[0])
    except Exception:
        pass

    return {
        "success": True,
        "tool": "OPEN_APP",
        "data": {
            "name": app_name,
            "desktop_id": desktop_id
        }
    }


def list_apps() -> Dict[str, Any]:
    """
    Returns a structured list of all discovered GUI applications.
    """
    apps_index = discover_apps()
    app_list = []
    seen_names = set()

    for desktop_id, app in sorted(apps_index.items(), key=lambda item: item[1]["Name"].lower()):
        name = app["Name"]
        if name not in seen_names:
            seen_names.add(name)
            app_list.append({
                "name": name,
                "desktop_id": desktop_id,
                "generic_name": app.get("GenericName", ""),
                "exec": app.get("Exec", "")
            })

    return {
        "success": True,
        "tool": "LIST_APPS",
        "data": {
            "apps": app_list
        }
    }
