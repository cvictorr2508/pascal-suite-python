"""Validated experiment profiles shared by solver-specific adapters."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParameterValue: TypeAlias = bool | int | float | str


class SolverName(str, Enum):
    """Optimization solvers supported by the experiment contract."""

    GUROBI = "gurobi"
    SCIP = "scip"


class ProfileKind(str, Enum):
    """Solver-independent experimental treatments."""

    DEFAULT = "default"
    PRESOLVE_OFF = "presolve-off"
    WARM_START = "warm-start"


class InitialSolutionSpec(BaseModel):
    """Map workloads to solver-readable or variable-value solution files."""

    model_config = ConfigDict(extra="forbid")

    files: dict[str, Path] = Field(min_length=1)
    required: bool = True

    def resolve_for(self, workload: Path) -> Path | None:
        """Resolve a solution using an absolute path or workload filename key."""

        candidates = (str(workload.resolve()), str(workload), workload.name)
        for candidate in candidates:
            if candidate in self.files:
                return self.files[candidate]
        return None


class SolverProfile(BaseModel):
    """A named treatment applied uniformly to every run in one Analyzer batch."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: ProfileKind
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)
    initial_solution: InitialSolutionSpec | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> "SolverProfile":
        reserved = {name.lower() for name in self.parameters} & {"threads", "seed"}
        if reserved:
            raise ValueError(
                "Threads and Seed are controlled by the experiment runner and cannot "
                f"be overridden by a profile: {sorted(reserved)}"
            )

        if self.kind == ProfileKind.WARM_START and self.initial_solution is None:
            raise ValueError("A warm-start profile requires initial_solution.files")
        if self.kind != ProfileKind.WARM_START and self.initial_solution is not None:
            raise ValueError(
                "initial_solution is only valid for a warm-start profile"
            )
        return self


def default_solver_profile() -> SolverProfile:
    """Return a new default profile for backward-compatible configurations."""

    return SolverProfile(id="default", kind=ProfileKind.DEFAULT)
