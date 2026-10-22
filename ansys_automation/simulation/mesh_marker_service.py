"""Extract browser-safe named-selection marker locations from a Gmsh mesh."""

from __future__ import annotations

import meshio


def named_selection_markers(mesh_path: str) -> dict:
    """Return centroids of exported line physical groups, keyed by group name.

    These locations are derived from mesh nodes; they are not reconstructed from
    the CAD model. A group without exported line elements is intentionally omitted.
    """
    mesh = meshio.read(mesh_path)
    physical_data = mesh.cell_data.get("gmsh:physical", [])
    markers = {}
    for name, field in (mesh.field_data or {}).items():
        physical_tag, dimension = (int(field[0]), int(field[1]))
        if dimension != 1:
            continue
        node_ids = set()
        for cell_block, tags in zip(mesh.cells, physical_data):
            if cell_block.type != "line":
                continue
            for element in cell_block.data[tags == physical_tag]:
                node_ids.update(int(node) for node in element)
        if node_ids:
            points = mesh.points[sorted(node_ids)]
            markers[name] = {
                "point": [float(value) for value in points.mean(axis=0)],
                "node_count": len(node_ids),
            }
    return markers


def browser_mesh(mesh_path: str) -> dict:
    """Convert exported VTK triangle connectivity to a compact WebGL payload."""
    mesh = meshio.read(mesh_path)
    triangles = []
    for cell_block in mesh.cells:
        if cell_block.type == "triangle":
            triangles.extend([[int(node) for node in row] for row in cell_block.data])
    if not triangles:
        raise ValueError("The exported mesh does not contain triangular shell elements.")
    return {
        "points": [[float(value) for value in point] for point in mesh.points],
        "triangles": triangles,
    }
