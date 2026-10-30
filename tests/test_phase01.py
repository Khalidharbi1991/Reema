"""Regression tests for process selection, fail-closed delivery and human review."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from src.utils.approvals import create_pending_record, read_record, record_decision
from src.utils.config import ConfigManager, SystemConfig, config_manager
from src.utils.validation import safe_filename, validate_formats, validate_sop

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    # A real validated catalog, with disposable paths and no credential use.
    shutil.copytree(ROOT / "config", tmp_path / "config")
    settings = SystemConfig(
        _env_file=None, project_root=tmp_path, config_dir=tmp_path / "config",
        output_dir=tmp_path / "output", anthropic_api_key="test-key",
        allow_external_ai=True,
    )
    return ConfigManager(settings)


@pytest.fixture
def pipeline(catalog, monkeypatch, sample_sop_content):
    from src.agents import leader_agent, format_agent
    monkeypatch.setattr(leader_agent, "config_manager", catalog)
    monkeypatch.setattr(format_agent, "config_manager", catalog)
    leader = leader_agent.LeaderAgent(api_key="test-key")
    workers = {
        "ResearchAgent": SimpleNamespace(research_process=AsyncMock(return_value={"raw_research": "Research"})),
        "StandardsAgent": SimpleNamespace(analyze_compliance=AsyncMock(return_value={"compliance_analysis": "Analysis"})),
        "ContentAgent": SimpleNamespace(generate_sop=AsyncMock(return_value=sample_sop_content), refine_content=AsyncMock(return_value=sample_sop_content)),
        "ReviewAgent": SimpleNamespace(review_content=AsyncMock(return_value={"quality_score": 90, "needs_revision": False, "issues": []})),
        "AccessAgent": SimpleNamespace(
            analyze_access_requirements=AsyncMock(return_value={"access_analysis": "Access"}),
            generate_access_content=AsyncMock(return_value="Access requirements"),
            validate_access_compliance=AsyncMock(return_value={"compliant": True}),
        ),
        "ProblemAgent": SimpleNamespace(
            research_problem_management=AsyncMock(return_value={"problem_research": "Problem"}),
            generate_problem_content=AsyncMock(return_value="Problem procedures"),
            validate_problem_compliance=AsyncMock(return_value={"compliant": True}),
        ),
        "DataAgent": SimpleNamespace(
            design_analytics_framework=AsyncMock(return_value={"analytics_framework": "KPIs"}),
            create_dashboard_design=AsyncMock(return_value={"dashboard_design": "Dashboard"}),
        ),
        "FormatAgent": format_agent.FormatAgent(),
    }
    for name, worker in workers.items():
        leader.register_worker(name, worker)
    return leader, catalog, workers


@pytest.mark.parametrize("name", ["Incident Management", "incident_management", " INCIDENT-management "])
def test_catalog_aliases_preserve_standards(catalog, name):
    key, definition = catalog.resolve_process(name)
    assert key == "incident_management"
    assert definition["specialists"] == ["problem"]
    assert catalog.get_standards_for_process(name) == catalog.standards_mapping[key]


def test_custom_process_requires_explicit_opt_in(catalog):
    with pytest.raises(ValueError, match="Unknown process"):
        catalog.resolve_process("New bespoke process")
    key, definition = catalog.resolve_process("New bespoke process", custom=True)
    assert key == "new_bespoke_process"
    assert definition["specialists"] == []
    with pytest.raises(ValueError):
        catalog.resolve_process("../", custom=True)


@pytest.mark.parametrize("filename, content, message", [
    ("agent_config.yaml", "{}", "nonempty mapping"),
    ("agent_config.yaml", "bad: {name: Test, role: Test, max_tokens: -1}", "max_tokens"),
    ("agent_config.yaml", "bad: {name: Test, role: Test, typo: true}", "typo"),
    ("agent_config.yaml", "bad: {name: Test, role: Test, max_tokens: '500'}", "max_tokens"),
    ("agent_config.yaml", "bad: {}\nbad: {}", "Duplicate YAML key"),
    ("process_definitions.yaml", "bad: {name: Test}", "category"),
    ("standards_mapping.yaml", "bad: [Example]", "every process"),
])
def test_invalid_config_fails_early(catalog, filename, content, message):
    (catalog.system_config.config_dir / filename).write_text(content)
    with pytest.raises(ValueError, match=message):
        ConfigManager(catalog.system_config)


def test_missing_yaml_is_actionable(catalog):
    (catalog.system_config.config_dir / "agent_config.yaml").unlink()
    with pytest.raises(ValueError, match="agent_config.yaml"):
        ConfigManager(catalog.system_config)


def test_ambiguous_catalog_alias_is_rejected(catalog):
    path = catalog.system_config.config_dir / "process_definitions.yaml"
    path.write_text(path.read_text().replace('name: "Change Management"', 'name: "Incident Management"'))
    with pytest.raises(ValueError, match="Ambiguous"):
        ConfigManager(catalog.system_config)


def test_paths_follow_project_root_and_docker_env(tmp_path, monkeypatch):
    monkeypatch.setenv("REEMA_OUTPUT_DIR", str(tmp_path / "container-output"))
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    settings = SystemConfig(_env_file=None, project_root=tmp_path)
    assert settings.output_dir == tmp_path / "container-output"
    assert settings.references_dir == tmp_path / "references"


@pytest.mark.asyncio
async def test_formatter_failure_cannot_report_partial_success(pipeline, sample_sop_content):
    _, catalog, workers = pipeline
    formatter = workers["FormatAgent"]
    formatter.formatters["html"].convert = AsyncMock(return_value=catalog.system_config.output_dir / "missing.html")
    with pytest.raises(ValueError, match="Missing, empty"):
        await formatter.convert_to_formats(sample_sop_content, ["markdown", "html"], "Test")


def test_section_validator_checks_end_of_document_and_code_fences(sample_sop_content):
    validate_sop(sample_sop_content)
    with pytest.raises(ValueError, match="Document Control"):
        validate_sop(sample_sop_content.replace("## 11. Document Control", "## Other"))
    with pytest.raises(ValueError, match="Document Control"):
        validate_sop(sample_sop_content.replace("Version 1.0 - Initial draft", ""))
    with pytest.raises(ValueError, match="required sections"):
        validate_sop("```markdown\n" + sample_sop_content + "\n```")


@pytest.mark.parametrize("name", ["..\\..\\secret", "../../secret", "a:b?c", "a/b", "a\nb"])
def test_safe_filename_stays_one_component(name):
    value = safe_filename(name)
    assert "/" not in value and "\\" not in value and ":" not in value
    assert value not in (".", "..")


def test_empty_and_reserved_names_and_formats_are_rejected():
    for name in ("../", "", "CON"):
        with pytest.raises(ValueError):
            safe_filename(name)
    with pytest.raises(ValueError):
        validate_formats([])
    assert validate_formats(["DOCX", "docx"]) == ["docx"]


@pytest.fixture
def approval(tmp_path):
    document = tmp_path / "draft.md"
    document.write_text("Reviewed draft")
    record = tmp_path / "approval.json"
    create_pending_record(record, "Test", {"markdown": str(document)}, 90)
    return record, document


def test_human_decision_has_identity_and_cannot_be_overwritten(approval):
    record, _ = approval
    result = record_decision(record, "approved", "Human reviewer", "Reviewed all drafts")
    assert result.status == "approved" and result.reviewer == "Human reviewer"
    assert result.decided_at and result.notes == "Reviewed all drafts"
    with pytest.raises(ValueError, match="already"):
        record_decision(record, "rejected", "Different reviewer")


@pytest.mark.parametrize("change", ["modified", "missing", "empty"])
def test_changed_artifact_cannot_be_approved(approval, change):
    record, document = approval
    if change == "missing":
        document.unlink()
    else:
        document.write_text("Different" if change == "modified" else "")
    with pytest.raises(ValueError):
        record_decision(record, "approved", "Reviewer")
    assert read_record(record).status == "awaiting_human_approval"
    assert not record.with_suffix(".json.lock").exists()
    # Rejection remains available even when artifacts were damaged.
    assert record_decision(record, "rejected", "Reviewer").status == "rejected"


def test_ai_owner_cannot_grant_approval():
    from src import agents
    assert not hasattr(agents, "OwnerAgent")
    assert "owner_agent" not in config_manager.agents_config


@pytest.mark.parametrize("missing", [False, True])
def test_supporting_review_records_are_bound_to_approval(tmp_path, missing):
    document = tmp_path / "draft.md"
    document.write_text("Synthetic test draft")
    evidence = tmp_path / "ready.json"
    evidence.write_text('{"review": "synthetic"}')
    path = tmp_path / "approval.json"
    create_pending_record(path, "Test", {"markdown": str(document)}, 90,
                          supporting_records={"ready": evidence})
    if missing:
        evidence.unlink()
    else:
        evidence.write_text('{}')
    with pytest.raises(ValueError):
        record_decision(path, "approved", "Synthetic test reviewer")
    assert read_record(path).status == "awaiting_human_approval"


@pytest.mark.asyncio
async def test_docx_retains_sections_between_horizontal_rules(tmp_path):
    from docx import Document
    from src.formatters.docx_formatter import DOCXFormatter
    path = tmp_path / "rules.docx"
    await DOCXFormatter().convert(
        "---\ntitle: Metadata\n---\n## First\nFirst body\n---\n## Middle\nMiddle body\n---\n## Last\nLast body",
        path, "Test",
    )
    paragraphs = "\n".join(p.text for p in Document(path).paragraphs)
    assert "Middle body" in paragraphs and "Last body" in paragraphs
    assert "title: Metadata" not in paragraphs


@pytest.mark.asyncio
async def test_external_ai_denied_before_client_call(monkeypatch):
    from src.agents import base_agent
    agent = base_agent.BaseAgent(api_key="")
    agent.client = MagicMock()
    monkeypatch.setattr(base_agent.config_manager.system_config, "allow_external_ai", False)
    with pytest.raises(PermissionError):
        await agent._call_claude([{"role": "user", "content": "Sensitive input"}])
    agent.client.messages.create.assert_not_called()


@pytest.mark.parametrize("args", [
    ["generate", "Typo"],
    ["generate", "Change Management", "-f", "invalid"],
    ["generate", "Change Management", "--specialist", "invalid"],
])
def test_cli_rejects_invalid_input_before_preparing(catalog, monkeypatch, args):
    from src import main, generate_job
    monkeypatch.setattr(main, "config_manager", catalog)
    monkeypatch.setattr(generate_job, "config_manager", catalog)
    result = CliRunner().invoke(main.app, args)
    assert result.exit_code == 2, result.output
    assert not (catalog.system_config.output_dir / "claude_code").exists()


def test_cli_generate_prepares_in_the_custom_output_and_restores_it(catalog, monkeypatch, tmp_path):
    from src import main, generate_job
    monkeypatch.setattr(main, "config_manager", catalog)
    monkeypatch.setattr(generate_job, "config_manager", catalog)
    original_dir = catalog.system_config.output_dir
    custom_dir = tmp_path / "custom"
    result = CliRunner().invoke(main.app, ["generate", "Bespoke", "--custom", "--specialist", "data", "-f", "markdown",
                                           "-o", str(custom_dir)], terminal_width=1000)
    assert result.exit_code == 0, result.output
    work = next((custom_dir / "claude_code").iterdir())
    request = json.loads((work / "generate_request.json").read_text())
    assert request["request"]["process_name"] == "Bespoke" and request["specialists"] == ["data"]
    assert f"write SOP work {work.name} with output root {custom_dir}" in result.output and "reema-generate" in result.output
    assert catalog.system_config.output_dir == original_dir


@pytest.mark.parametrize("answer, status", [("n\n", "awaiting_human_approval"), ("y\n", "approved")])
def test_cli_approval_requires_human_confirmation(approval, answer, status):
    from src.main import app
    record, _ = approval
    result = CliRunner().invoke(app, ["approve", str(record), "--reviewer", "Reviewer"], input=answer)
    assert result.exit_code == (0 if status == "approved" else 1), result.output
    assert read_record(record).status == status


def test_cli_reject_records_reason(approval):
    from src.main import app
    record, _ = approval
    result = CliRunner().invoke(app, ["reject", str(record), "--reviewer", "Reviewer", "--notes", "Fix roles"], input="y\n")
    assert result.exit_code == 0, result.output
    assert read_record(record).status == "rejected"
    assert read_record(record).notes == "Fix roles"


def test_pdf_dependency_failure_does_not_disable_other_exports(monkeypatch):
    from src.agents import format_agent
    original = format_agent.import_module
    def load(name, package):
        if "pdf_formatter" in name:
            raise OSError("Missing PDF native library")
        return original(name, package)
    monkeypatch.setattr(format_agent, "import_module", load)
    formatter = format_agent.FormatAgent()
    assert set(formatter.get_supported_formats()) == {"markdown", "docx", "html"}
    with pytest.raises(ValueError, match="unavailable"):
        formatter.validate_requested_formats(["pdf"])
