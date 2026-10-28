"""Agent 9: building-design advice, drawing intake, and bounded concept meshes.

Concept meshes are generated from selected wall linework, not a full BIM model.
"""

from pathlib import Path
import hashlib
from ..utils.config import config_manager

from .base_agent import BaseAgent


class BuildingDesignAgent(BaseAgent):
    AGENT_NAME = "Agent 9"
    AGENT_ROLE = "Building 3D Modeling & Interior/Exterior Design Specialist"
    CONFIG_KEY = "building_design_agent"

    def create_concept_model(self, dxf_path: Path, output_dir: Path, bounds: tuple[float, float, float, float],
                             *, wall_height=3.0, design_spec: Path | None = None, source_units=None):
        """Build a bounded, assumption-labeled wall mesh and local preview."""
        from ..utils.cad_model import generate_concept_model
        return generate_concept_model(dxf_path, output_dir, bounds,
                                      wall_height=wall_height, design_spec=design_spec, source_units=source_units)

    def inspect_drawing(self, path: Path) -> dict:
        """Identify a local drawing without transmitting or interpreting its geometry."""
        drawing = Path(path)
        if drawing.suffix.casefold() != ".dwg":
            raise ValueError("DWG drawing required for this intake check")
        if not drawing.is_file() or drawing.is_symlink():
            raise ValueError("A regular local drawing file is required")
        if drawing.stat().st_size > config_manager.specialist_policy.cad_max_bytes:
            raise ValueError("Drawing exceeds the configured file limit")
        with drawing.open("rb") as source:
            header = source.read(6)
        versions = {b"AC1009", b"AC1012", b"AC1014", b"AC1015", b"AC1018", b"AC1021", b"AC1024", b"AC1027", b"AC1032"}
        if header not in versions:
            raise ValueError("File is not a recognized AutoCAD DWG drawing")
        return {
            "filename": drawing.name,
            "format": "DWG",
            "dwg_version_code": header.decode("ascii"),
            "size_bytes": drawing.stat().st_size,
            "sha256": hashlib.sha256(drawing.read_bytes()).hexdigest(),
            "geometry_extracted": False,
            "model_created": False,
        }
