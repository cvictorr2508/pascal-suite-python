import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_gurobi_hard_default_8h_shard import (  # noqa: E402
    ShardConfigurationError,
    build_shard_configuration,
    campaign_shards,
    load_configuration,
)
from summarize_gurobi_hard_default_8h import (  # noqa: E402
    _compact_config,
    summarize_campaign,
)


class GurobiHardDefaultEightHourTests(unittest.TestCase):
    def setUp(self):
        self.config_path = (
            PROJECT_ROOT / "experiments" / "gurobi-hard-default-8h.yaml"
        )
        self.configuration = load_configuration(self.config_path)

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
        self.assertEqual(profile["parameters"], {"TimeLimit": 28800})
        self.assertTrue(all(shard.cores in {1, 2, 4} for shard in shards))

    def test_non_default_parameter_is_rejected(self):
        invalid = copy.deepcopy(self.configuration)
        invalid["experiment"]["profiles"][0]["parameters"]["MIPGap"] = 0.1

        with self.assertRaisesRegex(
            ShardConfigurationError, "only Gurobi TimeLimit"
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
        submit = PROJECT_ROOT / "jobs" / "submit_gurobi_hard_default_8h.sh"
        slurm = PROJECT_ROOT / "jobs" / "run_gurobi_hard_default_8h.slurm"
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
            for shard in campaign_shards(self.configuration):
                shard_root = campaign_root / "shards" / shard.identifier
                profile_root = shard_root / "gurobi" / "default"
                profile_root.mkdir(parents=True)
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
                                "parameters": {"TimeLimit": 28800},
                            }
                        ],
                    },
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
                    metadata = {
                        "cores": shard.cores,
                        "input_idx": shard.input_index,
                        "parameters": {
                            "threads_effective": shard.cores,
                            "profile_effective": {"TimeLimit": 28800.0},
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

            report = summarize_campaign(
                config_path=self.config_path,
                campaign_root=campaign_root,
            )
            viewer = json.loads(
                (campaign_root / "gurobi_hard_default_8h_viewer.json").read_text(
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


if __name__ == "__main__":
    unittest.main()
