"""Main entry point for the IT Process Documentation System (REEMA).

REEMA — personal assistance and IT process documentation
12-role architecture: Ahmad, Abdullah, Agents 1–8, building-design Agent 9, and EUC Agent 10.
"""

import asyncio
import json
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table

from .agents.leader_agent import LeaderAgent
from .agents.research_agent import ResearchAgent
from .agents.standards_agent import StandardsAgent
from .agents.content_agent import ContentAgent
from .agents.review_agent import ReviewAgent
from .agents.format_agent import FormatAgent
from .agents.data_agent import DataAgent
from .agents.access_agent import AccessAgent
from .agents.problem_agent import ProblemAgent
from .agents.secretary_agent import SecretaryAgent
from .agents.building_design_agent import BuildingDesignAgent
from .assistant import AssistantSession
from .utils.logger import logger
from .utils.config import config_manager
from .utils.validation import validate_formats
from .utils.output_safety import unignored_output
from .utils.approvals import read_record, record_decision
from .utils.tasks import AREAS
from .utils.specialists import SpecialistInputs

app = typer.Typer(
    name="REEMA",
    help="REEMA - Personal task coordination and IT process documentation"
)
console = Console()
task_app = typer.Typer(help="Ahmad's local work and personal task lists")
app.add_typer(task_app, name="task")
memory_app = typer.Typer(help="Explicit preferences, profile, project context, lessons and examples")
app.add_typer(memory_app, name="memory")
drawing_app = typer.Typer(help="Agent 9's local building-drawing intake")
app.add_typer(drawing_app, name="drawing")


@drawing_app.command("inspect")
def drawing_inspect(path: Path = typer.Argument(..., help="Local AutoCAD DWG drawing")):
    """Identify a DWG locally; this does not extract geometry or create a model."""
    try:
        report = BuildingDesignAgent(api_key="").inspect_drawing(path)
        console.print(f"Agent 9 recognized {report['filename']} as an AutoCAD DWG drawing.", markup=False)
        console.print("This intake check did not extract geometry or create a 3D model.")
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@drawing_app.command("concept")
def drawing_concept(
    path: Path = typer.Argument(..., help="Local DXF working copy"),
    output_dir: Path = typer.Option(..., "--output-dir", help="New local directory for OBJ and preview"),
    xmin: float = typer.Option(..., "--xmin"),
    ymin: float = typer.Option(..., "--ymin"),
    xmax: float = typer.Option(..., "--xmax"),
    ymax: float = typer.Option(..., "--ymax"),
    wall_height: float = typer.Option(3.0, "--wall-height", help="Assumed metres; 2 to 6"),
    design_spec: Path | None = typer.Option(None, "--design-spec", help="Local JSON concept placements"),
    source_units: str | None = typer.Option(None, "--source-units", help="Explicit DXF units: metres, millimetres, centimetres or feet; bounds remain metres"),
):
    """Create a concept wall mesh for one selected DXF area; not a full BIM model."""
    try:
        result = BuildingDesignAgent(api_key="").create_concept_model(
            path, output_dir, (xmin, ymin, xmax, ymax),
            wall_height=wall_height, design_spec=design_spec, source_units=source_units)
        console.print(f"Concept model: {result['obj_path']}", markup=False)
        console.print(f"Preview: {result['preview_path']}", markup=False)
        console.print(
            f"Wall segments: {result['wall_segments']}; "
            f"generic furniture proxies: {result['furniture_proxies']}; "
            f"fixture proxies: {result['fixture_proxies']}")
        console.print("Assumed dimensions; not a construction-accurate or full-building model.")
    except (ValueError, OSError, FileExistsError, json.JSONDecodeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


def _task_agent(area: str):
    if area not in AREAS:
        raise ValueError("Area must be work or personal")
    return SecretaryAgent(api_key="")


def _task_table(records):
    table = Table(show_header=True)
    for label in ("ID", "Task", "Project", "Priority", "Due", "Status"):
        table.add_column(label)
    for item in records:
        table.add_row(item["id"], item["title"], item["project"], item["priority"],
                      item["due"] or "", item["status"])
    console.print(table)


@task_app.command("add")
def task_add(
    title: str = typer.Argument(..., help="Task to remember"),
    area: str = typer.Option(..., "--area", help="work or personal"),
    project: str = typer.Option("", "--project"),
    priority: str = typer.Option("normal", "--priority"),
    due: Optional[str] = typer.Option(None, "--due", help="YYYY-MM-DD"),
    details: str = typer.Option("", "--details"),
):
    """Save one local task without a model call."""
    try:
        item = _task_agent(area).add_task(area, title, project=project,
                                          priority=priority, due=due, details=details)
        _task_table([item])
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("list")
def task_list(area: str = typer.Option(..., "--area", help="work or personal"),
              status: str = typer.Option("open", "--status", help="open, done, archived, or all"),
              project: Optional[str] = typer.Option(None, "--project")):
    """List tasks in one area."""
    try:
        _task_table(_task_agent(area).list_tasks(area, status=status, project=project))
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("today")
def task_today(area: str = typer.Option(..., "--area", help="work or personal")):
    """Show open tasks due today or overdue in one area."""
    try:
        _task_table(_task_agent(area).due_tasks(area))
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("show")
def task_show(task_id: str, area: str = typer.Option(..., "--area", help="work or personal")):
    """Show one task, including its details."""
    try:
        item = _task_agent(area).task_store(area).get(task_id)
        _task_table([item])
        if item["details"]:
            console.print("Details: " + item["details"], markup=False)
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("upcoming")
def task_upcoming(area: str = typer.Option(..., "--area", help="work or personal"),
                  days: int = typer.Option(7, "--days", help="Planning horizon, 1–90 days")):
    """Show overdue and upcoming open tasks in one area."""
    try:
        _task_table(_task_agent(area).upcoming_tasks(area, days))
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("edit")
def task_edit(task_id: str, area: str = typer.Option(..., "--area", help="work or personal"),
              title: Optional[str] = typer.Option(None, "--title"),
              project: Optional[str] = typer.Option(None, "--project"),
              priority: Optional[str] = typer.Option(None, "--priority"),
              due: Optional[str] = typer.Option(None, "--due"),
              clear_due: bool = typer.Option(False, "--clear-due"),
              details: Optional[str] = typer.Option(None, "--details")):
    """Change task details; use --clear-due to remove a due date."""
    if clear_due and due is not None:
        raise typer.BadParameter("Choose --due or --clear-due")
    changes = {key: value for key, value in {"title": title, "project": project,
                "priority": priority, "details": details}.items() if value is not None}
    if due is not None or clear_due:
        changes["due"] = None if clear_due else due
    try:
        _task_table([_task_agent(area).change_task(area, task_id, **changes)])
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@task_app.command("set-status")
def task_set_status(task_id: str, area: str = typer.Option(..., "--area", help="work or personal"),
                    status: str = typer.Option(..., "--status", help="open, done, or archived")):
    """Complete, reopen, or archive a task."""
    try:
        _task_table([_task_agent(area).change_task(area, task_id, status=status)])
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@memory_app.command("set")
def memory_set(key: str, value: str,
               area: str = typer.Option(..., "--area", help="work or personal"),
               kind: str = typer.Option("preference", "--kind", help="preference, profile, project, lesson, or example"),
               project: str = typer.Option("", "--project", help="Required for project memory; optional for lessons/examples")):
    """Save or replace an explicitly supplied memory in one area."""
    try:
        item = _task_agent(area).task_store(area).remember(key, value, kind=kind, project=project)
        console.print(f"Saved {item['area']} {kind}: {item['key']}", markup=False)
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@memory_app.command("list")
def memory_list(area: str = typer.Option(..., "--area", help="work or personal"),
                kind: Optional[str] = typer.Option(None, "--kind", help="Filter by memory kind"),
                project: Optional[str] = typer.Option(None, "--project", help="Filter by exact project; omit to inspect all")):
    """Inspect saved memory in one area, including its project scopes."""
    try:
        records = _task_agent(area).task_store(area).memories(kind=kind, project=project)
        for item in records:
            console.print(f"{item['kind']} [{item['project'] or area}]: {item['key']}: {item['value']}", markup=False)
        if not records:
            console.print("No saved memories.")
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@memory_app.command("forget")
def memory_forget(key: str,
                  area: str = typer.Option(..., "--area", help="work or personal"),
                  kind: str = typer.Option("preference", "--kind", help="Kind of memory to remove"),
                  project: str = typer.Option("", "--project", help="Exact project scope of the memory")):
    """Remove one explicitly named memory from its area and project."""
    try:
        _task_agent(area).task_store(area).forget(key, kind=kind, project=project)
        console.print(f"Forgot {area} {kind}: {key}", markup=False)
    except (ValueError, OSError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


@app.command("agents")
def agents():
    """Show the active coordination and specialist roles."""
    table = Table(show_header=True)
    table.add_column("Agent")
    table.add_column("Role")
    for key in ("secretary_agent", "leader_agent", "research_agent", "standards_agent",
                "content_agent", "review_agent", "format_agent", "access_agent",
                "problem_agent", "data_agent", "building_design_agent", "euc_agent"):
        item = config_manager.get_agent_config(key)
        table.add_row(item["name"], item["role"])
    console.print(table)


@app.command("chat")
def chat(
    message: Optional[str] = typer.Argument(None, help="One message, or omit for an interactive session"),
    area: str = typer.Option(..., "--area", help="work or personal"),
    allow_external_ai: bool = typer.Option(False, "--allow-external-ai", help="Authorize sending conversation, selected memory and relevant task context to Anthropic"),
    project: str = typer.Option("", "--project", help="Use saved context and planning tasks for this exact project"),
    resolve_intent: bool = typer.Option(False, "--resolve-intent", help="Use a consent-gated structured model pass to resolve advisory intent"),
):
    """Talk with Ahmad; he consults specialists for relevant work questions."""
    async def converse():
        session = AssistantSession(area, project=project, resolve_intent=resolve_intent)
        try:
            if message is not None:
                result = await session.reply(message, allow_external_ai=allow_external_ai)
                console.print(result["reply"], markup=False)
                return
            console.print("Ahmad is ready. Use /task help, /remember [--kind KIND] KEY VALUE, /memory, /project NAME, or /exit.", markup=False)
            while True:
                try:
                    entry = input("You> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if entry == "/exit":
                    break
                if not entry:
                    continue
                try:
                    result = await session.reply(entry, allow_external_ai=allow_external_ai)
                    console.print("Ahmad: " + result["reply"], markup=False)
                except (ValueError, PermissionError, OSError, RuntimeError) as error:
                    console.print(str(error), markup=False)
        finally:
            await session.close()
    try:
        asyncio.run(converse())
    except (ValueError, PermissionError, OSError, RuntimeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)


def initialize_system(specialists: Optional[List[str]] = None) -> dict:
    """Initialize the multi-agent system.

    Returns:
        Dictionary with the leader and its registered, process-selected workers.
    """
    leader = LeaderAgent()
    for cls in (ResearchAgent, StandardsAgent, ContentAgent, ReviewAgent, FormatAgent):
        leader.register_worker(cls.__name__, cls())
    optional = {"access": AccessAgent, "problem": ProblemAgent, "data": DataAgent}
    for name in sorted(set(specialists or [])):
        cls = optional[name]
        leader.register_worker(cls.__name__, cls())
    console.print(f"Initialized {len(leader.worker_agents)} workers; final approval requires a human decision.")
    return {"leader": leader}


def _warn_if_output_unignored(directory: Path):
    """Drafts and checkpoints can hold customer content; flag folders Git would not ignore."""
    root = unignored_output(directory)
    if root is not None:
        console.print(f"Warning: output folder {directory} is inside the Git repository at {root} and is not "
                      "ignored by .gitignore. Drafts, run checkpoints and source excerpts written there could be "
                      "committed. Use a folder under output/ or add it to .gitignore.", markup=False)


async def _generate_and_close(leader, *args, **kwargs):
    try:
        return await leader.generate_documentation(*args, **kwargs)
    finally:
        if hasattr(leader, "close"):
            await leader.close()


@app.command()
def generate(
    process: str = typer.Argument(..., help="Name of the IT process to document"),
    formats: Optional[List[str]] = typer.Option(
        None,
        "--format", "-f",
        help="Output formats (pdf, docx, markdown, html)"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output)"
    ),
    custom: bool = typer.Option(False, "--custom", help="Allow a process outside the configured catalog"),
    specialists: Optional[List[str]] = typer.Option(None, "--specialist", help="Additional specialist: access, problem, data (repeatable)"),
    allow_external_ai: bool = typer.Option(False, "--allow-external-ai", help="Authorize sending this run's input and reference excerpts to Anthropic"),
    objective: Optional[str] = typer.Option(None, "--objective", help="Specific objective for this SOP"),
    constraints: Optional[List[str]] = typer.Option(None, "--constraint", help="Explicit constraint; repeatable"),
    acceptance_criteria: Optional[List[str]] = typer.Option(None, "--acceptance", help="Additional human acceptance criterion; repeatable"),
    specialist_input: Optional[Path] = typer.Option(None, "--specialist-input", help="Explicit JSON input for IAM snapshot, incident observations or metric data; included in authorized model context"),
):
    """
    Generate IT process documentation.

    Examples:
        python -m src.main generate "Incident Management" --allow-external-ai
        python -m src.main generate "Change Management" --format docx --allow-external-ai
    """
    console.print(f"\n[bold cyan]📝 Generating documentation for: {process}[/bold cyan]\n")

    # Reject invalid requests before initializing agents or reading references.
    try:
        specialist_data = None
        if specialist_input is not None:
            if specialist_input.is_symlink() or not specialist_input.is_file() or specialist_input.stat().st_size > 2000000:
                raise ValueError("Specialist input must be a regular local JSON file no larger than 2 MB")
            try:
                specialist_data = SpecialistInputs.model_validate_json(specialist_input.read_text(encoding="utf-8")).validate_limits(config_manager.specialist_policy).model_dump()
            except ValueError:
                raise ValueError("Invalid specialist input; check the documented schema and field types") from None
        _, definition = config_manager.resolve_process(process, custom=custom)
        selected = sorted(set(definition.get("specialists", [])) | set(specialists or []))
        if specialist_data:
            selected = sorted(set(selected) | SpecialistInputs.model_validate(specialist_data).required_specialists())
        if set(selected) - {"access", "problem", "data"}:
            raise ValueError("Specialists must be access, problem, or data")
        formats = validate_formats(config_manager.system_config.default_formats if formats is None else formats)
    except ValueError as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)

    settings = config_manager.system_config
    _warn_if_output_unignored(Path(output_dir).expanduser().resolve() if output_dir else settings.output_dir)
    if not (allow_external_ai or settings.allow_external_ai):
        console.print("This run sends input and reference excerpts to Anthropic. Use --allow-external-ai after confirming permission for those documents.")
        raise typer.Exit(code=2)

    # Check for API key
    if not config_manager.system_config.anthropic_api_key:
        console.print("[bold red]❌ Error: ANTHROPIC_API_KEY environment variable not set![/bold red]")
        console.print("\nPlease set your API key:")
        console.print("  export ANTHROPIC_API_KEY='your-api-key-here'\n")
        raise typer.Exit(code=1)

    previous_output_dir = settings.output_dir
    previous_authorization = settings.allow_external_ai
    try:
        settings.allow_external_ai = True
        if output_dir:
            settings.output_dir = Path(output_dir).expanduser().resolve()
        agents = initialize_system(selected)
        leader = agents["leader"]
        with console.status(f"[bold green]Generating {process} documentation..."):
            output_files = asyncio.run(
                _generate_and_close(leader, process, formats, custom=custom, specialists=selected,
                                    objective=objective, constraints=constraints, acceptance_criteria=acceptance_criteria,
                                    specialist_inputs=specialist_data)
            )

        # Display results
        console.print("\nDrafts generated; awaiting human approval.\n")

        table = Table(title="Generated Documents", show_header=True)
        table.add_column("Format", style="cyan")
        table.add_column("File Path", style="green")

        for fmt, file_path in output_files.items():
            table.add_row(fmt.upper(), str(file_path))

        console.print(table)
        console.print("Approval record: " + leader.context["delivery"]["approval_record"], markup=False)
        for warning in leader.context.get("quality", {}).get("warnings", []):
            console.print("Review note: " + warning, markup=False)
        console.print()

    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")
        logger.error(f"Generation failed: {e}")
        raise typer.Exit(code=1)
    finally:
        settings.output_dir = previous_output_dir
        settings.allow_external_ai = previous_authorization


@app.command()
def resume(
    run: Path = typer.Argument(..., exists=True, file_okay=False, help="Run directory containing verified checkpoints"),
    formats: Optional[List[str]] = typer.Option(None, "--format", "-f"),
    model_phases: bool = typer.Option(False, "--model-phases", help="Recover interrupted model phases instead of offline export"),
    allow_external_ai: bool = typer.Option(False, "--allow-external-ai", help="Fresh authorization for model-phase recovery"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Original output root for model recovery"),
):
    """Resume into a NEW run; default is offline export, model recovery is explicit."""
    async def execute():
        if model_phases:
            if not allow_external_ai:
                raise PermissionError("Model-phase recovery requires fresh --allow-external-ai")
            if not config_manager.system_config.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is needed for model-phase recovery")
            from .utils.execution import load_execution
            record, _ = load_execution(run, config_manager)
            leader = initialize_system(record.request.specialists)["leader"]
        else:
            leader = LeaderAgent(api_key="")
            leader.register_worker("FormatAgent", FormatAgent())
        try:
            outputs = (await leader.resume_execution(run, formats, allow_external_ai=allow_external_ai)
                       if model_phases else await leader.resume_formatting(run, formats))
            for fmt, path in outputs.items():
                console.print(f"{fmt}: {path}", markup=False)
            console.print("Awaiting human approval: " + leader.context["delivery"]["approval_record"], markup=False)
        finally:
            await leader.close()
    previous_output = config_manager.system_config.output_dir
    try:
        if output_dir is not None:
            config_manager.system_config.output_dir = output_dir.expanduser().resolve()
        _warn_if_output_unignored(config_manager.system_config.output_dir)
        asyncio.run(execute())
    except (ValueError, OSError, KeyError, PermissionError, RuntimeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)
    finally:
        config_manager.system_config.output_dir = previous_output


def _human_decision(record: Path, reviewer: str, decision: str, notes: str):
    try:
        pending = read_record(record)
        if pending.status != "awaiting_human_approval":
            raise ValueError("This run already has a human decision")
        console.print(f"Process: {pending.process_name}\nModel quality score: {pending.quality_score}", markup=False)
        for fmt, artifact in pending.artifacts.items():
            console.print(f"{fmt}: {artifact.path}", markup=False)
        for label, artifact in pending.supporting_records.items():
            console.print(f"Review/evidence record ({label}): {artifact.path}", markup=False)
        # Deliberately no --yes switch: the local CLI user must confirm.
        typer.confirm(f"Have you reviewed these drafts and want to record '{decision}' as {reviewer}?", abort=True)
        result = record_decision(record, decision, reviewer, notes)
        console.print(f"Human decision recorded: {result.status}")
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)


@app.command()
def approve(
    record: Path = typer.Argument(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(..., "--reviewer", help="Human reviewer's name"),
    notes: str = typer.Option("", "--notes"),
):
    """Record explicit human approval of an unchanged set of draft outputs."""
    _human_decision(record, reviewer, "approved", notes)


@app.command()
def reject(
    record: Path = typer.Argument(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(..., "--reviewer"),
    notes: str = typer.Option("", "--notes"),
):
    """Record a human rejection; a revision requires a new generation run."""
    _human_decision(record, reviewer, "rejected", notes)


@app.command()
def list_processes():
    """List all available IT processes that can be documented."""
    console.print("\n[bold cyan]📋 Available IT Processes:[/bold cyan]\n")

    processes = config_manager.process_definitions

    if not processes:
        console.print("[yellow]No processes defined in configuration.[/yellow]\n")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Process Name", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Standards", style="yellow")
    table.add_column("Complexity", style="blue")

    for process_id, details in processes.items():
        name = details.get("name", process_id)
        category = details.get("category", "N/A")
        standards = ", ".join(config_manager.standards_mapping.get(process_id, []))
        complexity = details.get("complexity", "N/A")

        table.add_row(name, category, standards, complexity)

    console.print(table)
    console.print()


@app.command()
def status():
    """Show system status and configuration."""
    console.print("\n[bold cyan]📊 System Status:[/bold cyan]\n")

    # Check API key
    api_key_status = "✓ Configured" if config_manager.system_config.anthropic_api_key else "❌ Not set"

    # Check the optional ITOM reference knowledge base
    itom_path = config_manager.system_config.references_dir / "itom" / "ITOM.pdf"
    itom_status = "✓ Found" if itom_path.exists() else "❌ Not found"

    table = Table(show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API Key", api_key_status)
    table.add_row("External AI permission", "Enabled" if config_manager.system_config.allow_external_ai else "Disabled (explicit authorization required)")
    table.add_row("Final approval", "Human decision required for each run")
    table.add_row("ITOM file (not auto-authorized)", itom_status)
    table.add_row("Reference permission manifest", str(config_manager.system_config.reference_manifest))
    table.add_row("API timeout / retries", f"{config_manager.system_config.api_timeout_seconds}s / {config_manager.system_config.api_max_retries}")
    table.add_row("Project Root", str(config_manager.system_config.project_root))
    table.add_row("Output Directory", str(config_manager.system_config.output_dir))
    table.add_row("Knowledge Directory", str(config_manager.system_config.knowledge_dir))
    table.add_row("References Directory", str(config_manager.system_config.references_dir))
    table.add_row("Leader Model", config_manager.system_config.leader_model)
    table.add_row("Worker Model", config_manager.system_config.worker_model)
    table.add_row("Generation agents", "Leader + 5 core workers + process-selected specialists")
    table.add_row("Personal coordination", "Ahmad; local work and personal task lists")
    table.add_row("Conversational entry", "chat --area work|personal (model advice requires authorization)")

    console.print(table)
    console.print()


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"\n[bold cyan]REEMA - Regulatory & Enterprise Management Automation[/bold cyan]")
    console.print(f"Version: {__version__}")
    console.print("Agents: 11 (Ahmad, Abdullah, Agents 1–9)\n")


if __name__ == "__main__":
    app()
