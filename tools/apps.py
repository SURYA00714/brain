import subprocess

APPROVED_APPS = {
    "brave": ["brave-browser"],
    "terminal": ["xfce4-terminal", "x-terminal-emulator"],
    "file_manager": ["thunar"],
    "text_editor": ["xedit", "x-text-editor", "nano"]
}


def open_app(app_name):
    """
    Launches an approved application safely based on an explicit allowlist.
    Rejects any unapproved application cleanly without execution.
    """
    if not app_name or not isinstance(app_name, str):
        return "Error: Invalid application name specified."

    clean_name = app_name.strip().lower()

    # Alias normalization
    if clean_name in ("browser", "brave-browser"):
        clean_name = "brave"
    elif clean_name in ("filemanager", "files", "folder"):
        clean_name = "file_manager"
    elif clean_name in ("editor", "texteditor", "notepad"):
        clean_name = "text_editor"

    if clean_name not in APPROVED_APPS:
        return f"Error: Application '{app_name}' is not in the approved safety allowlist."

    executables = APPROVED_APPS[clean_name]
    for exe in executables:
        try:
            subprocess.Popen([exe])
            return f"Application '{clean_name}' opened successfully ({exe})."
        except FileNotFoundError:
            continue
        except Exception as e:
            return f"Error launching '{clean_name}' via {exe}: {str(e)}"

    return f"Error: Executable for '{clean_name}' was not found on your system."


def open_brave():
    """Backward compatibility wrapper for opening Brave browser."""
    return open_app("brave")
