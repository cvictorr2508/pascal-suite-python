from pathlib import Path
import unittest


class Refactor28ArchiveProbeTests(unittest.TestCase):
    def test_probe_uses_pinned_standalone_extractor(self):
        source = Path("scripts/refactor28_inspect_pyinstaller_archive.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("pyinstxtractor-ng", source)
        self.assertIn("2026.07.03", source)
        self.assertIn("fe51aa23e122133163de873a430b2b88dac182d5519ef348b27890b0fcb4cd27", source)
        self.assertIn("region_energy_string_present", source)
        self.assertNotIn("pip install", source)


if __name__ == "__main__":
    unittest.main()
