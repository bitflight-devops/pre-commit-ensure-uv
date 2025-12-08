"""
Ensure uv is installed and available for subsequent hooks.

Cross-platform: Works on Linux, macOS, and Windows.

Behavior:
- If uv in PATH: pass (exit 0)
- If uv installed but not in PATH: re-run hooks with corrected PATH
- If uv not installed: install it, then re-run hooks with corrected PATH
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Marker to detect if we're in a re-run to prevent infinite recursion
_RERUN_MARKER = "_ENSURE_UV_RERUN"


def get_uv_bin_dir() -> Path:
    """Get the directory where uv is installed."""
    return Path.home() / ".local" / "bin"


def get_uv_path() -> Path:
    """Get the full path to the uv binary."""
    suffix = ".exe" if sys.platform == "win32" else ""
    return get_uv_bin_dir() / f"uv{suffix}"


def is_uv_in_path() -> bool:
    """Check if uv is available in PATH."""
    return shutil.which("uv") is not None


def is_uv_installed() -> bool:
    """Check if uv is installed at default location."""
    return get_uv_path().exists()


def install_uv() -> bool:
    """Install uv silently. Returns True on success."""
    if sys.platform == "win32":
        script = (
            "$ProgressPreference = 'SilentlyContinue'; "
            "irm https://astral.sh/uv/install.ps1 | iex *>&1 | Out-Null"
        )
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "ByPass", "-NoProfile",
             "-NonInteractive", "-Command", script],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        result = subprocess.run(
            ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --quiet"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return result.returncode == 0 and is_uv_installed()


def get_hook_runner() -> str | None:
    """Detect if we're running under pre-commit or prek."""
    # Check prek first as it's the preferred runner
    for runner in ["prek", "pre-commit"]:
        if shutil.which(runner):
            return runner
    return None


def rerun_with_uv_in_path() -> int:
    """Re-run all hooks with uv's bin directory in PATH."""
    runner = get_hook_runner()
    if not runner:
        print("Neither prek nor pre-commit found.", file=sys.stderr)
        return 1

    env = os.environ.copy()

    # Add uv's bin dir to PATH
    uv_bin = str(get_uv_bin_dir())
    env["PATH"] = f"{uv_bin}{os.pathsep}{env.get('PATH', '')}"

    # Set marker to prevent infinite recursion
    env[_RERUN_MARKER] = "1"

    # Re-run hooks
    result = subprocess.run([runner, "run", "--all-files"], env=env, check=False)
    return result.returncode


def main() -> int:
    """Entry point for the ensure-uv hook."""
    # If we're in a re-run, just check uv is available and pass
    if os.environ.get(_RERUN_MARKER):
        return 0 if is_uv_in_path() else 1

    # Normal run: check if uv is available
    if is_uv_in_path():
        return 0

    # uv not in PATH - check if installed
    if not is_uv_installed():
        if not install_uv():
            print("Failed to install uv.", file=sys.stderr)
            return 1

    # uv is installed but not in PATH - re-run with corrected PATH
    # Return the rerun's exit code, which will be shown to user
    # The original run stops here because we don't return 0
    exit_code = rerun_with_uv_in_path()

    # Exit with 1 to stop original run, but print success if rerun passed
    if exit_code == 0:
        # Hooks passed in rerun, but we return 1 to stop original run
        # from continuing with hooks that won't have uv in PATH
        sys.exit(0)  # Actually exit success since rerun handled everything

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
