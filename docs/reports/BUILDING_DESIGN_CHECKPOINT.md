# Agent 9 building-design checkpoint

This is the earlier concept-artifact checkpoint. [Package 4](AGENT_IMPROVEMENTS_PACKAGE_4.md)
adds stricter intake, selected-region geometry and furnishing-boundary checks;
historical artifacts below were not regenerated or revalidated by that package.

Date: 2026-09-29. Ahmad and Abdullah keep their names. The eight existing IT
specialists now have display names Agent 1 through Agent 8, in the agreed roster
order. Their internal role keys and knowledge files remain intact. Agent 9 is
registered as a building 3D modeling and interior/exterior design specialist.

## Available now

- Ahmad can route authorized building-design chat questions to Agent 9 for
  conceptual advice and modeling preparation. Anthropic remains the model
  provider; explicit permission is needed before sending any conversation or
  reference content to it.
- `drawing inspect` recognizes a local AutoCAD DWG header without an API key or
  external transmission. It does not extract the drawing's geometry.
- The supplied `المخططات المعمارية تعديل.dwg` is present locally under
  `references/`, is ignored by Git, and passes the intake check. It reports
  DWG header `AC1024` and a size of 3,281,352 bytes.
- The original drawing was opened read-only in AutoCAD and exported to a local
  2018 DXF working copy in `output/agent9/`. The original was not modified or
  uploaded. The DXF contains metre units and architectural linework.
- `drawing concept` now turns a selected DXF area into an editable OBJ mesh,
  material file, PNG preview, and assumptions manifest. For this drawing, the
  first selected area produced 543 wall segments, four generic furniture
  placeholders, and 26 generic bathroom fixture placeholders in
  `output/agent9/concept-plan-c-2018-v2/`. The output is a
  one-area concept, not a finished building model.
- Eight spatially separate wall-plan areas were also exported as individual
  concept meshes and previews in `output/agent9/areas-2018/area-1/` through
  `area-8/`. All eight OBJ meshes passed vertex/face index checks. These are
  numbered by their drawing position, **not** by floor level or construction
  sequence; their floor relationships remain unverified.
- Area 6 was chosen for a more detailed concept. The local JSON placement file
  `output/agent9/area-6-design-suggestions.json` adds one bed, one sofa, one
  TV, and two planters. Its editable mesh and cutaway preview are in
  `output/agent9/area-6-furnished-v3/`. These placements are illustrative and
  must be checked against the architect's room uses and circulation.

## Not yet available

Agent 9 does not yet interpret all floors or align them into a full building,
model verified doors and windows, furnish named rooms, landscape the site, or
render finished interior/exterior views. The current conversion extrudes
`A-WALL` linework at an assumed 3-metre height and shows furniture and sanitary
fixtures only as generic proxies. The Arabic drawing labels and one missing SHX font limit
reliable room identification; no room use has been inferred from them. Floor
plans, elevations, actual floor heights, and design preferences need human
review before a detailed model can be represented as faithful to the plans.
The source drawing must remain local unless the user explicitly authorizes
sharing it with a particular external service. Concept output is not
architectural, structural, safety, or code-compliance approval.
