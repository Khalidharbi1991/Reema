import pytest
from pathlib import Path
from scripts.verify_exports import verify
from src.knowledge.retrieval import units, make_chunks


@pytest.mark.asyncio
async def test_real_pdf_and_docx_export(tmp_path):
    try:
        from src.formatters.pdf_formatter import PDFFormatter
    except (ImportError, OSError) as error:
        pytest.skip(f"PDF native libraries unavailable: {type(error).__name__}")
    outputs = await verify(tmp_path)
    records = make_chunks(Path(outputs["pdf"]), "synthetic.pdf", "public")
    assert any("Document Control" in r["text"] for r in records)
    assert all("page " in r["location"] for r in records)


@pytest.mark.asyncio
async def test_docx_empty_cells_and_legacy_parser(tmp_path, monkeypatch):
    from src.utils.config import config_manager
    from src.knowledge import ITOMDocxParser, ITOMParser
    monkeypatch.setattr(config_manager.system_config, "references_dir", tmp_path)
    assert ITOMParser().extract_knowledge() == {}
    outputs = await verify(tmp_path, ["docx"])
    parser = ITOMDocxParser()
    parser.docx_path = Path(outputs["docx"])
    knowledge = parser.extract_knowledge()
    assert knowledge
    assert parser.search_knowledge("restoration")
    assert "SRC-" in parser.get_relevant_context("restoration")


def test_unsupported_and_empty_sources_fail(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("")
    with pytest.raises(ValueError, match="no readable text"):
        make_chunks(path, "empty", "public")
    with pytest.raises(ValueError, match="format"):
        units(tmp_path / "source.exe")
