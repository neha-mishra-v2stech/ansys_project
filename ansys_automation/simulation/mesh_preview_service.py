"""Create a portable PNG preview for an individual generated mesh."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import meshio


def create_mesh_preview(vtk_file, image_file):
    """Render triangle edges in the XY plane without requiring a GPU/browser."""
    vtk_path = Path(vtk_file)
    image_path = Path(image_file)
    mesh = meshio.read(vtk_path)
    triangles = [block.data for block in mesh.cells if block.type == "triangle"]
    if not triangles:
        raise ValueError("The VTK file has no triangular surface cells.")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 6), dpi=150)
    axis.triplot(mesh.points[:, 0], mesh.points[:, 1], triangles[0], color="#185abd", linewidth=0.25)
    axis.set_aspect("equal", adjustable="box")
    axis.set_title("Generated shell mesh")
    axis.set_xlabel("X (mm)")
    axis.set_ylabel("Y (mm)")
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(image_path, format="png")
    plt.close(figure)
    return str(image_path.resolve())
