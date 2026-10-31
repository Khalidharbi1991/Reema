"""New SOP written by a Claude Code session (the reema-generate skill), with no Anthropic API call.

Claude Code writes the section text (the reema-writer subagent) and, when the euc specialist is
selected, Agent 10's patch appendix (the reema-agent10-euc subagent); this module does everything
else: the request and plan, the template skeleton, local checks on supplied specialist data, the
per-section and whole-document checks, export and the pending human approval record. No model reviews
the draft. The access, problem and data specialists add no appendix. `reema generate` runs prepare;
scripts/claude_code_generate.py runs prepare, check and finish. Nothing here approves anything.
"""

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .agents.content_agent import ContentAgent
from .agents.euc_agent import EUCAgent
from .agents.file_workers import FileSectionWriter, section_files
from .agents.format_agent import FormatAgent
from .agents.leader_agent import LeaderAgent
from .knowledge.retrieval import EVIDENCE_POLICY, ReferenceIndex
from .utils.config import config_manager
from .utils.diagrams import GraphFlow, SequenceFlow
from .utils.documents import ControlRegister, legacy_register
from .utils.read_gate import check_manifest, references_sha256, require_references_permission
from .utils.specialists import SpecialistInputs, specialist_checks

# Named by Khalid for the printed approve command; this module never runs approve itself.
REVIEWER = "Khalid Alharbi"

CHECKS = [
    "Each section file holds that section's body only, with no # or ## headings; use ### and below.",
    "Section 3 needs an activity-by-role RACI table: first column Activity, Task or Step, then one column "
    "per role, a Markdown separator row, exactly one A and at least one R in every activity row.",
    "Name every standard in standards somewhere in the document.",
    "Cite only the [SRC-...] identifiers listed in evidence; with no evidence, cite none.",
    "Diagrams are optional and only in sections whose diagrams_allowed is true: a ```reema-flow fenced JSON "
    "block matching one of flow_schemas, closed properly.",
    "Mark organization-specific facts you do not have (names, systems, numbers, dates) as [to confirm].",
    "specialist_checks are local checks on data Khalid supplied, not verified facts; describe them as such.",
]
APPENDIX_FILE = "appendices/endpoint.md"
ENDPOINT_RULES = ("No fleet data, tenant configuration or calendar has been supplied unless specialist_inputs "
                  "holds it. Do not invent device counts, group names, dates or product settings; write "
                  "[to confirm] where the organization must supply a value. ")


def work_root():
    return config_manager.system_config.output_dir / "claude_code"


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def work_dir(work_id):
    if not work_id.isalnum():
        raise ValueError("Unknown work id")
    path = work_root() / work_id
    if not (path / "generate_request.json").is_file():
        raise ValueError(f"No prepared generate request at {path}")
    return path


def _specialist_input(path):
    """A local specialist input file, checked as `reema generate --specialist-input` checks it."""
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2000000:
        raise ValueError("Specialist input must be a regular local JSON file no larger than 2 MB")
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    check_manifest(path, sha256)
    try:
        inputs = SpecialistInputs.model_validate_json(data.decode("utf-8")).validate_limits(config_manager.specialist_policy)
    except ValueError:
        raise ValueError("Invalid specialist input; check the documented schema and field types") from None
    return {"path": str(path.resolve()), "name": path.name, "sha256": sha256}, inputs.model_dump(mode="json")


def _plan(arguments):
    """The validated request, plan and evidence, re-derived from the prepare arguments; local only."""
    process_id, request = LeaderAgent.documentation_request(**arguments)
    FormatAgent().validate_requested_formats(request.formats)
    leader = LeaderAgent()
    leader.context = {"request": request.model_dump()}
    workflow = asyncio.run(leader._plan_workflow(request.process_name))
    evidence = ReferenceIndex(config_manager.system_config).search(request.process_name)
    return process_id, request, workflow, evidence


def _sources(evidence):
    return {record["id"]: {key: value for key, value in record.items() if key != "text"} for record in evidence}


def _load(work_id):
    """The prepared request, refused if the process configuration or the reference excerpts changed."""
    path = work_dir(work_id)
    prepared = json.loads((path / "generate_request.json").read_text(encoding="utf-8"))
    if prepared["specialist_input"] and _specialist_input(prepared["specialist_input"]["path"])[0] != prepared["specialist_input"]:
        raise ValueError("The specialist input file changed since prepare; prepare it again")
    _, request, workflow, evidence = _plan(prepared["arguments"])
    if request.model_dump(mode="json") != prepared["request"] or workflow["applicable_standards"] != prepared["standards"]:
        raise ValueError("The process configuration changed since prepare; prepare it again")
    if [record["id"] for record in evidence] != [record["id"] for record in prepared["evidence"]] or (
            evidence and references_sha256(evidence) != prepared["evidence_sha256"]):
        raise ValueError("The reference excerpts changed since prepare; prepare it again")
    return path, prepared, request, workflow, evidence


def prepare(process, formats=None, *, custom=False, objective=None, constraints=(), acceptance=(), specialists=(),
            specialist_input=None, confirm_read=None):
    supplied, inputs = _specialist_input(specialist_input) if specialist_input is not None else (None, None)
    arguments = {"process_name": process, "output_formats": list(formats) if formats else None, "custom": bool(custom),
                 "specialists": sorted(set(specialists)) or None, "objective": objective,
                 "constraints": list(constraints) or None, "acceptance_criteria": list(acceptance) or None,
                 "specialist_inputs": inputs}
    process_id, request, workflow, evidence = _plan(arguments)
    checks = specialist_checks(inputs, _sources(evidence), config_manager.specialist_policy) if inputs else {}
    # Checked after the local request checks, and before any reference or input text is copied.
    permission = require_references_permission(evidence, confirm_read,
                                               [(supplied["name"], supplied["sha256"])] if supplied else ())
    profile = config_manager.document_profile
    standards = workflow["applicable_standards"]
    work_id = uuid4().hex
    path = work_root() / work_id
    files = section_files(path / "sections")
    prepared = {
        "arguments": arguments, "process_id": process_id, "request": request.model_dump(mode="json"),
        "standards": standards, "kpis": workflow["kpis"], "page_target": list(config_manager.system_config.page_target),
        "section_rules": ContentAgent.SECTION_RULES, "checks": CHECKS,
        "foundation_sections": list(ContentAgent.FOUNDATION_SECTIONS),
        "sections": [{"number": number, "id": section.id, "title": section.display_title or section.title,
                      "instructions": section.instructions, "target_pages": section.target_pages,
                      "diagrams_allowed": section.id in ContentAgent.DIAGRAM_SECTIONS,
                      "file": str(files[section.id].relative_to(path))}
                     for number, section in enumerate(profile.sections, 1)],
        "flow_schemas": {"sequence": SequenceFlow.model_json_schema(), "graph": GraphFlow.model_json_schema()},
        "control_register": legacy_register(standards).model_dump(),
        "evidence_policy": EVIDENCE_POLICY, "evidence": evidence,
        "evidence_sha256": references_sha256(evidence) if evidence else None, "read_permission": permission,
        "specialists": request.specialists, "specialist_input": supplied, "specialist_inputs": inputs,
        "specialist_checks": checks,
        "endpoint_appendix": {
            "file": APPENDIX_FILE, "writer": "reema-agent10-euc",
            "title": "Appendix: Endpoint Deployment & Rollback Plan",
            "headings": [title for title, _ in EUCAgent.APPENDIX_SECTIONS],
            "outline": EUCAgent.appendix_outline(),
            "rules": ENDPOINT_RULES + EUCAgent.APPENDIX_RULES + " Use ### headings exactly as in outline; no # or ##.",
        } if "euc" in request.specialists else None}
    (path / "sections").mkdir(parents=True)
    if prepared["endpoint_appendix"]:
        (path / "appendices").mkdir()
    _write(path / "generate_request.json", prepared)
    print(f"Prepared {work_id}: {request.process_name}, {len(prepared['sections'])} sections, "
          f"{len(evidence)} reference excerpt(s), formats {', '.join(request.formats)}")
    print(f"Request: {path / 'generate_request.json'}")
    print(f"Write one file per section into: {path / 'sections'}")
    if prepared["endpoint_appendix"]:
        print(f"Agent 10 writes the patch appendix to: {path / APPENDIX_FILE}")
    dropped = sorted(set(request.specialists) - {"euc"})
    if dropped:
        print(f"No appendix for: {', '.join(dropped)}" + ("; local checks on the supplied data are in the request." if checks else "."))
    return work_id


def _appendix(path, prepared):
    """Agent 10's checked patch appendix text; None when the euc specialist is not selected."""
    if not prepared["endpoint_appendix"]:
        return None
    file = path / APPENDIX_FILE
    if file.is_symlink() or not file.is_file():
        raise ValueError(f"No {APPENDIX_FILE} yet: ask Claude Code to run reema-agent10-euc on this work id ({path.name}).")
    text = file.read_text(encoding="utf-8")
    EUCAgent.check_appendix(text)
    return text


def _draft(path, prepared):
    """The assembled draft from the section files, through the unchanged per-section loop, and the appendix."""
    missing = [p.name for p in section_files(path / "sections").values() if not p.is_file()]
    if missing:
        raise ValueError(f"Missing section file(s): {', '.join(missing)}. Ask Claude Code to run reema-writer "
                         f"on this work id ({path.name}).")
    process_name = prepared["request"]["process_name"]
    writer = FileSectionWriter(path / "sections")
    content = asyncio.run(writer.generate_sop(process_name, {"standards": {"control_register": prepared["control_register"]}}))
    appendix = _appendix(path, prepared)
    if appendix is not None:
        content += "\n\n" + LeaderAgent()._format_euc_section(appendix, process_name)
    return content, appendix


def check(work_id):
    path, prepared, request, workflow, evidence = _load(work_id)
    content, _ = _draft(path, prepared)
    quality = LeaderAgent.check_draft(content, prepared["standards"], _sources(evidence),
                                      ControlRegister.model_validate(prepared["control_register"]))
    (path / "draft_preview.md").write_text(content, encoding="utf-8")
    low, high = prepared["page_target"]
    print(f"Draft passed every check: {quality['word_count']} words (target {low}-{high} pages, counted at finish).")
    for warning in quality["warnings"]:
        print(f"Note: {warning}")
    print(f"Preview: {path / 'draft_preview.md'}")
    return quality


def finish(work_id):
    path, prepared, request, _, evidence = _load(work_id)
    _, appendix = _draft(path, prepared)
    leader = LeaderAgent()
    leader.register_worker("ContentAgent", FileSectionWriter(path / "sections"))
    leader.register_worker("FormatAgent", FormatAgent())
    arguments = prepared["arguments"]

    async def run():
        try:
            return await leader.generate_local(
                arguments["process_name"], arguments["output_formats"], custom=arguments["custom"],
                specialists=arguments["specialists"], objective=arguments["objective"],
                constraints=arguments["constraints"], acceptance_criteria=arguments["acceptance_criteria"],
                specialist_inputs=arguments["specialist_inputs"], evidence=evidence, endpoint_appendix=appendix,
                origin={"claude_code_work": str(path)})
        finally:
            await leader.close()

    outputs = asyncio.run(run())
    record = leader.context["delivery"]["approval_record"]
    print(f"Generated {request.process_name}; no model reviewed it.")
    for fmt, output in outputs.items():
        print(f"{fmt}: {output}")
    for warning in leader.context.get("quality", {}).get("warnings", []):
        print(f"Note: {warning}")
    print(f"Awaiting human approval: {record}")
    print("For a model review first, ask Ahmad to review the Markdown draft (reema-review skill).")
    print("After reading it, approve with:")
    print(f'reema approve "{record}" --reviewer "{REVIEWER}"')
    return outputs


