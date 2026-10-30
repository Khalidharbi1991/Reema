from typer.testing import CliRunner
from tests.test_phase01 import catalog


def test_cli_status_and_catalog_need_no_key(catalog, monkeypatch):
    from src import main
    monkeypatch.setattr(main, "config_manager", catalog)
    catalog.system_config.anthropic_api_key = ""
    for command in ("status", "list-processes", "version"):
        result = CliRunner().invoke(main.app, [command])
        assert result.exit_code == 0, result.output


