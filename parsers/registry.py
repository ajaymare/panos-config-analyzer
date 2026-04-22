"""Auto-discover and register all parser subclasses."""
import importlib
import pkgutil
from pathlib import Path

from .base import BaseParser


def get_parsers() -> list:
    """Discover all BaseParser subclasses in the parsers package.

    Returns:
        List of parser classes, sorted by FEATURE_NAME
    """
    # Import all modules in this package
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name in ('base', 'config_detector', 'registry', '__init__'):
            continue
        importlib.import_module(f'.{module_name}', package='parsers')

    # Collect all subclasses
    parsers = []
    for cls in BaseParser.__subclasses__():
        if cls.FEATURE_NAME:  # Skip abstract intermediaries
            parsers.append(cls)

    return sorted(parsers, key=lambda c: c.FEATURE_NAME)
