
# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions
modeler = None

try:
    modeler = launch_modeler_with_discovery(
        version=251,
        api_version=ApiVersions.V_251,
        timeout=180,
        client_log_level=10,
        client_log_file="discovery_client.log",
    )
    print("Geometry backend launched successfully!")
    print(modeler)

except Exception as exc:
    print("Geometry backend launch failed:")
    print(repr(exc))

finally:
    if modeler is not None:
        modeler.close()
