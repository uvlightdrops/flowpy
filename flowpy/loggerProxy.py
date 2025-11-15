"""Logger proxy utilities for flowpy: lazy logger (LoggerProxy) implementation.

Provides setup_logger(name, logfile, ...) which returns a LoggerProxy.
The proxy defers creation of file handlers until the first actual logging
call, so importing modules that call `setup_logger(...)` at module level
won't create log files immediately.

Usage remains backwards-compatible:
    from flowpy.loggerProxy import setup_logger
    logger = setup_logger(__name__, __name__ + '.log')

The proxy implements common Logger methods and delegates to a real
logging.Logger after the first emission. Initialization is thread-safe.
"""

from __future__ import annotations

import logging
import os
import threading
from logging import Logger
from typing import Optional
from flowpy.utils_old import _resolve_project_dir, _load_config
from pathlib import Path

from pygments.filters import get_filter_by_name


class LoggerProxy:
    """Proxy that lazily initializes an actual Logger and its handlers.

    It exposes the common logging API (info, debug, warning, error, exception,
    critical, log, setLevel, addHandler, etc.). The real logger and file
    handler(s) are created on the first logging call.
    """

    def __init__(self, name: str, logfile: Optional[str] = None, *,
                 level: int = logging.INFO, fmt: Optional[str] = None,
                 maxBytes: Optional[int] = None, backupCount: int = 0,
                 encoding: Optional[str] = 'utf-8') -> None:
        self._name = name
        self._logfile = logfile
        self._level = level
        self._fmt = fmt
        self._maxBytes = maxBytes
        self._backupCount = backupCount
        self._encoding = encoding

        self._real: Optional[Logger] = None
        self._lock = threading.RLock()


    def get_formatter(self):
        #fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        #fmt = '%(asctime)s %(lineno)d/%(funcName)s  %(name)s: %(message)s'
        fmt = '%(asctime)s : %(message)s'
        if self._fmt:
            fmt = self._fmt
        return logging.Formatter(fmt, datefmt='%M:%S')


    def _ensure_real(self) -> Logger:
        """Create and return the underlying real logger, thread-safely."""
        if self._real is not None:
            return self._real

        with self._lock:
            if self._real is not None:
                return self._real

            # ensure config is loaded (lazy) and use local maps (no global mapping vars)
            cfg = _load_config()
            debug_map = cfg.get('debug', [])
            #print(debug_map)
            info_map = cfg.get('info', [])
            warn_map = cfg.get('warning', [])

            # Determine level using the (lazy-loaded) config maps
            try:
                level = logging.INFO
                name = self._name
                #print('name:', name)
                if (name in debug_map):
                    level = logging.DEBUG
                if isinstance(name, str) or (name in debug_map):
                    level = logging.DEBUG
                elif name in info_map:
                    level = logging.INFO
                elif name in warn_map:
                    level = logging.WARNING
                #print(level, name)

            except Exception:
                level = self._level
                #print("set default", level)

            logger = logging.getLogger(self._name)
            logger.setLevel(level)
            # Avoid duplicate handlers when running tests/imports repeatedly
            # The proxy manages its own handlers; do not propagate by default.
            logger.propagate = False

            formatter = self.get_formatter()
            #formatter = logging.Formatter(self._fmt)

            # If a logfile was requested, try to create its directory and handler.
            if self._logfile:

                base = _resolve_project_dir()
                abs_log_path = Path(base).joinpath('log')
                abs_log_path.mkdir(parents=True, exist_ok=True)
                abs_log_file = abs_log_path.joinpath(self._logfile)
                try:
                    fh = logging.FileHandler(abs_log_file, encoding=self._encoding)
                    fh.setFormatter(formatter)
                    logger.addHandler(fh)
                except Exception:
                    # If file handler cannot be created, fall back to a stream handler
                    sh = logging.StreamHandler()
                    sh.setFormatter(formatter)
                    logger.addHandler(sh)
            else:
                # No logfile requested: ensure at least one handler exists
                if not logger.handlers:
                    sh = logging.StreamHandler()
                    sh.setFormatter(formatter)
                    logger.addHandler(sh)
                    #print(self._logfile)
            self._real = logger

            return self._real

    # Basic logging methods delegate to the real logger (ensuring init).
    def debug(self, *args, **kwargs):
        return self._ensure_real().debug(*args, **kwargs)

    def info(self, *args, **kwargs):
        return self._ensure_real().info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        return self._ensure_real().warning(*args, **kwargs)

    def warn(self, *args, **kwargs):  # backward compatibility
        return self.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        return self._ensure_real().error(*args, **kwargs)

    def exception(self, *args, **kwargs):
        return self._ensure_real().exception(*args, **kwargs)

    def critical(self, *args, **kwargs):
        return self._ensure_real().critical(*args, **kwargs)

    def log(self, *args, **kwargs):
        return self._ensure_real().log(*args, **kwargs)

    def setLevel(self, level):
        # If the real logger exists, set it there too
        if self._real is not None:
            self._real.setLevel(level)
        self._level = level

    def addHandler(self, h):
        self._ensure_real().addHandler(h)

    def removeHandler(self, h):
        if self._real is not None:
            self._real.removeHandler(h)

    def getEffectiveLevel(self):
        return self._ensure_real().getEffectiveLevel()

    @property
    def name(self):
        return self._name

    @property
    def handlers(self):
        return self._ensure_real().handlers

    def isEnabledFor(self, level):
        return self._ensure_real().isEnabledFor(level)

    def __getattr__(self, item):
        # Delegate remaining attributes to the real logger (initializing it)
        if item.startswith('_'):
            raise AttributeError(item)
        real = self._ensure_real()
        return getattr(real, item)


def setup_logger(name: str, logfile: Optional[str] = None, **kwargs) -> LoggerProxy:
    """Factory for a LoggerProxy.

    Parameters
    - name: logger name (str)
    - logfile: optional path to logfile (str)
    - kwargs: optional settings accepted by LoggerProxy (level, fmt, maxBytes, backupCount, encoding)

    Returns a LoggerProxy instance. No files are created on import.
    """
    return LoggerProxy(name, logfile, **kwargs)

