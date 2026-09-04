"""Canonical solver lifecycle regions shared by solver adapters."""

SOLVER_REGION_SCHEMA_VERSION = 1

SOLVER_PIPELINE_REGION_ID = 0
MODEL_BUILD_REGION_ID = 1
SOLVE_EXECUTION_REGION_ID = 2


def solver_region_schema() -> dict:
    """Return a fresh, JSON-serializable solver region catalog.

    Nested PaScal region keys are hierarchical: local child IDs 1 and 2
    opened inside region 0 are emitted by the Analyzer as ``0.1`` and ``0.2``.
    """
    return {
        "version": SOLVER_REGION_SCHEMA_VERSION,
        "regions": {
            "0": {
                "name": "solver_pipeline",
                "local_id": SOLVER_PIPELINE_REGION_ID,
                "parent": None,
                "inclusive": True,
            },
            "0.1": {
                "name": "model_build",
                "local_id": MODEL_BUILD_REGION_ID,
                "parent": "0",
                "inclusive": False,
            },
            "0.2": {
                "name": "solve_execution",
                "local_id": SOLVE_EXECUTION_REGION_ID,
                "parent": "0",
                "inclusive": False,
            },
        },
    }
