"""
Installed as sitecustomize.py before great-docs build.

Patches builtins.__import__ so that after any module import, if sys.stdout
or sys.stderr has been replaced with an object lacking isatty() (e.g.
chainladder's _DetailStream), the method is added automatically.

This prevents the AttributeError that breaks llms-full.txt generation.
"""
import sys
import builtins


def _ensure_isatty():
    for attr in ("stdout", "stderr"):
        s = getattr(sys, attr, None)
        if s is not None and not hasattr(type(s), "isatty"):
            type(s).isatty = lambda self: False


_real_import = builtins.__import__


def _patched_import(name, *args, **kwargs):
    result = _real_import(name, *args, **kwargs)
    _ensure_isatty()
    return result


builtins.__import__ = _patched_import
_ensure_isatty()
