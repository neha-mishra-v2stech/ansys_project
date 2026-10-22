
# from ansys.geometry.core import launch_modeler_with_spaceclaim
from ansys.geometry.core import launch_modeler_with_discovery
from ansys.geometry.core.connection.backend import ApiVersions
from ansys.geometry.core.sketch import Sketch


def inspect_object(label, obj, keywords):
    print(f"\n--- {label} ---")
    for name in dir(obj):
        if any(word in name.lower() for word in keywords):
            try:
                attribute = getattr(obj, name)
                if callable(attribute):
                    print(f"{name}{_get_signature(attribute)}")
                else:
                    print(f"{name}: {type(attribute).__name__}")
            except Exception:
                print(name)


def _get_signature(func):
    import inspect
    try:
        return str(inspect.signature(func))
    except (TypeError, ValueError):
        return "(signature unavailable)"


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
        design = modeler.create_design("GeometryAPIDetails")

        print("Design:", design.name)
        print("Sketch class:", Sketch)

        inspect_object(
            "Sketch class",
            Sketch,
            ["line", "arc", "circle", "rectangle", "segment",
             "close", "face", "plane", "point"]
        )

        inspect_object(
            "Design",
            design,
            ["sketch", "extrude", "revolve", "body",
             "surface", "step", "share", "named"]
        )

        # Check whether the design exposes a sketch factory or plane.
        inspect_object(
            "Modeler",
            modeler,
            ["plane", "sketch", "design", "unit"]
        )

    finally:
        if modeler is not None:
            try:
                modeler.exit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
