
from ansys.mechanical.core import launch_mechanical

mechanical = None

try:
    # Launch ANSYS Mechanical locally
    mechanical = launch_mechanical(
        transport_mode="insecure"
    )

    print("Connected to:", mechanical)

    script = r'''
import traceback

try:
    # Start with a clean Mechanical model
    Model.ClearGeneratedData()

    # Create a 100 x 20 x 10 mm rectangular solid
    # through the Mechanical scripting API.
    # Geometry creation itself is performed using a
    # supported CAD geometry workflow.

    print("Mechanical session is ready.")
    print("Next: import generated geometry and create Static Structural.")

except Exception as e:
    print(traceback.format_exc())
'''

    result = mechanical.run_python_script(script)
    print(result)

finally:
    if mechanical is not None:
        mechanical.exit()
