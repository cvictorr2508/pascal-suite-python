# Refatoração 26 — validação de energia regional no NPAD

Esta sequência valida a instrumentação manual do PaScal aplicada ao `model.optimize()` do Gurobi sem alterar o JSON nativo produzido pelo Analyzer.

## Contexto do diagnóstico

O primeiro teste NPAD com `-t man` confirmou que `libmpascalops.so` exporta `_pascal_start` e `_pascal_stop`, mas todas as execuções do dummy terminaram com código `-11` (SIGSEGV). A causa identificada foi uma incompatibilidade de ABI no binding `ctypes`: `pascalops.h` declara três argumentos para cada função nativa, enquanto o binding anterior passava apenas o `region_id`.

Assinatura esperada:

```c
void _pascal_start(long id, int start_line, const char *filename);
void _pascal_stop(long id, int stop_line, const char *filename);
```

O smoke test abaixo é obrigatório antes de repetir a matriz Gurobi.

## 1. Preparar a branch do PR

```bash
cd ~/pascal-suite-python
git fetch origin
git switch refactor/26-energy-region-validation-v2
git pull --ff-only origin refactor/26-energy-region-validation-v2
```

## 2. Confirmar header e símbolos no NPAD

```bash
module purge
module load softwares/pascalsuite/2025-07-08

grep -RIn -E 'pascal_start|pascal_stop' \
  /opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/include

nm -D \
  /opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so \
  | grep -E 'pascal_start|pascal_stop'
```

Critério de aceite: `_pascal_start` e `_pascal_stop` disponíveis e assinatura de três argumentos confirmada no header.

## 3. Verificar o binding Python e os testes unitários

```bash
module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

python3 scripts/check_pascalops_symbols.py
python3 -m unittest discover -s tests -v
```

Critérios de aceite:

- `available: true`;
- símbolos start/stop resolvidos;
- todos os testes unitários passam, incluindo o teste de regressão da ABI com três argumentos.

## 4. Executar o smoke test sem Gurobi

O smoke test usa uma região PaScal de aproximadamente 2 segundos e não depende de Gurobi.

```bash
sbatch smoke_refactor26.slurm
```

Depois que o job terminar:

```bash
sacct -j JOB_ID \
  --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,NodeList

cat smoke26_JOB_ID.out
cat smoke26_JOB_ID.err
```

Critérios de aceite:

- `State=COMPLETED`;
- `ExitCode=0:0`;
- stdout contém `ANTES DA REGIAO` e `DEPOIS DA REGIAO`;
- stderr não contém `Segmentation fault` nem `Program finished with error: -11`.

## 5. Validar o JSON do smoke test

O job já executa a validação automaticamente. Ela também pode ser repetida manualmente:

```bash
python3 scripts/validate_pascal_energy.py smoke_pascal_region.json
```

Critérios de aceite:

- `has_extras: true`;
- `has_regions_descriptor: true`;
- pelo menos um domínio declara `region_energy`;
- `runs_with_required_region > 0`;
- `required_region_energy_samples > 0`;
- `viewer_energy_ready: true`;
- exit code 0.

Como o smoke mantém a região ativa por aproximadamente 2 segundos, espera-se preferencialmente energia regional maior que zero, embora a primeira barreira seja validar o contrato e eliminar o SIGSEGV.

## 6. Só então repetir o experimento dummy Gurobi

Usar um YAML de validação separado para não sobrescrever resultados experimentais existentes.

Configuração recomendada:

```yaml
experiment:
  name: "refactor26_dummy"
  model_sense: "MAXIMIZE"
  scaling_mode: "strong"
  resources: [1, 2, 4, 8, 16]
  repetitions: 3
  workloads:
    - "instances/dummy.mps"

environment:
  track_cores: false
  track_energy_rapl: "sysfs"
  idle_time_seconds: 5.0

output:
  directory: "resultados_finais/refactor26_dummy"
```

Registrar no log a versão efetiva do Python, Gurobi e PaScal utilizada no job.

O dummy valida principalmente o contrato estrutural. Como `model.optimize()` pode durar frações de milissegundo, `region_energy=0` ainda pode ser aceitável nessa etapa.

## 7. Validar automaticamente o JSON dummy

```bash
python3 scripts/validate_pascal_energy.py \
  resultados_finais/refactor26_dummy/exp_refactor26_dummy_batch_pascal.json
```

Critérios de aceite:

- todas as execuções terminam sem `-11`;
- `config.data_descriptor.extras` existe;
- `extras.regions` existe;
- existe pelo menos um domínio com `region_energy`;
- a região `1` está presente;
- há amostras de energia para a região `1`;
- `viewer_energy_ready: true`;
- exit code 0.

## 8. Validar Threads e afinidade

Para cada metadata Gurobi, verificar:

```text
cores == parameters.threads_requested == parameters.threads_effective
```

A afinidade efetiva também deve ser registrada para auditoria.

## 9. Abrir o JSON nativo no PaScal Viewer

Abrir diretamente o JSON produzido pelo Analyzer, sem pós-processamento.

Critérios de aceite:

- a região `1` aparece;
- `Energy` aparece como métrica selecionável;
- o Viewer abre o JSON sem transformação artificial do schema.

## 10. Repetir com uma instância Gurobi mais longa

Usar inicialmente uma única instância com duração de alguns segundos, poucos valores de cores e uma repetição.

Depois validar:

```bash
python3 scripts/validate_pascal_energy.py \
  /caminho/para/resultado_pascal.json \
  --require-nonzero-energy
```

Critério de aceite instrumental: pelo menos uma amostra `region_energy` da região `1` maior que zero.

## 11. Validação cruzada de tempo

Comparar, para as mesmas rodadas:

- duração da região PaScal `1`;
- `metrics.gurobi_runtime_s`;
- `metrics.solve_wall_clock_s`.

Os valores não precisam ser idênticos, mas devem ser compatíveis em ordem de grandeza e duração.

## Critério para merge em `develop`

O PR só deve ser promovido e mesclado quando:

1. header e símbolos nativos estiverem confirmados;
2. binding Python reportar `available: true`;
3. todos os unit tests passarem;
4. smoke test terminar sem SIGSEGV;
5. JSON do smoke apresentar região `1` e contrato regional de energia;
6. dummy terminar todas as rodadas sem `-11`;
7. JSON dummy retornar `viewer_energy_ready: true`;
8. `Threads requested == Threads effective == cores`;
9. Viewer reconhecer `Energy` e região `1`;
10. instância longa produzir `region_energy > 0` para região `1`;
11. tempos PaScal/Gurobi/wall forem consistentes.

Não fabricar nem reestruturar manualmente o JSON do PaScal para satisfazer o Viewer.
