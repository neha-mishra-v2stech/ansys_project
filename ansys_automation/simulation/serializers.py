
from rest_framework import serializers
from .models import AnalysisJob,SimulationProject


class AnalysisJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisJob
        fields = "__all__"
        read_only_fields = [
            "id",
            "status",
            "geometry_file",
            "result_data",
            "error_message",
            "created_at",
            "updated_at",
        ]

    def validate_material_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Material data must be an object.")
        if not value:
            return value
        required = {"name", "density_kg_m3", "youngs_modulus_mpa", "poissons_ratio", "shell_thickness_mm"}
        missing = required - set(value)
        if missing:
            raise serializers.ValidationError(f"Missing material properties: {', '.join(sorted(missing))}")
        try:
            density = float(value["density_kg_m3"])
            modulus = float(value["youngs_modulus_mpa"])
            poisson = float(value["poissons_ratio"])
            thickness = float(value["shell_thickness_mm"])
        except (TypeError, ValueError):
            raise serializers.ValidationError("Material values must be numeric in kg/m³, MPa, and mm.")
        if density <= 0 or modulus <= 0 or thickness <= 0 or not -1.0 < poisson < 0.5:
            raise serializers.ValidationError("Material requires positive density/modulus/thickness and -1 < Poisson ratio < 0.5.")
        return {**value, "density_kg_m3": density, "youngs_modulus_mpa": modulus, "poissons_ratio": poisson, "shell_thickness_mm": thickness}

    def validate_mesh_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Mesh settings must be an object.")
        allowed = {"global", "shell", "knuckle", "bellow1", "bellow2"}
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(f"Unknown mesh controls: {', '.join(sorted(unknown))}")
        try:
            result = {key: float(item) for key, item in value.items()}
        except (TypeError, ValueError):
            raise serializers.ValidationError("Mesh sizes must be numbers in mm.")
        if any(item <= 0 for item in result.values()):
            raise serializers.ValidationError("Mesh sizes must be greater than zero.")
        return result

    def validate_boundary_conditions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Boundary conditions must be an object.")
        allowed_conditions = {"fixed_support", "frictionless_support", "force", "pressure"}
        unknown = set(value) - allowed_conditions
        if unknown:
            raise serializers.ValidationError(f"Unknown condition types: {', '.join(sorted(unknown))}")
        supported_selections = {"Frictionless Edge", "Force & Displacement Edge", "Pressure_Load"}
        for kind, condition in value.items():
            if not isinstance(condition, dict):
                raise serializers.ValidationError(f"{kind} must be an object.")
            selection = condition.get("selection")
            if selection not in supported_selections:
                raise serializers.ValidationError(f"{kind} must reference one of: {', '.join(sorted(supported_selections))}.")
            if kind in {"force", "pressure"}:
                try:
                    if float(condition.get("magnitude_N", condition.get("magnitude_mpa"))) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    unit = "N" if kind == "force" else "MPa"
                    raise serializers.ValidationError(f"{kind} needs a positive magnitude in {unit}.")
        return value

    def validate_dimensions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Dimensions must be a JSON object."
            )

        allowed = {
            "NSID", "SLTS", "T1", "T2", "T3",
            "R1", "L3", "L4", "L5", "L6", "L7", "TPSL",
        }

        for key, item in value.items():
            if key not in allowed:
                raise serializers.ValidationError(
                    f"Unknown geometry parameter: {key}"
                )

            try:
                number = float(item)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"{key} must be numeric."
                )

            if number <= 0:
                raise serializers.ValidationError(
                    f"{key} must be greater than zero."
                )

        return value



class SimulationProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationProject
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "updated_at",
            "status",
            "error_message",
            "mesh_file",
            "vtk_file",
            "result_data",
        ]
