"""Explicit local ITOM DOCX extraction retaining repeated headings and tables."""
from .source_parser import LocalSourceParser
from ..utils.config import config_manager


class ITOMDocxParser(LocalSourceParser):
    def __init__(self):
        self.name = "ITOM DOCX Parser"
        self.docx_path = config_manager.system_config.references_dir / "itom" / "ITOM.docx"
        self.knowledge_cache, self.records = {}, []

    @property
    def path(self):
        return self.docx_path
