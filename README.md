# PaScal Suite Python - Gurobi HPC Integration

Este repositório contém a infraestrutura de orquestração e telemetria automatizada para execução massiva de instâncias de Programação Linear Inteira Mista (MILP) utilizando o solver Gurobi e o framework [PaScal Suite Analyzer](https://pascalsuite.imd.ufrn.br/analyzer/) em ambientes de Computação de Alto Desempenho (HPC), especificamente no [Núcleo de Computação de Alto Desempenho - NPAD](https://www.google.com/search?q=https://npad.ufrn.br/npad/bemvindo) da Universidade Federal do Rio Grande do Norte - UFRN.

## 🏛 Arquitetura e Metodologia

Para garantir o isolamento de performance, precisão na coleta de métricas de hardware e total reprodutibilidade, a arquitetura foi dividida em um núcleo de biblioteca (`src/pascalpy/`) e uma esteira de execução orientada a configurações estáticas (YAML).

O fluxo metodológico (Pipeline Declarativo) opera em três estágios estritos:

1. **Definição do Experimento (YAML):** Os parâmetros da pesquisa — instâncias matemáticas (`.mps`, `.lp`), threads de CPU alocadas (`resources`), políticas de afinidade de núcleo e repetições — são declarados no arquivo de configuração (ex: `meu_experimento.yaml`), garantindo que o código-fonte permaneça inalterado entre diferentes testes.
2. **Isolamento em Lote (Batch) e Regiões do Solver:** Acionado via gerenciador de recursos (SLURM), o motor `rodar_yaml.py` traduz a configuração e delega o controle do loop experimental ao binário nativo do PaScal Analyzer. A biblioteca impõe afinidade de CPU em nível de sistema operacional e registra três regiões hierárquicas: pipeline completo (`0`), leitura/construção do modelo (`0.1`) e otimização (`0.2`). Assim, custos de preparação e solução permanecem distinguíveis sem acoplar a instrumentação ao Gurobi.
3. **Consolidação de Telemetria:** Após o término computacional, o motor `run_analysis_master.py` lê o único arquivo de telemetria unificado gerado nativamente pelo PaScal e cruza essas informações com os metadados matemáticos locais do Gurobi, exportando um `DataFrame` relacional final para `.csv`.

## 📁 Estrutura de Diretórios

* `/src/pascalpy/`: Núcleo da biblioteca contendo os adaptadores do solver, modelos estritos de experimento (Pydantic) e lógicas de consolidação.
* `/src/pascalpy/instrumentation/`: Contém o módulo nativo `pascalops.py`, responsável pelo *binding* em C com a biblioteca `libmpascalops.so`, habilitando a marcação de regiões de telemetria rigorosas (*Solve-Only*).
* `/instances/`: Diretório público sugerido para armazenar os modelos matemáticos e instâncias base para execução.
* `/resultados_finais/`: Diretório local ignorado pelo Git contendo os artefatos gerados, incluindo o JSON de telemetria (`_batch_pascal.json`), metadados e resumos de validação.
* `meu_experimento.yaml`: Arquivo mestre de configuração da pesquisa.
* `rodar_yaml.py` / `run_analysis_master.py`: Scripts de orquestração (Turno de HPC e Turno de Análise).
* `master.slurm`: Job de submissão otimizado para o gerenciador do cluster.

## ⚙️ Pré-requisitos

Para rodar este pipeline em um cluster, é necessário:

* **Gerenciador de Recursos:** SLURM Workload Manager.
* **Python:** 3.13+ (com as bibliotecas `gurobipy`, `pandas`, `pydantic`, `pyyaml`).
* **PaScal Analyzer:** Instalado e mapeado no `PATH` do sistema.
* **Licença Gurobi:** Variável de ambiente `GRB_LICENSE_FILE` devidamente configurada no job de submissão.

## 🚀 Como Executar no Cluster

1. Ajuste os parâmetros (lista de workloads, cores, política de energia, etc.) no arquivo `meu_experimento.yaml`. Dica: Para observar o comportamento de Weak Scalability no visualizador, agrupe instâncias de dificuldades crescentes (ex: Easy, Medium, Hard) na lista de workloads do mesmo arquivo YAML.
2. Submeta o job para o gerenciador SLURM:
```bash
sbatch master.slurm

```



## 📊 Visualização de Dados (PaScal Viewer)

O wrapper solicita simultaneamente energia global (`--rple`) e potência RAPL amostrada (`--rpls`). O JSON nativo resultante contém a matéria-prima necessária para integrar energia sobre as regiões sem reescrever o arquivo.

Para inspecionar os dados no Viewer:

1. Acesse o [PaScal Viewer](https://pascalsuite.imd.ufrn.br/viewer/).
2. Na interface da aplicação, faça o upload dos arquivos consolidados finais gerados pelo pipeline (ex: `exp_pesquisa_gurobi_batch_pascal.json`).
3. A integração da Trilha A no Viewer deve reconhecer `rapl_sample-*`, integrar a potência sobre a união temporal dos intervalos e então exibir Energy e EDP. Até essa integração ser concluída, o JSON é validado pelo sumarizador Python, mas o Viewer publicado pode não apresentar os gráficos energéticos derivados.

## Validação energética reproduzível

`refactor28_gurobi_nested_validation.slurm` calibra o método em uma configuração com cinco repetições. `refactor28_gurobi_hard_validation.slurm` executa a campanha representativa com cinco instâncias hard, recursos `[1, 2, 4]` e cinco repetições, totalizando 75 execuções. As métricas de erro e variabilidade são avaliadas separadamente por combinação de instância e núcleos.

---

## 📥 Data Download

Due to the very large size of the dataset, the raw data can be downloaded directly from MILPBench, specifically using the following links:

* **CFL_easy:** [https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing](https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing)
* **CFL_medium:** [https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing](https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing)
* **CFL_hard:** [https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing](https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing)
