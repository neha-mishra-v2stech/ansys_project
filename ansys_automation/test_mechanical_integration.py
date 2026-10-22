
import os
import traceback

from ansys.geometry.core import (
    launch_modeler_with_discovery,
)
# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core.connection.backend import ApiVersions
from ansys.geometry.core.sketch import Sketch
from ansys.geometry.core.math import Point2D
from ansys.geometry.core.misc import UNITS
from ansys.mechanical.core import launch_mechanical


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = (
    r"C:\Users\SOLVER-3\Documents\Project\ansys_automation"
)

STEP_FILE = None

os.makedirs(PROJECT_DIR, exist_ok=True)


def log(message):
    print(message, flush=True)


def launch_geometry_modeler():
    """Launch SpaceClaim and fall back to the local Discovery backend."""

    launch_options = {
        "version": 251,
        "api_version": ApiVersions.V_251,
        "timeout": 180,
        "client_log_level": 10,
    }

    # try:
    #     log("Trying to connect to SpaceClaim...")
    #     modeler = launch_modeler_with_spaceclaim(
    #         **launch_options,
    #         client_log_file="spaceclaim_client.log",
    #     )
    #     log("Connected to SpaceClaim.")
    #     return modeler
    # except Exception as spaceclaim_error:
    #     log(
    #         "SpaceClaim connection failed; trying Discovery instead: "
    #         f"{spaceclaim_error}"
    #     )
    log("Trying to connect to discovery...")
    modeler = launch_modeler_with_discovery(
        **launch_options,
        client_log_file="discovery_client.log",
    )
    log("Connected to Discovery.")
    return modeler


def create_geometry():
    """Create a 100 x 20 x 10 mm block and export it to STEP."""

    log("\n[1/6] Creating geometry using PyAnsys Geometry...")

    modeler = None

    try:
        modeler = launch_geometry_modeler()

        sketch = Sketch()
        sketch.box(
            center=Point2D([0, 0], unit=UNITS.mm),
            width=100 * UNITS.mm,
            height=20 * UNITS.mm,
        )

        design = modeler.create_design("StaticStructuralDemo")

        body = design.extrude_sketch(
            name="TestBlock",
            sketch=sketch,
            distance=10 * UNITS.mm,
        )

        log(f"Created body: {body.name}")
        log(f"Face count: {len(body.faces)}")
        log(f"Edge count: {len(body.edges)}")

        # Pass a directory, not a filename.
        # PyAnsys generates StaticStructuralDemo.stp in this directory.
        exported_file = design.export_to_step(PROJECT_DIR)
        exported_file = os.path.abspath(str(exported_file))

        if not os.path.isfile(exported_file):
            raise FileNotFoundError(
                f"STEP export did not create a file: {exported_file}"
            )

        log(f"STEP export successful: {exported_file}")

        return exported_file

    finally:
        if modeler is not None:
            modeler.close()
            log("Geometry service closed.")


def run_mechanical(step_path):
    """Import STEP, create a structural analysis, and attempt to solve."""

    mechanical = None

    try:
        # ----------------------------------------------------
        # STEP 2: Launch Mechanical
        # ----------------------------------------------------

        log("\n[2/6] Launching ANSYS Mechanical...")

        mechanical = launch_mechanical(
            transport_mode="insecure"
        )

        log("Mechanical launched successfully.")

        if not os.path.isfile(step_path):
            raise FileNotFoundError(
                f"STEP file not found: {step_path}"
            )

        # ----------------------------------------------------
        # STEP 3: Import geometry
        # ----------------------------------------------------

        log("\n[3/6] Importing STEP geometry...")

        safe_step_path = step_path.replace("\\", "\\\\")

        import_script = r'''
import os
import traceback

geometry_path = r"''' + safe_step_path + r'''"

try:
    print("STEP path:", geometry_path)

    if not os.path.isfile(geometry_path):
        raise FileNotFoundError(geometry_path)

    geometry_import = Model.GeometryImportGroup.AddGeometryImport()

    geometry_format = (
        Ansys.Mechanical.DataModel.Enums
        .GeometryImportPreference.Format.Automatic
    )

    geometry_import.Import(
        geometry_path,
        geometry_format,
        None
    )

    bodies = Model.Geometry.GetChildren(
        DataModelObjectCategory.Body,
        True
    )

    print("Imported body count:", len(bodies))

    for body in bodies:
        print("Imported body:", body.Name)

    if len(bodies) == 0:
        raise RuntimeError("STEP import completed but no bodies were found.")

    print("GEOMETRY_IMPORT_SUCCESS")

except Exception:
    traceback.print_exc()
    raise
'''

        mechanical.run_python_script(import_script)

        log("Geometry import script completed.")

        # ----------------------------------------------------
        # STEP 4: Static Structural, material, mesh and loads
        # ----------------------------------------------------

        log("\n[4/6] Setting up Static Structural analysis...")

        analysis_script = r'''
import traceback

try:
    # Create a Static Structural analysis.
    analysis = Model.AddStaticStructuralAnalysis()

    print("Analysis created:", analysis.Name)

    # Find imported Mechanical bodies.
    bodies = Model.Geometry.GetChildren(
        DataModelObjectCategory.Body,
        True
    )

    if len(bodies) == 0:
        raise RuntimeError("No bodies found in Mechanical.")

    # Assign a common built-in material.
    # Confirm that this material exists in your installation.
    for body in bodies:
        print("Assigning material to:", body.Name)
        body.Material = "Structural Steel"

    print("Material assignment completed.")

    # Obtain geometry faces from Mechanical GeoData.
    # DataModelObjectCategory.Face is deliberately not used.
    face_ids = []

    for assembly in ExtAPI.DataModel.GeoData.Assemblies:
        for part in assembly.Parts:
            for geo_body in part.Bodies:
                for face in geo_body.Faces:
                    face_ids.append(face.Id)

    # Remove duplicate IDs while preserving order.
    face_ids = list(dict.fromkeys(face_ids))

    print("Available geometry face IDs:", face_ids)

    if len(face_ids) < 2:
        raise RuntimeError(
            "At least two geometry faces are required. "
            "Check the imported geometry and GeoData."
        )

    # Create selections using the actual geometry IDs.
    fixed_selection = (
        ExtAPI.SelectionManager.CreateSelectionInfo(
            SelectionTypeEnum.GeometryEntities
        )
    )
    fixed_selection.Ids = [face_ids[0]]

    force_selection = (
        ExtAPI.SelectionManager.CreateSelectionInfo(
            SelectionTypeEnum.GeometryEntities
        )
    )
    force_selection.Ids = [face_ids[1]]

    # Fixed Support.
    fixed_support = analysis.AddFixedSupport()
    fixed_support.Location = fixed_selection

    print("Fixed Support added to face ID:", face_ids[0])

    # Force.
    force = analysis.AddForce()
    force.Location = force_selection

    force.DefineBy = LoadDefineBy.Components

    force.XComponent.Output.SetDiscreteValue(
        0, Quantity("1000 [N]")
    )
    force.YComponent.Output.SetDiscreteValue(
        0, Quantity("0 [N]")
    )
    force.ZComponent.Output.SetDiscreteValue(
        0, Quantity("0 [N]")
    )

    print("Force added: X = 1000 N.")
    print("Force applied to face ID:", face_ids[1])

    # Generate mesh.
    Model.Mesh.GenerateMesh()

    print("MESH_GENERATION_SUCCESS")

    # --------------------------------------------------------
    # STEP 5: Solve
    # --------------------------------------------------------

    print("Starting Static Structural solve...")
    analysis.Solve(True)

    print("SOLVE_COMPLETED")

    # --------------------------------------------------------
    # STEP 6: Results
    # --------------------------------------------------------

    solution = analysis.Solution

    deformation = solution.AddTotalDeformation()
    stress = solution.AddEquivalentStress()

    solution.EvaluateAllResults()

    print("Total Deformation result evaluated.")
    print("Equivalent Stress result evaluated.")

    try:
        print("Maximum deformation:", deformation.Maximum.Value)
    except Exception as exc:
        print("Deformation value unavailable:", str(exc))

    try:
        print("Maximum equivalent stress:", stress.Maximum.Value)
    except Exception as exc:
        print("Stress value unavailable:", str(exc))

    print("ANALYSIS_WORKFLOW_COMPLETED")

except Exception:
    traceback.print_exc()
    raise
'''

        mechanical.run_python_script(analysis_script)

        log("Analysis setup and solve script completed.")

        # ----------------------------------------------------
        # Save project
        # ----------------------------------------------------

        log("\nSaving Mechanical project...")

        save_path = os.path.join(
            PROJECT_DIR,
            "StaticStructuralDemo.mechdat"
        )
        safe_save_path = save_path.replace("\\", "\\\\")

        save_script = r'''
save_path = r"''' + safe_save_path + r'''"

ExtAPI.DataModel.Project.SaveAs(save_path)

print("Project saved:", save_path)
'''

        mechanical.run_python_script(save_script)

        log("Mechanical workflow completed.")

    finally:
        if mechanical is not None:
            try:
                mechanical.exit()
                log("Mechanical closed.")
            except Exception as exc:
                log(f"Mechanical shutdown message: {exc}")


def main():
    global STEP_FILE

    try:
        log("Starting PyAnsys Static Structural demo.")

        STEP_FILE = create_geometry()
        run_mechanical(STEP_FILE)

        log("\nSUCCESS: Workflow completed.")

    except Exception:
        error_text = traceback.format_exc()

        log("\nWORKFLOW FAILED:")
        log(error_text)

        error_file = os.path.join(
            PROJECT_DIR,
            "mechanical_integration_output.txt"
        )

        with open(
            error_file,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(error_text)

        log(f"Error details saved to: {error_file}")


if __name__ == "__main__":
    main()
