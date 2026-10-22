
import inspect

from ansys.geometry.core.sketch import Sketch
from ansys.geometry.core.math import Point2D

# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions

def show_signature(label, obj):
    try:
        print(f"{label}: {inspect.signature(obj)}")
    except (TypeError, ValueError):
        print(f"{label}: signature unavailable")


def main():
    modeler = None
    try:
        modeler = launch_modeler_with_discovery(
            version=251,
            api_version=ApiVersions.V_251,
            timeout=180,
            client_log_level=10,
            client_log_file="discovery_client.log",
        )
        design = modeler.create_design("ConstructorCheck")

        show_signature("Sketch", Sketch)
        show_signature("Point2D", Point2D)
        show_signature("Sketch.segment", Sketch.segment)
        show_signature("Sketch.arc", Sketch.arc)
        show_signature("Design.create_surface", design.create_surface)
        show_signature("Design.create_named_selection",
                       design.create_named_selection)

        print("\nSketch module:", inspect.getfile(Sketch))
        print("Point2D module:", inspect.getfile(Point2D))

    finally:
        if modeler is not None:
            try:
                modeler.exit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
