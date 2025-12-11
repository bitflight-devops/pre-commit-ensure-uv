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


def _get_exe_linux(pid: int) -> str | None:
    """Get process executable path on Linux via /proc filesystem.

    Args:
        pid: Process ID.

    Returns:
        The executable path, or None if unavailable.
    """
    try:
        exe_link = Path(f"/proc/{pid}/exe")
        if exe_link.exists():
            return str(exe_link.resolve())
    except (OSError, PermissionError):
        pass
    return None


def _get_ppid_linux(pid: int) -> int | None:
    """Get parent process ID on Linux via /proc filesystem.

    Args:
        pid: Process ID.

    Returns:
        The parent process ID, or None if unavailable.
    """
    # /proc/PID/stat format: "pid (comm) state ppid ..."
    # After the closing paren, fields are: state(0), ppid(1), pgrp(2), ...
    ppid_field_index = 1
    try:
        stat_file = Path(f"/proc/{pid}/stat")
        if stat_file.exists():
            content = stat_file.read_text(encoding="utf-8")
            # Find the closing paren to skip comm field (may contain spaces)
            paren_idx = content.rfind(")")
            if paren_idx != -1:
                # Skip ") " to get to the fields after comm
                fields = content[paren_idx + 2 :].split()
                if len(fields) > ppid_field_index:
                    return int(fields[ppid_field_index])
    except (OSError, PermissionError, ValueError):
        pass
    return None


def _get_exe_darwin(pid: int) -> str | None:
    """Get process executable path on macOS via lsof command.

    Args:
        pid: Process ID.

    Returns:
        The executable path, or None if unavailable.
    """
    if not (lsof_path := shutil.which("lsof")):
        return None
    try:
        # lsof -p PID -Fn shows the executable path as 'n/path/to/exe'
        result = subprocess.run(
            [lsof_path, "-p", str(pid), "-Fn"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # First 'n' line with 'txt' type is the executable
                if line.startswith("n/"):
                    return line[1:]  # Strip 'n' prefix
    except OSError:
        pass
    return None


def _get_ppid_darwin(pid: int) -> int | None:
    """Get parent process ID on macOS via ps command.

    Args:
        pid: Process ID.

    Returns:
        The parent process ID, or None if unavailable.
    """
    if not (ps_path := shutil.which("ps")):
        return None
    try:
        result = subprocess.run(
            [ps_path, "-o", "ppid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (OSError, ValueError):
        pass
    return None


def _get_exe_win32(pid: int) -> str | None:
    """Get process executable path on Windows via wmic.

    Args:
        pid: Process ID.

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
                f"ProcessId={pid}",
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


def _get_ppid_win32(pid: int) -> int | None:
    """Get parent process ID on Windows via wmic.

    Args:
        pid: Process ID.

    Returns:
        The parent process ID, or None if unavailable.
    """
    if not (wmic_path := shutil.which("wmic")):
        return None
    try:
        result = subprocess.run(
            [
                wmic_path,
                "process",
                "where",
                f"ProcessId={pid}",
                "get",
                "ParentProcessId",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            if len(lines) > 1 and lines[1]:
                return int(lines[1])
    except (OSError, ValueError):
        pass
    return None


def _find_runner_in_ancestors() -> str | None:
    """Walk up the process tree to find a known runner executable.

    Pre-commit/prek run hooks in isolated Python environments, so the immediate
    parent is typically 'python'. We need to walk up the tree to find the
    actual runner (prek or pre-commit).

    Returns:
        The full path to the runner executable, or None if not found.
    """
    # Platform-specific functions for getting exe path and parent PID
    exe_funcs = {
        "linux": _get_exe_linux,
        "darwin": _get_exe_darwin,
        "win32": _get_exe_win32,
    }
    ppid_funcs = {
        "linux": _get_ppid_linux,
        "darwin": _get_ppid_darwin,
        "win32": _get_ppid_win32,
    }

    get_exe = exe_funcs.get(sys.platform)
    get_ppid = ppid_funcs.get(sys.platform)
    if not get_exe or not get_ppid:
        return None

    # Walk up process tree (limit iterations to avoid infinite loops)
    max_depth = 10
    pid: int | None = os.getppid()

    for _ in range(max_depth):
        if pid is None or pid <= 1:
            break

        exe_path = get_exe(pid)
        if exe_path:
            # Check if this is a known runner
            for runner in _KNOWN_RUNNERS:
                if runner in exe_path:
                    return exe_path

        # Move to parent
        pid = get_ppid(pid)

    return None


def _get_runner() -> str | None:
    """Get the full path to the runner that invoked this hook.

    First walks up the process tree to find the runner executable directly.
    Falls back to checking which runners are available in PATH.

    Returns:
        The full path to the runner executable, or None if unavailable.
    """
    # Walk up process tree to find runner (works even in isolated venvs)
    runner_path = _find_runner_in_ancestors()
    if runner_path:
        return runner_path

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
