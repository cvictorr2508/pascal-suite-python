import ctypes
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation import pascalops


class _FakeCFunction:
    def __init__(self):
        self.argtypes = None
        self.restype = object()


class PascalOpsAbiTests(unittest.TestCase):
    def test_import_does_not_probe_native_pascal_runtime(self):
        env = os.environ.copy()
        env.pop("PASCAL_REGION_PROXY_COMMAND_FD", None)
        env.pop("PASCAL_REGION_PROXY_ACK_FD", None)
        env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

        result = subprocess.run(
            [sys.executable, "-c", "import pascalpy.instrumentation.pascalops"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("[Pascal]", result.stderr)

    def test_configures_three_argument_ctypes_signature(self):
        start_fn = _FakeCFunction()
        stop_fn = _FakeCFunction()

        with (
            patch.object(pascalops, "_pascal_start_fn", start_fn),
            patch.object(pascalops, "_pascal_stop_fn", stop_fn),
        ):
            pascalops._configure_manual_instrumentation_abi()

        expected = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
        self.assertEqual(start_fn.argtypes, expected)
        self.assertEqual(stop_fn.argtypes, expected)
        self.assertIsNone(start_fn.restype)
        self.assertIsNone(stop_fn.restype)

    def test_region_passes_three_arguments_to_native_api(self):
        start_mock = Mock()
        stop_mock = Mock()

        with (
            patch.object(pascalops, "PASCAL_AVAILABLE", True),
            patch.object(pascalops, "_lib", object()),
            patch.object(pascalops, "_pascal_start_fn", start_mock),
            patch.object(pascalops, "_pascal_stop_fn", stop_mock),
        ):
            with pascalops.pascal_region(
                1,
                filename="gurobi_runner.py",
                start_line=123,
                stop_line=125,
            ):
                pass

        start_mock.assert_called_once_with(1, 123, b"gurobi_runner.py")
        stop_mock.assert_called_once_with(1, 125, b"gurobi_runner.py")

    def test_region_rejects_negative_region_id(self):
        with self.assertRaises(ValueError):
            with pascalops.pascal_region(-1):
                pass


if __name__ == "__main__":
    unittest.main()
