import json
import pandas as pd
from pathlib import Path
import yaml
import sys

def main():
    yaml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("meu_experimento.yaml")
    with yaml_path.open("r") as f:
        config = yaml.safe_load(f)
        
    output_dir = Path(config["output"]["directory"])
    
    # Encontra o JSON único gerado pelo PaScal Batch
    pascal_files = list(output_dir.glob("*_batch_pascal.json"))
    if not pascal_files:
        print("[Erro] Arquivo batch do PaScal não encontrado.")
        return
        
    with open(pascal_files[0], "r", encoding="utf-8") as f:
        pascal_data = json.load(f)
        
    # Carrega todos os metadados do Gurobi salvos pelo runner
    meta_files = list(output_dir.glob("meta_*.json"))
    meta_records = []
    for mf in meta_files:
        with open(mf, "r", encoding="utf-8") as f:
            meta_records.append(json.load(f))
            
    df_meta = pd.DataFrame(meta_records)
    
    # COMO LIGAMOS OS DADOS?
    # Agrupamos por (Cores, Input) e ordenamos pelo Timestamp.
    # O Rank natural (1º, 2º, 3º) nos dá o número da Repetição Exata!
    df_meta['repetition'] = df_meta.groupby(['cores', 'input_idx'])['start_timestamp'].rank(method='first').astype(int)
    
    rows = []
    for _, row in df_meta.iterrows():
        c = int(row['cores'])
        i = int(row['input_idx'])
        r = int(row['repetition'])
        
        # Monta a chave exata que o PaScal usou (ex: "4;0;1")
        p_key = f"{c};{i};{r}"
        p_run = pascal_data.get("data", {}).get(p_key, {})
        
        rows.append({
            "workload": Path(row["workload"]).name,
            "cores": c,
            "input_index": i,
            "repetition": r,
            "gurobi_runtime_s": row.get("metrics", {}).get("gurobi_runtime_s"),
            "solve_wall_clock_s": row.get("metrics", {}).get("solve_wall_clock_s"),
            "objective": row.get("metrics", {}).get("objective")
        })
        
    csv_path = output_dir / f"tabela_{config['experiment']['name']}.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    
    print(f"\n[Sucesso] Tabela final gerada em: {csv_path}")
    print("O arquivo JSON original do PaScal já está pronto para upload no Viewer!")

if __name__ == "__main__":
    main()