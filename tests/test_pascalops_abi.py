import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation import pascalops


class PascalOpsAbiTests(unittest.TestCase):
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
