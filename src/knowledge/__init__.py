"""Knowledge base modules for IT standards and frameworks."""

__all__ = ["ITOMParser", "ITOMDocxParser"]


def __getattr__(name):
    from importlib import import_module
    modules = {"ITOMParser": "itom_parser", "ITOMDocxParser": "itom_docx_parser"}
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(f".{modules[name]}", __name__), name)
