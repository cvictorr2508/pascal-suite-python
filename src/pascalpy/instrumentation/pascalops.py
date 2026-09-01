import ctypes
import logging
import os
import threading
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

_PROXY_COMMAND_FD_ENV = "PASCAL_REGION_PROXY_COMMAND_FD"
_PROXY_ACK_FD_ENV = "PASCAL_REGION_PROXY_ACK_FD"
_proxy_lock = threading.Lock()


class PascalInstrumentationError(RuntimeError):
    """Raised when the PaScal manual-instrumentation runtime cannot be used."""


def _parse_proxy_fd(name: str):
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        fd = int(raw)
    except ValueError:
        logger.error("%s não contém um descritor numérico válido: %r", name, raw)
        return None
    if fd < 0:
        logger.error("%s contém descritor negativo: %s", name, fd)
        return None
    return fd


_proxy_env_requested = (
    os.environ.get(_PROXY_COMMAND_FD_ENV) is not None
    or os.environ.get(_PROXY_ACK_FD_ENV) is not None
)
_proxy_command_fd = _parse_proxy_fd(_PROXY_COMMAND_FD_ENV)
_proxy_ack_fd = _parse_proxy_fd(_PROXY_ACK_FD_ENV)
PASCAL_PROXY_AVAILABLE = _proxy_command_fd is not None and _proxy_ack_fd is not None


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


if PASCAL_PROXY_AVAILABLE:
    # O processo Python não deve abrir libmpascalops diretamente neste modo.
    # O supervisor ELF reconhecido pelo Analyzer executa _pascal_start/_pascal_stop.
    PASCAL_AVAILABLE = True
elif not _proxy_env_requested:
    _load_library()


def instrumentation_status() -> dict:
    """Retorna diagnostico serializavel da instrumentacao manual do PaScal."""
    if PASCAL_PROXY_AVAILABLE:
        backend = "proxy"
    elif PASCAL_AVAILABLE:
        backend = "ctypes"
    else:
        backend = "unavailable"

    return {
        "available": PASCAL_AVAILABLE,
        "backend": backend,
        "library_path": PASCAL_LIBRARY_PATH,
        "start_symbol": PASCAL_START_SYMBOL,
        "stop_symbol": PASCAL_STOP_SYMBOL,
        "proxy_command_fd": _proxy_command_fd if PASCAL_PROXY_AVAILABLE else None,
        "proxy_ack_fd": _proxy_ack_fd if PASCAL_PROXY_AVAILABLE else None,
    }


def require_pascal() -> None:
    """Falha explicitamente quando a instrumentacao manual nao esta disponivel."""
    if PASCAL_PROXY_AVAILABLE:
        return

    if _proxy_env_requested:
        raise PascalInstrumentationError(
            "Backend proxy PaScal foi solicitado, mas os descritores "
            f"{_PROXY_COMMAND_FD_ENV}/{_PROXY_ACK_FD_ENV} são inválidos ou incompletos."
        )

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


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        try:
            written = os.write(fd, view)
        except OSError as exc:
            raise PascalInstrumentationError(
                f"Falha ao escrever no supervisor PaScal: {exc}"
            ) from exc
        if written <= 0:
            raise PascalInstrumentationError(
                "Supervisor PaScal encerrou o canal de comando durante a escrita."
            )
        view = view[written:]


def _read_ack_line(fd: int) -> str:
    data = bytearray()
    while len(data) < 512:
        try:
            chunk = os.read(fd, 1)
        except OSError as exc:
            raise PascalInstrumentationError(
                f"Falha ao ler confirmação do supervisor PaScal: {exc}"
            ) from exc
        if not chunk:
            raise PascalInstrumentationError(
                "Supervisor PaScal encerrou o canal de confirmação inesperadamente."
            )
        data.extend(chunk)
        if chunk == b"\n":
            return data.decode("utf-8", errors="replace").rstrip("\r\n")
    raise PascalInstrumentationError("Confirmação do supervisor PaScal excedeu 512 bytes.")


def _proxy_roundtrip(command: str, region_id: int, line_no: int, filename: str) -> None:
    if not PASCAL_PROXY_AVAILABLE:
        raise PascalInstrumentationError("Backend proxy PaScal não está disponível.")
    if any(char in filename for char in ("\t", "\r", "\n")):
        raise ValueError("filename da região PaScal não pode conter tab ou quebra de linha")

    payload = f"{command}\t{region_id}\t{line_no}\t{filename}\n".encode("utf-8")
    with _proxy_lock:
        _write_all(_proxy_command_fd, payload)
        ack = _read_ack_line(_proxy_ack_fd)

    expected = f"OK {command}"
    if ack != expected:
        raise PascalInstrumentationError(
            f"Supervisor PaScal rejeitou {command} da região {region_id}: {ack}"
        )


@contextmanager
def pascal_region(
    region_id: int,
    *,
    filename: str = "python",
    start_line: int = 0,
    stop_line: int = 0,
):
    """Delimita uma região PaScal via supervisor IPC ou ABI nativa direta."""
    if region_id < 0:
        raise ValueError("region_id deve ser maior ou igual a zero")

    require_pascal()

    if PASCAL_PROXY_AVAILABLE:
        _proxy_roundtrip("START", region_id, start_line, filename)
        try:
            yield
        finally:
            _proxy_roundtrip("STOP", region_id, stop_line, filename)
        return

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
