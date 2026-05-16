"""
Installed as sitecustomize.py before great-docs build.

Patches builtins.__import__ so that after any module import, if sys.stdout
or sys.stderr has been replaced with an object lacking isatty() (e.g.
chainladder's _DetailStream), the method is added automatically.

This prevents the AttributeError that breaks llms-full.txt generation.

Also patches inspect.getdoc and griffe.Docstring.parse to translate
sphinx.ext.doctest RST directives (.. testsetup::, .. testcode::,
.. testoutput::) into Quarto-friendly Markdown before great-docs processes
them. The source docstrings are unchanged; Sphinx still sees and validates the
directives normally.
"""
import sys
import inspect
import builtins
import re
import textwrap


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
# Translate sphinx.ext.doctest directives into Quarto-friendly Markdown.
# ---------------------------------------------------------------------------

_DOCTEST_DIRECTIVE = re.compile(
    r"^[ \t]*\.\.\s+(testsetup|testcode|testoutput)\s*:*\s*[^\n]*$"
)


def _dedent_block(lines):
    return textwrap.dedent("\n".join(lines)).strip("\n")


def _read_directive_block(lines, start):
    """Read an indented RST directive body starting after the directive line."""
    i = start
    block = []

    while i < len(lines) and not lines[i].strip():
        i += 1

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            block.append(line)
            i += 1
        elif line[0] in (" ", "\t"):
            block.append(line)
            i += 1
        else:
            break

    return _dedent_block(block), i


def _append_blank(out):
    if out and out[-1] != "":
        out.append("")


def _append_code_block(out, code):
    if not code:
        return
    _append_blank(out)
    out.append("``` {.python .cell-code}")
    out.extend(code.splitlines())
    out.append("```")
    out.append("")


def _append_output_block(out, output):
    if not output:
        return
    _append_blank(out)
    out.append("::: {.cell-output .cell-output-stdout}")
    out.append("```")
    out.extend(output.splitlines())
    out.append("```")
    out.append(":::")
    out.append("")


def _translate_doctest_directives(doc):
    if not doc:
        return doc

    lines = doc.splitlines()
    out = []
    i = 0

    while i < len(lines):
        match = _DOCTEST_DIRECTIVE.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue

        directive = match.group(1)
        body, i = _read_directive_block(lines, i + 1)

        if directive == "testcode":
            _append_code_block(out, body)
        elif directive == "testoutput":
            _append_output_block(out, body)
        # testsetup is setup-only, matching Sphinx's hidden rendered behavior.

    return "\n".join(out).strip("\n")


_original_getdoc = inspect.getdoc


def _patched_getdoc(obj):
    return _translate_doctest_directives(_original_getdoc(obj))


inspect.getdoc = _patched_getdoc


def _patch_griffe_docstring_parse():
    try:
        import griffe
    except Exception:
        return

    docstring_cls = getattr(griffe, "Docstring", None)
    if docstring_cls is None or getattr(docstring_cls, "_chainladder_patched", False):
        return

    original_parse = docstring_cls.parse

    def _patched_parse(self, *args, **kwargs):
        original_value = self.value
        if isinstance(original_value, str):
            self.value = _translate_doctest_directives(original_value)
        try:
            return original_parse(self, *args, **kwargs)
        finally:
            self.value = original_value

    docstring_cls.parse = _patched_parse
    docstring_cls._chainladder_patched = True


_patch_griffe_docstring_parse()
