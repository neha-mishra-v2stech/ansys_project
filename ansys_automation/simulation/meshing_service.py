
"""
Gmsh-based meshing service for the bellows STEP geometry.

Generates:
- Gmsh MSH file with physical groups
- VTK surface mesh for visualization
- Mesh statistics and quality information

This creates a 2D surface mesh. It does not perform structural solving.
"""

from pathlib import Path
import math
import traceback

import gmsh
import meshio
import numpy as np


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_GEOMETRY_PATH = (
    BASE_DIR / "generated_geometry" / "Nominal UnCorroded.stp"
)

DEFAULT_MESH_PATH = (
    BASE_DIR / "generated_geometry" / "bellows_mesh.msh"
)

DEFAULT_VTK_PATH = (
    BASE_DIR / "generated_geometry" / "bellows_mesh.vtk"
)


# ---------------------------------------------------------------------
# Named selections
# Entity tags are based on the currently inspected STEP geometry.
# Revalidate them if the geometry is regenerated or changed.
# ---------------------------------------------------------------------

NAMED_SELECTIONS = {
    "Frictionless Edge": {
        "dim": 1,
        "tags": [8],
    },
    "Force & Displacement Edge": {
        "dim": 1,
        "tags": [4],
    },
    "Pressure_Load": {
        "dim": 1,
        "tags": [3, 6, 9, 10, 11, 12, 13, 14, 15, 19],
    },
    "Mesh_Face_Meshing": {
        "dim": 2,
        "tags": [1],
    },
    "Mesh_Edge_Size_Shell": {
        "dim": 1,
        "tags": [2, 4],
    },
    "Mesh_Edge_Size_Knuckle": {
        "dim": 1,
        "tags": [6, 10, 12, 19],
    },
    "Mesh_Edge_Size_Bellow1": {
        "dim": 1,
        "tags": [8],
    },
    "Mesh_Edge_Size_Bellow2": {
        "dim": 1,
        "tags": [14],
    },
    "Mesh_Face_Sizing": {
        "dim": 2,
        "tags": [1, 2],
    },
}


DEFAULT_MESH_SIZES = {
    "global": 20.0,
    "shell": 20.0,
    "knuckle": 8.0,
    "bellow1": 10.0,
    "bellow2": 10.0,
}


# ---------------------------------------------------------------------
# Physical groups
# ---------------------------------------------------------------------

def _create_physical_groups():
    """
    Create named physical groups and validate their entity tags.

    Returns a dictionary containing the physical group metadata.
    """

    created = {}

    available_by_dimension = {
        dim: {
            tag for _, tag in gmsh.model.getEntities(dim)
        }
        for dim in range(4)
    }

    for name, selection in NAMED_SELECTIONS.items():
        dim = selection["dim"]
        tags = selection["tags"]

        invalid_tags = [
            tag
            for tag in tags
            if tag not in available_by_dimension[dim]
        ]

        if invalid_tags:
            raise ValueError(
                f"Invalid entity tags for '{name}': "
                f"{invalid_tags}. "
                "The STEP geometry may have changed."
            )

        group_tag = gmsh.model.addPhysicalGroup(dim, tags)
        gmsh.model.setPhysicalName(dim, group_tag, name)

        created[name] = {
            "dimension": dim,
            "entity_tags": tags.copy(),
            "physical_tag": group_tag,
        }

    return created


# ---------------------------------------------------------------------
# Local mesh sizing
# ---------------------------------------------------------------------


def _apply_local_mesh_sizes(sizes):
    """Apply local mesh-size constraints to configured curve endpoints."""

    curve_size_groups = {
        "Mesh_Edge_Size_Shell": sizes.get("shell", 20.0),
        "Mesh_Edge_Size_Knuckle": sizes.get("knuckle", 8.0),
        "Mesh_Edge_Size_Bellow1": sizes.get("bellow1", 10.0),
        "Mesh_Edge_Size_Bellow2": sizes.get("bellow2", 10.0),
    }

    for group_name, target_size in curve_size_groups.items():
        group = NAMED_SELECTIONS[group_name]

        for curve_tag in group["tags"]:
            boundary = gmsh.model.getBoundary(
                [(1, curve_tag)],
                combined=False,
                oriented=False,
                recursive=False,
            )

            point_tags = [
                tag for dim, tag in boundary if dim == 0
            ]

            if point_tags:
                gmsh.model.mesh.setSize(
                    [(0, tag) for tag in point_tags],
                    float(target_size),
                )

    # Apply the global size limits as well.
    global_size = float(sizes.get("global", 20.0))
    gmsh.option.setNumber("Mesh.MeshSizeMin", 0.1)
    gmsh.option.setNumber("Mesh.MeshSizeMax", global_size)


# ---------------------------------------------------------------------
# Geometry summary
# ---------------------------------------------------------------------

def _get_geometry_summary():
    entities = {
        dim: gmsh.model.getEntities(dim)
        for dim in range(4)
    }

    return {
        "points": len(entities[0]),
        "curves": len(entities[1]),
        "surfaces": len(entities[2]),
        "volumes": len(entities[3]),
    }


# ---------------------------------------------------------------------
# Mesh statistics
# ---------------------------------------------------------------------

def _get_mesh_statistics():
    node_tags, node_coordinates, _ = gmsh.model.mesh.getNodes()

    element_count_1d = 0
    element_count_2d = 0
    element_count_3d = 0
    triangle_areas = []
    triangle_min_angles = []
    degenerate_triangles = 0

    for dim in range(4):
        for entity_dim, entity_tag in gmsh.model.getEntities(dim):
            element_types, element_tag_blocks, _ = (
                gmsh.model.mesh.getElements(
                    entity_dim,
                    entity_tag,
                )
            )

            for element_type, element_tags in zip(
                element_types,
                element_tag_blocks,
            ):
                properties = gmsh.model.mesh.getElementProperties(
                    int(element_type)
                )

                element_dimension = int(properties[1])
                element_name = str(properties[0])

                count = len(element_tags)

                if element_dimension == 1:
                    element_count_1d += count
                elif element_dimension == 2:
                    element_count_2d += count
                elif element_dimension == 3:
                    element_count_3d += count

                if (
                    element_dimension == 2
                    and "Triangle" in element_name
                ):
                    _, _, connectivity = (
                        gmsh.model.mesh.getElements(
                            entity_dim,
                            entity_tag,
                        )
                    )

                    node_count = int(properties[3])
                    element_node_tags = np.asarray(
                        connectivity[
                            list(element_types).index(element_type)
                        ],
                        dtype=np.int64,
                    ).reshape(-1, node_count)

                    # Get coordinates for the triangle's corner nodes.
                    corner_count = int(properties[5])

                    if corner_count != 3:
                        continue

                    node_tag_to_index = {
                        int(tag): index
                        for index, tag in enumerate(node_tags)
                    }

                    points = np.asarray(
                        node_coordinates,
                        dtype=float,
                    ).reshape(-1, 3)

                    for connectivity_row in element_node_tags:
                        triangle_tags = connectivity_row[:3]

                        triangle_points = np.array([
                            points[node_tag_to_index[int(tag)]]
                            for tag in triangle_tags
                        ])

                        p1, p2, p3 = triangle_points

                        area = 0.5 * np.linalg.norm(
                            np.cross(p2 - p1, p3 - p1)
                        )

                        if area <= 1e-12:
                            degenerate_triangles += 1
                            continue

                        triangle_areas.append(float(area))

                        side_a = np.linalg.norm(p2 - p3)
                        side_b = np.linalg.norm(p1 - p3)
                        side_c = np.linalg.norm(p1 - p2)

                        angles = []

                        for opposite, side_x, side_y in (
                            (side_a, side_b, side_c),
                            (side_b, side_a, side_c),
                            (side_c, side_a, side_b),
                        ):
                            denominator = 2.0 * side_x * side_y

                            if denominator <= 1e-12:
                                angle = 0.0
                            else:
                                cosine = (
                                    side_x**2
                                    + side_y**2
                                    - opposite**2
                                ) / denominator

                                angle = math.degrees(
                                    math.acos(
                                        max(-1.0, min(1.0, cosine))
                                    )
                                )

                            angles.append(angle)

                        triangle_min_angles.append(min(angles))

    return {
        "node_count": len(node_tags),
        "element_count_1d": element_count_1d,
        "element_count_2d": element_count_2d,
        "element_count_3d": element_count_3d,
        "triangle_count": len(triangle_areas),
        "degenerate_triangle_count": degenerate_triangles,
        "minimum_triangle_area": (
            min(triangle_areas) if triangle_areas else None
        ),
        "maximum_triangle_area": (
            max(triangle_areas) if triangle_areas else None
        ),
        "minimum_triangle_angle": (
            min(triangle_min_angles)
            if triangle_min_angles
            else None
        ),
    }


# ---------------------------------------------------------------------
# VTK export
# ---------------------------------------------------------------------

def _export_surface_vtk(mesh_path, vtk_path):
    """
    Export only surface triangles and quadrilaterals to VTK.

    Deliberately do not pass gmsh:physical or gmsh:geometrical cell data.
    This avoids the meshio error caused by mismatched cell-data blocks
    after Gmsh exports multiple element blocks.

    Named physical groups remain in the MSH file. This VTK file is
    intended for surface visualization.
    """

    source_mesh = meshio.read(str(mesh_path))

    surface_cells = [
        (cell_block.type, cell_block.data)
        for cell_block in source_mesh.cells
        if cell_block.type in ("triangle", "quad")
    ]

    if not surface_cells:
        raise ValueError(
            "No triangle or quadrilateral surface elements "
            "were found in the MSH file."
        )

    vtk_mesh = meshio.Mesh(
        points=source_mesh.points,
        cells=surface_cells,
    )

    vtk_mesh.write(str(vtk_path))

    return {
        "vtk_surface_cell_count": sum(
            len(cell_data)
            for _, cell_data in surface_cells
        ),
        "vtk_cell_types": sorted({
            cell_type
            for cell_type, _ in surface_cells
        }),
    }


def _verify_exported_physical_groups(mesh_path, expected_groups):
    """Verify group names and element membership in the written MSH file."""
    exported = meshio.read(str(mesh_path))
    fields = exported.field_data or {}
    verification = {}
    for name, group in expected_groups.items():
        field = fields.get(name)
        physical_tag = group["physical_tag"]
        exported_membership = 0
        for block, tags in zip(exported.cells, exported.cell_data.get("gmsh:physical", [])):
            if block.dim == group["dimension"]:
                exported_membership += int(np.count_nonzero(np.asarray(tags) == physical_tag))
        source_membership = 0
        for entity_tag in group["entity_tags"]:
            _, element_blocks, _ = gmsh.model.mesh.getElements(group["dimension"], entity_tag)
            source_membership += sum(len(block) for block in element_blocks)
        verification[name] = {
            "declared_in_msh": field is not None,
            "source_entity_element_count": source_membership,
            "exported_physical_tag_element_count": exported_membership,
            "has_members": source_membership > 0,
            "note": "An element shared by overlapping Gmsh groups may have one physical tag in meshio output.",
        }
    return verification


# ---------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------

def generate_mesh(
    step_path=None,
    mesh_path=None,
    vtk_path=None,
    mesh_size=20.0,
    mesh_sizes=None,
):
    """
    Generate a 2D surface mesh from the STEP file.

    Parameters
    ----------
    step_path:
        Optional STEP geometry path.
    mesh_path:
        Optional output MSH path.
    vtk_path:
        Optional output VTK path.
    mesh_size:
        Global target mesh size.

    Returns
    -------
    dict
        Success/failure status, output paths, named selections,
        geometry information, and mesh statistics.
    """

    step_path = Path(
        step_path or DEFAULT_GEOMETRY_PATH
    ).resolve()

    mesh_path = Path(
        mesh_path or DEFAULT_MESH_PATH
    ).resolve()

    vtk_path = Path(
        vtk_path or DEFAULT_VTK_PATH
    ).resolve()

    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    vtk_path.parent.mkdir(parents=True, exist_ok=True)

    if not step_path.is_file():
        return {
            "success": False,
            "message": "STEP geometry file was not found.",
            "error": str(step_path),
            "geometry_file": str(step_path),
            "mesh_file": str(mesh_path),
            "vtk_file": str(vtk_path),
        }

    sizes = DEFAULT_MESH_SIZES.copy()
    sizes["global"] = float(mesh_size)
    if mesh_sizes:
        unknown = set(mesh_sizes) - set(sizes)
        if unknown:
            return {"success": False, "message": "Unknown mesh-size controls.", "error": ", ".join(sorted(unknown))}
        sizes.update({name: float(value) for name, value in mesh_sizes.items()})

    if any(
        not math.isfinite(float(value)) or float(value) <= 0
        for value in sizes.values()
    ):
        return {
            "success": False,
            "message": "Mesh sizes must be positive finite numbers.",
            "error": repr(sizes),
            "geometry_file": str(step_path),
            "mesh_file": str(mesh_path),
            "vtk_file": str(vtk_path),
        }

    initialized_here = False

    try:
        if not gmsh.isInitialized():
            # Django can execute this in a worker thread.  Do not install
            # Gmsh's process-level SIGINT handler from that thread.
            gmsh.initialize(interruptible=False)
            initialized_here = True

        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.1)
        gmsh.option.setNumber("Mesh.MeshSizeMax", sizes["global"])

        # Do not enable Mesh.SaveAll here. We want normal physical-group
        # export and will verify the MSH metadata after writing.
        gmsh.clear()
        gmsh.model.add("bellows_mesh")

        gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()

        geometry_summary = _get_geometry_summary()

        if geometry_summary["surfaces"] == 0:
            raise ValueError(
                "The imported STEP file contains no surfaces."
            )

        # Register named physical groups.
        physical_groups = _create_physical_groups()

        # Apply local sizes to selected curve endpoints.
        _apply_local_mesh_sizes(sizes)

        # Generate a 2D surface mesh.
        gmsh.model.mesh.generate(2)

        statistics = _get_mesh_statistics()

        if statistics["element_count_2d"] == 0:
            raise ValueError(
                "No 2D surface elements were generated."
            )

        # Export the physical-group mesh.
        gmsh.write(str(mesh_path))

        if not mesh_path.is_file():
            raise RuntimeError(
                "The MSH file was not created."
            )

        physical_group_verification = _verify_exported_physical_groups(
            mesh_path, physical_groups
        )
        missing_groups = [
            name for name, item in physical_group_verification.items()
            if not item["declared_in_msh"] or not item["has_members"]
        ]
        if missing_groups:
            raise ValueError("Named selections have no exported membership: " + ", ".join(missing_groups))

        # Export VTK without carrying over incompatible cell metadata.
        vtk_summary = _export_surface_vtk(
            mesh_path,
            vtk_path,
        )

        if not vtk_path.is_file():
            raise RuntimeError(
                "The VTK file was not created."
            )

        return {
            "success": True,
            "message": "Surface mesh generated successfully.",
            "geometry_file": str(step_path),
            "mesh_file": str(mesh_path),
            "vtk_file": str(vtk_path),
            "geometry": geometry_summary,
            "mesh_statistics": statistics,
            "mesh_sizes": sizes,
            "physical_groups": physical_groups,
            "physical_group_verification": physical_group_verification,
            "vtk": vtk_summary,
            "analysis_ready": (
                statistics["element_count_3d"] > 0
            ),
            "note": (
                "This is a 2D surface mesh. "
                "It does not perform structural solving. "
                "The VTK file is for surface visualization; "
                "named physical-group metadata is kept in the MSH file."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Mesh generation or export failed.",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "geometry_file": str(step_path),
            "mesh_file": str(mesh_path),
            "vtk_file": str(vtk_path),
        }

    finally:
        if initialized_here and gmsh.isInitialized():
            gmsh.finalize()
