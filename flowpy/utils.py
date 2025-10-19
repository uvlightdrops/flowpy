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

# requires logconf.ini in the main script directory
# [debug]
# mymodule=
### so use = sign to fit into configparser ini format
config = configparser.ConfigParser()
ini_path = Path('logconf.ini')
if not ini_path.exists():
    print('path not found: %s', ini_path)
    sys.exit()

config.read(ini_path)
loglevel_error  = config['error']
loglevel_warning = config['warning']
loglevel_debug  = config['debug']
loglevel_info   = config['info']
off = []


lld = loglevel_debug
lli = loglevel_info
lle = loglevel_error
llw = loglevel_warning
#print(lld)


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
        return project_dir
    except Exception:
        pass
    # check environment variables
    for v in ('PROJECT_DIR', 'FLOWPY_PROJECT_DIR'):
        val = os.environ.get(v)
        if val:
            try:
                project_dir = Path(val)
                return project_dir
            except Exception:
                continue
    # fallback to cwd
    project_dir = Path.cwd()
    return project_dir


def setup_logger(name, log_name, level=None):
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

    handlers = []

    # Try to create a FileHandler if possible
    if log_file:
        # Formatter
        dfmt = '%H:%M:%S'
        formatter = logging.Formatter('%(asctime)s, %(lineno)d/%(funcName)s, "%(message)s"', datefmt=dfmt)

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
            handler_r = RichHandler()
            handler_r.setFormatter(formatter)
            handlers.append(handler_r)
        except Exception:
            pass

    if not handlers:
        handler_s = logging.StreamHandler()
        handler_s.setFormatter(formatter)
        handlers.append(handler_s)

    logger = logging.getLogger(name)

    # Determine level using the (eagerly loaded) config
    if not level:
        try:
            level = logging.INFO
            if (name in lld):
                level = logging.DEBUG
            if isinstance(log_name, str) and ((log_id in lld) or (log_name[:-4] in lld)):
                level = logging.DEBUG
            elif log_id in lli or name in lli:
                level = logging.INFO
            elif log_id in llw or name in llw:
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


def log_class_mro(cls):
    """Logs the Method Resolution Order (MRO) of a class."""
    mro = cls.__mro__
    logger = setup_logger(__name__, __name__ + '.log', level=logging.DEBUG)
    logger.debug("Class MRO for %s: %s", cls.__name__, ' -> '.join([c.__name__ for c in mro]))


def safe_fn(unsafe_str):
    safe = unsafe_str.replace(' ', '_')
    safe = safe.replace('/', '__')
    return safe


def log_memory_usage():
    with open('/proc/self/status') as f:
        for line in f:
            if line.startswith('VmRSS:'):
                result = 'MEMORY: ' + line.strip()
                break
    return result
