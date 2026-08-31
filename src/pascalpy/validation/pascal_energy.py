import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PascalEnergyValidationReport:
    """Resultado da validacao estrutural da telemetria energetica regional."""

    source: str
    required_region_id: int
    has_data_descriptor: bool
    has_extras: bool
    has_regions_descriptor: bool
    rapl_domains: tuple[str, ...]
    run_count: int
    runs_with_regions: int
    runs_with_required_region: int
    runs_with_rapl_data: int
    required_region_energy_samples: int
    nonzero_required_region_energy_samples: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def structurally_valid(self) -> bool:
        return not self.errors

    @property
    def viewer_energy_ready(self) -> bool:
        """Indica se o documento possui o contrato minimo de energia por regiao."""
        return (
            self.structurally_valid
            and self.has_extras
            and self.has_regions_descriptor
            and bool(self.rapl_domains)
            and self.runs_with_required_region > 0
            and self.runs_with_rapl_data > 0
            and self.required_region_energy_samples > 0
        )

    @property
    def required_region_has_nonzero_energy(self) -> bool:
        return self.nonzero_required_region_energy_samples > 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["structurally_valid"] = self.structurally_valid
        data["viewer_energy_ready"] = self.viewer_energy_ready
        data["required_region_has_nonzero_energy"] = (
            self.required_region_has_nonzero_energy
        )
        return data


def _energy_domains(extras: Any) -> tuple[str, ...]:
    if not isinstance(extras, dict):
        return ()

    domains = []
    for name, descriptor in extras.items():
        if not isinstance(descriptor, dict):
            continue
        values = descriptor.get("values", [])
        if isinstance(values, list) and "region_energy" in values:
            domains.append(str(name))
    return tuple(sorted(domains))


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def validate_pascal_energy_document(
    document: Any,
    *,
    source: str = "<memory>",
    required_region_id: int = 1,
) -> PascalEnergyValidationReport:
    """Valida o contrato observado nos JSONs PaScal aceitos pelo Viewer.

    O validador nao assume nomes fixos como ``raplpackage-0``. Qualquer entrada de
    ``config.data_descriptor.extras`` que declare ``region_energy`` e tratada como
    dominio energetico.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(document, dict):
        return PascalEnergyValidationReport(
            source=source,
            required_region_id=required_region_id,
            has_data_descriptor=False,
            has_extras=False,
            has_regions_descriptor=False,
            rapl_domains=(),
            run_count=0,
            runs_with_regions=0,
            runs_with_required_region=0,
            runs_with_rapl_data=0,
            required_region_energy_samples=0,
            nonzero_required_region_energy_samples=0,
            errors=("O JSON raiz deve ser um objeto.",),
        )

    config = document.get("config")
    if not isinstance(config, dict):
        config = {}
        errors.append("Campo config ausente ou invalido.")

    descriptor = config.get("data_descriptor")
    has_data_descriptor = isinstance(descriptor, dict)
    if not has_data_descriptor:
        descriptor = {}
        errors.append("config.data_descriptor ausente ou invalido.")

    extras = descriptor.get("extras") if isinstance(descriptor, dict) else None
    has_extras = isinstance(extras, dict)
    if not has_extras:
        extras = {}
        errors.append("config.data_descriptor.extras ausente.")

    has_regions_descriptor = (
        isinstance(extras, dict) and isinstance(extras.get("regions"), dict)
    )
    if not has_regions_descriptor:
        errors.append("Descriptor extras.regions ausente.")

    rapl_domains = _energy_domains(extras)
    if not rapl_domains:
        errors.append(
            "Nenhum dominio energetico declara values contendo region_energy."
        )

    data = document.get("data")
    if not isinstance(data, dict):
        data = {}
        errors.append("Campo data ausente ou invalido.")

    required_region_key = str(required_region_id)
    runs_with_regions = 0
    runs_with_required_region = 0
    runs_with_rapl_data = 0
    required_region_energy_samples = 0
    nonzero_required_region_energy_samples = 0

    for run_key, run_data in data.items():
        if not isinstance(run_data, dict):
            warnings.append(f"Rodada {run_key} nao e um objeto e foi ignorada.")
            continue

        regions = run_data.get("regions")
        if isinstance(regions, dict):
            runs_with_regions += 1
            if required_region_key in regions:
                runs_with_required_region += 1

        run_has_rapl = False
        for domain in rapl_domains:
            domain_data = run_data.get(domain)
            if not isinstance(domain_data, dict):
                continue

            run_has_rapl = True
            if required_region_key not in domain_data:
                continue

            value = _coerce_number(domain_data[required_region_key])
            if value is None:
                warnings.append(
                    f"Rodada {run_key}, dominio {domain}: energia da regiao "
                    f"{required_region_key} nao numerica."
                )
                continue

            required_region_energy_samples += 1
            if value > 0:
                nonzero_required_region_energy_samples += 1

        if run_has_rapl:
            runs_with_rapl_data += 1

    if data and runs_with_required_region == 0:
        errors.append(
            f"Nenhuma rodada contem a regiao obrigatoria {required_region_key}."
        )

    if data and rapl_domains and runs_with_rapl_data == 0:
        errors.append(
            "Os dominios region_energy foram declarados, mas nao aparecem nas rodadas."
        )

    if data and rapl_domains and required_region_energy_samples == 0:
        errors.append(
            f"Nao ha amostras de energia para a regiao {required_region_key}."
        )

    if required_region_energy_samples and not nonzero_required_region_energy_samples:
        warnings.append(
            f"A regiao {required_region_key} existe, mas todas as amostras de energia "
            "sao zero. Isso pode ser esperado para workloads muito curtos, como dummy."
        )

    return PascalEnergyValidationReport(
        source=source,
        required_region_id=required_region_id,
        has_data_descriptor=has_data_descriptor,
        has_extras=has_extras,
        has_regions_descriptor=has_regions_descriptor,
        rapl_domains=rapl_domains,
        run_count=len(data),
        runs_with_regions=runs_with_regions,
        runs_with_required_region=runs_with_required_region,
        runs_with_rapl_data=runs_with_rapl_data,
        required_region_energy_samples=required_region_energy_samples,
        nonzero_required_region_energy_samples=nonzero_required_region_energy_samples,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_pascal_energy_file(
    path: str | Path,
    *,
    required_region_id: int = 1,
) -> PascalEnergyValidationReport:
    source_path = Path(path)
    try:
        with source_path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return PascalEnergyValidationReport(
            source=str(source_path),
            required_region_id=required_region_id,
            has_data_descriptor=False,
            has_extras=False,
            has_regions_descriptor=False,
            rapl_domains=(),
            run_count=0,
            runs_with_regions=0,
            runs_with_required_region=0,
            runs_with_rapl_data=0,
            required_region_energy_samples=0,
            nonzero_required_region_energy_samples=0,
            errors=(f"Falha ao ler JSON: {exc}",),
        )

    return validate_pascal_energy_document(
        document,
        source=str(source_path),
        required_region_id=required_region_id,
    )
