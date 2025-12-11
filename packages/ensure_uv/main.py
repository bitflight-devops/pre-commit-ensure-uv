"""Ensure uv is installed and available for subsequent hooks."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _get_uv_bin_dir() -> Path:
    """Get the directory where uv is installed.

    Returns:
        Path to ~/.local/bin where uv is typically installed.
    """
    return Path.home() / ".local" / "bin"


def _get_uv_path() -> Path:
    """Get the full path to the uv executable.

    Returns:
        Path to the uv binary, with .exe suffix on Windows.
    """
    suffix = ".exe" if sys.platform == "win32" else ""
    return _get_uv_bin_dir() / f"uv{suffix}"


def _is_uv_in_path() -> bool:
    """Check if uv is available in PATH.

    Returns:
        True if uv can be found via shutil.which().
    """
    return shutil.which("uv") is not None


def _is_uv_installed() -> bool:
    """Check if uv is installed at the expected location.

    Returns:
        True if the uv binary exists at the expected path.
    """
    return _get_uv_path().exists()


def _install_uv() -> bool:
    """Install uv using the official installer script.

    Returns:
        True if installation succeeded and uv is found at expected path.
    """
    print("Installing uv...")

    if sys.platform == "win32":
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "ByPass",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ProgressPreference='SilentlyContinue';irm https://astral.sh/uv/install.ps1|iex",
        ]
    else:
        cmd = [
            "sh",
            "-c",
            "curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --quiet",
        ]

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"uv installer failed (exit {result.returncode})", file=sys.stderr)
        if result.stdout:
            print(f"stdout: {result.stdout.strip()}", file=sys.stderr)
        if result.stderr:
            print(f"stderr: {result.stderr.strip()}", file=sys.stderr)
        return False

    uv_path = _get_uv_path()
    if not uv_path.exists():
        print(f"uv not found at expected path: {uv_path}", file=sys.stderr)
        # Check common alternative locations
        alt_path = (
            Path.home()
            / ".cargo"
            / "bin"
            / f"uv{'.exe' if sys.platform == 'win32' else ''}"
        )
        if alt_path.exists():
            print(f"uv found at alternative path: {alt_path}", file=sys.stderr)
        return False

    print(f"uv installed successfully at {uv_path}")
    return True


def main() -> int:
    """Entry point for the ensure-uv pre-commit hook.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # If uv is already in PATH, we're done
    if _is_uv_in_path():
        return 0

    # If uv is installed but not in PATH, tell user to add it
    if _is_uv_installed():
        uv_bin = _get_uv_bin_dir()
        print(f"uv is installed but not in PATH. Add {uv_bin} to your PATH.")
        print("Then re-run your pre-commit hooks.")
        return 1

    # Install uv
    if not _install_uv():
        print("Failed to install uv.", file=sys.stderr)
        return 1

    # Installation succeeded, but PATH doesn't include uv yet
    uv_bin = _get_uv_bin_dir()
    print()
    print("=" * 60)
    print("uv has been installed successfully!")
    print()
    print(f"Add {uv_bin} to your PATH, then re-run your hooks.")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
