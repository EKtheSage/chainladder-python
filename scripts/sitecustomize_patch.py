"""
Installed as sitecustomize.py before great-docs build.

Patches builtins.__import__ so that after any module import, if sys.stdout
or sys.stderr has been replaced with an object lacking isatty() (e.g.
chainladder's _DetailStream), the method is added automatically.

This prevents the AttributeError that breaks llms-full.txt generation.

Also patches inspect.getdoc to strip sphinx.ext.doctest RST directives
(.. testsetup::, .. testcode::, .. testoutput::) from docstrings before
great-docs processes them. The source docstrings are unchanged; Sphinx
still sees and validates the directives normally.
"""
import re
import sys
import inspect
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


# ---------------------------------------------------------------------------
# Strip sphinx.ext.doctest directives so great-docs renders clean code blocks
# ---------------------------------------------------------------------------

# Remove entire .. testsetup:: blocks (directive line + blank lines + indented content).
# These are setup-only imports not meant to be shown in rendered docs.
_TESTSETUP_BLOCK = re.compile(
    r"[ \t]*\.\. testsetup::[ \t]*[^\n]*\n"  # directive declaration line
    r"(?:[ \t]*\n)*"                           # optional blank lines
    r"(?:[ \t]+[^\n]*\n)*",                    # indented content block
    re.MULTILINE,
)

# Remove only the directive declaration lines for testcode / testoutput,
# keeping their indented content so great-docs renders them as code blocks.
_DIRECTIVE_DECL = re.compile(
    r"^[ \t]*\.\. (?:testcode|testoutput)::[ \t]*[^\n]*\n",
    re.MULTILINE,
)


def _strip_doctest_directives(doc):
    if not doc:
        return doc
    doc = _TESTSETUP_BLOCK.sub("", doc)
    doc = _DIRECTIVE_DECL.sub("\n", doc)
    return doc


_original_getdoc = inspect.getdoc


def _patched_getdoc(obj):
    return _strip_doctest_directives(_original_getdoc(obj))


inspect.getdoc = _patched_getdoc
