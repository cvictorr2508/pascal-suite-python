"""Gurobi adapter for the shared file-based solver pipeline."""

from pascalpy.adapters.solver_file_adapter import SolverFileAdapter
from pascalpy.experiment_profiles import SolverName, SolverProfile


class GurobiFileAdapter(SolverFileAdapter):
    """Build one PaScal Analyzer batch for a validated Gurobi profile."""

    def __init__(
        self,
        profile: SolverProfile | None = None,
        limits: dict | None = None,
    ):
        super().__init__(
            solver=SolverName.GUROBI,
            runner_name="gurobi_runner.py",
            profile=profile,
            legacy_parameters=limits,
        )
