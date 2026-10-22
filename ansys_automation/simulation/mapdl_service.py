"""PyMAPDL adapter for the generated two-dimensional shell mesh."""

from pathlib import Path
from math import sqrt, isfinite

import meshio
from ansys.mapdl.core import launch_mapdl
from django.conf import settings


def mapdl_executable():
    """Resolve the MAPDL path from Django deployment configuration."""
    return Path(settings.MAPDL_EXECUTABLE).expanduser().resolve()


def _selection_nodes(mesh, selection_name):
    """Return nodes from a named Gmsh line group in the exported mesh."""
    group = (mesh.field_data or {}).get(selection_name)
    physical_data = mesh.cell_data.get("gmsh:physical", [])
    if group is None or not physical_data:
        return set()
    physical_tag = int(group[0])
    nodes = set()
    for block, tags in zip(mesh.cells, physical_data):
        if block.type == "line":
            for element in block.data[tags == physical_tag]:
                nodes.update(int(node) + 1 for node in element)
    return nodes


def preflight_shell_job(job):
    """Validate a shell solve without starting MAPDL or consuming a licence."""
    executable = mapdl_executable()
    material = job.material_data or {}
    conditions = job.boundary_conditions or {}
    fixed = conditions.get("fixed_support")
    force = conditions.get("force")
    errors = []
    if not executable.is_file():
        errors.append(f"MAPDL executable was not found: {executable}")
    if not job.mesh_file or not Path(job.mesh_file).is_file():
        errors.append("A generated MSH mesh is required.")
        return {"ready": False, "errors": errors}
    required_material = {"youngs_modulus_mpa", "poissons_ratio", "density_kg_m3", "shell_thickness_mm"}
    if required_material - set(material):
        errors.append("Shell material is incomplete.")
    if not fixed:
        errors.append("A fixed_support is required to prevent rigid-body motion.")
    if not force:
        errors.append("A force is required.")
    mesh = meshio.read(job.mesh_file)
    triangle_count = sum(len(block.data) for block in mesh.cells if block.type == "triangle")
    fixed_nodes = _selection_nodes(mesh, fixed.get("selection")) if fixed else set()
    force_nodes = _selection_nodes(mesh, force.get("selection")) if force else set()
    if fixed and not fixed_nodes:
        errors.append("The fixed support selection has no exported line nodes.")
    if force and not force_nodes:
        errors.append("The force selection has no exported line nodes.")
    if force:
        direction = force.get("direction", [1, 0, 0])
        try:
            if len(direction) != 3 or sqrt(sum(float(value) ** 2 for value in direction)) == 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Force direction must be a non-zero [x, y, z] vector.")
    return {
        "ready": not errors,
        "errors": errors,
        "executable": str(executable),
        "node_count": len(mesh.points),
        "triangle_count": triangle_count,
        "fixed_node_count": len(fixed_nodes),
        "force_node_count": len(force_nodes),
        "model_type": "SHELL181 triangular shell mesh in mm-N-MPa units",
    }


def solve_shell_job(job, output_dir):
    """Run a genuine MAPDL SHELL181 static solve from the Gmsh surface mesh."""
    preflight = preflight_shell_job(job)
    if not preflight["ready"]:
        raise RuntimeError(" ".join(preflight["errors"]))
    executable = mapdl_executable()
    material = job.material_data or {}
    if not material:
        raise RuntimeError("Assign shell material data before solving.")
    conditions = job.boundary_conditions or {}
    fixed = conditions.get("fixed_support")
    force = conditions.get("force")

    mesh = meshio.read(job.mesh_file)
    triangles = [block.data for block in mesh.cells if block.type == "triangle"]
    if not triangles:
        raise RuntimeError("The mesh has no triangular shell elements.")
    fixed_nodes = _selection_nodes(mesh, fixed.get("selection"))
    force_nodes = _selection_nodes(mesh, force.get("selection"))
    if not fixed_nodes or not force_nodes:
        raise RuntimeError("Support or force named selection has no exported line nodes.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mapdl = None
    try:
        mapdl = launch_mapdl(
            exec_file=str(executable), run_location=str(output_dir),
            jobname=f"job_{job.id}", override=True, cleanup_on_exit=False,
        )
        mapdl.clear()
        mapdl.prep7()
        mapdl.et(1, "SHELL181")
        mapdl.sectype(1, "SHELL")
        mapdl.secdata(float(material["shell_thickness_mm"]))
        mapdl.mp("EX", 1, float(material["youngs_modulus_mpa"]))
        mapdl.mp("PRXY", 1, float(material["poissons_ratio"]))
        # kg/m³ -> tonne/mm³ for the mm-N-MPa unit system.
        mapdl.mp("DENS", 1, float(material["density_kg_m3"]) / 1_000_000_000_000)
        mapdl.type(1)
        mapdl.mat(1)
        mapdl.secnum(1)
        for number, point in enumerate(mesh.points, start=1):
            mapdl.n(number, float(point[0]), float(point[1]), float(point[2]))
        for triangle in triangles:
            for element in triangle:
                mapdl.e(*(int(node) + 1 for node in element))
        # fixed_support intentionally constrains all shell DOFs. A
        # frictionless support must be implemented separately with a defined
        # local normal; it is not silently treated as fixed.
        for node in fixed_nodes:
            mapdl.d(node, "ALL", 0)
        total_force = float(force["magnitude_N"])
        direction = force.get("direction", [1, 0, 0])
        direction_norm = sqrt(sum(float(value) ** 2 for value in direction))
        labels = ("FX", "FY", "FZ")
        for label, component in zip(labels, direction):
            if float(component):
                for node in force_nodes:
                    mapdl.f(node, label, total_force * float(component) / direction_norm / len(force_nodes))
        mapdl.finish()
        mapdl.slashsolu()
        mapdl.antype("STATIC")
        mapdl.solve()
        mapdl.finish()
        
        mapdl.post1()
        mapdl.set("LAST")

        # Extract the maximum displacement and equivalent stress.
        max_displacement = float(
            mapdl.get("MAX_U", "NODE", 0, "U", "SUM", "MAX")
        )
        max_stress = float(
            mapdl.get("MAX_S", "ELEM", 0, "S", "EQV", "MAX")
        )

        # Confirm that MAPDL generated a non-empty result file.
        result_file = output_dir / f"job_{job.id}.rst"

        if not result_file.is_file() or result_file.stat().st_size == 0:
            raise RuntimeError(
                "MAPDL did not produce a valid non-empty result file."
            )

        # Reject invalid numerical results.
        if not isfinite(max_displacement) or not isfinite(max_stress):
            raise RuntimeError(
                "MAPDL returned invalid displacement or stress values."
            )

        if max_displacement < 0 or max_stress < 0:
            raise RuntimeError(
                "MAPDL returned unexpected negative maximum result values."
            )

        mapdl.finish()

        return {
            "solver": "PyMAPDL / MAPDL SHELL181",
            "result_state": "calculated",
            "result_file": str(result_file),
            "maximum_displacement_mm": max_displacement,
            "maximum_equivalent_stress_mpa": max_stress,
            "fixed_node_count": len(fixed_nodes),
            "force_node_count": len(force_nodes),
        }

    finally:
        if mapdl is not None:
            mapdl.exit()
