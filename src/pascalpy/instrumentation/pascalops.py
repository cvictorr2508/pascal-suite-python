import ctypes
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_lib = None
PASCAL_AVAILABLE = False

def _load_library() -> None:
    """Tenta carregar libmpascalops.so em tempo de execução."""
    global _lib, PASCAL_AVAILABLE
    
    # Busca da variável de ambiente, ou usa o nome default torcendo para estar no PATH
    lib_path = os.environ.get("PASCAL_OPS_LIB", "libmpascalops.so")
    
    try:
        _lib = ctypes.CDLL(lib_path)
        _lib.pascal_start.argtypes = [ctypes.c_int]
        _lib.pascal_start.restype  = None
        _lib.pascal_stop.argtypes  = [ctypes.c_int]
        _lib.pascal_stop.restype   = None
        PASCAL_AVAILABLE = True
        logger.info("libmpascalops carregada com sucesso: %s", lib_path)
    except OSError as exc:
        logger.warning("libmpascalops não disponível — executando sem região manual: %s", exc)

_load_library()

@contextmanager
def pascal_region(region_id: int):
    """
    Context manager que delimita uma região de medição PaScal.
    Requer que o pascalanalyzer seja iniciado com a flag -t man.
    Garante pascal_stop mesmo diante de exceção Gurobi ou interrupção.
    """
    if PASCAL_AVAILABLE:
        _lib.pascal_start(region_id)
    try:
        yield
    finally:
        if PASCAL_AVAILABLE:
            _lib.pascal_stop(region_id)