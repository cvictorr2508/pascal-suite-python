import ctypes
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_lib = None
_pascal_start_fn = None
_pascal_stop_fn = None
PASCAL_AVAILABLE = False
PASCAL_START_SYMBOL = None
PASCAL_STOP_SYMBOL = None
PASCAL_LIBRARY_PATH = os.environ.get(
    "PASCAL_OPS_LIB",
    "/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so",
)


class PascalInstrumentationError(RuntimeError):
    """Raised when the PaScal manual-instrumentation runtime cannot be used."""


def _resolve_symbol(library, candidates):
    for symbol_name in candidates:
        try:
            return getattr(library, symbol_name), symbol_name
        except AttributeError:
            continue
    raise AttributeError(
        "Nenhum dos simbolos esperados foi encontrado: " + ", ".join(candidates)
    )


def _configure_manual_instrumentation_abi() -> None:
    """Configura a ABI C declarada em pascalops.h para start/stop manuais."""
    # pascalops.h:
    # void _pascal_start(long id, int start_line, const char *filename);
    # void _pascal_stop(long id, int stop_line, const char *filename);
    _pascal_start_fn.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
    _pascal_start_fn.restype = None
    _pascal_stop_fn.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
    _pascal_stop_fn.restype = None


def _load_library() -> None:
    """Carrega libmpascalops.so e valida os simbolos exigidos pelo runner."""
    global _lib
    global _pascal_start_fn
    global _pascal_stop_fn
    global PASCAL_AVAILABLE
    global PASCAL_START_SYMBOL
    global PASCAL_STOP_SYMBOL

    try:
        _lib = ctypes.CDLL(PASCAL_LIBRARY_PATH)
        _pascal_start_fn, PASCAL_START_SYMBOL = _resolve_symbol(
            _lib, ("_pascal_start", "pascal_start")
        )
        _pascal_stop_fn, PASCAL_STOP_SYMBOL = _resolve_symbol(
            _lib, ("_pascal_stop", "pascal_stop")
        )
        _configure_manual_instrumentation_abi()
    except Exception as exc:
        _lib = None
        _pascal_start_fn = None
        _pascal_stop_fn = None
        PASCAL_AVAILABLE = False
        PASCAL_START_SYMBOL = None
        PASCAL_STOP_SYMBOL = None
        logger.error(
            "Falha ao carregar a instrumentacao manual do PaScal em %s: %s",
            PASCAL_LIBRARY_PATH,
            exc,
        )
        return

    PASCAL_AVAILABLE = True
    logger.info(
        "libmpascalops carregada: %s (start=%s, stop=%s)",
        PASCAL_LIBRARY_PATH,
        PASCAL_START_SYMBOL,
        PASCAL_STOP_SYMBOL,
    )


_load_library()


def instrumentation_status() -> dict:
    """Retorna diagnostico serializavel da instrumentacao manual do PaScal."""
    return {
        "available": PASCAL_AVAILABLE,
        "library_path": PASCAL_LIBRARY_PATH,
        "start_symbol": PASCAL_START_SYMBOL,
        "stop_symbol": PASCAL_STOP_SYMBOL,
    }


def require_pascal() -> None:
    """Falha explicitamente quando a instrumentacao manual nao esta disponivel."""
    if (
        not PASCAL_AVAILABLE
        or _lib is None
        or _pascal_start_fn is None
        or _pascal_stop_fn is None
    ):
        raise PascalInstrumentationError(
            "Instrumentacao manual do PaScal indisponivel. "
            "Verifique PASCAL_OPS_LIB e os simbolos "
            f"_pascal_start/pascal_start e _pascal_stop/pascal_stop em {PASCAL_LIBRARY_PATH}."
        )


@contextmanager
def pascal_region(
    region_id: int,
    *,
    filename: str = "python",
    start_line: int = 0,
    stop_line: int = 0,
):
    """Delimita uma regiao PaScal usando a ABI nativa declarada em pascalops.h."""
    if region_id < 0:
        raise ValueError("region_id deve ser maior ou igual a zero")

    require_pascal()
    filename_bytes = os.fsencode(filename)

    try:
        _pascal_start_fn(region_id, start_line, filename_bytes)
    except Exception as exc:
        raise PascalInstrumentationError(
            f"Falha ao iniciar a regiao PaScal {region_id}: {exc}"
        ) from exc

    try:
        yield
    finally:
        try:
            _pascal_stop_fn(region_id, stop_line, filename_bytes)
        except Exception as exc:
            raise PascalInstrumentationError(
                f"Falha ao encerrar a regiao PaScal {region_id}: {exc}"
            ) from exc
