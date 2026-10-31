"""Validated settings and process catalog shared by the CLI and pipeline."""

import re
from pathlib import Path
from typing import Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .documents import DocumentProfile
from .specialists import SpecialistPolicy

OutputFormat = Literal["pdf", "docx", "markdown", "html"]
Specialist = Literal["access", "problem", "data", "euc"]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CHECKOUT = (PACKAGE_ROOT / "pyproject.toml").is_file()


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    specialization: List[str] = Field(default_factory=list)
    quality_threshold: int = Field(default=85, ge=0, le=100)
    min_quality_for_delivery: int = Field(default=85, ge=0, le=100)
    supported_formats: List[OutputFormat] = Field(default_factory=list)
    default_formats: List[OutputFormat] = Field(default_factory=list)


class ProcessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    # Retired: standards_mapping.yaml is the only source. Kept so old catalogs get a clear error.
    standards: List[str] = Field(default_factory=list)
    complexity: Literal["low", "medium", "high"]
    estimated_pages: int = Field(gt=0)
    kpis: List[str] = Field(default_factory=list)
    specialists: List[Specialist] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class SystemConfig(BaseSettings):
    # Unknown entries are ignored, so an old .env with removed model settings still loads.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    project_root: Path = Field(default_factory=lambda: PACKAGE_ROOT if SOURCE_CHECKOUT else Path.cwd())
    output_dir: Path = Field(
        default=Path("output"),
        validation_alias=AliasChoices("output_dir", "REEMA_OUTPUT_DIR"),
    )
    config_dir: Path = Path("config")
    templates_dir: Path = Path("src/templates")
    knowledge_dir: Path = Path("src/knowledge")
    references_dir: Path = Path("references")
    log_dir: Path = Path("logs")
    task_data_dir: Path = Path("output/assistant")
    user_timezone: str = "Asia/Riyadh"
    default_formats: List[OutputFormat] = Field(
        default_factory=lambda: ["pdf", "docx", "markdown", "html"], min_length=1
    )
    page_target: tuple[int, int] = (15, 30)
    review_chunk_chars: int = Field(default=24_000, ge=1000, le=100_000)
    knowledge_context_chars: int = Field(default=12_000, ge=1000, le=50_000)
    reference_manifest: Path = Path("references/manifest.yaml")
    enforce_page_target: bool = False

    @model_validator(mode="after")
    def resolve_paths(self):
        explicit_paths = set(self.model_fields_set)
        self.project_root = self.project_root.resolve()
        for name in ("output_dir", "config_dir", "templates_dir", "knowledge_dir", "references_dir", "reference_manifest", "log_dir", "task_data_dir"):
            value = getattr(self, name)
            if not value.is_absolute():
                base = PACKAGE_ROOT if not SOURCE_CHECKOUT and name in {"config_dir", "templates_dir", "knowledge_dir"} and name not in explicit_paths else self.project_root
                setattr(self, name, base / value)
        if not 0 < self.page_target[0] <= self.page_target[1]:
            raise ValueError("page_target must be a positive, ordered range")
        try:
            ZoneInfo(self.user_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("USER_TIMEZONE must be a valid IANA time zone") from error
        return self


class CatalogLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently dropping earlier values."""


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


CatalogLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def normalize_process_name(name: str) -> str:
    return re.sub(r"[\W_]+", "_", name.casefold(), flags=re.UNICODE).strip("_")


class ConfigManager:
    def __init__(self, system_config: Optional[SystemConfig] = None):
        self.system_config = system_config or SystemConfig()
        self._load_configs()

    def _read(self, filename, schema):
        path = self.system_config.config_dir / filename
        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=CatalogLoader)
            if not isinstance(data, dict) or not data:
                raise ValueError("expected a nonempty mapping")
            return TypeAdapter(schema).validate_python(data, strict=True)
        except (OSError, ValueError, yaml.YAMLError) as error:
            raise ValueError(f"Invalid configuration {path}: {error}") from error

    def _load_configs(self):
        agents = self._read("agent_config.yaml", Dict[str, AgentConfig])
        processes = self._read("process_definitions.yaml", Dict[str, ProcessConfig])
        standards = self._read("standards_mapping.yaml", Dict[str, List[str]])
        profile = self._read("document_profile.yaml", DocumentProfile)
        specialist_policy = self._read("specialist_policy.yaml", SpecialistPolicy)
        retired = sorted(key for key, process in processes.items() if process.standards)
        if retired:
            raise ValueError("Process standards are read only from standards_mapping.yaml; remove 'standards' "
                             "from process_definitions.yaml for: " + ", ".join(retired))
        if processes.keys() != standards.keys() or any(
            not values or any(not value.strip() for value in values)
            for values in standards.values()
        ):
            raise ValueError("Standards mapping must contain a nonempty list for every process, with no unknown IDs")
        self._process_aliases = {}
        for key, process in processes.items():
            for alias in (key, process.name):
                normalized = normalize_process_name(alias)
                if not normalized:
                    raise ValueError("Process names and IDs cannot be empty")
                if normalized in self._process_aliases and self._process_aliases[normalized] != key:
                    raise ValueError(f"Ambiguous process name: {alias}")
                self._process_aliases[normalized] = key
        self.agents_config = {key: value.model_dump() for key, value in agents.items()}
        self.process_definitions = {key: value.model_dump(exclude={"standards"}) for key, value in processes.items()}
        self.standards_mapping = standards
        self.document_profile = profile
        self.specialist_policy = specialist_policy

    def resolve_process(self, name: str, custom: bool = False) -> tuple[str, dict]:
        if not name.strip() or len(name) > 160 or any(ord(c) < 32 for c in name):
            raise ValueError("Process name must contain 1–160 printable characters")
        key = self._process_aliases.get(normalize_process_name(name))
        if key is not None:
            return key, self.process_definitions[key]
        if custom and normalize_process_name(name):
            return normalize_process_name(name), {
                "name": name.strip(), "standards": [], "specialists": [], "kpis": []
            }
        raise ValueError(f"Unknown process '{name}'. Use list-processes or explicitly pass --custom.")

    def get_agent_config(self, agent_name: str) -> dict:
        return self.agents_config.get(agent_name, {})

    def get_process_definition(self, process_name: str) -> dict:
        key = self._process_aliases.get(normalize_process_name(process_name))
        return self.process_definitions.get(key, {})

    def get_standards_for_process(self, process_name: str) -> list:
        key = self._process_aliases.get(normalize_process_name(process_name))
        return self.standards_mapping.get(key, [])


config_manager = ConfigManager()
