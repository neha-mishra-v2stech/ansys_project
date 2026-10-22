
"""
Gmsh named-selection service for the bellows STEP geometry.

Creates physical groups for Shell, Bellow, and the nine original
SpaceClaim named selections.

The current inspected STEP contains 2 surfaces and 19 curves.
All geometry coordinates are in millimetres.
"""

from __future__ import annotations

import math
import os
from typing import Any

import gmsh


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_STEP_FILE = os.path.join(
    BASE_DIR,
    "generated_geometry",
    "Nominal UnCorroded.stp",
)

TOL_MM = 0.01
GEOMETRY_TOL_MM = 0.05

DEFAULT_INPUTS = {
    "NSID": 242.82,
    "SLTS": 2234.0,
    "T1": 15.09,
    "T2": 24.56,
    "T3": 14.0,
    "R1": 45.0,
    "L3": 65.0,
    "L4": 20.0,
    "L5": 20.0,
    "L6": 25.0,
    "L7": 75.0,
}


# ---------------------------------------------------------------------
# Geometry parameters
# ---------------------------------------------------------------------

def get_geometry_parameters(
    params: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Calculate the derived parameters used by the selection rules."""

    values = dict(DEFAULT_INPUTS)

    if params:
        values.update(params)

    nsid = float(values["NSID"])
    slts = float(values["SLTS"])
    t1 = float(values["T1"])
    t2 = float(values["T2"])
    t3 = float(values["T3"])
    r1 = float(values["R1"])
    l3 = float(values["L3"])
    l4 = float(values["L4"])
    l5 = float(values["L5"])
    l6 = float(values["L6"])
    l7 = float(values["L7"])

    sid = nsid / 2.0
    r4 = r1
    r3 = t3 + r4
    l8 = t2 - t3
    bid = sid + r1 + r3 + l4 + l8
    l1 = slts / 2.0
    l9 = (t2 - t1) * 3.0
    l10 = t3 + r1 + r4 + l3 + l5 + l6 + l7
    l2 = l1 - l10

    values.update({
        "SID": sid,
        "R4": r4,
        "R3": r3,
        "L8": l8,
        "BID": bid,
        "L1": l1,
        "L9": l9,
        "L10": l10,
        "L2": l2,
    })

    return {
        key: float(value)
        for key, value in values.items()
    }


# ---------------------------------------------------------------------
# Gmsh geometry helpers
# ---------------------------------------------------------------------

def validate_step_file(step_file: str) -> str:
    """Validate and resolve the STEP file path."""

    path = os.path.abspath(step_file)

    if not os.path.isfile(path):
        raise FileNotFoundError(f"STEP file not found: {path}")

    if os.path.getsize(path) == 0:
        raise ValueError(f"STEP file is empty: {path}")

    return path


def _close(
    first: float,
    second: float,
    tolerance: float = TOL_MM,
) -> bool:
    return abs(float(first) - float(second)) <= tolerance


def _entity_tags(dimension: int) -> list[int]:
    return sorted(
        tag
        for dim, tag in gmsh.model.getEntities(dimension)
        if dim == dimension
    )


def _bbox(dimension: int, tag: int) -> tuple[float, ...]:
    return tuple(
        float(value)
        for value in gmsh.model.getBoundingBox(dimension, tag)
    )


def _mass(dimension: int, tag: int) -> float:
    return float(gmsh.model.occ.getMass(dimension, tag))


def _center_of_mass(
    dimension: int,
    tag: int,
) -> tuple[float, float, float]:
    values = gmsh.model.occ.getCenterOfMass(dimension, tag)
    return tuple(float(value) for value in values)


def _boundary_tags(
    dimension: int,
    tag: int,
    boundary_dimension: int,
) -> list[int]:
    boundary = gmsh.model.getBoundary(
        [(dimension, tag)],
        combined=False,
        oriented=False,
        recursive=False,
    )

    return sorted({
        int(entity_tag)
        for entity_dimension, entity_tag in boundary
        if entity_dimension == boundary_dimension
    })


def _point_coordinates(
    point_tag: int,
) -> tuple[float, float, float]:
    values = gmsh.model.getValue(0, point_tag, [])
    return tuple(float(value) for value in values)


def _curve_endpoints(
    curve_tag: int,
) -> list[tuple[float, float, float]]:
    point_tags = _boundary_tags(1, curve_tag, 0)

    return [
        _point_coordinates(tag)
        for tag in point_tags
    ]


def _curve_midpoint(
    curve_tag: int,
) -> tuple[float, float, float]:
    lower, upper = gmsh.model.getParametrizationBounds(
        1,
        curve_tag,
    )

    parameter = (
        float(lower[0]) + float(upper[0])
    ) / 2.0

    values = gmsh.model.getValue(1, curve_tag, [parameter])

    return tuple(float(value) for value in values)


def _curve_type(curve_tag: int) -> str:
    return str(gmsh.model.getType(1, curve_tag))


def _is_circle(curve_tag: int) -> bool:
    return "circle" in _curve_type(curve_tag).lower()


def _curve_matches_midpoint(
    curve_tag: int,
    target_x: float,
    target_y: float,
    tolerance: float = TOL_MM,
) -> bool:
    x, y, _ = _curve_midpoint(curve_tag)

    return (
        _close(abs(x), target_x, tolerance)
        and _close(abs(y), target_y, tolerance)
    )


def _curve_matches_radius_and_center(
    curve_tag: int,
    center_x: float,
    center_y: float,
    radius: float,
    tolerance: float = GEOMETRY_TOL_MM,
) -> bool:
    """
    Match a circular curve by checking its endpoints against the
    expected circle center and radius.
    """

    if not _is_circle(curve_tag):
        return False

    endpoints = _curve_endpoints(curve_tag)

    if len(endpoints) < 2:
        return False

    for x, y, _ in endpoints:
        distance = math.hypot(
            x - center_x,
            y - center_y,
        )

        if not _close(distance, radius, tolerance):
            return False

    return True


def _add_physical_group(
    dimension: int,
    entity_tags: list[int],
    name: str,
    physical_tag: int,
) -> dict[str, Any]:
    """Create a named Gmsh physical group."""

    tags = sorted(set(int(tag) for tag in entity_tags))

    if not tags:
        return {
            "name": name,
            "dimension": dimension,
            "physical_tag": None,
            "entity_tags": [],
            "entity_count": 0,
            "created": False,
            "warning": "No matching entities were found.",
        }

    actual_tag = gmsh.model.addPhysicalGroup(
        dimension,
        tags,
        physical_tag,
    )

    gmsh.model.setPhysicalName(
        dimension,
        actual_tag,
        name,
    )

    return {
        "name": name,
        "dimension": dimension,
        "physical_tag": actual_tag,
        "entity_tags": tags,
        "entity_count": len(tags),
        "created": True,
    }


# ---------------------------------------------------------------------
# Surface identification and curve classification
# ---------------------------------------------------------------------

def identify_shell_and_bellow_surfaces() -> dict[str, Any]:
    """
    Identify the larger surface as Shell and the next-largest as Bellow.

    This rule matches the current STEP geometry. Review it if the
    geometry changes or additional surfaces are introduced.
    """

    surface_tags = _entity_tags(2)

    if len(surface_tags) < 2:
        raise ValueError(
            f"Expected at least 2 surfaces; found {len(surface_tags)}."
        )

    areas = {
        tag: _mass(2, tag)
        for tag in surface_tags
    }

    ordered = sorted(
        surface_tags,
        key=lambda tag: areas[tag],
        reverse=True,
    )

    return {
        "shell_surface": ordered[0],
        "bellow_surface": ordered[1],
        "surface_areas": areas,
        "surface_count": len(surface_tags),
    }


def classify_shell_and_bellow_curves(
    shell_surface: int,
    bellow_surface: int,
) -> tuple[list[int], list[int]]:
    """Find the curves bounding each identified surface."""

    shell_curves = _boundary_tags(
        2,
        shell_surface,
        1,
    )

    bellow_curves = _boundary_tags(
        2,
        bellow_surface,
        1,
    )

    return shell_curves, bellow_curves


# ---------------------------------------------------------------------
# Named-selection rules
# ---------------------------------------------------------------------

def _build_selection_entities(
    params: dict[str, float],
    shell_surface: int,
    bellow_surface: int,
    shell_curves: list[int],
    bellow_curves: list[int],
) -> dict[str, list[int]]:
    """Build the nine original named selections."""

    sid = params["SID"]
    t1 = params["T1"]
    t2 = params["T2"]
    t3 = params["T3"]
    r1 = params["R1"]
    r3 = params["R3"]
    l3 = params["L3"]
    l4 = params["L4"]
    l5 = params["L5"]
    l6 = params["L6"]
    l7 = params["L7"]
    l8 = params["L8"]
    bid = params["BID"]
    l1 = params["L1"]
    l2 = params["L2"]
    l10 = params["L10"]

    # 1. Frictionless Edge:
    # Bellow curves with both endpoints at Y = 0.
    frictionless_edges = []

    for tag in bellow_curves:
        endpoints = _curve_endpoints(tag)

        if len(endpoints) >= 2 and all(
            abs(y) <= TOL_MM
            for _, y, _ in endpoints
        ):
            frictionless_edges.append(tag)

    # 2. Force & Displacement Edge:
    # Shell curve with abs(midpoint Y) = L1.
    force_displacement_edges = [
        tag
        for tag in shell_curves
        if _close(abs(_curve_midpoint(tag)[1]), l1)
    ]

    # 3. Pressure_Load:
    # Circle/radius conditions and midpoint-coordinate conditions.
    pressure_edges: set[int] = set()

    center1_x = sid + l8 + r3
    center1_y = -(l10 - l7 - l6 - l5)

    center2_x = sid + l8 + r3 + l4
    center2_y = -l3

    for tag in bellow_curves:
        if _curve_matches_radius_and_center(
            tag, center1_x, center1_y, r3
        ):
            pressure_edges.add(tag)

        if _curve_matches_radius_and_center(
            tag, center1_x, center1_y, r1
        ):
            pressure_edges.add(tag)

        if _curve_matches_radius_and_center(
            tag, center2_x, center2_y, r3
        ):
            pressure_edges.add(tag)

        if _curve_matches_radius_and_center(
            tag, center2_x, center2_y, r1
        ):
            pressure_edges.add(tag)

    pressure_midpoint_targets = [
        (bid, l3 / 2.0),
        (bid - r1 - l4 / 2.0, l3 + r1),
        (sid + l8, l10 - l7 - (l5 + l6) / 2.0),
        (sid + l8 / 2.0, l10 - l7),
        (sid, l10 - l7 / 2.0),
    ]

    for tag in bellow_curves:
        for target_x, target_y in pressure_midpoint_targets:
            if _curve_matches_midpoint(tag, target_x, target_y):
                pressure_edges.add(tag)

    shell_pressure_target_x = sid
    shell_pressure_target_y = l1 - l2 / 2.0

    for tag in shell_curves:
        if _curve_matches_midpoint(
            tag,
            shell_pressure_target_x,
            shell_pressure_target_y,
        ):
            pressure_edges.add(tag)

    # 4. Mesh_Face_Meshing: Shell surface.
    mesh_face_meshing = [shell_surface]

    # 5. Mesh_Edge_Size_Shell:
    # Shell curves with abs(midpoint Y) = L1 or L10.
    mesh_edge_size_shell = []

    for tag in shell_curves:
        y = _curve_midpoint(tag)[1]

        if (
            _close(abs(y), l1)
            or _close(abs(y), l10)
        ):
            mesh_edge_size_shell.append(tag)

    # 6. Mesh_Edge_Size_Knuckle:
    # Circular Bellow curves.
    mesh_edge_size_knuckle = [
        tag
        for tag in bellow_curves
        if _is_circle(tag)
    ]

    # 7. Mesh_Edge_Size_Bellow1:
    # Bellow curves with abs(midpoint Y) = 0.
    mesh_edge_size_bellow1 = [
        tag
        for tag in bellow_curves
        if _close(abs(_curve_midpoint(tag)[1]), 0.0)
    ]

    # 8. Mesh_Edge_Size_Bellow2:
    # Midpoint X = SID + L8/2 and abs(Y) = L10 - L7.
    mesh_edge_size_bellow2 = [
        tag
        for tag in bellow_curves
        if _curve_matches_midpoint(
            tag,
            sid + l8 / 2.0,
            l10 - l7,
        )
    ]

    # 9. Mesh_Face_Sizing: all surfaces.
    mesh_face_sizing = _entity_tags(2)

    return {
        "Frictionless Edge": sorted(set(frictionless_edges)),
        "Force & Displacement Edge": sorted(
            set(force_displacement_edges)
        ),
        "Pressure_Load": sorted(pressure_edges),
        "Mesh_Face_Meshing": sorted(set(mesh_face_meshing)),
        "Mesh_Edge_Size_Shell": sorted(
            set(mesh_edge_size_shell)
        ),
        "Mesh_Edge_Size_Knuckle": sorted(
            set(mesh_edge_size_knuckle)
        ),
        "Mesh_Edge_Size_Bellow1": sorted(
            set(mesh_edge_size_bellow1)
        ),
        "Mesh_Edge_Size_Bellow2": sorted(
            set(mesh_edge_size_bellow2)
        ),
        "Mesh_Face_Sizing": sorted(set(mesh_face_sizing)),
    }


# ---------------------------------------------------------------------
# Public function: create named-selection physical groups
# ---------------------------------------------------------------------

def create_named_selection_groups(
    step_file: str = DEFAULT_STEP_FILE,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Import STEP geometry and create physical groups for the geometry
    and all nine named selections.
    """

    resolved_path = validate_step_file(step_file)
    geometry_params = get_geometry_parameters(params)

    gmsh.initialize(interruptible=False)

    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.model.add("bellows_named_selections")

        imported = gmsh.model.occ.importShapes(resolved_path)
        gmsh.model.occ.synchronize()

        if not imported:
            raise RuntimeError(
                "Gmsh could not import any entities from the STEP file."
            )

        surfaces = _entity_tags(2)
        curves = _entity_tags(1)

        surface_info = identify_shell_and_bellow_surfaces()

        shell_surface = surface_info["shell_surface"]
        bellow_surface = surface_info["bellow_surface"]

        shell_curves, bellow_curves = (
            classify_shell_and_bellow_curves(
                shell_surface,
                bellow_surface,
            )
        )

        groups = [
            _add_physical_group(
                2, [shell_surface], "Shell", 1
            ),
            _add_physical_group(
                2, [bellow_surface], "Bellow", 2
            ),
            _add_physical_group(
                1, shell_curves, "Shell_Boundary", 3
            ),
            _add_physical_group(
                1, bellow_curves, "Bellow_Profile_Edges", 4
            ),
        ]

        selections = _build_selection_entities(
            params=geometry_params,
            shell_surface=shell_surface,
            bellow_surface=bellow_surface,
            shell_curves=shell_curves,
            bellow_curves=bellow_curves,
        )

        face_selection_names = {
            "Mesh_Face_Meshing",
            "Mesh_Face_Sizing",
        }

        selection_groups = []

        for index, (name, entity_tags) in enumerate(
            selections.items(),
            start=5,
        ):
            dimension = 2 if name in face_selection_names else 1

            group = _add_physical_group(
                dimension,
                entity_tags,
                name,
                index,
            )

            groups.append(group)
            selection_groups.append(group)

        # Expected counts for the currently inspected geometry.
        expected_counts = {
            "Shell": 1,
            "Bellow": 1,
            "Shell_Boundary": 4,
            "Bellow_Profile_Edges": 15,
            "Frictionless Edge": 1,
            "Force & Displacement Edge": 1,
            "Pressure_Load": 10,
            "Mesh_Face_Meshing": 1,
            "Mesh_Edge_Size_Shell": 2,
            "Mesh_Edge_Size_Knuckle": 4,
            "Mesh_Edge_Size_Bellow1": 1,
            "Mesh_Edge_Size_Bellow2": 1,
            "Mesh_Face_Sizing": 2,
        }

        validation = []

        for group in groups:
            name = group["name"]
            expected = expected_counts.get(name)
            actual = group["entity_count"]

            validation.append({
                "name": name,
                "expected_count": expected,
                "actual_count": actual,
                "matches_expected": (
                    None
                    if expected is None
                    else actual == expected
                ),
            })

        validation_by_name = {
            item["name"]: item
            for item in validation
        }

        # IMPORTANT: each status is a plain string, not a tuple.
        named_selection_status = []

        for group in selection_groups:
            name = group["name"]
            check = validation_by_name[name]

            if not group["created"]:
                status = "no_matching_entities"
            elif check["matches_expected"] is True:
                status = "created_count_matches_expected"
            else:
                status = "created_but_count_needs_verification"

            named_selection_status.append({
                "name": name,
                "status": status,
            })

        return {
            "success": (
                len(surfaces) == 2
                and len(curves) == 19
                and len(shell_curves) == 4
                and len(bellow_curves) == 15
            ),
            "step_file": resolved_path,
            "surface_count": len(surfaces),
            "curve_count": len(curves),
            "shell_surface": shell_surface,
            "bellow_surface": bellow_surface,
            "shell_surface_area": surface_info[
                "surface_areas"
            ][shell_surface],
            "bellow_surface_area": surface_info[
                "surface_areas"
            ][bellow_surface],
            "shell_bbox": _bbox(2, shell_surface),
            "bellow_bbox": _bbox(2, bellow_surface),
            "shell_curve_tags": shell_curves,
            "bellow_curve_tags": bellow_curves,
            "geometry_parameters": geometry_params,
            "groups": groups,
            "validation": validation,
            "named_selection_status": named_selection_status,
            "message": (
                "Physical groups created. Expected counts are based on "
                "the currently inspected STEP geometry. Verify entity "
                "locations before applying loads or mesh controls."
            ),
        }

    finally:
        gmsh.finalize()


# ---------------------------------------------------------------------
# Public function: inspect STEP geometry
# ---------------------------------------------------------------------

def inspect_step_geometry(
    step_file: str = DEFAULT_STEP_FILE,
) -> dict[str, Any]:
    """Inspect surface and curve details for debugging."""

    resolved_path = validate_step_file(step_file)

    gmsh.initialize(interruptible=False)

    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.model.add("bellows_geometry_inspection")

        gmsh.model.occ.importShapes(resolved_path)
        gmsh.model.occ.synchronize()

        surface_info = []

        for tag in _entity_tags(2):
            surface_info.append({
                "surface_tag": tag,
                "area": _mass(2, tag),
                "bbox": _bbox(2, tag),
                "center_of_mass": _center_of_mass(2, tag),
                "boundary_curves": _boundary_tags(2, tag, 1),
            })

        curve_info = []

        for tag in _entity_tags(1):
            try:
                midpoint = _curve_midpoint(tag)
            except Exception:
                midpoint = None

            curve_info.append({
                "curve_tag": tag,
                "type": _curve_type(tag),
                "length": _mass(1, tag),
                "bbox": _bbox(1, tag),
                "midpoint": midpoint,
                "endpoints": _curve_endpoints(tag),
            })

        return {
            "step_file": resolved_path,
            "surface_count": len(surface_info),
            "curve_count": len(curve_info),
            "surfaces": surface_info,
            "curves": curve_info,
        }

    finally:
        gmsh.finalize()


if __name__ == "__main__":
    from pprint import pprint

    pprint(create_named_selection_groups(DEFAULT_STEP_FILE))
