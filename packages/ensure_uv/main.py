"""Ensure uv is installed and available for subsequent hooks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_RERUN_MARKER = "_ENSURE_UV_RERUN"
_KNOWN_RUNNERS = ("prek", "pre-commit")


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
    """Install uv using the official installer script.

    Returns:
        True if installation succeeded and uv is found at expected path.
    """
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

    # Show installer output even on success to see where it installed
    if result.stdout:
        print(f"installer stdout: {result.stdout.strip()}")

    uv_path = _get_uv_path()
    if not uv_path.exists():
        print(f"uv not found at expected path: {uv_path}", file=sys.stderr)
        # Check common alternative locations
        alt_locations = [
            Path.home()
            / ".cargo"
            / "bin"
            / f"uv{'.exe' if sys.platform == 'win32' else ''}"
        ]
        for alt in alt_locations:
            if alt.exists():
                print(f"uv found at alternative path: {alt}", file=sys.stderr)
        return False

    return True


def _get_parent_exe_linux(ppid: int) -> str | None:
    """Get parent process executable path on Linux via /proc filesystem.

    Args:
        ppid: Parent process ID.

    Returns:
        The executable path, or None if unavailable.
    """
    try:
        exe_link = Path(f"/proc/{ppid}/exe")
        if exe_link.exists():
            return str(exe_link.resolve())
    except (OSError, PermissionError):
        pass
    return None


def _get_parent_exe_darwin(ppid: int) -> str | None:
    """Get parent process executable path on macOS via lsof command.

    Args:
        ppid: Parent process ID.

    Returns:
        The executable path, or None if unavailable.
    """
    if not (lsof_path := shutil.which("lsof")):
        return None
    try:
        # lsof -p PID -Fn shows the executable path as 'n/path/to/exe'
        result = subprocess.run(
            [lsof_path, "-p", str(ppid), "-Fn"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("n") and ("prek" in line or "pre-commit" in line):
                    return line[1:]  # Strip 'n' prefix
    except OSError:
        pass
    return None


def _get_parent_exe_win32(ppid: int) -> str | None:
    """Get parent process executable path on Windows via wmic.

    Args:
        ppid: Parent process ID.

    Returns:
        The executable path, or None if unavailable.
    """
    if not (wmic_path := shutil.which("wmic")):
        return None
    try:
        result = subprocess.run(
            [
                wmic_path,
                "process",
                "where",
                f"ProcessId={ppid}",
                "get",
                "ExecutablePath",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            if len(lines) > 1 and lines[1]:
                return lines[1]
    except OSError:
        pass
    return None


def _get_parent_exe() -> str | None:
    """Get the executable path of the parent process.

    Returns:
        The parent process executable path, or None if unavailable.
    """
    ppid = os.getppid()
    platform_handlers = {
        "linux": _get_parent_exe_linux,
        "darwin": _get_parent_exe_darwin,
        "win32": _get_parent_exe_win32,
    }
    handler = platform_handlers.get(sys.platform)
    return handler(ppid) if handler else None


def _get_runner() -> str | None:
    """Get the full path to the runner that invoked this hook.

    First attempts to get the parent process executable path directly.
    Falls back to checking which runners are available in PATH.

    Returns:
        The full path to the runner executable, or None if unavailable.
    """
    # Try to get parent executable path directly (works even in isolated venvs)
    parent_exe = _get_parent_exe()
    if parent_exe:
        # Verify it's a known runner
        for runner in _KNOWN_RUNNERS:
            if runner in parent_exe:
                return parent_exe

    # Fallback to PATH lookup (may not work in isolated venvs)
    for runner in _KNOWN_RUNNERS:
        if path := shutil.which(runner):
            return path
    return None


def _rerun_with_uv() -> int:
    """Re-run hooks with uv's bin directory prepended to PATH.

    Returns:
        Exit code from the runner subprocess.
    """
    # Debug parent process detection
    parent_exe = _get_parent_exe()
    print(f"[ensure-uv] parent exe: {parent_exe}")

    runner = _get_runner()
    if not runner:
        print("[ensure-uv] _get_runner() returned None - can't re-run")
        print(f"[ensure-uv] PATH in hook: {os.environ.get('PATH', '')[:200]}")
        return 1
    print(f"[ensure-uv] found runner: {runner}")

    env = os.environ.copy()
    uv_bin = str(_get_uv_bin_dir())
    current_path = os.environ.get("PATH", "")

    # On Windows, env var names are case-insensitive but os.environ.copy()
    # creates a case-sensitive dict. Remove any existing PATH/Path keys
    # to avoid duplicates when we set the new value.
    if sys.platform == "win32":
        for key in list(env.keys()):
            if key.upper() == "PATH":
                del env[key]

    env["PATH"] = f"{uv_bin}{os.pathsep}{current_path}"
    env[_RERUN_MARKER] = "1"
    result = subprocess.run([runner, "run", "--all-files"], env=env, check=False)
    return result.returncode


def main() -> int:
    """Entry point for the ensure-uv pre-commit hook.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Debug: always show state at entry
    marker = os.environ.get(_RERUN_MARKER)
    in_path = _is_uv_in_path()
    print(
        f"[ensure-uv] marker={marker!r} in_path={in_path} path={os.environ.get('PATH', '')[:100]}"
    )

    if marker:
        if _is_uv_in_path():
            return 0
        # Debug: show why uv not found in re-run
        _get_uv_bin_dir()
        uv_path = _get_uv_path()
        print("Re-run check failed: uv not in PATH", file=sys.stderr)
        print(f"Expected uv at: {uv_path}", file=sys.stderr)
        print(f"File exists: {uv_path.exists()}", file=sys.stderr)
        print(
            f"PATH dirs: {os.environ.get('PATH', '').split(os.pathsep)[:5]}",
            file=sys.stderr,
        )
        return 1

    if _is_uv_in_path():
        return 0

    installed = _is_uv_installed()
    print(f"[ensure-uv] uv_installed={installed} uv_path={_get_uv_path()}")

    if not installed and not _install_uv():
        print("Failed to install uv.", file=sys.stderr)
        return 1

    print("[ensure-uv] triggering re-run with uv in PATH")
    rc = _rerun_with_uv()
    print(f"[ensure-uv] re-run returned {rc}")
    sys.exit(rc)


if __name__ == "__main__":
    sys.exit(main())
