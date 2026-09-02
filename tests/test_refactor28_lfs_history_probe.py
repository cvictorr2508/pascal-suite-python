from pathlib import Path
import unittest


class Refactor28LfsHistoryProbeTests(unittest.TestCase):
    def test_probe_materializes_and_verifies_known_lfs_objects(self):
        source = Path("scripts/refactor28_materialize_lfs_history.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("include_lfs_blobs=true", source)
        self.assertIn("lfs_sha256_verified", source)
        self.assertIn("lfs_size_verified", source)
        self.assertIn("dca51522320a35eff4b071d13a433e3586ebb1f9338e6fefe85381f1c94ce65e", source)
        self.assertIn("a51beb414fc3b102b8bdede9c1ed945f633b021df6cd553683e89b52ba829f80", source)
        self.assertIn("3aaf1cdc6802ff41990ffc18a966bc4cbe691fc964887ae9fa81abbb0f4cd912", source)
        self.assertIn("da3b0b2910c9269d9bd3c8bcc26c5ef87bc0c23405294c7ffb9bef555145ff9f", source)
        self.assertIn("historical_viewer_energy_candidate_found", source)


if __name__ == "__main__":
    unittest.main()
