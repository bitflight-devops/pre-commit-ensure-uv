"""Compute the version number and store it in the `__version__` variable.

Based on <https://github.com/maresb/hatch-vcs-footgun-example>.
"""

from __future__ import annotations

import pathlib


def _get_hatch_version() -> str | None:
    """Compute the most up-to-date version number in a development environment.

    For more details, see <https://github.com/maresb/hatch-vcs-footgun-example/>.

    Returns:
        The version string from hatch-vcs, or None if Hatchling is not installed.
    """
    try:
        # Lazy import: hatchling is an optional dev-only dependency
        from hatchling.metadata.core import ProjectMetadata  # noqa: PLC0415
        from hatchling.plugin.manager import PluginManager  # noqa: PLC0415
        from hatchling.utils.fs import locate_file  # noqa: PLC0415
    except ImportError:
        # Hatchling is not installed, so probably we are not in
        # a development environment.
        return None

    pyproject_toml = locate_file(__file__, "pyproject.toml")
    if pyproject_toml is None:
        raise RuntimeError("pyproject.toml not found although hatchling is installed")
    root = str(pathlib.Path(pyproject_toml).parent)
    metadata = ProjectMetadata(root=root, plugin_manager=PluginManager())
    # Version can be either statically set in pyproject.toml or computed dynamically:
    output_version: str | None = metadata.core.version or metadata.hatch.version.cached
    return str(output_version) if output_version is not None else None


def _get_importlib_metadata_version() -> str:
    """Compute the version number using importlib.metadata.

    This is the official Pythonic way to get the version number of an installed
    package. However, it is only updated when a package is installed. Thus, if a
    package is installed in editable mode, and a different version is checked out,
    then the version number will not be updated.

    Returns:
        The version string from package metadata.
    """
    # Lazy import: deferred to avoid import overhead at module load time
    from importlib.metadata import version  # noqa: PLC0415

    return version(__package__ or __name__)


__version__ = _get_hatch_version() or _get_importlib_metadata_version()
