"""Ensure uv is installed and available for subsequent hooks."""

from __future__ import annotations

import os
import re
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


def _get_parent_cmdline_linux(ppid: int) -> str | None:
    """Get parent process command line on Linux via /proc filesystem.

    Args:
        ppid: Parent process ID.

    Returns:
        The command line string, or None if unavailable.
    """
    try:
        cmdline = Path(f"/proc/{ppid}/cmdline").read_bytes()
        return cmdline.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    except (OSError, PermissionError):
        return None


def _get_parent_cmdline_darwin(ppid: int) -> str | None:
    """Get parent process command line on macOS via ps command.

    Args:
        ppid: Parent process ID.

    Returns:
        The command line string, or None if unavailable.
    """
    if not (ps_path := shutil.which("ps")):
        return None
    try:
        result = subprocess.run(
            [ps_path, "-o", "command=", "-p", str(ppid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def _get_parent_cmdline_win32(ppid: int) -> str | None:
    """Get parent process command line on Windows via wmic.

    Args:
        ppid: Parent process ID.

    Returns:
        The command line string, or None if unavailable.
    """
    if not (wmic_path := shutil.which("wmic")):
        return None
    try:
        result = subprocess.run(
            [wmic_path, "process", "where", f"ProcessId={ppid}", "get", "CommandLine"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return lines[1] if len(lines) > 1 else None
    except OSError:
        pass
    return None


def _get_parent_cmdline() -> str | None:
    """Get the command line of the parent process.

    Returns:
        The parent process command line string, or None if unavailable.
    """
    ppid = os.getppid()
    platform_handlers = {
        "linux": _get_parent_cmdline_linux,
        "darwin": _get_parent_cmdline_darwin,
        "win32": _get_parent_cmdline_win32,
    }
    handler = platform_handlers.get(sys.platform)
    return handler(ppid) if handler else None


def _detect_runner_from_cmdline(cmdline: str) -> str | None:
    """Detect prek or pre-commit from a command line string.

    Args:
        cmdline: The command line string to parse.

    Returns:
        The detected runner name, or None if not found.
    """
    for runner in _KNOWN_RUNNERS:
        if re.search(rf"\b{re.escape(runner)}\b", cmdline):
            return runner
    return None


def _get_runner() -> str | None:
    """Get the runner that invoked this hook.

    First attempts to detect the runner from the parent process command line.
    Falls back to checking which runners are available in PATH.

    Returns:
        The runner command name ('prek' or 'pre-commit'), or None if unavailable.
    """
    cmdline = _get_parent_cmdline()
    if cmdline:
        detected = _detect_runner_from_cmdline(cmdline)
        if detected and shutil.which(detected):
            return detected
    for runner in _KNOWN_RUNNERS:
        if shutil.which(runner):
            return runner
    return None


def _rerun_with_uv() -> int:
    """Re-run hooks with uv's bin directory prepended to PATH.

    Returns:
        Exit code from the runner subprocess.
    """
    runner = _get_runner()
    if not runner:
        return 1

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

    if not _is_uv_installed() and not _install_uv():
        print("Failed to install uv.", file=sys.stderr)
        return 1

    sys.exit(_rerun_with_uv())


if __name__ == "__main__":
    sys.exit(main())
