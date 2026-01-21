import os, sys
from pathlib import Path



def get_user_data_dir():
    """
    Returns the path to the user's application data directory for Osdag.

    This directory is used to store user-specific data such as settings,
    databases, and temporary files. The location varies by operating system:

    - On Windows: Uses the %APPDATA% environment variable.
    - On macOS: Uses ~/Library/Application Support/
    - On Linux: Uses ~/.local/share/

    Returns:
        str: Absolute path to the user's Osdag application data directory.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:  # Linux / Unix
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    return Path(base) / "Osdag"

def get_user_temp_dir():
    """
    Returns the path to the user's temporary directory for Osdag.

    This directory is used to store temporary files specific to the user.

    - Windows: %TEMP% / Osdag
    - macOS/Linux: /tmp / Osdag_<uid>

    Returns:
        Path: Absolute path to the user's Osdag temporary directory.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("TEMP") or os.environ.get("TMP")
    else:
        base = "/tmp"

    return Path(base) / "Osdag"

def remove_user_dirs():
    """
    Removes the user data and temporary directories for Osdag.

    This function deletes the directories used to store user-specific data
    and temporary files. Use with caution, as this will remove all user data
    associated with Osdag.
    """
    user_data_dir = get_user_data_dir()
    user_temp_dir = get_user_temp_dir()

    try:
        if user_data_dir.exists() and user_data_dir.is_dir():
            for item in user_data_dir.iterdir():
                if item.is_dir():
                    os.rmdir(item)
                else:
                    item.unlink()
            os.rmdir(user_data_dir)

        if user_temp_dir.exists() and user_temp_dir.is_dir():
            for item in user_temp_dir.iterdir():
                if item.is_dir():
                    os.rmdir(item)
                else:
                    item.unlink()
            os.rmdir(user_temp_dir)

    except Exception as e:
        print(f"[Error] removing user directories: {e}")