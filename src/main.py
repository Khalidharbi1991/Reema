"""Main entry point for the IT Process Documentation System (REEMA).

REEMA — Khalid's IT company: coordination and IT process documentation
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
from .agents.format_agent import FormatAgent
from .agents.secretary_agent import SecretaryAgent
from .agents.building_design_agent import BuildingDesignAgent
from .utils.config import config_manager
from .utils.output_safety import unignored_output
from .utils.approvals import read_record, record_decision
from .utils.publish import NotPublishable, PublishError, plan_publish, publish as publish_run, record_skipped
from .utils.tasks import AREAS

app = typer.Typer(
    name="REEMA",
    help="REEMA - Khalid's IT company: coordination and IT process documentation"
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


@app.command(hidden=True, context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def chat(ctx: typer.Context):
    """Ahmad now works in Claude Code; this only says so."""
    console.print("Ahmad now works in Claude Code: open a Claude Code session in this folder and talk to him there. "
                  "Here, use task, memory and find-sop. Nothing was sent.", markup=False)
    raise typer.Exit(code=2)


@app.command("find-sop")
def find_sop(
    words: List[str] = typer.Argument(..., help="Words from the SOP's file name, e.g. incident management"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output root (default: ./output)"),
):
    """List finished SOPs in output/ whose file names best match the words, newest first. Reads no file."""
    import re
    from datetime import datetime
    from .utils.existing_sops import find_sops
    root = (output_dir or config_manager.system_config.output_dir).expanduser()
    wanted = {w for word in words for w in re.split(r"[^\w]+|_", word.casefold()) if w and w != "sop"}
    matches = find_sops(root, wanted)
    if not matches:
        console.print(f"No SOP file name in {root} matches: {' '.join(words)}", markup=False)
        raise typer.Exit(code=1)
    for number, path in enumerate(matches, 1):
        console.print(f"{number}. {path} (modified {datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d})",
                      markup=False, soft_wrap=True)


def _warn_if_output_unignored(directory: Path):
    """Drafts and checkpoints can hold customer content; flag folders Git would not ignore."""
    root = unignored_output(directory)
    if root is not None:
        console.print(f"Warning: output folder {directory} is inside the Git repository at {root} and is not "
                      "ignored by .gitignore. Drafts, run checkpoints and source excerpts written there could be "
                      "committed. Use a folder under output/ or add it to .gitignore.", markup=False)


@app.command()
def generate(
    process: str = typer.Argument(..., help="Name of the IT process to document"),
    formats: Optional[List[str]] = typer.Option(None, "--format", "-f", help="Output formats (pdf, docx, markdown, html)"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output root (default: ./output)"),
    custom: bool = typer.Option(False, "--custom", help="Allow a process outside the configured catalog"),
    specialists: Optional[List[str]] = typer.Option(None, "--specialist", help="Additional specialist: access, problem, data, euc (repeatable); euc adds Agent 10's patch appendix"),
    objective: Optional[str] = typer.Option(None, "--objective", help="Specific objective for this SOP"),
    constraints: Optional[List[str]] = typer.Option(None, "--constraint", help="Explicit constraint; repeatable"),
    acceptance_criteria: Optional[List[str]] = typer.Option(None, "--acceptance", help="Additional human acceptance criterion; repeatable"),
    specialist_input: Optional[Path] = typer.Option(None, "--specialist-input", help="Local JSON input: IAM snapshot, incident observations or metric data"),
    confirm_read: Optional[str] = typer.Option(None, "--confirm-read", help="Token printed for the reference or input files; give it only after Khalid's yes"),
):
    """Prepare a new SOP for Claude Code to write; REEMA makes no model call.

    The section text is written in a Claude Code session (reema-generate skill); REEMA then checks,
    exports and records it for human approval.
    """
    from .generate_job import prepare
    settings = config_manager.system_config
    previous_output = settings.output_dir
    try:
        if output_dir is not None:
            settings.output_dir = output_dir.expanduser().resolve()
        _warn_if_output_unignored(settings.output_dir)
        work_id = prepare(process, formats, custom=custom, objective=objective, constraints=constraints or (),
                          acceptance=acceptance_criteria or (), specialists=specialists or (),
                          specialist_input=specialist_input, confirm_read=confirm_read)
        root = "" if output_dir is None else f" with output root {settings.output_dir}"
    except ValueError as error:
        console.print(str(error), markup=False, soft_wrap=True)
        raise typer.Exit(code=2)
    except (OSError, RuntimeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)
    finally:
        settings.output_dir = previous_output
    console.print(f"Next, in a Claude Code session in this folder, ask Ahmad to write SOP work {work_id}{root} "
                  "(reema-generate skill). REEMA checks it, exports it and records it for your approval.",
                  markup=False, soft_wrap=True)


@app.command()
def resume(
    run: Path = typer.Argument(..., exists=True, file_okay=False, help="Run directory containing verified checkpoints"),
    formats: Optional[List[str]] = typer.Option(None, "--format", "-f"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output root (default: ./output)"),
):
    """Export a run's checked draft again into a NEW run, with no model call."""
    async def execute():
        leader = LeaderAgent(api_key="")
        leader.register_worker("FormatAgent", FormatAgent())
        try:
            outputs = await leader.resume_formatting(run, formats)
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


@app.command()
def review(
    file: Path = typer.Argument(..., help="Finished SOP (.md or .docx); it is only read, never changed"),
    local_only: bool = typer.Option(True, "--local-only", hidden=True, help="Accepted for old commands; review here is always local"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output root (default: ./output)"),
):
    """Check a finished SOP against the template (no model) and save the gaps to a NEW run folder.

    The full review runs in Claude Code: ask Ahmad there (reema-review skill).
    """
    from .utils.existing_sops import load_sop
    try:
        source = load_sop(file)
    except ValueError as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=2)
    settings = config_manager.system_config
    leader = LeaderAgent(api_key="")
    previous_output = settings.output_dir
    try:
        if output_dir is not None:
            settings.output_dir = output_dir.expanduser().resolve()
        _warn_if_output_unignored(settings.output_dir)
        findings = asyncio.run(_close_after(leader, leader.review_existing(source, local_only=True)))
    except (ValueError, OSError, PermissionError, RuntimeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)
    finally:
        settings.output_dir = previous_output
    run_dir = Path(leader.context["run_dir"])
    console.print(f"{len(findings['template_gaps'])} template gap(s). The SOP was not changed.", markup=False)
    console.print(f"Findings: {run_dir / 'findings.md'}", markup=False)
    console.print("For the full review, ask Ahmad in Claude Code (reema-review skill).", markup=False)


@app.command(hidden=True, context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def revise(ctx: typer.Context):
    """Revisions run in Claude Code; this only says so."""
    console.print("Revisions now run in Claude Code: ask Ahmad there to revise the SOP (reema-revise skill). "
                  "Nothing was read or changed.", markup=False)
    raise typer.Exit(code=2)


async def _close_after(leader, job):
    try:
        return await job
    finally:
        await leader.close()


def _human_decision(record: Path, reviewer: str, decision: str, notes: str, publish: bool = False):
    output_root = config_manager.system_config.output_dir
    publishable = False
    try:
        pending = read_record(record)
        if pending.status != "awaiting_human_approval":
            raise ValueError("This run already has a human decision")
        score = "not reviewed" if pending.quality_score is None else pending.quality_score
        console.print(f"Process: {pending.process_name}\nModel quality score: {score}", markup=False)
        for fmt, artifact in pending.artifacts.items():
            console.print(f"{fmt}: {artifact.path}", markup=False)
        for label, artifact in pending.supporting_records.items():
            console.print(f"Review/evidence record ({label}): {artifact.path}", markup=False)
        if publish:
            # Preview the publish before the decision, so a refusal is known while it can still be weighed.
            try:
                steps = plan_publish(record, output_root, pending_ok=True)
                publishable = True
                for step in steps:
                    console.print(f"Will {step['action']}: {step['from']} -> {step['to']}", markup=False)
            except NotPublishable as note:
                console.print(str(note), markup=False)
            except (OSError, PublishError) as error:
                publishable = True
                console.print(f"Warning: publishing will be refused after approval: {error}", markup=False)
        # Deliberately no --yes switch: the local CLI user must confirm.
        typer.confirm(f"Have you reviewed these drafts and want to record '{decision}' as {reviewer}?", abort=True)
        result = record_decision(record, decision, reviewer, notes)
        console.print(f"Human decision recorded: {result.status}")
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)
    if result.status == "approved" and publishable:
        _publish(record, output_root)
    elif result.status == "approved" and not publish:
        try:
            plan_publish(record, output_root)
        except NotPublishable:
            return
        except PublishError:
            pass
        record_skipped(record, "approve --no-publish")
        console.print(f'Not published (--no-publish). Publish later with: reema publish "{record}"', markup=False)


def _publish(record: Path, output_root: Path):
    try:
        state = publish_run(record, output_root)
    except (OSError, PublishError) as error:
        console.print(f"Approved, not published: {error}", markup=False)
        console.print(f'The approval stays recorded. Retry with: reema publish "{record}"', markup=False)
        raise typer.Exit(code=1)
    for step in state["attempts"][-1]["steps"]:
        verb = "Published" if step["action"] == "copy" else "Archived"
        console.print(f"{verb}: {step['to']}", markup=False)


@app.command()
def approve(
    record: Path = typer.Argument(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(..., "--reviewer", help="Human reviewer's name"),
    notes: str = typer.Option("", "--notes"),
    publish: bool = typer.Option(True, "--publish/--no-publish",
                                 help="Copy an approved revision into output/ and archive older versions"),
):
    """Record explicit human approval of an unchanged set of draft outputs, then publish a revision."""
    _human_decision(record, reviewer, "approved", notes, publish=publish)


@app.command()
def reject(
    record: Path = typer.Argument(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(..., "--reviewer"),
    notes: str = typer.Option("", "--notes"),
):
    """Record a human rejection; a revision requires a new generation run."""
    _human_decision(record, reviewer, "rejected", notes)


@app.command("publish")
def publish_command(record: Path = typer.Argument(..., exists=True, dir_okay=False)):
    """Publish an approved revision, or finish one that failed or was skipped with --no-publish."""
    from .utils.publish import read_publish
    try:
        if read_record(record).status != "approved":
            raise ValueError("Only approved runs are published.")
        if read_publish(record) is None:
            raise ValueError("This run was approved before automatic publishing (or is not a revision); "
                             "it is left as it is.")
        if read_publish(record).get("status") == "published":
            raise ValueError("This run is already published.")
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(code=1)
    _publish(record, config_manager.system_config.output_dir)


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

    table = Table(show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API Key", api_key_status)
    table.add_row("External AI permission", "Enabled" if config_manager.system_config.allow_external_ai else "Disabled (explicit authorization required)")
    table.add_row("Final approval", "Human decision required for each run")
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
    table.add_row("Conversation", "Ahmad in Claude Code; task, memory and find-sop run locally here")

    console.print(table)
    console.print()


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"\n[bold cyan]REEMA - Regulatory & Enterprise Management Automation[/bold cyan]")
    console.print(f"Version: {__version__}")
    console.print("Agents: 12 (Ahmad, Abdullah, Agents 1–10)\n")


if __name__ == "__main__":
    app()
