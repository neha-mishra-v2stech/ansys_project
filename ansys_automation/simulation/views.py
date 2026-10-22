from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .geometry_service import generate_geometry
from .mesh_inspection_service import inspect_step_geometry
from .meshing_service import generate_mesh
from .mesh_preview_service import create_mesh_preview
from .mesh_marker_service import browser_mesh, named_selection_markers
from .mapdl_service import solve_shell_job
from .mechanical_service import solve_static_structural
from .workbench_service import create_static_structural_workbench_project
from .models import AnalysisJob
from .serializers import AnalysisJobSerializer
from .solver_service import solver_capability
import traceback


def home(request):
    return render(request, "simulation/index.html")


class AnalysisJobListCreateView(generics.ListCreateAPIView):
    queryset = AnalysisJob.objects.all().order_by("-created_at")
    serializer_class = AnalysisJobSerializer


class AnalysisJobDetailView(APIView):
    def get(self, request, pk):
        return Response(AnalysisJobSerializer(get_object_or_404(AnalysisJob, pk=pk)).data)

    def patch(self, request, pk):
        job = get_object_or_404(AnalysisJob, pk=pk)
        serializer = AnalysisJobSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class JobGeometryValidationView(APIView):
    def get(self, request, pk):
        job = get_object_or_404(AnalysisJob, pk=pk)
        if not job.geometry_file:
            return Response({"error": "No STEP geometry is assigned."}, status=status.HTTP_409_CONFLICT)
        result = inspect_step_geometry(job.geometry_file)
        return Response(result, status=status.HTTP_200_OK if result.get("success") else status.HTTP_422_UNPROCESSABLE_ENTITY)


class JobMeshMetadataView(APIView):
    """Provide derived marker locations for named mesh selections."""

    def get(self, request, pk):
        job = get_object_or_404(AnalysisJob, pk=pk)
        if not job.mesh_file or not Path(job.mesh_file).is_file():
            return Response(
                {"error": "Generate the mesh before requesting mesh metadata."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"named_selection_markers": named_selection_markers(job.mesh_file)})


class JobMeshDisplayView(APIView):
    """Return the real exported VTK shell mesh in a browser-renderable form."""

    def get(self, request, pk):
        job = get_object_or_404(AnalysisJob, pk=pk)
        if not job.vtk_file or not Path(job.vtk_file).is_file():
            return Response(
                {"error": "Generate the VTK mesh before requesting viewport data."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(browser_mesh(job.vtk_file))


class JobFileView(APIView):
    fields = {"geometry": "geometry_file", "mesh": "mesh_file", "vtk": "vtk_file"}

    def get(self, request, pk, kind):
        job = get_object_or_404(AnalysisJob, pk=pk)
        field = self.fields.get(kind)
        path = Path(getattr(job, field, "")) if field else None
        inline = False
        if kind == "preview":
            path = Path((job.result_data or {}).get("mesh", {}).get("preview_image", ""))
        if kind == "mechanical":
            path = Path(
                (job.result_data or {})
                .get("mechanical_project", {})
                .get("mechanical_project_file", "")
            )
        if kind == "spaceclaim":
            path = Path(
                (job.result_data or {})
                .get("geometry", {})
                .get("spaceclaim_file", "")
            )
        if kind == "workbench":
            path = Path((job.result_data or {}).get("workbench_project", {}).get("workbench_project_file", ""))
        if kind == "named-selection-verification":
            path = Path(settings.BASE_DIR) / "generated_geometry" / "named_selection_verification.png"
            inline = True
        root = (Path(settings.BASE_DIR) / "generated_geometry").resolve()
        if not path or not path.is_file() or root not in path.resolve().parents:
            raise Http404("Generated file not found.")
        return FileResponse(
            path.open("rb"),
            as_attachment=not inline,
            filename=path.name,
            content_type="image/png" if inline else None,
        )


class JobActionView(APIView):
    """Run one guarded workflow stage synchronously for a job."""

    def post(self, request, pk, action):
        job = get_object_or_404(AnalysisJob, pk=pk)
        if job.status in {"GEOMETRY_RUNNING", "MESHING", "SOLVING"}:
            return Response({"error": "This job is already running."}, status=status.HTTP_409_CONFLICT)
        try:
            if action == "geometry":
                return self._geometry(job)
            if action == "mesh":
                return self._mesh(job, request.data.get("mesh_size", 20.0))
            if action == "solve":
                return self._solve(job)
            if action == "mechanical":
                return self._mechanical(job)
            if action == "workbench":
                return self._workbench(job)
            if action == "validate":
                return self._validate(job)
            return Response({"error": "Unknown workflow action."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            traceback.print_exc()

            job.status = "FAILED"
            job.error_message = str(exc)
            job.save(
                update_fields=[
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
            return Response(
                {
                    "error": str(exc),
                    "job_id": job.id,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @staticmethod
    def _geometry(job):
        job.status, job.error_message = "GEOMETRY_RUNNING", ""
        job.save(update_fields=["status", "error_message", "updated_at"])
        result = generate_geometry(settings.BASE_DIR / "generated_geometry", job.id, job.dimensions)
        job.geometry_file = result["geometry_file"]
        job.result_data = {**(job.result_data or {}), "geometry": result}
        job.status = "GEOMETRY_COMPLETED"
        job.save(update_fields=["geometry_file", "result_data", "status", "updated_at"])
        return Response(AnalysisJobSerializer(job).data)

    @staticmethod
    def _mesh(job, mesh_size):
        if not job.geometry_file:
            return Response({"error": "Generate geometry before meshing."}, status=status.HTTP_409_CONFLICT)
        job.status, job.error_message = "MESHING", ""
        job.save(update_fields=["status", "error_message", "updated_at"])
        output_dir = Path(settings.BASE_DIR) / "generated_geometry" / f"job_{job.id}"
        settings_data = {**{"global": mesh_size}, **(job.mesh_settings or {})}
        result = generate_mesh(step_path=job.geometry_file, mesh_path=output_dir / "bellows.msh", vtk_path=output_dir / "bellows.vtk", mesh_size=settings_data["global"], mesh_sizes=settings_data)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Mesh generation failed."))
        job.mesh_file, job.vtk_file = result["mesh_file"], result["vtk_file"]
        result["preview_image"] = create_mesh_preview(
            job.vtk_file, output_dir / "mesh_preview.png"
        )
        job.result_data = {**(job.result_data or {}), "mesh": result}
        job.status = "MESH_COMPLETED"
        job.save(update_fields=["mesh_file", "vtk_file", "result_data", "status", "updated_at"])
        return Response(AnalysisJobSerializer(job).data)

    @staticmethod
    def _mechanical(job):
        """Create a saved ANSYS Mechanical static structural project for a job."""
        if not job.geometry_file or not Path(job.geometry_file).is_file():
            return Response(
                {"error": "Generate STEP geometry before creating a Mechanical project."},
                status=status.HTTP_409_CONFLICT,
            )
        output_dir = Path(settings.BASE_DIR) / "generated_geometry" / f"job_{job.id}"
        result = solve_static_structural(
            geometry_file=job.geometry_file,
            force_newtons=job.force,
            project_file=output_dir / "static_structural_named.mechdat",
        )
        project_file = Path(result["mechanical_project_file"])
        if not project_file.is_file() or project_file.stat().st_size == 0:
            raise RuntimeError("ANSYS Mechanical did not create a valid static structural project.")
        job.solver_data = {**(job.solver_data or {}), "mechanical_project": result}
        job.result_data = {**(job.result_data or {}), "mechanical_project": result}
        job.error_message = ""
        if job.status == "FAILED":
            job.status = "GEOMETRY_COMPLETED"
        job.save(
            update_fields=[
                "solver_data",
                "result_data",
                "status",
                "error_message",
                "updated_at",
            ]
        )
        return Response(AnalysisJobSerializer(job).data)

    @staticmethod
    def _workbench(job):
        """Create one linked Workbench project for SpaceClaim and Mechanical."""
        if not job.geometry_file or not Path(job.geometry_file).is_file():
            return Response({"error": "Generate geometry before creating a Workbench project."}, status=status.HTTP_409_CONFLICT)
        output_dir = Path(settings.BASE_DIR) / "generated_geometry" / f"job_{job.id}"
        geometry_result = (job.result_data or {}).get("geometry", {})
        spaceclaim_file = Path(geometry_result.get("spaceclaim_file", ""))
        # Native SpaceClaim retains the selection tree; older STEP-only jobs stay supported.
        source = spaceclaim_file if spaceclaim_file.is_file() else Path(job.geometry_file)
        result = create_static_structural_workbench_project(source, output_dir / "static_structural_workbench.wbpj")
        job.result_data = {**(job.result_data or {}), "workbench_project": result}
        job.error_message = ""
        if job.status == "FAILED":
            job.status = "GEOMETRY_COMPLETED"
        job.save(update_fields=["result_data", "status", "error_message", "updated_at"])
        return Response(AnalysisJobSerializer(job).data)

    @staticmethod
    def _solve(job):
        
        if not job.geometry_file:
            return Response(
                {"error": "Generate geometry before solving."},
                status=status.HTTP_409_CONFLICT,
            )

        if not job.mesh_file:
            return Response(
                {"error": "Generate the mesh before solving."},
                status=status.HTTP_409_CONFLICT,
            )

        mesh_path = Path(job.mesh_file)
        if not mesh_path.is_file():
            return Response(
                {"error": "Mesh file does not exist. Generate the mesh again."},
                status=status.HTTP_409_CONFLICT,
            )
        job.status, job.error_message = "SOLVING", ""
        job.save(update_fields=["status", "error_message", "updated_at"])
        result = solver_capability(job)
        if not result["available"]:
            job.solver_data = result
            job.result_data = {**(job.result_data or {}), "solve": result}
            job.status = "MESH_COMPLETED"
            job.save(update_fields=["solver_data", "result_data", "status", "updated_at"])
            return Response({"job": AnalysisJobSerializer(job).data, "message": "Solver is not ready: " + " ".join(result["reasons"])})
        
        result = solve_shell_job(job, Path(settings.BASE_DIR) / "generated_geometry" / f"job_{job.id}" / "mapdl")
        job.solver_data = result
        job.result_data = {**(job.result_data or {}), "solve": result}
        result_file = result.get("result_file")
        if (
            result.get("result_state") != "calculated"
            or not result_file
            or not Path(result_file).is_file()
            or Path(result_file).stat().st_size == 0
            or result.get("maximum_displacement_mm") is None
            or result.get("maximum_equivalent_stress_mpa") is None
        ):
            raise RuntimeError(
                "MAPDL did not return a complete, valid result set."
            )

        job.status = "COMPLETED"
        job.error_message = ""
        job.save(
            update_fields=[
                "solver_data",
                "result_data",
                "status",
                "error_message",
                "updated_at",
            ]
        )

        return Response({
            "job": AnalysisJobSerializer(job).data,
            "message": "MAPDL solve completed and result-file checks passed.",
        })

    @staticmethod
    def _validate(job):
        if not job.geometry_file:
            return Response({"error": "Generate or assign STEP geometry first."}, status=status.HTTP_409_CONFLICT)
        return Response(inspect_step_geometry(job.geometry_file))


from .mapdl_service import preflight_shell_job

class JobSolverPreflightView(APIView):
    def get(self, request, pk):
        job = get_object_or_404(AnalysisJob, pk=pk)
        result = preflight_shell_job(job)
        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result.get("ready")
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
        )
