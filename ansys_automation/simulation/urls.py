
from django.urls import path
from .views import (
    JobSolverPreflightView,
    home,
    AnalysisJobListCreateView,
    AnalysisJobDetailView,
    JobActionView,
    JobGeometryValidationView,
    JobMeshMetadataView,
    JobMeshDisplayView,
    JobFileView,
)

urlpatterns = [
    path("", home, name="home"),
    path("api/jobs/", AnalysisJobListCreateView.as_view(), name="job-list-create"),
    path("api/jobs/<int:pk>/", AnalysisJobDetailView.as_view(), name="job-detail"),
    path("api/jobs/<int:pk>/geometry-validation/", JobGeometryValidationView.as_view(), name="job-geometry-validation"),
    path("api/jobs/<int:pk>/mesh-metadata/", JobMeshMetadataView.as_view(), name="job-mesh-metadata"),
    path("api/jobs/<int:pk>/mesh-display/", JobMeshDisplayView.as_view(), name="job-mesh-display"),
    path("api/jobs/<int:pk>/files/<str:kind>/", JobFileView.as_view(), name="job-file"),
    
    path(
        "api/jobs/<int:pk>/solver-preflight/",
        JobSolverPreflightView.as_view(),
        name="job-solver-preflight",
    ),
    path("api/jobs/<int:pk>/<str:action>/", JobActionView.as_view(), name="job-action"),
    
]

