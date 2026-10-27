"""Explicit local ITOM PDF extraction with page/character provenance."""
from .source_parser import LocalSourceParser
from ..utils.config import config_manager


class ITOMParser(LocalSourceParser):
    def __init__(self):
        self.name = "ITOM Parser"
        self.pdf_path = config_manager.system_config.references_dir / "itom" / "ITOM.pdf"
        self.knowledge_cache, self.records = {}, []

    @property
    def path(self):
        return self.pdf_path
