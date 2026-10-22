from django.db import models

# Create your models here.

from django.db import models


class AnalysisJob(models.Model):
    STATUS_CHOICES = [
    ("PENDING", "Pending"),
    ("GEOMETRY_RUNNING", "Geometry Running"),
    ("GEOMETRY_COMPLETED", "Geometry Completed"),
    ("MESHING", "Meshing"),
    ("MESH_COMPLETED", "Meshing Completed"),
    ("SOLVING", "Solving"),
    ("COMPLETED", "Completed"),
    ("FAILED", "Failed"),
    ]

    project_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Geometry parameters from the SpaceClaim reference script
    dimensions = models.JSONField(default=dict)

    # Initial load input
    force = models.FloatField(default=1000.0)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    geometry_file = models.CharField(max_length=500, blank=True)
    mesh_file = models.CharField(max_length=500, blank=True)
    vtk_file = models.CharField(max_length=500, blank=True)
    material_data = models.JSONField(default=dict, blank=True)
    mesh_settings = models.JSONField(default=dict, blank=True)
    boundary_conditions = models.JSONField(default=dict, blank=True)
    solver_data = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_name} - {self.status}"



from django.db import models


class SimulationProject(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("geometry_ready", "Geometry Ready"),
        ("mesh_ready", "Mesh Ready"),
        ("configured", "Configured"),
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    analysis_type = models.CharField(
        max_length=50,
        default="Static Structural",
    )
    unit_system = models.CharField(
        max_length=30,
        default="mm-N-MPa",
    )

    geometry_file = models.CharField(max_length=500, blank=True)
    mesh_file = models.CharField(max_length=500, blank=True)
    vtk_file = models.CharField(max_length=500, blank=True)

    material_data = models.JSONField(default=dict, blank=True)
    mesh_settings = models.JSONField(default=dict, blank=True)
    boundary_conditions = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
    )
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
