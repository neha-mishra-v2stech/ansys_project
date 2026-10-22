
from pathlib import Path

import gmsh


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STEP_FILE = (
    PROJECT_ROOT
    / "generated_geometry"
    / "Nominal UnCorroded.stp"
)


def inspect_step_geometry(step_path=None):
    """
    Inspect imported STEP surfaces and curves.

    Reports geometric measurements to help identify
    Shell, Bellow, support edges, and load edges safely.
    """

    step_path = Path(step_path or STEP_FILE).resolve()

    if not step_path.is_file():
        return {
            "success": False,
            "error": f"STEP file not found: {step_path}",
        }

    initialized = False

    try:
        gmsh.initialize(interruptible=False)
        initialized = True

        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("GeometryInspection")

        imported = gmsh.model.occ.importShapes(
            str(step_path),
            highestDimOnly=False,
        )
        gmsh.model.occ.synchronize()

        surfaces = gmsh.model.getEntities(dim=2)
        curves = gmsh.model.getEntities(dim=1)

        surface_details = []

        for _, tag in surfaces:
            bbox = gmsh.model.getBoundingBox(2, tag)
            area = gmsh.model.occ.getMass(2, tag)
            center = gmsh.model.occ.getCenterOfMass(2, tag)

            surface_details.append({
                "tag": tag,
                "area": round(area, 6),
                "center_of_mass": [
                    round(value, 6) for value in center
                ],
                "bounding_box": [
                    round(value, 6) for value in bbox
                ],
            })

        curve_details = []

        for _, tag in curves:
            bbox = gmsh.model.getBoundingBox(1, tag)
            length = gmsh.model.occ.getMass(1, tag)
            center = gmsh.model.occ.getCenterOfMass(1, tag)

            boundary = gmsh.model.getBoundary(
                [(1, tag)],
                combined=False,
                oriented=False,
                recursive=False,
            )

            endpoints = []

            for dim, point_tag in boundary:
                if dim != 0:
                    continue

                coordinates = gmsh.model.getValue(
                    0, point_tag, []
                )

                endpoints.append([
                    round(value, 6)
                    for value in coordinates
                ])

            curve_details.append({
                "tag": tag,
                "length": round(length, 6),
                "center_of_mass": [
                    round(value, 6) for value in center
                ],
                "bounding_box": [
                    round(value, 6) for value in bbox
                ],
                "endpoints": endpoints,
            })

        return {
            "success": True,
            "step_file": str(step_path),
            "imported_entity_count": len(imported),
            "surface_count": len(surfaces),
            "curve_count": len(curves),
            "surfaces": surface_details,
            "curves": curve_details,
            "message": (
                "STEP geometry inspection completed."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    finally:
        if initialized:
            gmsh.finalize()
