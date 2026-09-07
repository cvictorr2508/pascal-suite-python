import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.experiment_profiles import (  # noqa: E402
    InitialSolutionSpec,
    ProfileKind,
    SolverProfile,
    default_solver_profile,
)


class SolverProfileTests(unittest.TestCase):
    def test_default_profile_is_backward_compatible(self):
        profile = default_solver_profile()

        self.assertEqual(profile.id, "default")
        self.assertEqual(profile.kind, ProfileKind.DEFAULT)
        self.assertEqual(profile.parameters, {})

    def test_warm_start_resolves_solution_by_workload_filename(self):
        profile = SolverProfile(
            id="warm-start",
            kind=ProfileKind.WARM_START,
            initial_solution=InitialSolutionSpec(
                files={"instance.lp.gz": Path("solutions/instance.mst")}
            ),
        )

        self.assertEqual(
            profile.initial_solution.resolve_for(Path("dataset/instance.lp.gz")),
            Path("solutions/instance.mst"),
        )

    def test_warm_start_requires_solution_mapping(self):
        with self.assertRaises(ValidationError):
            SolverProfile(id="warm-start", kind=ProfileKind.WARM_START)

    def test_non_warm_start_rejects_solution_mapping(self):
        with self.assertRaises(ValidationError):
            SolverProfile(
                id="default",
                kind=ProfileKind.DEFAULT,
                initial_solution=InitialSolutionSpec(
                    files={"instance.lp": Path("instance.sol")}
                ),
            )

    def test_profile_cannot_override_controlled_parameters(self):
        for parameter in ("Threads", "Seed", "threads", "seed"):
            with self.subTest(parameter=parameter):
                with self.assertRaises(ValidationError):
                    SolverProfile(
                        id="invalid",
                        kind=ProfileKind.DEFAULT,
                        parameters={parameter: 2},
                    )


if __name__ == "__main__":
    unittest.main()
