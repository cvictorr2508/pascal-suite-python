import json
from pathlib import Path

def merge_pascal_jsons(json_paths, output_path):
    super_json = None
    
    for index, file_path in enumerate(json_paths):
        # Cria rótulos numéricos para o eixo Y do gráfico ficar na ordem correta
        # 1 = Easy, 2 = Medium, 3 = Hard
        size_label = str(index + 1) 
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                
            if super_json is None:
                # Copia a estrutura do primeiro JSON (metadados do cluster, etc)
                super_json = content
                
                # O PULO DO GATO: Adiciona o eixo 'input_size' no descritor de chaves
                # Original: ["cores", "repetitions"] -> Novo: ["input_size", "cores", "repetitions"]
                chaves_atuais = super_json["config"]["data_descriptor"]["keys"]
                if "input_size" not in chaves_atuais:
                    super_json["config"]["data_descriptor"]["keys"] = ["input_size"] + chaves_atuais
                
                # Esvazia os dados para repopular com a nova formatação
                super_json["data"] = {} 
                
            # Adiciona os dados injetando a nova dimensão na chave (ex: "1;1" vira "3;1;1")
            for old_key, metrics in content["data"].items():
                new_key = f"{size_label};{old_key}"
                super_json["data"][new_key] = metrics
                
            print(f"[OK] Lido: {file_path.name} (Tamanho={size_label})")
            
        except FileNotFoundError:
            print(f"[Aviso] Arquivo não encontrado, ignorando: {file_path}")
        except Exception as e:
            print(f"[Erro] Falha ao processar {file_path.name}: {e}")
            
    if super_json and super_json["data"]:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(super_json, f, indent=4)
        print(f"\n[Sucesso] Super JSON consolidado salvo em: {output_path}")
    else:
        print("\n[Erro] Nenhum dado foi processado.")

if __name__ == "__main__":
    # Caminhos baseados na sua estrutura de pastas atual
    base_dir = Path("resultados_finais")
    
    # IMPORTANTE: A ordem desta lista define a ordem no eixo Y do gráfico (Crescente)
    arquivos_para_fundir = [
        # 1. EASY
        base_dir / "easy" / "pascal_viewer_consolidado_experiment_gurobi_cfl_instance_0.json",
        # 2. MEDIUM
        base_dir / "medium" / "pascal_viewer_consolidado_experiment_gurobi_cfl_medium_instance_0.json",
        # 3. HARD
        base_dir / "hard" / "pascal_viewer_consolidado_experiment_gurobi_cfl_hard_instance_0.json"
    ]
    
    arquivo_saida = base_dir / "pascal_viewer_SUPER_consolidado_MILPBench.json"
    
    print("--- Iniciando Fusão de JSONs para o PaScal Viewer ---")
    merge_pascal_jsons(arquivos_para_fundir, arquivo_saida)