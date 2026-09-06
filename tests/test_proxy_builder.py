import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation import proxy_builder


class ProxyBuilderTests(unittest.TestCase):
    def test_build_command_links_mpascalops_and_embeds_rpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "proxy"
            with patch.dict(
                os.environ,
                {
                    "PASCAL_OPS_LIB": "/opt/pascal/lib/libmpascalops.so",
                    "CC": "gcc",
                },
                clear=False,
            ):
                command = proxy_builder.region_proxy_build_command(binary)

        self.assertEqual(command[0], "gcc")
        self.assertIn("-I/opt/pascal/include", command)
        self.assertIn("-L/opt/pascal/lib", command)
        self.assertIn("-Wl,-rpath,/opt/pascal/lib", command)
        self.assertIn("-lmpascalops", command)
        self.assertEqual(command[-2:], ["-o", str(binary)])

    def test_source_is_versioned_with_package(self):
        source = proxy_builder.region_proxy_source()
        self.assertTrue(source.is_file())
        text = source.read_text(encoding="utf-8")
        self.assertIn("_pascal_start", text)
        self.assertIn("_pascal_stop", text)
        self.assertIn("PASCAL_REGION_PROXY_COMMAND_FD", text)
        self.assertIn("MAX_OPEN_REGIONS", text)
        self.assertIn("open_region_ids", text)
        self.assertIn("region-stack-full", text)


class SolverRegionSchemaTests(unittest.TestCase):
    def test_schema_uses_stable_hierarchical_region_keys(self):
        from pascalpy.instrumentation.solver_regions import solver_region_schema

        schema = solver_region_schema()

        self.assertEqual(schema["version"], 1)
        self.assertEqual(
            set(schema["regions"]),
            {"0", "0.1", "0.2"},
        )
        self.assertEqual(schema["regions"]["0"]["name"], "solver_pipeline")
        self.assertEqual(schema["regions"]["0.1"]["name"], "model_build")
        self.assertEqual(
            schema["regions"]["0.2"]["name"],
            "solve_execution",
        )
        self.assertTrue(schema["regions"]["0"]["inclusive"])
        self.assertEqual(schema["regions"]["0.1"]["parent"], "0")
        self.assertEqual(schema["regions"]["0.2"]["parent"], "0")


if __name__ == "__main__":
    unittest.main()
