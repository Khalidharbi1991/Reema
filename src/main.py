"""Main entry point for the IT Process Documentation System."""

import asyncio
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import os

from .agents.leader_agent import LeaderAgent
from .agents.research_agent import ResearchAgent
from .agents.standards_agent import StandardsAgent
from .agents.content_agent import ContentAgent
from .agents.review_agent import ReviewAgent
from .agents.format_agent import FormatAgent
from .utils.logger import logger
from .utils.config import config_manager

app = typer.Typer(
    name="REEMA",
    help="REEMA - Multi-agent system for generating IT process documentation"
)
console = Console()


def initialize_system() -> LeaderAgent:
    """Initialize the multi-agent system."""
    console.print("\n[bold blue]🤖 Initializing Multi-Agent Documentation System...[/bold blue]\n")

    # Create leader agent
    leader = LeaderAgent()

    # Create and register worker agents
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing agents...", total=5)

        research = ResearchAgent()
        leader.register_worker("ResearchAgent", research)
        progress.update(task, advance=1, description="✓ Research Agent initialized")

        standards = StandardsAgent()
        leader.register_worker("StandardsAgent", standards)
        progress.update(task, advance=1, description="✓ Standards Agent initialized")

        content = ContentAgent()
        leader.register_worker("ContentAgent", content)
        progress.update(task, advance=1, description="✓ Content Agent initialized")

        review = ReviewAgent()
        leader.register_worker("ReviewAgent", review)
        progress.update(task, advance=1, description="✓ Review Agent initialized")

        format_agent = FormatAgent()
        leader.register_worker("FormatAgent", format_agent)
        progress.update(task, advance=1, description="✓ Format Agent initialized")

    console.print("\n[bold green]✓ All agents initialized successfully![/bold green]\n")

    return leader


@app.command()
def generate(
    process: str = typer.Argument(..., help="Name of the IT process to document"),
    formats: Optional[List[str]] = typer.Option(
        ["pdf", "docx", "markdown", "html"],
        "--format", "-f",
        help="Output formats (pdf, docx, markdown, html)"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output)"
    )
):
    """
    Generate IT process documentation.

    Examples:
        python -m src.main generate "Incident Management"
        python -m src.main generate "Change Management" --format pdf --format docx
    """
    console.print(f"\n[bold cyan]📝 Generating documentation for: {process}[/bold cyan]\n")

    # Check for API key
    if not config_manager.system_config.anthropic_api_key:
        console.print("[bold red]❌ Error: ANTHROPIC_API_KEY environment variable not set![/bold red]")
        console.print("\nPlease set your API key:")
        console.print("  export ANTHROPIC_API_KEY='your-api-key-here'\n")
        raise typer.Exit(code=1)

    # Initialize system
    leader = initialize_system()

    # Update output directory if specified
    if output_dir:
        config_manager.system_config.output_dir = Path(output_dir)

    # Generate documentation
    try:
        with console.status(f"[bold green]Generating {process} documentation..."):
            output_files = asyncio.run(
                leader.generate_documentation(process, list(formats))
            )

        # Display results
        console.print("\n[bold green]✓ Documentation generated successfully![/bold green]\n")

        table = Table(title="Generated Documents", show_header=True)
        table.add_column("Format", style="cyan")
        table.add_column("File Path", style="green")

        for fmt, file_path in output_files.items():
            table.add_column(fmt.upper(), file_path)

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")
        logger.error(f"Generation failed: {e}")
        raise typer.Exit(code=1)


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
        standards = ", ".join(details.get("standards", []))
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

    # Check ITOM.pdf
    itom_path = config_manager.system_config.project_root / "ITOM.pdf"
    itom_status = "✓ Found" if itom_path.exists() else "❌ Not found"

    table = Table(show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API Key", api_key_status)
    table.add_row("ITOM.pdf", itom_status)
    table.add_row("Project Root", str(config_manager.system_config.project_root))
    table.add_row("Output Directory", str(config_manager.system_config.output_dir))
    table.add_row("Leader Model", config_manager.system_config.leader_model)
    table.add_row("Worker Model", config_manager.system_config.worker_model)

    console.print(table)
    console.print()


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"\n[bold cyan]REEMA - Regulatory & Enterprise Management Automation[/bold cyan]")
    console.print(f"Version: {__version__}\n")


if __name__ == "__main__":
    app()
