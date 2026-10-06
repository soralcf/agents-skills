"""Serialize applied maintenance and restore all managed artifacts on exceptions."""
import fcntl
import functools
import hashlib
import inspect
from pathlib import Path
import shutil
import tempfile


# Every path an applied maintenance command is allowed to rewrite.
MANAGED_PATHS = ('.agents/skills', '.agents/plugins', 'registry')


def transactional(function):
    @functools.wraps(function)
    def wrapped(catalog, *args, **kwargs):
        bound = inspect.signature(function).bind(catalog, *args, **kwargs)
        if not bound.arguments.get('apply') or getattr(catalog, '_transaction', False):
            return function(catalog, *args, **kwargs)
        key = hashlib.sha256(str(catalog.root).encode()).hexdigest()
        with (Path(tempfile.gettempdir()) / ('skill-maintenance-' + key + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # Reject a stale in-memory catalog rather than overwriting another writer.
            import json
            if (json.loads(catalog.skills_path.read_text()) != catalog.skills_doc or
                    json.loads(catalog.workflows_path.read_text()) != catalog.workflows_doc):
                raise RuntimeError('Registry changed; reload the catalog before applying')
            backup = Path(tempfile.mkdtemp(prefix='skill-maintenance-backup-'))
            for name in MANAGED_PATHS:
                shutil.copytree(catalog.root / name, backup / name)
            catalog._transaction = True
            try:
                result = function(catalog, *args, **kwargs)
            except BaseException:
                try:
                    for name in MANAGED_PATHS:
                        shutil.rmtree(catalog.root / name)
                        shutil.copytree(backup / name, catalog.root / name)
                    catalog.__init__(catalog.root)
                except BaseException as recovery_error:
                    raise RuntimeError(f'Recovery failed; intact backup retained at {backup}') from recovery_error
                else:
                    shutil.rmtree(backup)
                raise
            else:
                shutil.rmtree(backup)
                return result
            finally:
                catalog._transaction = False
    return wrapped
