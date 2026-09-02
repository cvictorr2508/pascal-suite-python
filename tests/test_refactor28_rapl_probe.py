from pathlib import Path
import unittest


class Refactor28RaplProbeTests(unittest.TestCase):
    def test_probe_separates_target_and_global_classification(self):
        source = Path("scripts/refactor28_inspect_rapl_bytecode.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("classify_file target_rapl", source)
        self.assertIn("classify_file global_pyz", source)
        self.assertIn('echo "${prefix}_${label}=true"', source)
        self.assertIn('echo "${prefix}_${label}=false"', source)
        self.assertIn("refactor28_rapl_target_matches.txt", source)
        self.assertIn("refactor28_rapl_global_matches.txt", source)


if __name__ == "__main__":
    unittest.main()
