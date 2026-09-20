InvalidOperation: 
Line |
   2 |  [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); Ge .
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot create type. Only core types are supported in this language mode.
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_gurobi_hard_default_300s_shard import (  # noqa: E402
    ShardConfigurationError,
    build_shard_configuration,
    campaign_shards,
    load_configuration,
)
from summarize_gurobi_hard_default_300s import (  # noqa: E402
    _compact_config,
    summarize_campaign,
)


class GurobiHardDefaultEightHourTests(unittest.TestCase):
    def setUp(self):
        self.config_path = (
            PROJECT_ROOT / "experiments" / "gurobi-hard-default-300s.yaml"
        )
        self.configuration = load_configuration(self.config_path)

    def _write_complete_campaign(self, campaign_root: Path) -> None:
        for shard in campaign_shards(self.configuration):
            shard_root = campaign_root / "shards" / shard.identifier
            profile_root = shard_root / "gurobi" / "default"
            profile_root.mkdir(parents=True)
            workload_sha256 = f"{shard.input_index + 1:064x}"
            manifest = {
                "source": {
                    "git_commit": "a" * 40,
                    "tracked_worktree_clean": True,
                },
                "experiment": {
                    "resources": [shard.cores],
                    "profiles": [
                        {
                            "id": "default",
                            "kind": "default",
                            "objective_sense": "minimize",
                            "parameters": {"TimeLimit": 300},
                        }
                    ],
                },
                "workloads": [
                    {
                        "path": str(shard.workload),
                        "size_bytes": 100 + shard.input_index,
                        "sha256": workload_sha256,
                    }
                ],
                "slurm": {
                    "allocation": {
                        "requested_mode": "exclusive",
                        "scheduler_oversubscribe": "NO",
                    }
                },
            }
            (shard_root / "research_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            data = {}
            for repetition in range(1, 7):
                data[f"{shard.cores};0;{repetition}"] = {
                    "start_time": 0,
                    "stop_time": 10,
                    "rapl-sysfs": 100,
                    "regions": {
                        "0": [[0, 10, 1, 2, 0, "runner.py"]],
                        "0.1": [[0, 4, 3, 4, 0, "runner.py"]],
                        "0.2": [[4, 10, 5, 6, 0, "runner.py"]],
                    },
                    "sensors": {
                        "rapl_sample-sysfs": [[10, 0], [10, 5], [10, 10]]
                    },
                }
                seed = 10000 + shard.input_index
                metadata = {
                    "cores": shard.cores,
                    "input_idx": shard.input_index,
                    "objective_sense": {
                        "requested": "minimize",
                        "source_value": -1,
                        "source_name": "maximize",
                        "effective_value": 1,
                        "effective_name": "minimize",
                        "overridden": True,
                        "fingerprint_before": 1000 + shard.input_index,
                        "fingerprint_after": 2000 + shard.input_index,
                    },
                    "parameters": {
                        "threads_requested": shard.cores,
                        "threads_effective": shard.cores,
                        "seed_requested": seed,
                        "seed_effective": seed,
                        "profile_requested": {"TimeLimit": 300},
                        "profile_effective": {"TimeLimit": 300.0},
                    },
                    "metrics": {
                        "status_name": "OPTIMAL",
                        "gurobi_runtime_s": 9.5,
                        "mip_gap": 0.0,
                    },
                }
                (profile_root / f"meta_{repetition}.json").write_text(
                    json.dumps(metadata), encoding="utf-8"
                )
            telemetry = {
                "config": {
                    "data_descriptor": {
                        "values": ["start_time", "stop_time", "rapl-sysfs"],
                        "extras": {
                            "regions": {
                                "values": [
                                    "start_time",
                                    "stop_time",
                                    "start_line",
                                    "stop_line",
                                    "thread_id",
                                    "filename",
                                ]
                            },
                            "sensors": {"values": ["info", "time"]},
                        },
                        "keys": ["cores", "input", "repetitions"],
                    }
                },
                "data": data,
            }
            (profile_root / "exp_pascal.json").write_text(
                json.dumps(telemetry), encoding="utf-8"
            )

    def test_matrix_maps_fifteen_array_tasks_deterministically(self):
        shards = campaign_shards(self.configuration)

        self.assertEqual(len(shards), 15)
        self.assertEqual(
            (shards[0].cores, shards[0].input_index, shards[0].workload.name),
            (1, 0, "CFL_hard_instance_5.lp.gz"),
        )
        self.assertEqual(
            (shards[5].cores, shards[5].input_index, shards[5].workload.name),
            (2, 0, "CFL_hard_instance_5.lp.gz"),
        )
        self.assertEqual(
            (shards[14].cores, shards[14].input_index, shards[14].workload.name),
            (4, 4, "CFL_hard_instance_25.lp.gz"),
        )

    def test_campaign_has_only_default_algorithmic_profile_and_time_limit(self):
        shards = campaign_shards(self.configuration)
        profile = self.configuration["experiment"]["profiles"][0]

        self.assertEqual(profile["id"], "default")
        self.assertEqual(profile["kind"], "default")
        self.assertEqual(profile["objective_sense"], "minimize")
        self.assertEqual(profile["parameters"], {"TimeLimit": 300})
        self.assertTrue(all(shard.cores in {1, 2, 4} for shard in shards))

    def test_non_default_parameter_is_rejected(self):
        invalid = copy.deepcopy(self.configuration)
        invalid["experiment"]["profiles"][0]["parameters"]["MIPGap"] = 0.1

        with self.assertRaisesRegex(
            ShardConfigurationError, "only Gurobi TimeLimit"
        ):
            campaign_shards(invalid)

    def test_non_minimization_objective_is_rejected(self):
        invalid = copy.deepcopy(self.configuration)
        invalid["experiment"]["profiles"][0]["objective_sense"] = "preserve"

        with self.assertRaisesRegex(
            ShardConfigurationError, "objective_sense=minimize"
        ):
            campaign_shards(invalid)

    def test_derived_configuration_contains_one_matrix_cell(self):
        shard = campaign_shards(self.configuration)[7]
        derived = build_shard_configuration(
            self.configuration, shard, Path("campaign-root")
        )

        self.assertEqual(derived["experiment"]["resources"], [2])
        self.assertEqual(
            [Path(item).name for item in derived["experiment"]["workloads"]],
            ["CFL_hard_instance_15.lp.gz"],
        )
        self.assertEqual(derived["experiment"]["repetitions"], 6)
        self.assertTrue(
            derived["output"]["directory"].replace("\\", "/").endswith(
                "campaign-root/shards/c2_i2"
            )
        )

    def test_compact_viewer_config_replaces_raw_samples_with_region_energy(self):
        analyzer_config = {
            "command": "pascalanalyzer",
            "data_descriptor": {
                "values": ["start_time", "stop_time", "rapl-sysfs"],
                "extras": {
                    "regions": {"values": ["start_time", "stop_time"]},
                    "sensors": {"values": ["info", "time"]},
                },
                "keys": ["cores", "repetitions"],
            },
        }

        compact = _compact_config(analyzer_config, ["a.lp.gz", "b.lp.gz"])

        descriptor = compact["data_descriptor"]
        self.assertNotIn("rapl-sysfs", descriptor["values"])
        self.assertNotIn("sensors", descriptor["extras"])
        self.assertEqual(
            descriptor["extras"]["rapl-sysfs"], {"values": ["region_energy"]}
        )
        self.assertEqual(descriptor["keys"], ["cores", "input", "repetitions"])

    def test_slurm_and_launchers_use_lf_and_bounded_array(self):
        submit = PROJECT_ROOT / "jobs" / "submit_gurobi_hard_default_300s.sh"
        slurm = PROJECT_ROOT / "jobs" / "run_gurobi_hard_default_300s.slurm"
        submit_text = submit.read_text(encoding="utf-8")
        slurm_text = slurm.read_text(encoding="utf-8")

        self.assertNotIn(b"\r\n", submit.read_bytes())
        self.assertNotIn(b"\r\n", slurm.read_bytes())
        self.assertIn('--array="0-14%$ARRAY_CONCURRENCY"', submit_text)
        self.assertIn('--time="$SLURM_TIME"', submit_text)
        self.assertIn("--exclusive", submit_text)
        self.assertIn("--check-inputs", submit_text)
        self.assertIn("#SBATCH --cpus-per-task=4", slurm_text)

    def test_complete_shard_set_builds_compact_viewer_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp)
            self._write_complete_campaign(campaign_root)

            report = summarize_campaign(
                config_path=self.config_path,
                campaign_root=campaign_root,
            )
            viewer = json.loads(
                (campaign_root / "gurobi_hard_default_300s_viewer.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(report["attempted_runs"], 90)
        self.assertEqual(report["valid_energy_runs"], 90)
        self.assertEqual(report["configuration_count"], 15)
        self.assertTrue(report["energy_gate"]["accuracy_accepted"])
        self.assertEqual(len(viewer["data"]), 90)
        self.assertNotIn("sensors", viewer["data"]["1;0;1"])
        self.assertEqual(
            viewer["data"]["1;0;1"]["rapl-sysfs"],
            {"0": 100.0, "0.1": 40.0, "0.2": 60.0},
        )

    def test_missing_attempt_is_rejected_instead_of_reporting_ninety(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp)
            self._write_complete_campaign(campaign_root)
            telemetry_path = (
                campaign_root
                / "shards/c1_i0/gurobi/default/exp_pascal.json"
            )
            telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
            telemetry["data"].pop("1;0;6")
            telemetry_path.write_text(json.dumps(telemetry), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "expected six attempted runs in c1_i0, found 5"
            ):
                summarize_campaign(
                    config_path=self.config_path,
                    campaign_root=campaign_root,
                )

    def test_effective_seed_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp)
            self._write_complete_campaign(campaign_root)
            metadata_path = (
                campaign_root / "shards/c2_i3/gurobi/default/meta_1.json"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["parameters"]["seed_effective"] = 999
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "effective Seed mismatch in c2_i3"
            ):
                summarize_campaign(
                    config_path=self.config_path,
                    campaign_root=campaign_root,
                )

    def test_effective_objective_sense_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp)
            self._write_complete_campaign(campaign_root)
            metadata_path = (
                campaign_root / "shards/c1_i0/gurobi/default/meta_1.json"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["objective_sense"]["effective_value"] = -1
            metadata["objective_sense"]["effective_name"] = "maximize"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "effective objective sense mismatch in c1_i0"
            ):
                summarize_campaign(
                    config_path=self.config_path,
                    campaign_root=campaign_root,
                )

    def test_workload_fingerprint_mismatch_across_cores_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp)
            self._write_complete_campaign(campaign_root)
            manifest_path = campaign_root / "shards/c2_i0/research_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["workloads"][0]["sha256"] = "f" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "workload fingerprint mismatch across cores for input 0"
            ):
                summarize_campaign(
                    config_path=self.config_path,
                    campaign_root=campaign_root,
                )


if __name__ == "__main__":
    unittest.main()

