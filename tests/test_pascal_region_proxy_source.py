import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "pascal_region_proxy_launcher.c"
PYTHON_WORKLOAD = ROOT / "scripts" / "diagnose_pascal_region_proxy.py"


class PascalRegionProxySourceTests(unittest.TestCase):
    def test_native_supervisor_calls_pascal_api_in_parent_process(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("_pascal_start(region_id, line_no, filename);", source)
        self.assertIn("_pascal_stop(region_id, line_no, filename);", source)
        self.assertIn("waitpid(child_pid", source)
        self.assertIn("PASCAL_REGION_PROXY_COMMAND_FD", source)
        self.assertIn("PASCAL_REGION_PROXY_ACK_FD", source)

    def test_python_workload_uses_handshake_around_region(self):
        source = PYTHON_WORKLOAD.read_text(encoding="utf-8")
        self.assertIn('f"START\\t1\\t100\\t{filename}\\n"', source)
        self.assertIn('f"STOP\\t1\\t110\\t{filename}\\n"', source)
        self.assertIn("_send_and_wait", source)
        self.assertIn("elapsed_region_wall_s", source)


if __name__ == "__main__":
    unittest.main()
