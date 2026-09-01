import unittest
from pathlib import Path


class LinkedLauncherSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "pascal_linked_launcher.c"
        ).read_text(encoding="utf-8")

    def test_native_selftest_calls_pascal_markers(self):
        self.assertIn("pascal_start(9);", self.source)
        self.assertIn("pascal_stop(9);", self.source)

    def test_launcher_has_exec_and_spawn_paths(self):
        self.assertIn('strcmp(mode, "exec")', self.source)
        self.assertIn('strcmp(mode, "spawn")', self.source)
        self.assertIn("execl(python, python, script", self.source)
        self.assertIn("fork()", self.source)


if __name__ == "__main__":
    unittest.main()
