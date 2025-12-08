"""Ensure uv is installed and available for subsequent hooks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_RERUN_MARKER = "_ENSURE_UV_RERUN"


def _get_uv_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def _get_uv_path() -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return _get_uv_bin_dir() / f"uv{suffix}"


def _is_uv_in_path() -> bool:
    return shutil.which("uv") is not None


def _is_uv_installed() -> bool:
    return _get_uv_path().exists()


def _install_uv() -> bool:
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
    result = subprocess.run(
        cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0 and _is_uv_installed()


def _get_runner() -> str | None:
    for runner in ["prek", "pre-commit"]:
        if shutil.which(runner):
            return runner
    return None


def _rerun_with_uv() -> int:
    runner = _get_runner()
    if not runner:
        return 1
    env = os.environ.copy()
    env["PATH"] = f"{_get_uv_bin_dir()}{os.pathsep}{env.get('PATH', '')}"
    env[_RERUN_MARKER] = "1"
    result = subprocess.run([runner, "run", "--all-files"], env=env, check=False)
    return result.returncode


def main() -> int:
    """Entry point for the ensure-uv pre-commit hook.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    if os.environ.get(_RERUN_MARKER):
        return 0 if _is_uv_in_path() else 1

    if _is_uv_in_path():
        return 0

    if not _is_uv_installed() and not _install_uv():
        print("Failed to install uv.", file=sys.stderr)
        return 1

    sys.exit(_rerun_with_uv())


if __name__ == "__main__":
    sys.exit(main())
