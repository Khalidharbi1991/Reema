"""Formatter modules for document conversion."""

from importlib import import_module

_MODULES = {
    "PDFFormatter": "pdf_formatter", "DOCXFormatter": "docx_formatter",
    "MarkdownFormatter": "markdown_formatter", "HTMLFormatter": "html_formatter",
}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f".{_MODULES[name]}", __name__), name)

__all__ = [
    "PDFFormatter",
    "DOCXFormatter",
    "MarkdownFormatter",
    "HTMLFormatter",
]
