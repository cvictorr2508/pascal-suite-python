from pathlib import Path
import unittest


class Refactor28RaplProbeTests(unittest.TestCase):
    def test_probe_separates_target_and_global_classification(self):
        source = Path("scripts/refactor28_inspect_rapl_bytecode.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("target_rapl_", source)
        self.assertIn("global_pyz_", source)
        self.assertIn("refactor28_rapl_target_matches.txt", source)
        self.assertIn("refactor28_rapl_global_matches.txt", source)


if __name__ == "__main__":
    unittest.main()
