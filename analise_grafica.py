import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

def plotar_escalabilidade():
    base_dir = Path("resultados_finais")
    
    # 1. Carrega e identifica os 3 níveis de dificuldade
    arquivos = {
        "1. Easy": base_dir / "easy/tabela_experiment_gurobi_cfl_instance_0.csv",
        "2. Medium": base_dir / "medium/tabela_experiment_gurobi_cfl_medium_instance_0.csv",
        "3. Hard": base_dir / "hard/tabela_experiment_gurobi_cfl_hard_instance_0.csv"
    }
    
    dfs = []
    for diff, caminho in arquivos.items():
        if caminho.exists():
            df = pd.read_csv(caminho)
            df['Dificuldade'] = diff
            dfs.append(df)
        else:
            print(f"[Aviso] Arquivo não encontrado: {caminho}")
            
    if not dfs:
        print("[Erro] Nenhum dado encontrado.")
        return
        
    df_master = pd.concat(dfs, ignore_index=True)
    
    # 2. Calcula as médias agrupando por Dificuldade e Núcleos
    df_agrupado = df_master.groupby(['Dificuldade', 'cores']).agg({
        'gurobi_gurobi_runtime_s': 'mean',
        'pascal_rapl-sysfs': 'mean'
    }).reset_index()

    # 3. Cria as matrizes 2D (Pivot Tables) para o Heatmap
    matriz_tempo = df_agrupado.pivot(index='cores', columns='Dificuldade', values='gurobi_gurobi_runtime_s')
    matriz_energia = df_agrupado.pivot(index='cores', columns='Dificuldade', values='pascal_rapl-sysfs')

    # 4. Plota os dois diagramas lado a lado
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # Gráfico 1: Tempo de Execução
    sns.heatmap(matriz_tempo, annot=True, fmt=".2f", cmap="YlGnBu", ax=axes[0],
                cbar_kws={'label': 'Tempo (Segundos)'})
    axes[0].set_title("Gurobi: Tempo de Execução (Wall-clock)")
    axes[0].set_ylabel("Threads / Cores")
    
    # Gráfico 2: Energia (RAPL)
    sns.heatmap(matriz_energia, annot=True, fmt=".1f", cmap="OrRd", ax=axes[1],
                cbar_kws={'label': 'Energia (Joules)'})
    axes[1].set_title("Hardware: Consumo de Energia (RAPL Sysfs)")
    axes[1].set_ylabel("Threads / Cores")
    
    plt.tight_layout()
    
    # Salva em alta resolução para artigos/pesquisas
    plt.savefig("matriz_escalabilidade_cfl.png", dpi=300)
    print("Gráfico gerado com sucesso: matriz_escalabilidade_cfl.png")

if __name__ == "__main__":
    plotar_escalabilidade()