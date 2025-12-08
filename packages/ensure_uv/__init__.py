"""Pre-commit hook to ensure uv is installed and available."""

from .main import main
from .version import __version__

__all__ = ["__version__", "main"]
