
from pathlib import Path

import gmsh
import meshio


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEOMETRY_DIR = PROJECT_ROOT / "generated_geometry"

DEFAULT_STEP = GEOMETRY_DIR / "Nominal UnCorroded.stp"
DEFAULT_MESH = GEOMETRY_DIR / "Nominal UnCorroded.msh"
DEFAULT_VTK = GEOMETRY_DIR / "Nominal UnCorroded.vtk"


def generate_named_mesh(
    step_path=None,
    mesh_path=None,
    vtk_path=None,
    mesh_size=20.0,
):
    """
    Generate a 2D mesh with named Shell and Bellow groups.

    Surface identification uses geometric measurements.
    Boundary curves are assigned by their adjacency to
    the identified surfaces, rather than fixed curve IDs.

    This does not yet assign structural loads or supports.
    """

    step_path = Path(step_path or DEFAULT_STEP).resolve()
    mesh_path = Path(mesh_path or DEFAULT_MESH).resolve()
    vtk_path = Path(vtk_path or DEFAULT_VTK).resolve()

    if not step_path.is_file():
        return {
            "success": False,
            "error": f"STEP file not found: {step_path}",
        }

    try:
        mesh_size = float(mesh_size)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error": "Mesh size must be a valid number.",
        }

    if not 0 < mesh_size < float("inf"):
        return {
            "success": False,
            "error": "Mesh size must be finite and positive.",
        }

    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    vtk_path.parent.mkdir(parents=True, exist_ok=True)

    initialized = False

    try:
        # Django handles this request in a worker thread.  Gmsh's default
        # interrupt handler registers SIGINT, which Python only permits from
        # the main thread.  Django already owns process interruption, so do
        # not install Gmsh's optional handler here.
        gmsh.initialize(interruptible=False)
        initialized = True

        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size * 0.5)
        gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)

        gmsh.model.add("BellowsShellNamedMesh")

        gmsh.model.occ.importShapes(
            str(step_path),
            highestDimOnly=False,
        )
        gmsh.model.occ.synchronize()

        surface_entities = gmsh.model.getEntities(dim=2)

        if len(surface_entities) < 2:
            raise ValueError(
                f"Expected Shell and Bellow surfaces; "
                f"found {len(surface_entities)} surface(s)."
            )

        # Identify surfaces using their bounding boxes and
        # centers of mass, not their imported entity numbers.
        surface_info = []

        for _, tag in surface_entities:
            bbox = gmsh.model.getBoundingBox(2, tag)
            center = gmsh.model.occ.getCenterOfMass(2, tag)
            area = gmsh.model.occ.getMass(2, tag)

            surface_info.append({
                "tag": tag,
                "bbox": bbox,
                "center": center,
                "area": area,
            })

        def shell_score(info):
            xmin, ymin, _, xmax, ymax, _ = info["bbox"]
            return (
                abs(xmin - 121.41)
                + abs(xmax - 136.50)
                + abs(ymin + 1117.0)
                + abs(ymax + 289.0)
            )

        def bellow_score(info):
            xmin, ymin, _, xmax, ymax, _ = info["bbox"]
            return (
                abs(xmin - 121.41)
                + abs(xmax - 269.97)
                + abs(ymin + 289.0)
                + abs(ymax - 0.0)
            )

        shell_info = min(surface_info, key=shell_score)
        remaining = [
            info for info in surface_info
            if info["tag"] != shell_info["tag"]
        ]
        bellow_info = min(remaining, key=bellow_score)

        if shell_score(shell_info) > 1.0:
            raise ValueError(
                "Could not confidently identify the Shell surface."
            )

        if bellow_score(bellow_info) > 1.0:
            raise ValueError(
                "Could not confidently identify the Bellow surface."
            )

        shell_tag = shell_info["tag"]
        bellow_tag = bellow_info["tag"]

        # Add named surface physical groups.
        shell_group = gmsh.model.addPhysicalGroup(
            2, [shell_tag]
        )
        gmsh.model.setPhysicalName(2, shell_group, "Shell")

        bellow_group = gmsh.model.addPhysicalGroup(
            2, [bellow_tag]
        )
        gmsh.model.setPhysicalName(2, bellow_group, "Bellow")

        # Identify curves by their adjacent surface entities.
        shell_curves = []
        bellow_curves = []

        for _, curve_tag in gmsh.model.getEntities(dim=1):
            upward, _ = gmsh.model.getAdjacencies(1, curve_tag)
            adjacent_surfaces = set(int(tag) for tag in upward)

            if shell_tag in adjacent_surfaces:
                shell_curves.append(curve_tag)

            if bellow_tag in adjacent_surfaces:
                bellow_curves.append(curve_tag)

        if not shell_curves or not bellow_curves:
            raise ValueError(
                "Could not identify boundary curves for both surfaces."
            )

        shell_edge_group = gmsh.model.addPhysicalGroup(
            1, sorted(shell_curves)
        )
        gmsh.model.setPhysicalName(
            1, shell_edge_group, "Shell_Boundary"
        )

        bellow_edge_group = gmsh.model.addPhysicalGroup(
            1, sorted(bellow_curves)
        )
        gmsh.model.setPhysicalName(
            1, bellow_edge_group, "Bellow_Profile_Edges"
        )

        # Generate the surface mesh.
        gmsh.model.mesh.generate(2)

        node_tags, _, _ = gmsh.model.mesh.getNodes()

        element_types, element_tags, _ = (
            gmsh.model.mesh.getElements(dim=2)
        )

        element_count = sum(
            len(tags) for tags in element_tags
        )

        if len(node_tags) == 0 or element_count == 0:
            raise ValueError("Mesh generation produced no elements.")

        # Save MSH with named physical groups.
        gmsh.write(str(mesh_path))

        # Export a clean VTK visualization mesh.
        mesh = meshio.read(str(mesh_path))

        supported_cells = {"triangle", "quad"}
        surface_cells = [
            block for block in mesh.cells
            if block.type in supported_cells
        ]

        if not surface_cells:
            raise ValueError(
                "No triangle or quadrilateral cells found for VTK."
            )

        vtk_mesh = meshio.Mesh(
            points=mesh.points,
            cells=surface_cells,
        )
        vtk_mesh.write(str(vtk_path))

        return {
            "success": True,
            "message": "Named surface mesh generated successfully.",
            "mesh_file": str(mesh_path),
            "vtk_file": str(vtk_path),
            "surface_count": len(surface_entities),
            "shell_surface_tag": shell_tag,
            "bellow_surface_tag": bellow_tag,
            "shell_boundary_curve_count": len(shell_curves),
            "bellow_profile_curve_count": len(bellow_curves),
            "node_count": len(node_tags),
            "element_count_2d": element_count,
            "physical_groups": [
                "Shell",
                "Bellow",
                "Shell_Boundary",
                "Bellow_Profile_Edges",
            ],
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Named mesh generation failed.",
            "error": str(exc),
        }

    finally:
        if initialized:
            gmsh.finalize()
