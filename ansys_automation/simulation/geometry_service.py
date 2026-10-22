
from pathlib import Path

# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions
from ansys.geometry.core.math import Point2D
from ansys.geometry.core.misc import UNITS, Distance
from ansys.geometry.core.sketch import Sketch

from .bellows_geometry_service import generate_bellows_geometry



def generate_geometry_test(output_dir, job_id):
    """
    Validate the Django -> PyAnsys Geometry -> STEP export pipeline.
    This creates a temporary test block, not the final bellows geometry.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    step_path = output_dir / f"analysis_{job_id}_test.step"
    modeler = None

    try:
        modeler = launch_modeler_with_discovery(
            version=251,
            api_version=ApiVersions.V_251,
            timeout=180,
            client_log_level=10,
            client_log_file="discovery_client.log",
        )

        design = modeler.create_design(f"AnalysisJob_{job_id}")

        # Create a 100 x 20 mm sketch.
        sketch = Sketch()
        sketch.box(
            center=Point2D([0, 0], unit=UNITS.mm),
            width=Distance(100, UNITS.mm),
            height=Distance(20, UNITS.mm),
            tag="TestProfile",
        )

        # Extrude by 10 mm to validate 3D geometry generation.
        design.extrude_sketch(
            name="GeometryIntegrationTest",
            sketch=sketch,
            distance=Distance(10, UNITS.mm),
        )

        exported_path = design.export_to_step(str(step_path))

        exported_path = Path(exported_path)

        if not exported_path.is_file() or exported_path.stat().st_size == 0:
            raise RuntimeError("STEP export did not produce a valid file.")

        return {
            "geometry_file": str(exported_path.resolve()),
            "file_size_bytes": exported_path.stat().st_size,
            "body_count": len(design.bodies),
        }

    finally:
        if modeler is not None:
            try:
                modeler.exit()
            except Exception:
                pass


def generate_geometry(output_dir, job_id, dimensions):
    """Generate the production bellows geometry for an analysis job."""
    job_output_dir = Path(output_dir) / f"job_{job_id}"
    result = generate_bellows_geometry(dimensions, output_dir=job_output_dir)
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Geometry generation failed."))
    geometry_file = Path(result["geometry_file"]).resolve()
    if not geometry_file.is_file():
        raise RuntimeError(f"Geometry export was not found: {geometry_file}")
    return {**result, "geometry_file": str(geometry_file), "job_id": job_id}
