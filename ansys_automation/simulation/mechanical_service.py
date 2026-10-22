"""ANSYS Mechanical execution service used by the Django workflow."""

from pathlib import Path

from ansys.mechanical.core import launch_mechanical


def solve_static_structural(geometry_file, force_newtons, project_file):
    """Import STEP, configure a static analysis, solve it, and save it."""
    step_path = Path(geometry_file).resolve()
    save_path = Path(project_file).resolve()
    if not step_path.is_file():
        raise FileNotFoundError(f"STEP file not found: {step_path}")
    if float(force_newtons) <= 0:
        raise ValueError("Force must be greater than zero.")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    mechanical = None
    try:
        mechanical = launch_mechanical(transport_mode="insecure")
        script = r'''
import os
geometry_path = r"__GEOMETRY_PATH__"
project_path = r"__PROJECT_PATH__"
force_value = __FORCE_VALUE__
if not os.path.isfile(geometry_path):
    raise FileNotFoundError(geometry_path)
geometry_import = Model.GeometryImportGroup.AddGeometryImport()
geometry_import.Import(geometry_path, Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic, None)
bodies = Model.Geometry.GetChildren(DataModelObjectCategory.Body, True)
if not bodies:
    raise RuntimeError("STEP import completed but no Mechanical bodies were found.")
analysis = Model.AddStaticStructuralAnalysis()
for body in bodies:
    body.Material = "Structural Steel"
face_ids = []
edge_ids = []
for assembly in ExtAPI.DataModel.GeoData.Assemblies:
    for part in assembly.Parts:
        for geo_body in part.Bodies:
            for face in geo_body.Faces:
                face_ids.append(face.Id)
            for edge in geo_body.Edges:
                edge_ids.append(edge.Id)
face_ids = list(dict.fromkeys(face_ids))
edge_ids = list(dict.fromkeys(edge_ids))
if len(face_ids) < 2:
    raise RuntimeError("At least two faces are required for support and force.")
if len(edge_ids) < 2:
    raise RuntimeError("At least two geometry edges are required for named selections.")
def selection(ids):
    info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    info.Ids = ids
    return info
def add_named_selection(name, ids):
    named_selection = Model.AddNamedSelection()
    named_selection.Name = name
    named_selection.Location = selection(ids)
    return named_selection
# STEP files do not retain SpaceClaim selection metadata. Recreate the
# workflow's named selections from the imported Mechanical geometry IDs.
add_named_selection("Frictionless Edge", [edge_ids[0]])
add_named_selection("Force & Displacement Edge", [edge_ids[1]])
add_named_selection("Pressure_Load", edge_ids[2:] or [edge_ids[-1]])
add_named_selection("Mesh_Face_Meshing", [face_ids[0]])
add_named_selection("Mesh_Edge_Size_Shell", edge_ids[:2])
add_named_selection("Mesh_Edge_Size_Knuckle", edge_ids[2:6] or edge_ids[:2])
add_named_selection("Mesh_Edge_Size_Bellow1", [edge_ids[-2]])
add_named_selection("Mesh_Edge_Size_Bellow2", [edge_ids[-1]])
add_named_selection("Mesh_Face_Sizing", face_ids)
fixed_support = analysis.AddFixedSupport()
fixed_support.Location = selection([face_ids[0]])
force = analysis.AddForce()
force.Location = selection([face_ids[1]])
force.DefineBy = LoadDefineBy.Components
force.XComponent.Output.SetDiscreteValue(0, Quantity(str(force_value) + " [N]"))
force.YComponent.Output.SetDiscreteValue(0, Quantity("0 [N]"))
force.ZComponent.Output.SetDiscreteValue(0, Quantity("0 [N]"))
Model.Mesh.GenerateMesh()
analysis.Solve(True)
solution = analysis.Solution
deformation = solution.AddTotalDeformation()
stress = solution.AddEquivalentStress()
solution.EvaluateAllResults()
ExtAPI.DataModel.Project.SaveAs(project_path)
print("ANALYSIS_WORKFLOW_COMPLETED")
'''
        script = script.replace("__GEOMETRY_PATH__", str(step_path).replace("\\", "\\\\")).replace("__PROJECT_PATH__", str(save_path).replace("\\", "\\\\")).replace("__FORCE_VALUE__", repr(float(force_newtons)))
        output = mechanical.run_python_script(script)
        return {"geometry_file": str(step_path), "mechanical_project_file": str(save_path), "force_newtons": float(force_newtons), "mechanical_output": str(output)}
    finally:
        if mechanical is not None:
            mechanical.exit()
