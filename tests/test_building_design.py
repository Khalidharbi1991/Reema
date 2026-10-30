"""Numbered specialist roster and Agent 9's local drawing intake."""

import json

import pytest
import ezdxf
from typer.testing import CliRunner

from src.agents import BuildingDesignAgent
from src.main import app
from src.utils.config import config_manager


def test_numbered_specialists_keep_configured_roles():
    keys = (
        "research_agent", "standards_agent", "content_agent", "review_agent",
        "format_agent", "access_agent", "problem_agent", "data_agent",
        "building_design_agent", "euc_agent",
    )
    assert [config_manager.get_agent_config(key)["name"] for key in keys] == [
        f"Agent {number}" for number in range(1, 11)
    ]
    assert config_manager.get_agent_config("secretary_agent")["name"] == "Ahmad"
    assert config_manager.get_agent_config("leader_agent")["name"] == "Abdullah"


def test_agent_9_inspects_dwg_without_claiming_a_model(tmp_path):
    drawing = tmp_path / "sample.dwg"
    drawing.write_bytes(b"AC1024" + b"\0" * 40)
    report = BuildingDesignAgent(api_key="").inspect_drawing(drawing)
    assert report["filename"] == "sample.dwg"
    assert report["dwg_version_code"] == "AC1024"
    assert report["geometry_extracted"] is False
    assert report["model_created"] is False
    result = CliRunner().invoke(app, ["drawing", "inspect", str(drawing)])
    assert result.exit_code == 0
    assert "did not extract geometry or create a 3D model" in result.output


def test_agent_9_rejects_unsupported_or_fake_drawings(tmp_path):
    agent = BuildingDesignAgent(api_key="")
    fake = tmp_path / "fake.dwg"
    fake.write_bytes(b"not a dwg")
    with pytest.raises(ValueError, match="recognized AutoCAD"):
        agent.inspect_drawing(fake)
    with pytest.raises(ValueError, match="DWG drawing required"):
        agent.inspect_drawing(tmp_path / "sample.dxf")


def test_agent_9_generates_a_labeled_local_concept_mesh(tmp_path):
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 6
    drawing.layers.new("A-WALL")
    drawing.layers.new("FURNITER")
    drawing.layers.new("FIXTURE")
    drawing.modelspace().add_line((0, 0), (8, 0), dxfattribs={"layer": "A-WALL"})
    drawing.modelspace().add_line((8, 0), (8, 6), dxfattribs={"layer": "A-WALL"})
    drawing.blocks.new("TEST_CHAIR")
    drawing.blocks.new("WC")
    drawing.modelspace().add_blockref("TEST_CHAIR", (4, 3),
                                     dxfattribs={"layer": "FURNITER"})
    drawing.modelspace().add_blockref("WC", (5, 3),
                                     dxfattribs={"layer": "FIXTURE"})
    source = tmp_path / "plan.dxf"
    drawing.saveas(source)

    result = BuildingDesignAgent(api_key="").create_concept_model(
        source, tmp_path / "model", (-1, -1, 10, 8))
    assert result["wall_segments"] == 2
    assert result["furniture_proxies"] == 1
    assert result["fixture_proxies"] == 1
    assert result["obj_path"].stat().st_size > 200
    assert result["preview_path"].stat().st_size > 100
    obj_lines = result["obj_path"].read_text(encoding="utf-8").splitlines()
    vertices = [line for line in obj_lines if line.startswith("v ")]
    faces = [line for line in obj_lines if line.startswith("f ")]
    assert len(vertices) == 32
    assert len(faces) == 24
    assert max(int(index) for face in faces for index in face.split()[1:]) == 32
    assert "Not a BIM" in " ".join(result["assumptions"])
    with pytest.raises(FileExistsError):
        BuildingDesignAgent(api_key="").create_concept_model(
            source, tmp_path / "model", (-1, -1, 10, 8))

    design_spec = tmp_path / "design.json"
    design_spec.write_text(json.dumps({"placements": [
        {"kind": "bed", "x": 3, "y": 2, "rotation_deg": 30},
        {"kind": "planter", "x": 6, "y": 3},
    ]}), encoding="utf-8")
    furnished = BuildingDesignAgent(api_key="").create_concept_model(
        source, tmp_path / "furnished", (-1, -1, 10, 8), design_spec=design_spec)
    assert [item["kind"] for item in furnished["design_suggestions"]] == ["bed", "planter"]
    furnished_obj = furnished["obj_path"].read_text(encoding="utf-8")
    assert "usemtl suggested_bed" in furnished_obj
    assert "usemtl suggested_planter" in furnished_obj

    design_spec.write_text(json.dumps({"placements": [
        {"kind": "bed", "x": 100, "y": 2},
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        BuildingDesignAgent(api_key="").create_concept_model(
            source, tmp_path / "invalid", (-1, -1, 10, 8), design_spec=design_spec)
