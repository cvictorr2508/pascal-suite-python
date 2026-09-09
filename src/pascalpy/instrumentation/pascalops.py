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
_native_load_lock = threading.Lock()
_native_load_attempted = False


class PascalInstrumentationError(RuntimeError):
    """Raised when the PaScal manual-instrumentation runtime cannot be used."""


def _parse_proxy_fd(name: str):
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        fd = int(raw)
    except ValueError:
        logger.error("%s does not contain a valid numeric descriptor: %r", name, raw)
        return None
    if fd < 0:
        logger.error("%s contains a negative descriptor: %s", name, fd)
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
        "None of the expected symbols was found: " + ", ".join(candidates)
    )


def _configure_manual_instrumentation_abi() -> None:
    """Configure the C ABI declared in pascalops.h for manual start/stop."""
    # pascalops.h:
    # void _pascal_start(long id, int start_line, const char *filename);
    # void _pascal_stop(long id, int stop_line, const char *filename);
    _pascal_start_fn.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
    _pascal_start_fn.restype = None
    _pascal_stop_fn.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
    _pascal_stop_fn.restype = None


def _load_library() -> None:
    """Load libmpascalops.so and validate the ctypes fallback symbols."""
    global _lib
    global _pascal_start_fn
    global _pascal_stop_fn
    global PASCAL_AVAILABLE
    global PASCAL_START_SYMBOL
    global PASCAL_STOP_SYMBOL
    global _native_load_attempted

    _native_load_attempted = True

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
            "Failed to load PaScal manual instrumentation from %s: %s",
            PASCAL_LIBRARY_PATH,
            exc,
        )
        return

    PASCAL_AVAILABLE = True
    logger.info(
        "Loaded libmpascalops: %s (start=%s, stop=%s)",
        PASCAL_LIBRARY_PATH,
        PASCAL_START_SYMBOL,
        PASCAL_STOP_SYMBOL,
    )


def _ensure_native_loaded() -> None:
    """Load the ctypes fallback only when it is actually needed."""
    if PASCAL_PROXY_AVAILABLE or _native_load_attempted:
        return

    with _native_load_lock:
        if not _native_load_attempted:
            _load_library()


if PASCAL_PROXY_AVAILABLE:
    # In the current production mode, Python does not open libmpascalops.
    # The ELF supervisor recognized by Analyzer runs _pascal_start/_pascal_stop.
    PASCAL_AVAILABLE = True


def instrumentation_status() -> dict:
    """Return a serializable PaScal manual-instrumentation diagnostic."""
    if PASCAL_PROXY_AVAILABLE:
        backend = "proxy"
    elif _proxy_env_requested:
        backend = "unavailable"
    else:
        # Explicitly querying fallback status remains a probe operation; simply
        # importing the module no longer loads libmpascalops.
        _ensure_native_loaded()
        backend = "ctypes" if PASCAL_AVAILABLE else "unavailable"

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
    """Fail explicitly when manual instrumentation is unavailable."""
    if PASCAL_PROXY_AVAILABLE:
        return

    if _proxy_env_requested:
        raise PascalInstrumentationError(
            "The PaScal proxy backend was requested, but descriptors "
            f"{_PROXY_COMMAND_FD_ENV}/{_PROXY_ACK_FD_ENV} are invalid or incomplete."
        )

    _ensure_native_loaded()

    if (
        not PASCAL_AVAILABLE
        or _lib is None
        or _pascal_start_fn is None
        or _pascal_stop_fn is None
    ):
        raise PascalInstrumentationError(
            "PaScal manual instrumentation is unavailable. Check PASCAL_OPS_LIB "
            "and the _pascal_start/pascal_start and _pascal_stop/pascal_stop "
            f"symbols in {PASCAL_LIBRARY_PATH}."
        )


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        try:
            written = os.write(fd, view)
        except OSError as exc:
            raise PascalInstrumentationError(
                f"Failed to write to the PaScal supervisor: {exc}"
            ) from exc
        if written <= 0:
            raise PascalInstrumentationError(
                "The PaScal supervisor closed its command channel during the write."
            )
        view = view[written:]


def _read_ack_line(fd: int) -> str:
    data = bytearray()
    while len(data) < 512:
        try:
            chunk = os.read(fd, 1)
        except OSError as exc:
            raise PascalInstrumentationError(
                f"Failed to read the PaScal supervisor acknowledgement: {exc}"
            ) from exc
        if not chunk:
            raise PascalInstrumentationError(
                "The PaScal supervisor closed its acknowledgement channel unexpectedly."
            )
        data.extend(chunk)
        if chunk == b"\n":
            return data.decode("utf-8", errors="replace").rstrip("\r\n")
    raise PascalInstrumentationError(
        "The PaScal supervisor acknowledgement exceeded 512 bytes."
    )


def _proxy_roundtrip(command: str, region_id: int, line_no: int, filename: str) -> None:
    if not PASCAL_PROXY_AVAILABLE:
        raise PascalInstrumentationError("The PaScal proxy backend is unavailable.")
    if any(char in filename for char in ("\t", "\r", "\n")):
        raise ValueError("The PaScal region filename cannot contain tabs or line breaks")

    payload = f"{command}\t{region_id}\t{line_no}\t{filename}\n".encode("utf-8")
    with _proxy_lock:
        _write_all(_proxy_command_fd, payload)
        ack = _read_ack_line(_proxy_ack_fd)

    expected = f"OK {command}"
    if ack != expected:
        raise PascalInstrumentationError(
            f"The PaScal supervisor rejected {command} for region {region_id}: {ack}"
        )


@contextmanager
def pascal_region(
    region_id: int,
    *,
    filename: str = "python",
    start_line: int = 0,
    stop_line: int = 0,
):
    """Delimit a PaScal region through supervisor IPC or the direct native ABI."""
    if region_id < 0:
        raise ValueError("region_id must be greater than or equal to zero")

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
            f"Failed to start PaScal region {region_id}: {exc}"
        ) from exc

    try:
        yield
    finally:
        try:
            _pascal_stop_fn(region_id, stop_line, filename_bytes)
        except Exception as exc:
            raise PascalInstrumentationError(
                f"Failed to stop PaScal region {region_id}: {exc}"
            ) from exc
