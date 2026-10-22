# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions

def main():
    modeler = None

    try:
        print("Launching ANSYS Discovery...")

        modeler = launch_modeler_with_discovery(
        version=251,
        api_version=ApiVersions.V_251,
        timeout=180,
        client_log_level=10,
        client_log_file="discovery_client.log",
    )

        print("Discovery connection successful!")
        print("Modeler:", modeler)

        # Add geometry generation after verifying the connection.

    except Exception as exc:
        print("Discovery connection failed:")
        print(exc)
        raise

    finally:
        if modeler is not None:
            modeler.close()


if __name__ == "__main__":
    main()
