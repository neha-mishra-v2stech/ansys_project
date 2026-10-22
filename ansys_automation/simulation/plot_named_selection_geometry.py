
from pathlib import Path

import gmsh
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


BASE_DIR = Path(__file__).resolve().parent.parent
STEP_FILE = BASE_DIR / "generated_geometry" / "Nominal UnCorroded.stp"
OUTPUT_FILE = (
    BASE_DIR / "generated_geometry" / "named_selection_verification.png"
)

SELECTIONS = {
    "Pressure_Load": [3, 6, 9, 10, 11, 12, 13, 14, 15, 19],
    "Frictionless Edge": [8],
    "Force & Displacement Edge": [4],
    "Mesh_Edge_Size_Shell": [2, 4],
    "Mesh_Edge_Size_Knuckle": [6, 10, 12, 19],
    "Mesh_Edge_Size_Bellow1": [8],
    "Mesh_Edge_Size_Bellow2": [14],
}

COLORS = {
    "Pressure_Load": "red",
    "Frictionless Edge": "green",
    "Force & Displacement Edge": "purple",
    "Mesh_Edge_Size_Shell": "royalblue",
    "Mesh_Edge_Size_Knuckle": "darkorange",
    "Mesh_Edge_Size_Bellow1": "deeppink",
    "Mesh_Edge_Size_Bellow2": "teal",
}

INDIVIDUAL_SELECTIONS = [
    "Pressure_Load",
    "Frictionless Edge",
    "Force & Displacement Edge",
]


def sample_curve(curve_tag, samples=120):
    """Sample the actual curve geometry from Gmsh."""
    lower, upper = gmsh.model.getParametrizationBounds(1, curve_tag)

    start = float(lower[0])
    end = float(upper[0])

    parameters = [
        start + (end - start) * i / (samples - 1)
        for i in range(samples)
    ]

    values = gmsh.model.getValue(1, curve_tag, parameters)

    return [
        (values[i], values[i + 1], values[i + 2])
        for i in range(0, len(values), 3)
    ]


def draw_geometry(ax, curve_points, selected_tags=None, color="lightgray"):
    """Draw all curves, highlighting selected tags if supplied."""
    selected_tags = set(selected_tags or [])

    for tag, points in curve_points.items():
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]

        highlighted = tag in selected_tags

        ax.plot(
            xs,
            ys,
            color=color if highlighted else "lightgray",
            linewidth=2.8 if highlighted else 1.0,
            zorder=3 if highlighted else 1,
        )

        midpoint = points[len(points) // 2]
        ax.annotate(
            str(tag),
            (midpoint[0], midpoint[1]),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=7,
            color="dimgray",
        )

    ax.set_xlabel("X")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")


def main():
    if not STEP_FILE.exists():
        raise FileNotFoundError(f"STEP file not found: {STEP_FILE}")

    gmsh.initialize()

    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("bellows_selection_inspection")
        gmsh.model.occ.importShapes(str(STEP_FILE))
        gmsh.model.occ.synchronize()

        curve_tags = sorted(
            tag for dim, tag in gmsh.model.getEntities(1)
        )

        curve_points = {
            tag: sample_curve(tag)
            for tag in curve_tags
        }

        fig, axes = plt.subplots(
            1,
            4,
            figsize=(22, 11),
            sharex=True,
            sharey=True,
        )

        # Panels 1–3: individual selections.
        for ax, selection_name in zip(
            axes[:3], INDIVIDUAL_SELECTIONS
        ):
            selected = SELECTIONS[selection_name]

            draw_geometry(
                ax,
                curve_points,
                selected_tags=selected,
                color=COLORS[selection_name],
            )

            ax.set_title(
                f"{selection_name}\nTags: {selected}"
            )

        # Panel 4: all edge-based selections together.
        combined_ax = axes[3]

        # Draw the base geometry first.
        draw_geometry(combined_ax, curve_points)
        combined_ax.set_title("Combined Named Selections")

        # Overlay each selection in its own color.
        for selection_name, tags in SELECTIONS.items():
            for tag in tags:
                if tag not in curve_points:
                    print(
                        f"WARNING: {selection_name}: "
                        f"curve tag {tag} was not found"
                    )
                    continue

                points = curve_points[tag]
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]

                combined_ax.plot(
                    xs,
                    ys,
                    color=COLORS[selection_name],
                    linewidth=3.0,
                    zorder=4,
                )

        legend_handles = [
            Line2D(
                [0],
                [0],
                color=COLORS[name],
                linewidth=3,
                label=f"{name}: {tags}",
            )
            for name, tags in SELECTIONS.items()
        ]

        combined_ax.legend(
            handles=legend_handles,
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            fontsize=8,
            borderaxespad=0,
        )

        axes[0].set_ylabel("Y")

        fig.suptitle(
            "Bellows Geometry — Named Selection Verification",
            fontsize=15,
        )

        fig.tight_layout(rect=(0, 0, 0.88, 0.95))
        fig.savefig(OUTPUT_FILE, dpi=180, bbox_inches="tight")

        print(f"STEP file: {STEP_FILE}")
        print(f"Curves plotted: {len(curve_points)}")
        print(f"Image saved: {OUTPUT_FILE}")

        plt.show()

    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()
