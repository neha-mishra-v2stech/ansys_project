"""Create a single Workbench project that owns the geometry and analysis."""

from __future__ import annotations

import subprocess
from pathlib import Path


WORKBENCH_RUNNER = Path(r"C:\Program Files\ANSYS Inc\v251\Framework\bin\Win64\RunWB2.exe")


def create_static_structural_workbench_project(geometry_file, project_file):
    """Build a linked Static Structural ``.wbpj`` project in batch Workbench."""
    geometry_path = Path(geometry_file).resolve()
    output_path = Path(project_file).resolve()
    if not WORKBENCH_RUNNER.is_file():
        raise FileNotFoundError(f"ANSYS Workbench runner was not found: {WORKBENCH_RUNNER}")
    if not geometry_path.is_file():
        raise FileNotFoundError(f"Geometry file was not found: {geometry_path}")
    if geometry_path.suffix.lower() not in {".scdoc", ".scdocx", ".stp", ".step"}:
        raise ValueError("Workbench geometry must be a SpaceClaim or STEP file.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path = output_path.with_suffix(".wbjn")
    geometry_literal = str(geometry_path).replace("\\", "/").replace('"', '\\"')
    output_literal = str(output_path).replace("\\", "/").replace('"', '\\"')
    journal_path.write_text(
        f'''# encoding: utf-8
SetScriptVersion(Version="25.1.0")
Reset()
template = GetTemplate(TemplateName="Static Structural", Solver="ANSYS")
system = template.CreateSystem(Position="Default")
geometry = system.GetContainer(ComponentName="Geometry")
geometry.SetFile(FilePath=r"{geometry_literal}")
# SetFile stores the native document in the Workbench Geometry cell.  We do
# not call Update here: in batch mode that starts Mechanical and requires a
# Workbench Mechanical license.  The user can open Geometry immediately in
# SpaceClaim; Workbench transfers it to Model on an interactive update.
Save(FilePath=r"{output_literal}", Overwrite=True)
''',
        encoding="utf-8",
    )
    try:
        completed = subprocess.run(
            [str(WORKBENCH_RUNNER), "-B", "-R", str(journal_path)],
            cwd=str(output_path.parent), text=True, capture_output=True,
            timeout=300, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Workbench did not finish creating the combined project within five minutes.") from exc
    finally:
        journal_path.unlink(missing_ok=True)

    transcript = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Workbench could not create the combined project. {(transcript or 'No Workbench output was returned.')[-3000:]}")
    return {
        "workbench_project_file": str(output_path),
        "geometry_file": str(geometry_path),
        "runner": str(WORKBENCH_RUNNER),
        "geometry_state": "attached_to_spaceclaim",
        "model_state": "requires_interactive_workbench_update",
        "output": transcript[-3000:],
    }
