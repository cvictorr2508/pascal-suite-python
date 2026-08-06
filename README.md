# PaScal Suite Python - Gurobi HPC Integration

Este repositório contém a infraestrutura de orquestração e telemetria automatizada para execução massiva de instâncias de Programação Linear Inteira Mista (MILP) utilizando o solver Gurobi e o framework PaScal Analyzer em ambientes de Computação de Alto Desempenho (HPC).

## 🏛 Arquitetura e Metodologia

Para garantir o isolamento de performance, precisão na coleta de métricas de hardware e total reprodutibilidade, a arquitetura foi dividida em um núcleo de biblioteca (`src/pascalpy/`) e uma esteira de execução orientada a configurações estáticas (YAML).

O fluxo metodológico (Pipeline Declarativo) opera em três estágios estritos:

1. **Definição do Experimento (YAML):** Os parâmetros da pesquisa — instâncias matemáticas (`.mps`, `.lp`), threads de CPU alocadas (`resources`), políticas de afinidade de núcleo e repetições — são declarados no arquivo de configuração (ex: `meu_experimento.yaml`), garantindo que o código-fonte permaneça inalterado entre diferentes testes.
2. **Isolamento e Execução:** Acionado via gerenciador de recursos (SLURM), o motor `rodar_yaml.py` traduz a configuração e injeta as diretivas do Gurobi em subprocessos (wrappers). A biblioteca impõe trava de afinidade de CPU em nível de Sistema Operacional (OS CPU Affinity) para evitar *cache thrashing*, enquanto o PaScal Analyzer acopla-se ao processo para medir energia (RAPL sysfs) e tempo de *wall-clock*.
3. **Consolidação de Telemetria:** Após o término computacional, o motor `run_analysis_master.py` rastreia automaticamente o mapa de execução gerado pelo YAML e consolida centenas de arquivos de telemetria independentes (JSON) em um único `DataFrame` relacional exportado para `.csv`.

## 📁 Estrutura de Diretórios

- `/src/pascalpy/`: Núcleo da biblioteca contendo os adaptadores do solver, modelos estritos de experimento (Pydantic) e lógicas de consolidação.
- `/instances/`: Diretório público sugerido para armazenar os modelos matemáticos e instâncias base para execução.
- `/resultados_finais/`: (Ignorado no Git) Diretório onde os artefatos de execução (JSONs, logs) e o arquivo CSV final são salvos.
- `meu_experimento.yaml`: Arquivo mestre de configuração da pesquisa.
- `rodar_yaml.py` / `run_analysis_master.py`: Scripts de orquestração (Turno de HPC e Turno de Análise).
- `master.slurm`: Job de submissão otimizado para o gerenciador do cluster.

## ⚙️ Pré-requisitos

Para rodar este pipeline em um cluster, é necessário:
- **Gerenciador de Recursos:** SLURM Workload Manager.
- **Python:** 3.13+ (com as bibliotecas `gurobipy`, `pandas`, `pydantic`, `pyyaml`).
- **PaScal Analyzer:** Instalado e mapeado no `PATH` do sistema.
- **Licença Gurobi:** Variável de ambiente `GRB_LICENSE_FILE` devidamente configurada no job de submissão.

## 🚀 Como Executar no Cluster

1. Ajuste os parâmetros (lista de workloads, cores, política de energia, etc.) no arquivo `meu_experimento.yaml`.
2. Submeta o job para o gerenciador SLURM:
   ```bash
   sbatch master.slurm
