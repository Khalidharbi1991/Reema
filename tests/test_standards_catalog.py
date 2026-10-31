"""Standards catalog: one source of truth and current framework editions."""

import shutil
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from src.utils.config import ConfigManager, SystemConfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return ConfigManager(SystemConfig(_env_file=None, project_root=tmp_path, config_dir=tmp_path / "config",
                                      output_dir=tmp_path / "output"))


def test_iso_27001_uses_the_2022_edition(catalog):
    standards = [value for values in catalog.standards_mapping.values() for value in values]
    assert not [value for value in standards if "27001:2013" in value]
    for process in ("security_operations", "compliance_audits", "risk_management"):
        assert "ISO/IEC 27001:2022" in catalog.standards_mapping[process]


def test_process_standards_come_only_from_the_mapping(catalog):
    assert all("standards" not in definition for definition in catalog.process_definitions.values())
    assert catalog.get_standards_for_process("Security Operations") == catalog.standards_mapping["security_operations"]


def test_process_level_standards_are_rejected_with_guidance(catalog):
    path = catalog.system_config.config_dir / "process_definitions.yaml"
    path.write_text(path.read_text().replace('name: "Change Management"',
                                             'name: "Change Management"\n  standards: ["ITIL v4"]'))
    with pytest.raises(ValueError, match="standards_mapping.yaml.*change_management"):
        ConfigManager(catalog.system_config)


def test_list_processes_shows_the_mapping_standards(catalog, monkeypatch):
    from src import main
    monkeypatch.setattr(main, "config_manager", catalog)
    monkeypatch.setattr(main, "console", Console(width=600))
    result = CliRunner().invoke(main.app, ["list-processes"])
    assert result.exit_code == 0, result.output
    assert "ISO/IEC 27001:2022, NIST Cybersecurity Framework, SOC 2 Type II, CIS Controls" in result.output
    assert "ISO/IEC 20000-1:2018 Section 8.2" in result.output


def test_compliance_audits_cover_saudi_frameworks_without_hipaa(catalog):
    assert catalog.standards_mapping["compliance_audits"] == [
        "ISO/IEC 27001:2022", "SOC 2 Type II", "NCA ECC-2:2024 (Essential Cybersecurity Controls)",
        "SDAIA PDPL (Personal Data Protection Law)", "GDPR", "PCI DSS"]


def test_nca_ecc_references_use_the_2024_edition(catalog):
    standards = [value for values in catalog.standards_mapping.values() for value in values]
    assert [value for value in standards if "ECC" in value] == [
        "NCA ECC-2:2024 (Essential Cybersecurity Controls)",
        "NCA ECC-2:2024 Control 2-2 (Identity and Access Management)"]
    for name in ("mohammad_standards_knowledge_ENHANCED.md", "rakan_access_knowledge_ENHANCED.md"):
        assert "ECC-1:2018" not in (ROOT / "src" / "knowledge" / name).read_text(encoding="utf-8")
