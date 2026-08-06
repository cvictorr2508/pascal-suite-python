import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    model_validator,
)

class ScalingMode(str, Enum):
    """Define o tipo de desenho experimental estatístico."""
    STRONG = "strong"  # Carga de trabalho constante, variam-se os núcleos
    WEAK = "weak"      # Carga de trabalho cresce proporcionalmente aos núcleos

@runtime_checkable
class ApplicationAdapter(Protocol):
    """
    Protocolo que todos os adaptadores (Gurobi, SCIP, Executable) devem seguir.
    O Pydantic usará isso para garantir duck-typing adequado na configuração.
    """
    def build_analyzer_command(
        self, 
        experiment_id: str,
        cores: int, 
        workload: Path, 
        repetition: int, 
        output_dir: Path,
        env_policy: Any = None
    ) -> list[str]:
        ...

class EnvironmentPolicy(BaseModel):
    """
    Configurações de hardware e sistema operacional gerenciadas pelo PaScal Analyzer.
    """
    model_config = ConfigDict(extra="forbid")

    cpu_affinity: bool = Field(default=True)
    disable_hyperthreading: bool = Field(default=True)
    cpu_governor: str = Field(default="performance")
    idle_time_seconds: float = Field(default=2.0, ge=0.0)
    performance_events: list[str] = Field(default_factory=list)
    track_energy_rapl: str | None = Field(default=None)
    track_cores: bool = Field(default=False)

class OutputPolicy(BaseModel):
    """Define como e onde os resultados e manifestos serão armazenados."""
    directory: Path = Field(...)
    create_if_missing: bool = Field(default=True)
    
    @model_validator(mode='after')
    def validate_directory(self) -> 'OutputPolicy':
        if self.create_if_missing:
            self.directory.mkdir(parents=True, exist_ok=True)
        elif not self.directory.exists() or not self.directory.is_dir():
            raise ValueError(f"O diretório de saída {self.directory} não existe.")
        return self

class Experiment(BaseModel):
    """Representação central de um experimento de escalabilidade do LAPPS."""
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

    @model_validator(mode='after')
    def validate_scaling_design(self) -> 'Experiment':
        # SE O ID ESTIVER VAZIO, USA O NOME DO EXPERIMENTO
        if not self.id:
            self.id = self.name
            
        res_len = len(self.resources)
        work_len = len(self.workloads)

        if self.scaling_mode == ScalingMode.WEAK:
            if res_len != work_len:
                raise ValueError(
                    f"Para escalabilidade FRACA, a quantidade de recursos ({res_len}) "
                    f"deve ser igual à quantidade de cargas de trabalho ({work_len})."
                )
        
        if sorted(self.resources) != self.resources:
            raise ValueError(f"A lista de recursos {self.resources} deve estar ordenada de forma crescente.")
            
        return self

    def generate_execution_plan(self) -> list[dict[str, Any]]:
        plan = []
        for rep in range(1, self.repetitions + 1):
            if self.scaling_mode == ScalingMode.STRONG:
                for w in self.workloads:
                    for r in self.resources:
                        plan.append({"repetition": rep, "cores": r, "workload": w})
            elif self.scaling_mode == ScalingMode.WEAK:
                for r, w in zip(self.resources, self.workloads):
                    plan.append({"repetition": rep, "cores": r, "workload": w})
        return plan