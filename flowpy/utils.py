"""Compatibility shim for flowpy logger utilities.

Keeps the historical import path `from flowpy.utils import setup_logger` working
by re-exporting from `flowpy.loggerProxy` and providing small helper functions
used across the codebase (safe_fn, log_memory_usage).
"""

import logging
import sys
from functools import lru_cache
from .utils_old import _load_config, _resolve_project_dir
from pathlib import Path

stream = False

__all__ = ["setup_logger", "safe_fn", "log_memory_usage"]

import os
import re

def get_default_log_format():
        fmt = '%(asctime)s %(lineno)d/%(funcName)s  %(name)s: %(message)s'
        #fmt = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"
        return (fmt)


def get_level_from_cfg(name):
    """Get log level from config for a given logger name."""
    cfg = _load_config()
    level = logging.INFO
    debug_map = cfg.get('debug', [])
    info_map = cfg.get('info', [])
    warn_map = cfg.get('warning', [])
    err_map = cfg.get('error', [])
    #print(debug_map)
    if name in debug_map:
        level = logging.DEBUG
    elif name in info_map:
        level = logging.INFO
    elif name in warn_map:
        level = logging.WARNING
    elif name in err_map:
        level = logging.ERROR
    #print(name, level)
    return level


class LazyFileHandler(logging.FileHandler):
    """FileHandler, der die Datei erst beim ersten Log-Eintrag öffnet."""
    def __init__(self, filename, mode='a', encoding=None, delay=True):
        super().__init__(filename, mode, encoding, delay)

@lru_cache(maxsize=16)
def setup_logger(name, log_file, level=None, fmt=None):
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    if level is None:
        level = get_level_from_cfg(name)
    logger.setLevel(level)

    fmt = fmt or get_default_log_format()
    formatter = logging.Formatter(fmt)

    if stream:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    if log_file:
        base = _resolve_project_dir()
        abs_log_path = Path(base).joinpath('log')
        abs_log_path.mkdir(parents=True, exist_ok=True)
        abs_log_file = abs_log_path.joinpath(log_file)
        file_handler = LazyFileHandler(abs_log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


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
