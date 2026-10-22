"""Open-source solver capability checks; no structural results are fabricated."""

from .mapdl_service import mapdl_executable, preflight_shell_job


def solver_capability(job):
    """Describe whether the current 2D shell model can be solved locally."""
    executable = str(mapdl_executable()) if mapdl_executable().is_file() else None
    material = job.material_data or {}
    mesh = (job.result_data or {}).get("mesh", {})
    preflight = preflight_shell_job(job)
    reasons = []
    if not executable:
        reasons.append("MAPDL251.exe was not found in the configured ANSYS installation.")
    if not material:
        reasons.append("A shell material and thickness have not been assigned.")
    if not mesh.get("mesh_statistics", {}).get("element_count_2d"):
        reasons.append("A validated 2D surface mesh has not been generated.")
    reasons.extend(error for error in preflight["errors"] if error not in reasons)
    return {
        "available": not reasons,
        "solver": "PyMAPDL / MAPDL SHELL181" if executable else None,
        "executable": executable,
        "model_type": "2D shell candidate; material shell thickness is required",
        "reasons": reasons,
        "result_state": "not_calculated",
        "preflight": preflight,
    }
