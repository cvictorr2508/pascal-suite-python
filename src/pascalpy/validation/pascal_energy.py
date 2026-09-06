import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PascalEnergyValidationReport:
    """Resultado da validacao estrutural da telemetria energetica regional."""

    source: str
    required_region_id: int | str
    has_data_descriptor: bool
    has_extras: bool
    has_regions_descriptor: bool
    rapl_domains: tuple[str, ...]
    legacy_region_energy_domains: tuple[str, ...]
    sampled_rapl_sensors: tuple[str, ...]
    run_count: int
    runs_with_regions: int
    runs_with_required_region: int
    runs_with_rapl_data: int
    runs_with_sampled_rapl: int
    runs_with_derivable_sampled_energy: int
    required_region_energy_samples: int
    legacy_required_region_energy_samples: int
    nonzero_required_region_energy_samples: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def structurally_valid(self) -> bool:
        return not self.errors

    @property
    def viewer_energy_ready(self) -> bool:
        """Indica se o JSON ja possui mapas RAPL consumiveis pelo Viewer atual."""
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
    def legacy_region_energy_ready(self) -> bool:
        """Indica se o contrato historico ``values: [region_energy]`` esta pronto."""
        return (
            self.viewer_energy_ready
            and self.legacy_required_region_energy_samples > 0
        )

    @property
    def sampled_energy_derivable(self) -> bool:
        """Indica se regioes e potencia amostrada permitem derivacao no Viewer."""
        return (
            self.structurally_valid
            and self.has_regions_descriptor
            and bool(self.sampled_rapl_sensors)
            and self.runs_with_required_region > 0
            and self.runs_with_derivable_sampled_energy > 0
        )

    @property
    def required_region_has_nonzero_energy(self) -> bool:
        return self.nonzero_required_region_energy_samples > 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["structurally_valid"] = self.structurally_valid
        data["viewer_energy_ready"] = self.viewer_energy_ready
        data["legacy_region_energy_ready"] = self.legacy_region_energy_ready
        data["sampled_energy_derivable"] = self.sampled_energy_derivable
        data["required_region_has_nonzero_energy"] = (
            self.required_region_has_nonzero_energy
        )
        return data


def _viewer_energy_domains(extras: Any) -> tuple[str, ...]:
    """Replica a selecao do Viewer: toda chave de extras iniciada por ``rapl``."""
    if not isinstance(extras, dict):
        return ()

    return tuple(
        sorted(
            str(name)
            for name, descriptor in extras.items()
            if str(name).lower().startswith("rapl")
            and isinstance(descriptor, dict)
        )
    )


def _legacy_energy_domains(extras: Any) -> tuple[str, ...]:
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


def _valid_power_samples(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        return []

    samples: list[tuple[float, float]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        power = _coerce_number(item[0])
        timestamp = _coerce_number(item[1])
        if power is None or timestamp is None:
            continue
        if not math.isfinite(power) or not math.isfinite(timestamp):
            continue
        samples.append((power, timestamp))

    samples.sort(key=lambda item: item[1])
    if len(samples) < 2:
        return []
    intervals = [
        right[1] - left[1] for left, right in zip(samples, samples[1:])
    ]
    if any(interval <= 0 for interval in intervals):
        return []
    sample_period = statistics.median(intervals)
    if any(interval > sample_period * 3 for interval in intervals):
        return []
    return samples


def _samples_cover_region(samples: list[tuple[float, float]], regions: Any) -> bool:
    if len(samples) < 2 or not isinstance(regions, list) or not regions:
        return False

    timestamps = [timestamp for _, timestamp in samples]
    sample_period = statistics.median(
        right - left for left, right in zip(timestamps, timestamps[1:])
    )
    lower_bound = timestamps[0] - sample_period
    upper_bound = timestamps[-1] + sample_period

    valid_intervals = 0
    for region in regions:
        if not isinstance(region, (list, tuple)) or len(region) < 2:
            return False
        start = _coerce_number(region[0])
        stop = _coerce_number(region[1])
        if start is None or stop is None or stop < start:
            return False
        if start < lower_bound or stop > upper_bound:
            return False
        valid_intervals += 1
    return valid_intervals > 0


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
    required_region_id: int | str = 1,
) -> PascalEnergyValidationReport:
    """Valida o contrato observado nos JSONs PaScal aceitos pelo Viewer.

    O validador nao assume nomes fixos como ``raplpackage-0``. Ele separa o mapa
    RAPL ja consumivel pelo Viewer, o contrato historico ``region_energy`` e a
    telemetria amostrada que ainda precisa ser integrada no proprio Viewer.
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
            legacy_region_energy_domains=(),
            sampled_rapl_sensors=(),
            run_count=0,
            runs_with_regions=0,
            runs_with_required_region=0,
            runs_with_rapl_data=0,
            runs_with_sampled_rapl=0,
            runs_with_derivable_sampled_energy=0,
            required_region_energy_samples=0,
            legacy_required_region_energy_samples=0,
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

    rapl_domains = _viewer_energy_domains(extras)
    legacy_region_energy_domains = _legacy_energy_domains(extras)

    data = document.get("data")
    if not isinstance(data, dict):
        data = {}
        errors.append("Campo data ausente ou invalido.")

    required_region_key = str(required_region_id)
    runs_with_regions = 0
    runs_with_required_region = 0
    runs_with_rapl_data = 0
    runs_with_sampled_rapl = 0
    runs_with_derivable_sampled_energy = 0
    required_region_energy_samples = 0
    legacy_required_region_energy_samples = 0
    nonzero_required_region_energy_samples = 0
    sampled_rapl_sensors: set[str] = set()

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
            if domain in legacy_region_energy_domains:
                legacy_required_region_energy_samples += 1
            if value > 0:
                nonzero_required_region_energy_samples += 1

        if run_has_rapl:
            runs_with_rapl_data += 1

        sensors = run_data.get("sensors")
        run_has_sampled_rapl = False
        run_has_derivable_samples = False
        if isinstance(sensors, dict):
            required_regions = (
                regions.get(required_region_key)
                if isinstance(regions, dict)
                else None
            )
            for sensor_name, sensor_data in sensors.items():
                if not str(sensor_name).lower().startswith("rapl_sample-"):
                    continue
                samples = _valid_power_samples(sensor_data)
                if not samples:
                    continue
                sampled_rapl_sensors.add(str(sensor_name))
                run_has_sampled_rapl = True
                if _samples_cover_region(samples, required_regions):
                    run_has_derivable_samples = True
        if run_has_sampled_rapl:
            runs_with_sampled_rapl += 1
        if run_has_derivable_samples:
            runs_with_derivable_sampled_energy += 1

    if data and runs_with_required_region == 0:
        errors.append(
            f"Nenhuma rodada contem a regiao obrigatoria {required_region_key}."
        )

    if data and rapl_domains and runs_with_rapl_data == 0:
        warnings.append(
            "Os dominios RAPL foram declarados, mas nao aparecem como mapas nas rodadas."
        )

    if data and rapl_domains and required_region_energy_samples == 0:
        warnings.append(
            f"Nao ha amostras de energia para a regiao {required_region_key}."
        )

    if data and not rapl_domains and not sampled_rapl_sensors:
        warnings.append("Nenhum mapa RAPL ou sensor RAPL amostrado foi encontrado.")

    if runs_with_derivable_sampled_energy and not required_region_energy_samples:
        warnings.append(
            "A energia regional pode ser derivada das amostras RAPL, mas o Viewer "
            "ainda precisa integrar a potencia sobre os intervalos das regioes."
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
        legacy_region_energy_domains=legacy_region_energy_domains,
        sampled_rapl_sensors=tuple(sorted(sampled_rapl_sensors)),
        run_count=len(data),
        runs_with_regions=runs_with_regions,
        runs_with_required_region=runs_with_required_region,
        runs_with_rapl_data=runs_with_rapl_data,
        runs_with_sampled_rapl=runs_with_sampled_rapl,
        runs_with_derivable_sampled_energy=runs_with_derivable_sampled_energy,
        required_region_energy_samples=required_region_energy_samples,
        legacy_required_region_energy_samples=(
            legacy_required_region_energy_samples
        ),
        nonzero_required_region_energy_samples=nonzero_required_region_energy_samples,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_pascal_energy_file(
    path: str | Path,
    *,
    required_region_id: int | str = 1,
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
            legacy_region_energy_domains=(),
            sampled_rapl_sensors=(),
            run_count=0,
            runs_with_regions=0,
            runs_with_required_region=0,
            runs_with_rapl_data=0,
            runs_with_sampled_rapl=0,
            runs_with_derivable_sampled_energy=0,
            required_region_energy_samples=0,
            legacy_required_region_energy_samples=0,
            nonzero_required_region_energy_samples=0,
            errors=(f"Falha ao ler JSON: {exc}",),
        )

    return validate_pascal_energy_document(
        document,
        source=str(source_path),
        required_region_id=required_region_id,
    )
