import json
import sys
from pathlib import Path

import pandas as pd
import yaml


def main():
    yaml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("meu_experimento.yaml")
    with yaml_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    output_dir = Path(config["output"]["directory"])

    # Locate the single JSON artifact produced by the PaScal batch.
    pascal_files = list(output_dir.glob("*_batch_pascal.json"))
    if not pascal_files:
        print("[Error] PaScal batch artifact was not found.")
        return

    with pascal_files[0].open("r", encoding="utf-8") as stream:
        pascal_data = json.load(stream)

    # Load every solver metadata record written by the runner.
    metadata_records = []
    for metadata_path in output_dir.glob("meta_*.json"):
        with metadata_path.open("r", encoding="utf-8") as stream:
            metadata_records.append(json.load(stream))

    metadata = pd.DataFrame(metadata_records)
    if metadata.empty:
        print("\n[Critical error] No solver metadata was found.")
        print("The runners stopped before optimization; inspect the job logs.")
        raise SystemExit(1)

    # PaScal keys use (cores, input, repetition). Metadata timestamps establish
    # the natural repetition rank inside each (cores, input) group.
    metadata["repetition"] = (
        metadata.groupby(["cores", "input_idx"])["start_timestamp"]
        .rank(method="first")
        .astype(int)
    )

    rows = []
    for _, row in metadata.iterrows():
        cores = int(row["cores"])
        input_index = int(row["input_idx"])
        repetition = int(row["repetition"])

        rows.append(
            {
                "workload": Path(row["workload"]).name,
                "cores": cores,
                "input_index": input_index,
                "repetition": repetition,
                "gurobi_runtime_s": row.get("metrics", {}).get("gurobi_runtime_s"),
                "solve_wall_clock_s": row.get("metrics", {}).get(
                    "solve_wall_clock_s"
                ),
                "objective": row.get("metrics", {}).get("objective"),
            }
        )

    csv_path = output_dir / f"tabela_{config['experiment']['name']}.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    print(f"\n[Success] Final table written to: {csv_path}")
    print("The original PaScal JSON is ready for upload to PaScal Viewer.")


if __name__ == "__main__":
    main()
