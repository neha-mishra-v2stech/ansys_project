from django.test import TestCase

from .serializers import AnalysisJobSerializer
from .solver_service import solver_capability


class WorkflowValidationTests(TestCase):
    def test_material_mesh_and_boundary_configuration_is_valid(self):
        serializer = AnalysisJobSerializer(data={
            "project_name": "Validation job",
            "dimensions": {"NSID": 242.82},
            "force": 1000,
            "material_data": {
                "name": "Structural Steel", "density_kg_m3": 7850,
                "youngs_modulus_mpa": 200000, "poissons_ratio": 0.3,
                "shell_thickness_mm": 3,
            },
            "mesh_settings": {"global": 20, "shell": 20, "knuckle": 8, "bellow1": 10, "bellow2": 10},
            "boundary_conditions": {
                "frictionless_support": {"selection": "Frictionless Edge"},
                "force": {"selection": "Force & Displacement Edge", "magnitude_N": 1000},
            },
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_solver_capability_never_claims_a_result(self):
        job = AnalysisJobSerializer(data={"project_name": "Empty", "dimensions": {}})
        self.assertTrue(job.is_valid(), job.errors)
        stored_job = job.save()
        capability = solver_capability(stored_job)
        self.assertEqual(capability["result_state"], "not_calculated")
