import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation import pascalops


class PascalOpsProxyTests(unittest.TestCase):
    def test_region_uses_proxy_start_and_stop(self):
        with (
            patch.object(pascalops, "PASCAL_PROXY_AVAILABLE", True),
            patch.object(pascalops, "PASCAL_AVAILABLE", True),
            patch.object(pascalops, "_proxy_roundtrip") as roundtrip,
        ):
            with pascalops.pascal_region(
                1,
                filename="gurobi_runner.py",
                start_line=120,
                stop_line=120,
            ):
                pass

        self.assertEqual(
            roundtrip.call_args_list,
            [
                call("START", 1, 120, "gurobi_runner.py"),
                call("STOP", 1, 120, "gurobi_runner.py"),
            ],
        )

    def test_nested_regions_preserve_lifo_event_order(self):
        with (
            patch.object(pascalops, "PASCAL_PROXY_AVAILABLE", True),
            patch.object(pascalops, "PASCAL_AVAILABLE", True),
            patch.object(pascalops, "_proxy_roundtrip") as roundtrip,
        ):
            with pascalops.pascal_region(0, filename="runner.py"):
                with pascalops.pascal_region(1, filename="runner.py"):
                    pass
                with pascalops.pascal_region(2, filename="runner.py"):
                    pass

        self.assertEqual(
            roundtrip.call_args_list,
            [
                call("START", 0, 0, "runner.py"),
                call("START", 1, 0, "runner.py"),
                call("STOP", 1, 0, "runner.py"),
                call("START", 2, 0, "runner.py"),
                call("STOP", 2, 0, "runner.py"),
                call("STOP", 0, 0, "runner.py"),
            ],
        )

    def test_proxy_rejects_filename_with_protocol_delimiter(self):
        with (
            patch.object(pascalops, "PASCAL_PROXY_AVAILABLE", True),
            patch.object(pascalops, "_proxy_command_fd", 10),
            patch.object(pascalops, "_proxy_ack_fd", 11),
        ):
            with self.assertRaises(ValueError):
                pascalops._proxy_roundtrip("START", 1, 10, "bad\tname.py")

    def test_status_reports_proxy_backend(self):
        with (
            patch.object(pascalops, "PASCAL_PROXY_AVAILABLE", True),
            patch.object(pascalops, "PASCAL_AVAILABLE", True),
            patch.object(pascalops, "_proxy_command_fd", 7),
            patch.object(pascalops, "_proxy_ack_fd", 8),
        ):
            status = pascalops.instrumentation_status()

        self.assertEqual(status["backend"], "proxy")
        self.assertEqual(status["proxy_command_fd"], 7)
        self.assertEqual(status["proxy_ack_fd"], 8)


if __name__ == "__main__":
    unittest.main()
