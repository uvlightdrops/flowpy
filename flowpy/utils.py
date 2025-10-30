"""Compatibility shim for flowpy logger utilities.

Keeps the historical import path `from flowpy.utils import setup_logger` working
by re-exporting from `flowpy.loggerProxy` and providing small helper functions
used across the codebase (safe_fn, log_memory_usage).
"""

from .loggerProxy import LoggerProxy, setup_logger

import os
import re

__all__ = ["LoggerProxy", "setup_logger", "safe_fn", "log_memory_usage"]


def safe_fn(path: str, maxlen: int = 63) -> str:
    """Create a filesystem/db-safe name from a path or filename.

    - Strips directories and extensions
    - Replaces non-alphanumeric characters with '_'
    - Lowercases the result
    - Ensures it doesn't start with a digit by prefixing 't' if needed
    - Truncates to `maxlen` characters
    """
    if path is None:
        return 'noname'
    name = os.path.basename(str(path))
    name = os.path.splitext(name)[0]
    # replace non word chars with underscore
    name = re.sub(r"[^0-9A-Za-z]+", "_", name)
    name = name.strip("_")
    name = name.lower()
    if not name:
        name = 'noname'
    # ensure starts with letter
    if name[0].isdigit():
        name = 't_' + name
    if len(name) > maxlen:
        name = name[:maxlen]
    return name


def log_memory_usage() -> str:
    """Return a small human-readable memory usage string for the current process.

    Tries `psutil` if available, otherwise falls back to `resource` (Unix).
    Returns a string like 'RSS: 12.3MB'.
    """
    try:
        import psutil
        p = psutil.Process()
        rss = p.memory_info().rss
    except Exception:
        try:
            import resource
            # ru_maxrss is in kilobytes on Linux
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        except Exception:
            return 'mem:unknown'

    # format
    mb = float(rss) / (1024.0 * 1024.0)
    return f"RSS: {mb:.1f}MB"
