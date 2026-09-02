from pathlib import Path
import unittest


class Refactor28ArchiveProbeTests(unittest.TestCase):
    def test_probe_requires_python_313_compatible_pyinstaller(self):
        source = Path("scripts/refactor28_inspect_pyinstaller_archive.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("pyinstaller>=6.10,<7", source)
        self.assertIn("https://pypi.org/simple", source)
        self.assertIn("pyi-archive_viewer", source)


if __name__ == "__main__":
    unittest.main()
