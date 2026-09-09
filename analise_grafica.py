from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plotar_escalabilidade():
    base_dir = Path("resultados_finais")

    # Identify the three benchmark difficulty levels.
    inputs = {
        "1. Easy": base_dir / "easy/tabela_experiment_gurobi_cfl_instance_0.csv",
        "2. Medium": base_dir
        / "medium/tabela_experiment_gurobi_cfl_medium_instance_0.csv",
        "3. Hard": base_dir
        / "hard/tabela_experiment_gurobi_cfl_hard_instance_0.csv",
    }

    frames = []
    for difficulty, path in inputs.items():
        if path.exists():
            frame = pd.read_csv(path)
            frame["Difficulty"] = difficulty
            frames.append(frame)
        else:
            print(f"[Warning] File not found: {path}")

    if not frames:
        print("[Error] No data was found.")
        return

    combined = pd.concat(frames, ignore_index=True)

    # Aggregate runtime and energy by difficulty and solver-core treatment.
    grouped = (
        combined.groupby(["Difficulty", "cores"])
        .agg(
            {
                "gurobi_gurobi_runtime_s": "mean",
                "pascal_rapl-sysfs": "mean",
            }
        )
        .reset_index()
    )

    runtime_matrix = grouped.pivot(
        index="cores",
        columns="Difficulty",
        values="gurobi_gurobi_runtime_s",
    )
    energy_matrix = grouped.pivot(
        index="cores",
        columns="Difficulty",
        values="pascal_rapl-sysfs",
    )

    figure, axes = plt.subplots(1, 2, figsize=(16, 6))
    sns.heatmap(
        runtime_matrix,
        annot=True,
        fmt=".2f",
        cmap="YlGnBu",
        ax=axes[0],
        cbar_kws={"label": "Time (seconds)"},
    )
    axes[0].set_title("Gurobi execution time (wall clock)")
    axes[0].set_ylabel("Threads / cores")

    sns.heatmap(
        energy_matrix,
        annot=True,
        fmt=".1f",
        cmap="OrRd",
        ax=axes[1],
        cbar_kws={"label": "Energy (joules)"},
    )
    axes[1].set_title("Hardware energy consumption (RAPL sysfs)")
    axes[1].set_ylabel("Threads / cores")

    plt.tight_layout()
    plt.savefig("matriz_escalabilidade_cfl.png", dpi=300)
    print("Plot written successfully: matriz_escalabilidade_cfl.png")


if __name__ == "__main__":
    plotar_escalabilidade()
