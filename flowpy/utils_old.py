import logging
from pathlib import Path
import os
import configparser

# Do not import env at module import time; resolve lazily in _resolve_project_dir().
project_dir = None

# optional rich logging handler
try:
    from rich.logging import RichHandler
except Exception:
    RichHandler = None

# Lazy config loader: returns a dict with section dicts, no globals created
_config_cache = None

def _load_config():
    """Return a dict-like mapping of config sections (debug, info, warning, error).

    Tries PROJECT_DIR then CWD. Returns empty dicts if no file found.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    cfg = configparser.ConfigParser()
    candidates = []
    try:
        pd = _resolve_project_dir()
        candidates.append(Path(pd) / 'logconf.ini')
    except Exception:
        pass
    candidates.append(Path('logconf.ini'))

    for p in candidates:
        try:
            if p.exists():
                print('using log config file:', p)
                cfg.read(p)
                def sec(name):
                    try:
                        return list(cfg[name])
                    except Exception:
                        return []
                _config_cache = {
                    'debug': sec('debug'),
                    'info': sec('info'),
                    'warning': sec('warning'),
                    'error': sec('error'),
                }
                return _config_cache
        except Exception:
            continue
    #print(_config_cache)
    _config_cache = {'debug': [], 'info': [], 'warning': [], 'error': []}
    return _config_cache


def _resolve_project_dir():
    """Resolve a sensible project_dir.

    Order:
      1. previously resolved/project_dir
      2. import local env module if present now
      3. environment variables PROJECT_DIR or FLOWPY_PROJECT_DIR
      4. current working directory
    """
    global project_dir
    if project_dir is not None:
        return Path(project_dir)
    # try to import env lazily (caller project may have put its directory on sys.path)
    try:
        import env as _env2
        project_dir = Path(_env2.project_dir)
        print("Resolved PROJECT_DIR from env module:", project_dir)
        return project_dir
    except Exception:
        pass
    # check environment variables
    for v in ('PROJECT_DIR', 'FLOWPY_PROJECT_DIR'):
        val = os.environ.get(v)
        if val:
            try:
                project_dir = Path(val)
                print("Resolved PROJECT_DIR from env var", v, ":", project_dir)
                return project_dir
            except Exception:
                continue
    # fallback to cwd
    project_dir = Path.cwd()
    print("Warning: could not resolve PROJECT_DIR, using CWD:", project_dir)
    return project_dir


def OLD_setup_logger(name, log_name, level=None):
    """Create or return a logger with a FileHandler (if possible) and a Rich/Stream fallback.

    This function is safe to call at import time because it will not raise when
    the log directory or config is missing.
    """
    log_id = name

    # Determine candidate log file path
    log_file = None
    try:
        if isinstance(log_name, str) and len(log_name.split('/')) == 1:
            parts = log_name.split('.')
            if len(parts) == 3:
                log_name_clean = '.'.join(parts[1:3])
            else:
                log_name_clean = log_name
            base = _resolve_project_dir()
            log_file = str(Path(base).joinpath('log', log_name_clean))
        else:
            log_file = str(Path(log_name))
    except Exception:
        log_file = None
    #print('log_file:', log_file)

    # ensure config is loaded (lazy) and use local maps (no global mapping vars)
    cfg = _load_config()
    debug_map = cfg.get('debug', [])
    #print(debug_map)
    info_map = cfg.get('info', [])
    warn_map = cfg.get('warning', [])
    err_map = cfg.get('error', [])
    handlers = []

    dfmt = '%H:%M:%S'
    rich_dfmt = '%H:%M:%S'
    formatter = logging.Formatter('%(asctime)s, %(lineno)d/%(funcName)s, "%(message)s"', datefmt=dfmt)
    # Rich-specific formatter: more compact, show level first and then time/function
    #rich_formatter = logging.Formatter('%(levelname)s %(asctime)s, %(lineno)d/%(funcName)s: %(message)s', datefmt=rich_dfmt)
    rich_formatter = logging.Formatter('%(asctime)s, %(lineno)d/%(funcName)s: %(message)s', datefmt=rich_dfmt)
    # Try to create a FileHandler if possible
    if log_file:
        # Formatter

        try:
            log_dir = Path(log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            handler_f = logging.FileHandler(log_file)
            handler_f.setFormatter(formatter)
            handlers.append(handler_f)
        except Exception:
            # best-effort: skip file handler
            pass

    # Add rich or stream handler as fallback
    if RichHandler:
        try:
            # Use a dedicated formatter for RichHandler so the console output is
            # more compact and shows the log level up front.
            handler_r = RichHandler()
            handler_r.setFormatter(rich_formatter)
            handlers.append(handler_r)
        except Exception:
            pass

    if not handlers:
        handler_s = logging.StreamHandler()
        handler_s.setFormatter(formatter)
        handlers.append(handler_s)

    logger = logging.getLogger(name)

    # Determine level using the (lazy-loaded) config maps
    if not level:
        try:
            level = logging.INFO
            #print('name:', name, 'log_id:', log_id, 'log_name:', log_name)
            if (name in debug_map):
                level = logging.DEBUG
            if isinstance(log_name, str) and ((log_id in debug_map) or (log_name[:-4] in debug_map)):
                level = logging.DEBUG
            elif log_id in info_map or name in info_map:
                level = logging.INFO
            elif log_id in warn_map or name in warn_map:
                level = logging.WARNING
        except Exception:
            level = logging.INFO

    logger.setLevel(level)

    # Avoid duplicate handlers
    existing = {(type(h), getattr(h, 'baseFilename', None)) for h in logger.handlers}
    for h in handlers:
        key = (type(h), getattr(h, 'baseFilename', None))
        if key not in existing:
            logger.addHandler(h)
            existing.add(key)

    return logger

