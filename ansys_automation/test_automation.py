
from ansys.mechanical.core import launch_mechanical

mechanical = None

try:
    mechanical = launch_mechanical(
        transport_mode="insecure"
    )

    print("Mechanical launched successfully!")
    print(mechanical)

    result = mechanical.run_python_script("2 + 3")
    print("Test result:", result)

except Exception as exc:
    print("Mechanical launch failed:")
    print(exc)

finally:
    if mechanical is not None:
        mechanical.exit()
