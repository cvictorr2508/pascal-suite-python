from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScalingMode(str, Enum):
    """Supported statistical experiment designs."""

    STRONG = "strong"  # Keep the workload fixed while changing core count.
    WEAK = "weak"  # Grow the workload proportionally with core count.


@runtime_checkable
class ApplicationAdapter(Protocol):
    """Interface implemented by Gurobi, SCIP, and executable adapters."""

    def build_analyzer_command(
        self,
        experiment_id: str,
        cores: int,
        workload: Path,
        repetition: int,
        output_dir: Path,
        env_policy: Any = None,
    ) -> list[str]: ...


class EnvironmentPolicy(BaseModel):
    """Hardware and operating-system settings managed by PaScal Analyzer."""

    model_config = ConfigDict(extra="forbid")

    cpu_affinity: bool = Field(default=True)
    disable_hyperthreading: bool = Field(default=True)
    cpu_governor: str = Field(default="performance")
    idle_time_seconds: float = Field(default=2.0, ge=0.0)
    performance_events: list[str] = Field(default_factory=list)
    track_energy_rapl: str | None = Field(default=None)
    track_cores: bool = Field(default=False)


class OutputPolicy(BaseModel):
    """Location and creation policy for results and manifests."""

    directory: Path = Field(...)
    create_if_missing: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_directory(self) -> "OutputPolicy":
        if self.create_if_missing:
            self.directory.mkdir(parents=True, exist_ok=True)
        elif not self.directory.exists() or not self.directory.is_dir():
            raise ValueError(f"Output directory does not exist: {self.directory}")
        return self


class Experiment(BaseModel):
    """Core representation of a LAPPS scalability experiment."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default="")
    name: str = Field(..., min_length=3)
    adapter: ApplicationAdapter = Field(...)
    scaling_mode: ScalingMode = Field(default=ScalingMode.STRONG)
    resources: list[int] = Field(..., min_length=1)
    workloads: list[Path] = Field(..., min_length=1)
    repetitions: int = Field(default=5, ge=1)
    environment: EnvironmentPolicy = Field(default_factory=EnvironmentPolicy)
    output: OutputPolicy

    @model_validator(mode="after")
    def validate_scaling_design(self) -> "Experiment":
        if not self.id:
            self.id = self.name

        resource_count = len(self.resources)
        workload_count = len(self.workloads)
        if self.scaling_mode == ScalingMode.WEAK and resource_count != workload_count:
            raise ValueError(
                "Weak scaling requires the same number of resources and workloads: "
                f"resources={resource_count}, workloads={workload_count}"
            )
        if sorted(self.resources) != self.resources:
            raise ValueError(
                f"Resources must be sorted in ascending order: {self.resources}"
            )
        return self

    def generate_execution_plan(self) -> list[dict[str, Any]]:
        plan = []
        for repetition in range(1, self.repetitions + 1):
            if self.scaling_mode == ScalingMode.STRONG:
                for workload in self.workloads:
                    for cores in self.resources:
                        plan.append(
                            {
                                "repetition": repetition,
                                "cores": cores,
                                "workload": workload,
                            }
                        )
            elif self.scaling_mode == ScalingMode.WEAK:
                for cores, workload in zip(self.resources, self.workloads):
                    plan.append(
                        {
                            "repetition": repetition,
                            "cores": cores,
                            "workload": workload,
                        }
                    )
        return plan
