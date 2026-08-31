import ctypes
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_lib = None
PASCAL_AVAILABLE = False
PASCAL_LIBRARY_PATH = os.environ.get(
    "PASCAL_OPS_LIB",
    "/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so",
)


class PascalInstrumentationError(RuntimeError):
    """Raised when the PaScal manual-instrumentation runtime cannot be used."""


def _load_library() -> None:
    """Carrega libmpascalops.so e valida os símbolos exigidos pelo runner."""
    global _lib, PASCAL_AVAILABLE

    try:
        _lib = ctypes.CDLL(PASCAL_LIBRARY_PATH)
        _lib._pascal_start.argtypes = [ctypes.c_int]
        _lib._pascal_start.restype = None
        _lib._pascal_stop.argtypes = [ctypes.c_int]
        _lib._pascal_stop.restype = None
    except Exception as exc:
        _lib = None
        PASCAL_AVAILABLE = False
        logger.error(
            "Falha ao carregar a instrumentacao manual do PaScal em %s: %s",
            PASCAL_LIBRARY_PATH,
            exc,
        )
        return

    PASCAL_AVAILABLE = True
    logger.info("libmpascalops carregada com sucesso: %s", PASCAL_LIBRARY_PATH)


_load_library()


def require_pascal() -> None:
    """Falha explicitamente quando a instrumentacao manual foi solicitada, mas nao esta disponivel."""
    if not PASCAL_AVAILABLE or _lib is None:
        raise PascalInstrumentationError(
            "Instrumentacao manual do PaScal indisponivel. "
            f"Verifique PASCAL_OPS_LIB e os simbolos _pascal_start/_pascal_stop em {PASCAL_LIBRARY_PATH}."
        )


@contextmanager
def pascal_region(region_id: int):
    """Delimita uma regiao PaScal e garante o fechamento mesmo diante de excecao."""
    if region_id < 0:
        raise ValueError("region_id deve ser maior ou igual a zero")

    require_pascal()

    try:
        _lib._pascal_start(region_id)
    except Exception as exc:
        raise PascalInstrumentationError(
            f"Falha ao iniciar a regiao PaScal {region_id}: {exc}"
        ) from exc

    try:
        yield
    finally:
        try:
            _lib._pascal_stop(region_id)
        except Exception as exc:
            raise PascalInstrumentationError(
                f"Falha ao encerrar a regiao PaScal {region_id}: {exc}"
            ) from exc
