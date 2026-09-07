"""SCIP adapter for the shared file-based solver pipeline."""

from pascalpy.adapters.solver_file_adapter import SolverFileAdapter
from pascalpy.experiment_profiles import SolverName, SolverProfile


class ScipFileAdapter(SolverFileAdapter):
    """Build one PaScal Analyzer batch for a validated SCIP profile."""

    def __init__(self, profile: SolverProfile | None = None):
        super().__init__(
            solver=SolverName.SCIP,
            runner_name="scip_runner.py",
            profile=profile,
        )
