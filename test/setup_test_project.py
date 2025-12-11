#!/usr/bin/env python3
"""Setup a test project for integration testing.

Creates a test git repository with virtual environment and pre-commit configuration.
Supports testing with prek, pre-commit, or both runners installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

RUNNERS = ("prek", "pre-commit")


def create_venv(venv_dir: Path) -> Path:
    """Create a virtual environment and return the pip executable path.

    Args:
        venv_dir: Path to create the virtual environment.

    Returns:
        Path to the pip executable in the virtual environment.
    """
    venv.create(venv_dir, with_pip=True)
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def install_runners(pip_path: Path, runners: Sequence[str]) -> None:
    """Install specified runners using pip.

    Args:
        pip_path: Path to pip executable.
        runners: Sequence of runner package names to install.
    """
    subprocess.run([str(pip_path), "install", *runners], check=True)


def verify_runners(venv_dir: Path, runners: Sequence[str]) -> None:
    """Verify that specified runners are installed and executable.

    Args:
        venv_dir: Path to virtual environment.
        runners: Sequence of runner names to verify.

    Raises:
        RuntimeError: If any runner is not found.
    """
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    for runner in runners:
        suffix = ".exe" if sys.platform == "win32" else ""
        runner_path = bin_dir / f"{runner}{suffix}"
        if not runner_path.exists():
            msg = f"Runner '{runner}' not found at {runner_path}"
            raise RuntimeError(msg)
        print(f"Verified: {runner_path}")


def get_venv_bin_dir(venv_dir: Path) -> Path:
    """Get the bin/Scripts directory for a virtual environment.

    Args:
        venv_dir: Path to virtual environment.

    Returns:
        Path to the bin/Scripts directory.
    """
    return venv_dir / ("Scripts" if sys.platform == "win32" else "bin")


def main() -> None:
    """Create a test git repository with pre-commit configuration."""
    parser = argparse.ArgumentParser(
        description="Setup test project for integration testing"
    )
    parser.add_argument(
        "--runner",
        choices=["prek", "pre-commit", "both"],
        default="both",
        help="Which runner(s) to install (default: both)",
    )
    args = parser.parse_args()

    # Determine which runners to install
    runners_to_install = list(RUNNERS) if args.runner == "both" else [args.runner]

    # RUNNER_TEMP is set by GitHub Actions (and `act`).
    # Fallback to ~/tmp for direct local execution.
    if not os.environ.get("RUNNER_TEMP"):
        os.environ["RUNNER_TEMP"] = str(Path.home() / "tmp")

    test_dir = Path(os.environ["RUNNER_TEMP"]) / "test-project"
    test_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(test_dir)

    if not (git := shutil.which("git")):
        msg = "git is not installed"
        raise RuntimeError(msg)

    # Create virtual environment and install runners
    venv_dir = test_dir / ".venv"
    print(f"Creating virtual environment at {venv_dir}")
    pip_path = create_venv(venv_dir)

    print(f"Installing runners: {', '.join(runners_to_install)}")
    install_runners(pip_path, runners_to_install)
    verify_runners(venv_dir, runners_to_install)

    # Output venv bin directory for workflow to use
    venv_bin = get_venv_bin_dir(venv_dir)
    print(f"VENV_BIN={venv_bin}")

    # Initialize git repo
    subprocess.run([git, "init"], check=True)
    subprocess.run([git, "config", "user.email", "test@test.com"], check=True)
    subprocess.run([git, "config", "user.name", "Test"], check=True)

    # Create .pre-commit-config.yaml
    workspace = os.environ.get(
        "GITHUB_WORKSPACE", os.environ.get("CI_PROJECT_DIR", ".")
    )
    config = f"""repos:
  - repo: {workspace}
    rev: HEAD
    hooks:
      - id: ensure-uv

  - repo: local
    hooks:
      - id: verify-uv
        name: Verify uv is available
        entry: uv tool run mypy --version
        language: system
        always_run: true
        pass_filenames: false
"""
    Path(".pre-commit-config.yaml").write_text(config, encoding="utf-8")

    # Create test file
    Path("test.txt").write_text("test", encoding="utf-8")

    # Stage files
    subprocess.run([git, "add", "."], check=True)

    print(f"Test project created at {test_dir}")
    print(f"Runners installed: {', '.join(runners_to_install)}")


if __name__ == "__main__":
    main()
