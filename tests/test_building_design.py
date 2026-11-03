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
    report = BuildingDesignAgent().inspect_drawing(drawing)
    assert report["filename"] == "sample.dwg"
    assert report["dwg_version_code"] == "AC1024"
    assert report["geometry_extracted"] is False
    assert report["model_created"] is False
    result = CliRunner().invoke(app, ["drawing", "inspect", str(drawing)])
    assert result.exit_code == 0
    assert "did not extract geometry or create a 3D model" in result.output


def test_agent_9_rejects_unsupported_or_fake_drawings(tmp_path):
    agent = BuildingDesignAgent()
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

    result = BuildingDesignAgent().create_concept_model(
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
        BuildingDesignAgent().create_concept_model(
            source, tmp_path / "model", (-1, -1, 10, 8))

    design_spec = tmp_path / "design.json"
    design_spec.write_text(json.dumps({"placements": [
        {"kind": "bed", "x": 3, "y": 2, "rotation_deg": 30},
        {"kind": "planter", "x": 6, "y": 3},
    ]}), encoding="utf-8")
    furnished = BuildingDesignAgent().create_concept_model(
        source, tmp_path / "furnished", (-1, -1, 10, 8), design_spec=design_spec)
    assert [item["kind"] for item in furnished["design_suggestions"]] == ["bed", "planter"]
    furnished_obj = furnished["obj_path"].read_text(encoding="utf-8")
    assert "usemtl suggested_bed" in furnished_obj
    assert "usemtl suggested_planter" in furnished_obj

    design_spec.write_text(json.dumps({"placements": [
        {"kind": "bed", "x": 100, "y": 2},
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        BuildingDesignAgent().create_concept_model(
            source, tmp_path / "invalid", (-1, -1, 10, 8), design_spec=design_spec)


def test_agent_9_playbook_names_the_local_commands_and_its_limits():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / ".claude" / "skills" / "reema-agent9-design-lead" / "SKILL.md").read_text(encoding="utf-8")
    assert "drawing inspect" in text and "drawing concept" in text and "drawing summary" in text
    for guard in ("Never invent dimensions", "[to confirm]", "licensed professional", "Khalid's yes",
                  "output/claude_code/advice/", "cannot read DWG geometry", "Next step:"):
        assert guard in text


def _plan_drawing(path, units=6):
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = units
    msp = drawing.modelspace()
    msp.add_line((0, 0), (6, 0), dxfattribs={"layer": "A-WALL"})
    msp.add_text("MAJLIS", dxfattribs={"layer": "A-ANNO", "insert": (3, 2)})
    msp.add_mtext("Family\\Psitting", dxfattribs={"layer": "A-ANNO", "insert": (9, 2)})
    msp.add_linear_dim(base=(0, -1), p1=(0, 0), p2=(6, 0), dxfattribs={"layer": "A-DIMS"}).render()
    drawing.blocks.new("DOOR-90")
    drawing.blocks.new("SOFA")
    msp.add_blockref("DOOR-90", (1, 0), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR-90", (5, 0), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("SOFA", (3, 3), dxfattribs={"layer": "FURNITER"})
    drawing.saveas(path)


def test_drawing_summary_lists_labels_dimensions_and_openings_without_inferring_rooms(tmp_path):
    from src.utils.cad_summary import summarize_drawing
    source = tmp_path / "plan.dxf"
    _plan_drawing(source)
    summary = summarize_drawing(source)
    assert summary["units"] == {"insunits_code": 6, "name": "metres"}
    assert [t["text"] for t in summary["text_labels"]] == ["MAJLIS", "Family sitting"]
    assert summary["dimensions"][0]["measured"] == 6.0 and summary["dimensions"][0]["layer"] == "A-DIMS"
    assert summary["door_window_candidates"] == [{"block": "DOOR-90", "layer": "A-DOOR", "count": 2}]
    assert not next(b for b in summary["block_inserts"] if b["block"] == "SOFA")["opening_candidate"]
    assert summary["rooms_inferred"] is False and len(summary["sha256"]) == 64


def test_drawing_summary_label_and_dimension_caps_are_configurable(tmp_path, monkeypatch):
    from src.utils.cad_summary import summarize_drawing
    from src.utils.specialists import SpecialistPolicy
    policy = config_manager.specialist_policy
    assert (policy.cad_summary_max_texts, policy.cad_summary_max_dimensions) == (5000, 5000)
    source = tmp_path / "plan.dxf"
    _plan_drawing(source)
    full = summarize_drawing(source)
    assert full["limits"] == {"text_labels": 5000, "dimensions": 5000}
    assert full["truncated"] == {"text_labels": 0, "dimensions": 0}
    monkeypatch.setattr(config_manager, "specialist_policy",
                        policy.model_copy(update={"cad_summary_max_texts": 1, "cad_summary_max_dimensions": 1}))
    capped = summarize_drawing(source)
    assert [t["text"] for t in capped["text_labels"]] == ["MAJLIS"] and len(capped["dimensions"]) == 1
    assert capped["limits"] == {"text_labels": 1, "dimensions": 1}
    assert capped["truncated"] == {"text_labels": 1, "dimensions": 0}
    for bad in (0, 100001):
        with pytest.raises(ValueError):
            SpecialistPolicy(cad_summary_max_texts=bad)
        with pytest.raises(ValueError):
            SpecialistPolicy(cad_summary_max_dimensions=bad)


def _openings_drawing(path):
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 6
    msp = drawing.modelspace()
    msp.add_line((0, 0), (0.9, 0), dxfattribs={"layer": "A-DOOR"})
    msp.add_arc((0, 0), 0.9, 0, 90, dxfattribs={"layer": "A-DOOR"})
    msp.add_lwpolyline([(2, 0), (3.4, 0), (3.4, 0.2)], dxfattribs={"layer": "WINDOW"})
    drawing.blocks.new("WIN-1.40-20CM")
    msp.add_blockref("WIN-1.40-20CM", (2.7, 0.1), dxfattribs={"layer": "WINDOW", "rotation": 40.75})
    msp.add_line((50, 50), (51, 50), dxfattribs={"layer": "A-DOOR"})
    msp.add_line((0, 0), (5, 0), dxfattribs={"layer": "A-WALL"})
    msp.add_text("D1", dxfattribs={"layer": "A-DOOR", "insert": (0.5, 0.5)})
    drawing.saveas(path)


def test_drawing_extract_keeps_only_the_named_layers_inside_the_area(tmp_path):
    from src.utils.cad_extract import extract_layers
    source = tmp_path / "plan.dxf"
    _openings_drawing(source)
    result = extract_layers(source, ["A-DOOR", "WINDOW", "A-Glaz"], (-1, -1, 4, 1))
    assert result["counts"] == {"A-DOOR/ARC": 1, "A-DOOR/LINE": 1, "WINDOW/INSERT": 1, "WINDOW/LWPOLYLINE": 1}
    arc = next(e for e in result["entities"] if e["type"] == "ARC")
    assert arc["radius"] == 0.9 and (arc["start_angle"], arc["end_angle"]) == (0, 90)
    window = next(e for e in result["entities"] if e["type"] == "INSERT")
    assert window["block"] == "WIN-1.40-20CM" and window["rotation"] == 40.75
    assert all(e["layer"] != "A-WALL" for e in result["entities"])
    assert result["layers_not_in_drawing"] == ["A-Glaz"] and result["skipped_types"] == {"TEXT": 1}
    assert result["units"]["name"] == "metres" and len(result["sha256"]) == 64


def test_drawing_extract_refuses_bad_layers_and_bounds(tmp_path):
    from src.utils.cad_extract import extract_layers
    source = tmp_path / "plan.dxf"
    _openings_drawing(source)
    with pytest.raises(ValueError, match="layers"):
        extract_layers(source, [" ", ""], (0, 0, 1, 1))
    with pytest.raises(ValueError, match="layers"):
        extract_layers(source, [f"L{n}" for n in range(21)], (0, 0, 1, 1))
    for bounds in ((1, 0, 0, 1), (0, 0, 600, 1), (0, 0, float("nan"), 1)):
        with pytest.raises(ValueError):
            extract_layers(source, ["A-DOOR"], bounds)


def test_drawing_extract_cli_writes_a_new_file_only(tmp_path):
    source = tmp_path / "plan.dxf"
    _openings_drawing(source)
    output = tmp_path / "extract.json"
    args = ["drawing", "extract", str(source), "--layers", "A-DOOR,WINDOW,MISSING", "--xmin", "-1", "--ymin", "-1",
            "--xmax", "4", "--ymax", "1", "--output", str(output)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0 and "Entities: 4" in result.output and "Layers not in the drawing: MISSING" in result.output
    assert json.loads(output.read_text(encoding="utf-8"))["bounds"] == [-1, -1, 4, 1]
    again = CliRunner().invoke(app, args)
    assert again.exit_code == 2 and "already exists" in again.output


def _room_drawing(path, angle=0.0):
    """A 3.8 by 3.0 m room with 0.2 m walls, rotated by angle degrees about the origin."""
    import math
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    rot = lambda x, y: (x * c - y * s, x * s + y * c)
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 6
    msp = drawing.modelspace()
    for x in (-0.2, 0.0, 3.8, 4.0):
        msp.add_line(rot(x, -0.2), rot(x, 3.2), dxfattribs={"layer": "A-WALL"})
    msp.add_lwpolyline([rot(-0.2, -0.2), rot(4.0, -0.2), rot(4.0, 0.0), rot(-0.2, 0.0)], close=True,
                       dxfattribs={"layer": "A-WALL"})
    msp.add_line(rot(-0.2, 3.0), rot(1.0, 3.0), dxfattribs={"layer": "A-WALL"})
    msp.add_line(rot(1.9, 3.0), rot(4.0, 3.0), dxfattribs={"layer": "A-WALL"})
    msp.add_line(rot(-0.2, 3.2), rot(4.0, 3.2), dxfattribs={"layer": "A-WALL"})
    msp.add_line(rot(1.0, 1.0), rot(2.0, 1.0), dxfattribs={"layer": "FURNITER"})
    drawing.saveas(path)
    return rot


@pytest.mark.parametrize("angle", [0.0, 40.75])
def test_drawing_measure_finds_wall_thickness_and_clear_spans(tmp_path, angle):
    from src.utils.cad_extract import measure_lines
    source = tmp_path / "room.dxf"
    rot = _room_drawing(source, angle)
    result = measure_lines(source, ["A-WALL"], [rot(1.9, 1.5), rot(1.4, 1.5)], [angle, angle + 90])
    across, up, _, up_at_opening = result["probes"]
    assert [s["length"] for s in across["spans"]] == [0.2, 3.8, 0.2]
    assert [s["contains_point"] for s in across["spans"]] == [False, True, False]
    assert [s["length"] for s in up["spans"]] == [0.2, 3.0, 0.2]
    assert [s["length"] for s in up_at_opening["spans"]] == [0.2, 3.2]
    assert result["source"] == "measured from geometry" and result["units"]["name"] == "metres"
    assert all(layer == "A-WALL" for probe in result["probes"] for hit in probe["hits"] for layer in hit["layers"])


def test_drawing_measure_refuses_bad_input(tmp_path):
    from src.utils.cad_extract import measure_lines
    source = tmp_path / "room.dxf"
    _room_drawing(source)
    for points, angles, reach in (([], [0], 20), ([(0, 0)], [], 20), ([(0, float("inf"))], [0], 20),
                                  ([(0, 0)], [0], 0), ([(0, 0)], [0], 101), ([(0, 0)] * 51, [0], 20)):
        with pytest.raises(ValueError):
            measure_lines(source, ["A-WALL"], points, angles, reach)


def test_drawing_measure_cli_writes_a_new_file_only(tmp_path):
    source = tmp_path / "room.dxf"
    _room_drawing(source)
    output = tmp_path / "measure.json"
    args = ["drawing", "measure", str(source), "--layers", "A-WALL", "--point", "1.9,1.5", "--angle", "0",
            "--angle", "90", "--output", str(output)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0 and "span through the point: 3.8" in result.output
    assert "span through the point: 3.0" in result.output and "Measured from geometry" in result.output
    assert json.loads(output.read_text(encoding="utf-8"))["source"] == "measured from geometry"
    again = CliRunner().invoke(app, args)
    assert again.exit_code == 2 and "already exists" in again.output
    bad = CliRunner().invoke(app, ["drawing", "measure", str(source), "--layers", "A-WALL", "--point", "1.9",
                                   "--angle", "0", "--output", str(tmp_path / "bad.json")])
    assert bad.exit_code == 2 and not (tmp_path / "bad.json").exists()


def test_drawing_summary_cli_writes_a_new_file_only(tmp_path):
    source = tmp_path / "plan.dxf"
    _plan_drawing(source, units=4)
    output = tmp_path / "summary.json"
    result = CliRunner().invoke(app, ["drawing", "summary", str(source), "--output", str(output)])
    assert result.exit_code == 0 and "Units: millimetres" in result.output
    assert json.loads(output.read_text(encoding="utf-8"))["filename"] == "plan.dxf"
    again = CliRunner().invoke(app, ["drawing", "summary", str(source), "--output", str(output)])
    assert again.exit_code == 2 and "already exists" in again.output
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a drawing", encoding="utf-8")
    refused = CliRunner().invoke(app, ["drawing", "summary", str(bad), "--output", str(tmp_path / "bad.json")])
    assert refused.exit_code == 2 and not (tmp_path / "bad.json").exists()
