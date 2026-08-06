import sys
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "src"))

from pascalpy.telemetry import TelemetryReader

def main():
    pasta_resultados = BASE_DIR / "resultados_finais"
    nome_experimento = "pesquisa_gurobi_v1"

    if len(sys.argv) >= 2:
        yaml_path = Path(sys.argv[1])
        if not yaml_path.is_absolute():
            yaml_path = BASE_DIR / yaml_path

        if yaml_path.exists():
            with yaml_path.open('r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                
                if "experiment" in config_data and "name" in config_data["experiment"]:
                    nome_experimento = config_data["experiment"]["name"]
                
                if "output" in config_data and "directory" in config_data["output"]:
                    pasta_resultados = BASE_DIR / config_data["output"]["directory"]
        else:
            print(f"Aviso: Arquivo {yaml_path} não encontrado. Usando valores padrão.")

    print(f"\n--- Iniciando consolidação de dados ---")
    print(f"-> Pasta Alvo: '{pasta_resultados}'")
    print(f"-> Buscando ID do Experimento: '{nome_experimento}'")
    
    if not pasta_resultados.exists():
        print(f"[Erro] Pasta de resultados não encontrada: {pasta_resultados}")
        sys.exit(1)

    reader = TelemetryReader(pasta_resultados)
    resultado = reader.read_experiment(nome_experimento)
    
    if resultado:
        df = resultado.to_dataframe()
        
        # ALTERAÇÃO AQUI: O CSV agora será salvo dentro da pasta apontada pelo YAML
        arquivo_csv = pasta_resultados / f"tabela_{nome_experimento}.csv"
        
        df.to_csv(arquivo_csv, index=False)
        print(f"\n[Sucesso] Tabela exportada para: {arquivo_csv}")
        
        print("\n=== PRÉVIA DOS DADOS (Primeiras 5 linhas) ===")
        colunas_interesse = [c for c in df.columns if 'rapl' in c or 'gurobi_runtime' in c or 'cores' in c or 'objective' in c]
        if colunas_interesse:
             print(df[colunas_interesse].head().to_string())
        else:
             print(df.head().to_string())
    else:
        print("\n[Erro] Falha ao ler os dados do experimento.")

if __name__ == "__main__":
    main()