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
    
    # Caminho exato da biblioteca que você validou no NPAD
    lib_path = os.environ.get("PASCAL_OPS_LIB", "/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so")
    
    try:
        _lib = ctypes.CDLL(lib_path)
        
        # AQUI ESTÁ O SEGREDO: Mapeando as funções com o prefixo '_'
        _lib._pascal_start.argtypes = [ctypes.c_int]
        _lib._pascal_start.restype  = None
        _lib._pascal_stop.argtypes  = [ctypes.c_int]
        _lib._pascal_stop.restype   = None
        
        PASCAL_AVAILABLE = True
        logger.info("libmpascalops carregada com sucesso: %s", lib_path)
        
    except Exception as exc:
        logger.warning(f"PaScal C-API falhou. Usando fallback de medição Python. Erro: {exc}")
        PASCAL_AVAILABLE = False

_load_library()

@contextmanager
def pascal_region(region_id: int):
    """
    Context manager que delimita uma região de medição PaScal.
    Garante pascal_stop mesmo diante de exceção.
    """
    if PASCAL_AVAILABLE:
        try:
            # Chama a função nativa com underscore
            _lib._pascal_start(region_id)
        except: pass
        
    try:
        yield
    finally:
        if PASCAL_AVAILABLE:
            try:
                # Chama a função nativa com underscore
                _lib._pascal_stop(region_id)
            except: pass
