"""Logging utilities for the multi-agent system."""

import logging
from pathlib import Path
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console
from .config import config_manager

console = Console()


class AgentLogger:
    """Custom logger for agent activities."""

    def __init__(self, name: str = "ITDocSystem"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Create logs directory if it doesn't exist
        log_dir = config_manager.system_config.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        if self.logger.handlers:
            return

        # File handler
        log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        # Rich console handler
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=False
        )
        console_handler.setLevel(logging.INFO)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message: str, agent: str = None):
        """Log info message."""
        prefix = f"[{agent}] " if agent else ""
        self.logger.info(f"{prefix}{message}")

    def debug(self, message: str, agent: str = None):
        """Log debug message."""
        prefix = f"[{agent}] " if agent else ""
        self.logger.debug(f"{prefix}{message}")

    def warning(self, message: str, agent: str = None):
        """Log warning message."""
        prefix = f"[{agent}] " if agent else ""
        self.logger.warning(f"{prefix}{message}")

    def error(self, message: str, agent: str = None):
        """Log error message."""
        prefix = f"[{agent}] " if agent else ""
        self.logger.error(f"{prefix}{message}")

    def agent_start(self, agent_name: str, task: str):
        """Log agent start."""
        console.print(f"[bold blue]🤖 {agent_name}[/bold blue] starting: {task}")
        self.info(f"Starting task: {task}", agent=agent_name)

    def agent_complete(self, agent_name: str, task: str):
        """Log agent completion."""
        console.print(f"[bold green]✓ {agent_name}[/bold green] completed: {task}")
        self.info(f"Completed task: {task}", agent=agent_name)

    def agent_error(self, agent_name: str, error: str):
        """Log agent error."""
        console.print(f"[bold red]✗ {agent_name}[/bold red] error: {error}")
        self.error(f"Error: {error}", agent=agent_name)


# Global logger instance
logger = AgentLogger()
