
from pathlib import Path
# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions
from ansys.geometry.core.math import Point2D
from ansys.geometry.core.misc import UNITS
from ansys.geometry.core.sketch import Sketch

from simulation.geometry_parameters import calculate_geometry_parameters


# =========================================================
# PATHS AND SETTINGS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "generated_geometry"

# SpaceClaim tolerance was 1e-5 m, equivalent to 0.01 mm.
TOL_MM = 0.01


# =========================================================
# COORDINATE HELPERS
# =========================================================

def point(x, y):
    """Create a 2D sketch point using millimetres."""
    return Point2D([float(x), float(y)], unit=UNITS.mm)


def coordinate_mm(value):
    """Convert a PyAnsys coordinate value to millimetres."""
    if hasattr(value, "to"):
        return float(value.to(UNITS.mm).magnitude)

    # PyAnsys point coordinates without explicit units are
    # normally expressed in metres.
    return float(value) * 1000.0


def xyz_mm(point_3d):
    """Return a 3D point as (x, y, z), in millimetres."""
    return (
        coordinate_mm(point_3d.x),
        coordinate_mm(point_3d.y),
        coordinate_mm(point_3d.z),
    )


def edge_endpoints_mm(edge):
    """Return the start and end coordinates of an edge."""
    return xyz_mm(edge.start), xyz_mm(edge.end)


def edge_midpoint_mm(edge):
    """
    Calculate the midpoint from the edge endpoints.

    This is the exact midpoint for a straight edge. For an arc,
    it is only the midpoint of the endpoint chord, so arc
    selection uses curve type instead of this value.
    """
    start, end = edge_endpoints_mm(edge)

    return (
        (start[0] + end[0]) / 2.0,
        (start[1] + end[1]) / 2.0,
        (start[2] + end[2]) / 2.0,
    )


def close_to(value, target, tolerance=TOL_MM):
    return abs(value - target) <= tolerance


def unique_edges(edges):
    """Remove duplicate edges while preserving their order."""
    result = []
    seen = set()

    for edge in edges:
        edge_id = getattr(edge, "id", None)

        if edge_id is None:
            if edge not in result:
                result.append(edge)
            continue

        if edge_id not in seen:
            seen.add(edge_id)
            result.append(edge)

    return result


def is_curved_edge(edge):
    """Identify non-linear edges using the PyAnsys curve type."""
    curve_type = str(edge.curve_type).lower()

    return not any(
        token in curve_type
        for token in ("line", "linear")
    )


# =========================================================
# SHELL PROFILE
# =========================================================

def create_shell_sketch(params):
    sid = params["SID"]
    t1 = params["T1"]
    l1 = params["L1"]
    l10 = params["L10"]

    p1 = point(sid, -l1)
    p2 = point(sid + t1, -l1)
    p3 = point(sid + t1, -l10)
    p4 = point(sid, -l10)

    sketch = Sketch()
    sketch.segment(p1, p2, tag="Shell_Top")
    sketch.segment(p2, p3, tag="Shell_Right")
    sketch.segment(p3, p4, tag="Shell_Bottom")
    sketch.segment(p4, p1, tag="Shell_Left")

    return sketch


# =========================================================
# BELLOW PROFILE
# =========================================================

def create_bellow_sketch(params):
    sid = params["SID"]
    t1 = params["T1"]
    t2 = params["T2"]
    t3 = params["T3"]

    r3 = params["R3"]
    r4 = params["R4"]

    l3 = params["L3"]
    l4 = params["L4"]
    l5 = params["L5"]
    l6 = params["L6"]
    l7 = params["L7"]
    l8 = params["L8"]
    l9 = params["L9"]
    l10 = params["L10"]
    bid = params["BID"]

    y_top = -(l10 - l7 - l6 - l5)
    y_line1 = -(l10 - l7)
    y_line2 = -(l10 - l7 - l6)
    y_line6 = -(l10 - l9)

    a = point(sid, -l10)
    b = point(sid, y_line1)
    c = point(sid + l8, y_line1)
    d = point(sid + l8, y_line2)
    e = point(sid + l8, y_top)

    # These signs match the original SpaceClaim formulas.
    f = point(sid + l8 + r3, y_top + r3)
    g = point(sid + l8 + r3 + l4, y_top + r3)

    arc2_start = point(sid + t2, y_top)
    arc2_end = point(sid + l8 + r3, y_top + r4)

    line9_end = point(
        sid + l8 + r3 + l4,
        y_top + r4,
    )

    line6_start = point(sid + t1, -l10)
    line6_end = point(sid + t2, y_line6)

    h = point(bid, -l3)
    i = point(bid, 0)
    j = point(bid + t3, 0)
    k = point(bid + t3, -l3)

    arc1_center = point(sid + l8 + r3, y_top)
    arc2_center = point(sid + l8 + r3, y_top)

    arc3_center = point(
        sid + l8 + r3 + l4,
        -l3,
    )
    arc4_center = point(
        sid + l8 + r3 + l4,
        -l3,
    )

    sketch = Sketch()

    sketch.segment(a, b, tag="Bellow_Line1")
    sketch.segment(b, c, tag="Bellow_Line2")
    sketch.segment(c, d, tag="Bellow_Line3")
    sketch.segment(d, e, tag="Bellow_Line4")
    sketch.segment(a, line6_start, tag="Bellow_Line5")
    sketch.segment(line6_start, line6_end, tag="Bellow_Line6")
    sketch.segment(line6_end, arc2_start, tag="Bellow_Line7")

    sketch.arc(
        e, f, arc1_center,
        clockwise=True,
        tag="Bellow_Arc1",
    )
    sketch.arc(
        arc2_start, arc2_end, arc2_center,
        clockwise=True,
        tag="Bellow_Arc2",
    )

    sketch.segment(f, g, tag="Bellow_Line8")
    sketch.segment(arc2_end, line9_end, tag="Bellow_Line9")

    sketch.arc(
        g, h, arc3_center,
        clockwise=False,
        tag="Bellow_Arc3",
    )
    sketch.arc(
        line9_end, k, arc4_center,
        clockwise=False,
        tag="Bellow_Arc4",
    )

    sketch.segment(h, i, tag="Bellow_Line10")
    sketch.segment(k, j, tag="Bellow_Line11")
    sketch.segment(i, j, tag="Bellow_Line12")

    return sketch


# =========================================================
# NAMED SELECTION CREATION HELPER
# =========================================================

def create_edge_selection(design, name, edges):
    edges = unique_edges(edges)

    if not edges:
        raise RuntimeError(
            f'Named selection "{name}" matched no edges. '
            "Check the coordinates, units, and geometry."
        )

    design.create_named_selection(name, edges=edges)

    return {
        "name": name,
        "entity_type": "edge",
        "entity_count": len(edges),
    }


def create_face_selection(design, name, faces):
    if not faces:
        raise RuntimeError(
            f'Named selection "{name}" matched no faces.'
        )

    design.create_named_selection(name, faces=faces)

    return {
        "name": name,
        "entity_type": "face",
        "entity_count": len(faces),
    }


# =========================================================
# NAMED SELECTIONS
# =========================================================

def create_bellows_named_selections(design, params):
    """
    Create the nine named selections from the SpaceClaim
    script, using PyAnsys Geometry entities.

    Coordinates are compared in millimetres.
    """

    bodies = {body.name: body for body in design.bodies}

    if "Shell" not in bodies or "Bellow" not in bodies:
        raise RuntimeError(
            "Expected bodies named Shell and Bellow."
        )

    shell = bodies["Shell"]
    bellow = bodies["Bellow"]

    shell_edges = list(shell.edges)
    bellow_edges = list(bellow.edges)

    shell_faces = list(shell.faces)
    bellow_faces = list(bellow.faces)

    selections = []

    # -----------------------------------------------------
    # 1. Frictionless Edge
    # Original rule: both endpoints have Y = 0 on Bellow.
    # -----------------------------------------------------

    frictionless_edges = []

    for edge in bellow_edges:
        start, end = edge_endpoints_mm(edge)

        if (
            close_to(start[1], 0.0)
            and close_to(end[1], 0.0)
        ):
            frictionless_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Frictionless Edge",
            frictionless_edges,
        )
    )

    # -----------------------------------------------------
    # 2. Force & Displacement Edge
    # Original rule: |midpoint Y| = L1 on Shell.
    # -----------------------------------------------------

    l1 = params["L1"]
    force_edges = []

    for edge in shell_edges:
        _, midpoint_y, _ = edge_midpoint_mm(edge)

        if close_to(abs(midpoint_y), l1):
            force_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Force & Displacement Edge",
            force_edges,
        )
    )

    # -----------------------------------------------------
    # 3. Pressure_Load
    #
    # Original script selects circular edges by radius and
    # centre, and straight edges by midpoint coordinates.
    # In this profile the four non-linear Bellow edges are
    # the four sweep arcs. They are selected as a group.
    # -----------------------------------------------------

    pressure_edges = []

    for edge in bellow_edges:
        if is_curved_edge(edge):
            pressure_edges.append(edge)

    # Straight-edge midpoint targets from the source script.
    # Values are expressed in mm, not divided by 1000.
    l3 = params["L3"]
    r1 = params["R1"]
    l4 = params["L4"]
    l5 = params["L5"]
    l6 = params["L6"]
    l7 = params["L7"]
    l8 = params["L8"]
    l10 = params["L10"]
    sid = params["SID"]
    bid = params["BID"]
    l2 = params["L2"]

    straight_targets = [
        # TARGET_Y1, TARGET_X1
        (l3 / 2.0, bid),

        # TARGET_Y2, TARGET_X2
        (l3 + r1, bid - r1 - l4 / 2.0),

        # TARGET_Y3, TARGET_X3
        (
            l10 - l7 - (l5 + l6) / 2.0,
            sid + l8,
        ),

        # TARGET_Y4, TARGET_X4
        (l10 - l7, sid + l8 / 2.0),

        # TARGET_Y5, TARGET_X5
        (l10 - l7 / 2.0, sid),

    ]

    for edge in bellow_edges:
        if is_curved_edge(edge):
            continue

        midpoint_x, midpoint_y, _ = edge_midpoint_mm(edge)

        for target_y, target_x in straight_targets:
            if (
                close_to(abs(midpoint_y), target_y)
                and close_to(abs(midpoint_x), target_x)
            ):
                pressure_edges.append(edge)
                break

    # Shell edge target from original TARGET_Y6 / TARGET_X6.
    target_y6 = l1 - l2 / 2.0
    target_x6 = sid

    for edge in shell_edges:
        midpoint_x, midpoint_y, _ = edge_midpoint_mm(edge)

        if (
            close_to(abs(midpoint_y), target_y6)
            and close_to(abs(midpoint_x), target_x6)
        ):
            pressure_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Pressure_Load",
            pressure_edges,
        )
    )

    # -----------------------------------------------------
    # 4. Mesh_Face_Meshing
    # Original rule: first face of Shell.
    # -----------------------------------------------------

    if not shell_faces:
        raise RuntimeError("Shell has no faces.")

    selections.append(
        create_face_selection(
            design,
            "Mesh_Face_Meshing",
            [shell_faces[0]],
        )
    )

    # -----------------------------------------------------
    # 5. Mesh_Edge_Size_Shell
    # Original rule: |midpoint Y| = L1 or L10.
    # -----------------------------------------------------

    mesh_shell_edges = []

    for edge in shell_edges:
        _, midpoint_y, _ = edge_midpoint_mm(edge)

        if (
            close_to(abs(midpoint_y), l1)
            or close_to(abs(midpoint_y), l10)
        ):
            mesh_shell_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Mesh_Edge_Size_Shell",
            mesh_shell_edges,
        )
    )

    # -----------------------------------------------------
    # 6. Mesh_Edge_Size_Knuckle
    # Original rule: all circular edges on Bellow.
    # Here: all non-linear edges of the Bellow profile.
    # -----------------------------------------------------

    knuckle_edges = [
        edge for edge in bellow_edges
        if is_curved_edge(edge)
    ]

    selections.append(
        create_edge_selection(
            design,
            "Mesh_Edge_Size_Knuckle",
            knuckle_edges,
        )
    )

    # -----------------------------------------------------
    # 7. Mesh_Edge_Size_Bellow1
    # Original rule: |midpoint Y| = 0 on Bellow.
    # -----------------------------------------------------

    bellow1_edges = []

    for edge in bellow_edges:
        _, midpoint_y, _ = edge_midpoint_mm(edge)

        if close_to(abs(midpoint_y), 0.0):
            bellow1_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Mesh_Edge_Size_Bellow1",
            bellow1_edges,
        )
    )

    # -----------------------------------------------------
    # 8. Mesh_Edge_Size_Bellow2
    # Original rule: midpoint at
    # X = SID + L8/2, Y = L10 - L7.
    # -----------------------------------------------------

    target_y = l10 - l7
    target_x = sid + l8 / 2.0
    bellow2_edges = []

    for edge in bellow_edges:
        if is_curved_edge(edge):
            continue

        midpoint_x, midpoint_y, _ = edge_midpoint_mm(edge)

        if (
            close_to(abs(midpoint_y), target_y)
            and close_to(abs(midpoint_x), target_x)
        ):
            bellow2_edges.append(edge)

    selections.append(
        create_edge_selection(
            design,
            "Mesh_Edge_Size_Bellow2",
            bellow2_edges,
        )
    )

    # -----------------------------------------------------
    # 9. Mesh_Face_Sizing
    # Original rule: all faces on all bodies.
    # -----------------------------------------------------

    all_faces = []

    for body in design.bodies:
        all_faces.extend(body.faces)

    selections.append(
        create_face_selection(
            design,
            "Mesh_Face_Sizing",
            all_faces,
        )
    )

    # Verify that the design contains all nine selections.
    actual_names = {
        selection.name for selection in design.named_selections
    }

    expected_names = {
        item["name"] for item in selections
    }

    missing = expected_names - actual_names

    if missing:
        raise RuntimeError(
            "Named selections were not registered: "
            + ", ".join(sorted(missing))
        )

    return selections


# =========================================================
# MAIN GENERATION SERVICE
# =========================================================

def generate_bellows_geometry(inputs=None, output_dir=None):
    """
    Generate Shell and Bellow profiles, create named
    selections, export STEP, and return a result dictionary.
    """

    modeler = None
    export_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR

    try:
        params = calculate_geometry_parameters(inputs)

        export_dir.mkdir(parents=True, exist_ok=True)
        
        modeler = launch_modeler_with_discovery(
            version=251,
            api_version=ApiVersions.V_251,
            timeout=180,
            client_log_level=10,
            client_log_file="discovery_client.log",
        )

        design = modeler.create_design(
            "Nominal UnCorroded"
        )

        # Create the Shell and Bellow profiles.
        create_shell_sketch(params)
        design.create_surface(
            "Shell",
            create_shell_sketch(params),
        )

        design.create_surface(
            "Bellow",
            create_bellow_sketch(params),
        )

        bodies = design.bodies

        if len(bodies) < 2:
            raise RuntimeError(
                f"Expected two bodies, found {len(bodies)}."
            )

        # Create all nine named selections.
        selection_summary = create_bellows_named_selections(
            design,
            params,
        )

        # Preserve the native SpaceClaim design so its named selections can
        # be opened and inspected in SpaceClaim. STEP exports geometry only.
        spaceclaim_path = Path(design.export_to_scdocx(str(export_dir)))
        if not spaceclaim_path.is_file() or spaceclaim_path.stat().st_size == 0:
            raise RuntimeError("SpaceClaim export did not produce a valid SCDOCX file.")

        # Export into the output directory. The Geometry
        # service returns the actual exported file path.
        exported_path = design.export_to_step(
            str(export_dir)
        )
        exported_path = Path(exported_path)

        if not exported_path.exists():
            raise RuntimeError(
                f"STEP file was not found: {exported_path}"
            )

        if exported_path.stat().st_size == 0:
            raise RuntimeError("The exported STEP file is empty.")

        body_summary = []

        for body in design.bodies:
            body_summary.append({
                "name": body.name,
                "edge_count": len(body.edges),
                "face_count": len(body.faces),
            })

        return {
            "success": True,
            "message": (
                "Geometry generated, named selections created, "
                "and STEP export completed."
            ),
            "design_name": design.name,
            "body_count": len(body_summary),
            "bodies": body_summary,
            "named_selections": selection_summary,
            "named_selection_count": len(selection_summary),
            "geometry_file": str(exported_path),
            "spaceclaim_file": str(spaceclaim_path),
            "file_size_bytes": exported_path.stat().st_size,
            "parameters": params,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Geometry generation failed.",
            "error": str(exc),
        }

    finally:
        if modeler is not None:
            try:
                modeler.exit()
            except Exception:
                pass
