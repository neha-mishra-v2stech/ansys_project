# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions
from ansys.geometry.core.sketch import Sketch
from ansys.geometry.core.math import Point2D
from ansys.geometry.core.misc import UNITS


modeler = None

try:
    # Connect to your working Discovery geometry backend
    modeler = launch_modeler_with_discovery(
        version=251,
        api_version=ApiVersions.V_251,
        timeout=180,
        client_log_level=10,
        client_log_file="discovery_client.log",
    )
    print("Connected to Discovery.")

    # Define box dimensions in millimeters
    length = 100
    width = 20
    height = 10

    # Create a 2D rectangular sketch
    sketch = Sketch()
    sketch.box(
        center=Point2D([0, 0], unit=UNITS.mm),
        width=length * UNITS.mm,
        height=width * UNITS.mm,
    )

    # Create a new 3D design
    design = modeler.create_design("StaticStructuralDemo")

    # Extrude the rectangle to create a solid
    body = design.extrude_sketch(
        name="TestBlock",
        sketch=sketch,
        distance=height * UNITS.mm,
    )

    print("3D geometry created successfully!")
    print("Body name:", body.name)
    print("Number of faces:", len(body.faces))
    print("Number of edges:", len(body.edges))

    # Save the native Discovery design
    output_file = design.export_to_scdocx()
    print("Saved geometry:", output_file)

    # Display the geometry
    # design.plot()

except Exception as exc:
    print("Geometry generation failed:")
    print(repr(exc))
    raise

finally:
    if modeler is not None:
        modeler.close()
