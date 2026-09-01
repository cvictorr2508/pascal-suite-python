import os
import shlex
import subprocess
from pathlib import Path

DEFAULT_PASCAL_OPS_LIB = Path(
    "/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so"
)


def resolve_pascal_ops_library() -> Path:
    """Resolve a biblioteca nativa usada pelo supervisor de regiões."""
    return Path(os.environ.get("PASCAL_OPS_LIB", str(DEFAULT_PASCAL_OPS_LIB))).expanduser()


def region_proxy_source() -> Path:
    return Path(__file__).resolve().parent / "native" / "pascal_region_proxy.c"


def region_proxy_build_command(binary_path: Path) -> list[str]:
    """Monta o comando determinístico de compilação do supervisor nativo."""
    library_path = resolve_pascal_ops_library()
    pascal_root = library_path.parent.parent
    compiler = shlex.split(os.environ.get("CC", "gcc"))
    if not compiler:
        raise RuntimeError("CC não define um compilador válido")

    return [
        *compiler,
        "-O2",
        "-std=c11",
        f"-I{pascal_root / 'include'}",
        str(region_proxy_source()),
        f"-L{pascal_root / 'lib'}",
        f"-Wl,-rpath,{pascal_root / 'lib'}",
        "-lmpascalops",
        "-o",
        str(binary_path),
    ]


def build_region_proxy(output_dir: Path, *, name: str) -> Path:
    """Compila o ELF que deve ser o alvo direto do pascalanalyzer -t man."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    binary_path = output_dir / name
    command = region_proxy_build_command(binary_path)

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Compilador não encontrado ao construir supervisor PaScal: {command[0]}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Falha ao compilar supervisor PaScal.\n"
            f"Comando: {' '.join(command)}\n"
            f"stdout:\n{exc.stdout}\n"
            f"stderr:\n{exc.stderr}"
        ) from exc

    if not binary_path.is_file():
        raise RuntimeError(
            "Compilação do supervisor PaScal terminou sem produzir o binário esperado: "
            f"{binary_path}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

    binary_path.chmod(0o755)
    return binary_path
