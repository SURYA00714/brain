import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# Explicit approved safe roots
SAFE_ROOTS = [
    Path("/home/jai/Downloads/Brain").resolve(),
    Path("/home/jai/Downloads").resolve()
]

# Allowed text file extensions for read_text_file
ALLOWED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml",
    ".csv", ".log", ".ini", ".cfg"
}

# Maximum file size for reading text files (1 MB)
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024


def resolve_location_alias(raw_path):
    """Maps logical location aliases (Downloads, Brain) or raw path strings to candidate Path objects."""
    if not raw_path or not isinstance(raw_path, str):
        return Path("/home/jai/Downloads/Brain")

    clean = raw_path.strip().strip("'\"")

    if clean.lower() in ("downloads", "download"):
        return Path("/home/jai/Downloads")
    elif clean.lower() in ("brain", "brain folder", "project", "root"):
        return Path("/home/jai/Downloads/Brain")

    # If starts with ~, expand user
    if clean.startswith("~"):
        return Path(clean).expanduser()

    # Handle leading Brain/ or Downloads/ prefix
    if clean.lower().startswith("brain/"):
        return Path("/home/jai/Downloads/Brain") / clean[6:]
    if clean.lower().startswith("downloads/"):
        return Path("/home/jai/Downloads") / clean[10:]

    p = Path(clean)
    if p.is_absolute():
        return p


    # Otherwise assume relative to Brain root
    return Path("/home/jai/Downloads/Brain") / p


def validate_safe_path(target_path, safe_roots=None, allow_nonexistent=False):
    """
    Centralized path validation:
    1. Resolves target_path safely using pathlib.Path.resolve().
    2. Checks if resolved target_path stays inside at least one approved safe root.
    3. Rejects path traversal attempts, symlink escapes, and system directories.
    Returns (validated_Path, None) if valid, or (None, error_message) if invalid.
    """
    if safe_roots is None:
        safe_roots = SAFE_ROOTS

    try:
        path_obj = Path(target_path)

        if allow_nonexistent and not path_obj.exists():
            parent_resolved = path_obj.parent.resolve()
            resolved = parent_resolved / path_obj.name
        else:
            resolved = path_obj.resolve()

        # Check if resolved path is inside an approved safe root
        is_safe = False
        for root in safe_roots:
            try:
                resolved_root = Path(root).resolve()
                if resolved == resolved_root or resolved_root in resolved.parents:
                    is_safe = True
                    break
            except (ValueError, Exception):
                continue

        if not is_safe:
            return None, f"Access Denied: Path '{target_path}' is outside approved safe directories."

        return resolved, None

    except Exception as e:
        return None, f"Path Error: Unable to resolve path '{target_path}' ({str(e)})."


def list_files(target_path="Brain", max_items=50, safe_roots=None):
    """
    Lists files and directories in the target path.
    Capped at max_items (default 50).
    """
    candidate = resolve_location_alias(target_path)
    validated, err = validate_safe_path(candidate, safe_roots=safe_roots)

    if err or not validated:
        return err or "Access Denied."

    if not validated.exists():
        return f"Error: Path '{target_path}' does not exist."

    if not validated.is_dir():
        return f"Error: Path '{target_path}' is a file, not a directory."

    try:
        items = sorted(list(validated.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
        total_count = len(items)

        output = [f"Contents of '{validated.name}' ({min(total_count, max_items)} of {total_count} items):"]
        for item in items[:max_items]:
            kind = "[DIR]" if item.is_dir() else "[FILE]"
            output.append(f"  {kind} {item.name}")

        return "\n".join(output)
    except PermissionError:
        return f"Error: Permission denied accessing '{target_path}'."
    except Exception as e:
        return f"Error listing directory '{target_path}': {str(e)}"


def find_files(pattern_or_query, search_root="Brain", max_results=20, safe_roots=None):
    """
    Finds files matching pattern or query within the specified safe root directory.
    Capped at max_results (default 20).
    """
    if not pattern_or_query or not pattern_or_query.strip():
        return "Error: Search pattern cannot be empty."

    candidate = resolve_location_alias(search_root)
    validated_root, err = validate_safe_path(candidate, safe_roots=safe_roots)

    if err or not validated_root:
        return err or "Access Denied."

    if not validated_root.exists() or not validated_root.is_dir():
        return f"Error: Search directory '{search_root}' does not exist or is not a directory."

    clean_pattern = pattern_or_query.strip()
    if not any(char in clean_pattern for char in "*?[]"):
        clean_pattern = f"*{clean_pattern}*"

    matches = []
    try:
        for p in validated_root.rglob(clean_pattern):
            val, _ = validate_safe_path(p, safe_roots=safe_roots)
            if val:
                matches.append(val)
                if len(matches) >= max_results:
                    break

        if not matches:
            return f"No files matching '{pattern_or_query}' found in '{validated_root.name}'."

        output = [f"Found {len(matches)} matching item(s) in '{validated_root.name}':"]
        for m in matches:
            rel = m.relative_to(validated_root) if m != validated_root else m.name
            kind = "[DIR]" if m.is_dir() else "[FILE]"
            output.append(f"  {kind} {rel}")

        return "\n".join(output)
    except Exception as e:
        return f"Error searching files: {str(e)}"


def read_text_file(filepath, max_size=MAX_FILE_SIZE_BYTES, safe_roots=None):
    """
    Reads text content from an allowed text file.
    Enforces extension checks, binary detection, and 1 MB size limit.
    """
    if not filepath or not str(filepath).strip():
        return "Error: Filepath cannot be empty."

    candidate = resolve_location_alias(str(filepath))
    validated, err = validate_safe_path(candidate, safe_roots=safe_roots)

    if err or not validated:
        return err or "Access Denied."

    if not validated.exists():
        return f"Error: File '{filepath}' does not exist."

    if validated.is_dir():
        return f"Error: Path '{filepath}' is a directory, not a text file."

    if validated.suffix.lower() not in ALLOWED_TEXT_EXTENSIONS:
        return f"Error: File extension '{validated.suffix}' is not in the allowed text file types."

    file_size = validated.stat().st_size
    if file_size > max_size:
        return f"Error: File size ({file_size} bytes) exceeds the maximum 1 MB limit."

    try:
        content = validated.read_text(encoding="utf-8", errors="strict")
        return f"--- Content of {validated.name} ({file_size} bytes) ---\n{content}"
    except UnicodeDecodeError:
        return f"Error: Unable to decode '{validated.name}' as text (binary content detected)."
    except Exception as e:
        return f"Error reading file '{filepath}': {str(e)}"


def create_folder(folder_name, parent_root="Downloads", safe_roots=None):
    """
    Creates a new folder inside an approved safe root directory.
    Validates target path before creation.
    """
    if not folder_name or not folder_name.strip():
        return "Error: Folder name cannot be empty."

    clean_name = folder_name.strip().strip("/\\")

    if ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        return "Error: Invalid folder name. Subdirectory traversal characters are not allowed."

    candidate_parent = resolve_location_alias(parent_root)
    validated_parent, err = validate_safe_path(candidate_parent, safe_roots=safe_roots)

    if err or not validated_parent:
        return err or "Access Denied."

    if not validated_parent.exists() or not validated_parent.is_dir():
        return f"Error: Parent directory '{parent_root}' does not exist."

    target_dir = validated_parent / clean_name
    validated_target, err = validate_safe_path(target_dir, safe_roots=safe_roots, allow_nonexistent=True)

    if err or not validated_target:
        return err or "Access Denied."

    try:
        validated_target.mkdir(parents=True, exist_ok=True)
        return f"Folder '{clean_name}' created successfully in '{validated_parent.name}'."
    except Exception as e:
        return f"Error creating folder '{clean_name}': {str(e)}"


# -------------------------------------------------------------------
# Phase 3 Deterministic Safe Filesystem Operations
# -------------------------------------------------------------------

def create_file(file_name: str, parent_root: str = "Downloads", safe_roots=None) -> Dict[str, Any]:
    """Creates a new empty file inside an approved safe root directory."""
    if not file_name or not file_name.strip():
        return {"success": False, "tool": "CREATE_FILE", "error": "File name cannot be empty."}

    clean_name = file_name.strip().strip("/\\")
    if ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        return {"success": False, "tool": "CREATE_FILE", "error": "Path traversal characters not allowed in file name."}

    candidate_parent = resolve_location_alias(parent_root)
    validated_parent, err = validate_safe_path(candidate_parent, safe_roots=safe_roots)
    if err or not validated_parent:
        return {"success": False, "tool": "CREATE_FILE", "error": err or "Access Denied."}

    target_file = validated_parent / clean_name
    validated_target, err = validate_safe_path(target_file, safe_roots=safe_roots, allow_nonexistent=True)
    if err or not validated_target:
        return {"success": False, "tool": "CREATE_FILE", "error": err or "Access Denied."}

    try:
        validated_target.touch(exist_ok=True)
        return {"success": True, "tool": "CREATE_FILE", "data": f"Empty file '{clean_name}' created at {validated_target}."}
    except Exception as e:
        return {"success": False, "tool": "CREATE_FILE", "error": f"Failed to create file '{clean_name}': {str(e)}"}


def copy_file(source: str, destination: str, confirmed: bool = False, safe_roots=None) -> Dict[str, Any]:
    """Copies a file from source path to destination path inside safe directories."""
    import shutil
    if not source or not destination:
        return {"success": False, "tool": "COPY_FILE", "error": "Source and destination paths are required."}

    cand_src = resolve_location_alias(source)
    val_src, err_src = validate_safe_path(cand_src, safe_roots=safe_roots)
    if err_src or not val_src:
        return {"success": False, "tool": "COPY_FILE", "error": err_src or "Source Access Denied."}

    if not val_src.exists():
        return {"success": False, "tool": "COPY_FILE", "error": f"Source file '{source}' does not exist."}

    cand_dst = resolve_location_alias(destination)
    if cand_dst.is_dir() or destination.endswith("/") or destination.endswith("\\"):
        cand_dst = cand_dst / val_src.name

    val_dst, err_dst = validate_safe_path(cand_dst, safe_roots=safe_roots, allow_nonexistent=True)
    if err_dst or not val_dst:
        return {"success": False, "tool": "COPY_FILE", "error": err_dst or "Destination Access Denied."}

    try:
        if val_src.is_dir():
            shutil.copytree(val_src, val_dst, dirs_exist_ok=True)
        else:
            shutil.copy2(val_src, val_dst)
        return {"success": True, "tool": "COPY_FILE", "data": f"Copied '{val_src.name}' to '{val_dst}'."}
    except Exception as e:
        return {"success": False, "tool": "COPY_FILE", "error": f"Copy failed: {str(e)}"}


def move_file(source: str, destination: str, confirmed: bool = False, safe_roots=None) -> Dict[str, Any]:
    """Moves a file or directory inside safe directories."""
    import shutil
    if not source or not destination:
        return {"success": False, "tool": "MOVE_FILE", "error": "Source and destination paths are required."}

    cand_src = resolve_location_alias(source)
    val_src, err_src = validate_safe_path(cand_src, safe_roots=safe_roots)
    if err_src or not val_src:
        return {"success": False, "tool": "MOVE_FILE", "error": err_src or "Source Access Denied."}

    if not val_src.exists():
        return {"success": False, "tool": "MOVE_FILE", "error": f"Source path '{source}' does not exist."}

    cand_dst = resolve_location_alias(destination)
    if cand_dst.is_dir():
        cand_dst = cand_dst / val_src.name

    val_dst, err_dst = validate_safe_path(cand_dst, safe_roots=safe_roots, allow_nonexistent=True)
    if err_dst or not val_dst:
        return {"success": False, "tool": "MOVE_FILE", "error": err_dst or "Destination Access Denied."}

    try:
        shutil.move(str(val_src), str(val_dst))
        return {"success": True, "tool": "MOVE_FILE", "data": f"Moved '{val_src.name}' to '{val_dst}'."}
    except Exception as e:
        return {"success": False, "tool": "MOVE_FILE", "error": f"Move failed: {str(e)}"}


def rename_file(source: str, new_name: str, confirmed: bool = False, safe_roots=None) -> Dict[str, Any]:
    """Renames a file or directory within its safe parent folder."""
    if not source or not new_name:
        return {"success": False, "tool": "RENAME_FILE", "error": "Source path and new name are required."}

    clean_new = new_name.strip().strip("/\\")
    if ".." in clean_new or "/" in clean_new or "\\" in clean_new:
        return {"success": False, "tool": "RENAME_FILE", "error": "Subdirectory characters not allowed in new name."}

    cand_src = resolve_location_alias(source)
    val_src, err_src = validate_safe_path(cand_src, safe_roots=safe_roots)
    if err_src or not val_src:
        return {"success": False, "tool": "RENAME_FILE", "error": err_src or "Source Access Denied."}

    if not val_src.exists():
        return {"success": False, "tool": "RENAME_FILE", "error": f"Source '{source}' does not exist."}

    target_path = val_src.parent / clean_new
    val_target, err_tgt = validate_safe_path(target_path, safe_roots=safe_roots, allow_nonexistent=True)
    if err_tgt or not val_target:
        return {"success": False, "tool": "RENAME_FILE", "error": err_tgt or "Target Access Denied."}

    try:
        val_src.rename(val_target)
        return {"success": True, "tool": "RENAME_FILE", "data": f"Renamed '{val_src.name}' to '{clean_new}'."}
    except Exception as e:
        return {"success": False, "tool": "RENAME_FILE", "error": f"Rename failed: {str(e)}"}


def file_info(target_path: str, safe_roots=None) -> Dict[str, Any]:
    """Inspects file metadata (size, timestamps, permissions, kind)."""
    if not target_path:
        return {"success": False, "tool": "FILE_INFO", "error": "Target path is required."}

    cand = resolve_location_alias(target_path)
    val, err = validate_safe_path(cand, safe_roots=safe_roots)
    if err or not val:
        return {"success": False, "tool": "FILE_INFO", "error": err or "Access Denied."}

    if not val.exists():
        return {"success": False, "tool": "FILE_INFO", "error": f"Path '{target_path}' does not exist."}

    try:
        st = val.stat()
        info = {
            "name": val.name,
            "path": str(val),
            "is_dir": val.is_dir(),
            "size_bytes": st.st_size,
            "modified": st.st_mtime,
            "permissions": oct(st.st_mode)[-3:]
        }
        kind = "Directory" if val.is_dir() else "File"
        formatted = f"{kind} '{val.name}': {st.st_size} bytes, modified {st.st_mtime}, mode {oct(st.st_mode)[-3:]}."
        return {"success": True, "tool": "FILE_INFO", "data": formatted, "info": info}
    except Exception as e:
        return {"success": False, "tool": "FILE_INFO", "error": f"Failed to retrieve file info: {str(e)}"}


def delete_file(target_path: str, confirmed: bool = False, safe_roots=None) -> Dict[str, Any]:
    """Deletes a file or folder (Confirmation Gated)."""
    import shutil
    if not target_path:
        return {"success": False, "tool": "DELETE_FILE", "error": "Target path is required."}

    if not confirmed and os.environ.get("BRAIN_MOCK_GUI") != "1":
        from core.confirmation import default_confirmation_manager
        status, req = default_confirmation_manager.evaluate_action("DELETE_FILE", {"target_path": target_path})
        if status == "REQUIRED":
            return {
                "success": False,
                "tool": "DELETE_FILE",
                "confirmation_required": True,
                "error": f"Confirmation Required: Deleting '{target_path}' requires explicit user confirmation."
            }

    cand = resolve_location_alias(target_path)
    val, err = validate_safe_path(cand, safe_roots=safe_roots)
    if err or not val:
        return {"success": False, "tool": "DELETE_FILE", "error": err or "Access Denied."}

    if not val.exists():
        return {"success": False, "tool": "DELETE_FILE", "error": f"Path '{target_path}' does not exist."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "DELETE_FILE", "data": f"Path '{val.name}' deleted (mocked)."}

    try:
        if val.is_dir():
            shutil.rmtree(val)
        else:
            val.unlink()
        return {"success": True, "tool": "DELETE_FILE", "data": f"Deleted '{val.name}' successfully."}
    except Exception as e:
        return {"success": False, "tool": "DELETE_FILE", "error": f"Deletion failed: {str(e)}"}

