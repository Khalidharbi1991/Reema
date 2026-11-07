import hashlib

import pytest
import yaml

from src.knowledge.retrieval import ReferenceIndex, make_chunks, chunks
from src.utils.config import SystemConfig
from src.utils.quality import quality_report, validate_quality


def manifest_settings(tmp_path, **overrides):
    root = tmp_path / "teams" / "documentation" / "input" / "references"
    root.mkdir(parents=True)
    source = root / "policy.md"
    source.write_text("# Unrelated heading\n" + "Boilerplate " * 300 + "Incident tail evidence")
    entry = {"path": "policy.md", "classification": "confidential", "external_ai_allowed": True,
             "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    entry.update(overrides)
    (root / "manifest.yaml").write_text(yaml.safe_dump({"version": 1, "sources": [entry]}))
    return SystemConfig(_env_file=None, project_root=tmp_path), source


def test_retrieval_searches_full_body_and_preserves_provenance(tmp_path):
    settings, source = manifest_settings(tmp_path)
    hits = ReferenceIndex(settings).search("Incident")
    assert len(hits) == 1 and "tail evidence" in hits[0]["text"]
    assert hits[0]["source"] == "policy.md" and "characters" in hits[0]["location"]
    assert hits[0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert ReferenceIndex(settings).search("doesnotoccur") == []


@pytest.mark.parametrize("overrides", [{"external_ai_allowed": False}, {"classification": "restricted"}])
def test_private_sources_require_explicit_permission(tmp_path, overrides):
    settings, _ = manifest_settings(tmp_path, **overrides)
    assert ReferenceIndex(settings).records == []


@pytest.mark.parametrize("change", ["hash", "path", "duplicate", "classification", "symlink"])
def test_invalid_or_changed_manifest_sources_fail_closed(tmp_path, change):
    settings, source = manifest_settings(tmp_path)
    path = settings.reference_manifest
    data = yaml.safe_load(path.read_text())
    if change == "hash":
        source.write_text("Changed bytes")
    elif change == "path":
        data["sources"][0]["path"] = "../../outside.md"
    elif change == "duplicate":
        data["sources"].append(data["sources"][0].copy())
    elif change == "classification":
        data["sources"][0]["classification"] = "unknown"
    else:
        outside = tmp_path / "outside.md"
        outside.write_text("Outside")
        link = settings.references_dir / "link.md"
        link.symlink_to(outside)
        data["sources"][0]["path"] = "link.md"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        ReferenceIndex(settings)


def test_docx_retrieval_preserves_tables_and_repeated_headings(tmp_path):
    from docx import Document
    doc = Document()
    doc.add_heading("Repeated")
    doc.add_paragraph("First body")
    doc.add_heading("Repeated")
    doc.add_paragraph("Second body")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "Table evidence"
    path = tmp_path / "source.docx"
    doc.save(path)
    extracted = make_chunks(path, "source.docx", "internal")
    assert len(extracted) == 5
    assert "Table evidence" in extracted[-1]["text"]


def test_chunks_cover_every_character_without_loss():
    text = "start" + "a" * 50000 + "end"
    assert "".join(part for _, part in chunks(text, 24000)) == text


def test_raci_and_source_citation_checks(sample_sop_content):
    original = sample_sop_content[sample_sop_content.index("| Role"):sample_sop_content.index("## 4.")]
    valid = "| Activity | Owner | Operator |\n| --- | --- | --- |\n| Resolve | A | R |\n\n"
    content = sample_sop_content.replace(original, valid)
    assert not quality_report(content)["errors"]
    for bad_row in ["| Later task | INVALID | R |", "| Later task | A |"]:
        with pytest.raises(ValueError, match="invalid activity row"):
            validate_quality(content.replace("| Resolve | A | R |", "| Resolve | A | R |\n" + bad_row))
    with pytest.raises(ValueError, match="exactly one accountable"):
        validate_quality(content.replace("| A | R |", "| A | A |"))
    with pytest.raises(ValueError, match="Unknown source"):
        validate_quality(content + "\n[SRC-abcdef]", sources={})
    assert quality_report(content, ["Absent Standard"])["standards_missing"] == ["Absent Standard"]


def test_html_rendering_disables_script_file_and_network_resources():
    from src.formatters.safe_html import render_markdown, deny_fetch
    from bs4 import BeautifulSoup
    result = render_markdown('<script>alert(1)</script>\n![local](file:///etc/passwd)\n![remote](https://example.test/x)\n[bad](javascript:alert(1))\n[good](https://example.test)')
    soup = BeautifulSoup(result, "html.parser")
    assert not soup.find_all(["script", "img", "iframe"])
    assert not any("javascript:" in a.get("href", "") for a in soup.find_all("a"))
    assert soup.find("a", href="https://example.test")
    with pytest.raises(ValueError):
        deny_fetch("file:///etc/passwd")
