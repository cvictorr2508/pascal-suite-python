# Refatoração 26 — validação de energia regional no NPAD

Esta sequência valida a instrumentação manual do PaScal aplicada ao `model.optimize()` do Gurobi sem alterar o JSON nativo produzido pelo Analyzer.

## Baseline

Branch base: `develop`  
Commit de referência: `9cda60ad8c42de15e5c342f0a61b64b475a96f35`

Preservar os resultados anteriores do experimento dummy antes de executar novos jobs.

## 1. Carregar o ambiente no NPAD

```bash
module purge
module load softwares/python/3.10.5-gnu8
module load softwares/gurobi/9.5.1-pre_compiled
module load softwares/pascalsuite/2025-07-08
```

Ajustar a versão de Python somente se o módulo Gurobi do NPAD exigir outra combinação já validada.

## 2. Validar a biblioteca de instrumentação

Verificação direta dos símbolos:

```bash
nm -D /opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so \
  | grep -E 'pascal_start|pascal_stop'
```

Verificação pelo próprio wrapper:

```bash
python scripts/check_pascalops_symbols.py
```

Critério de aceite: saída com `available: true` e símbolos de start/stop resolvidos.

## 3. Executar os testes locais que não dependem do hardware

```bash
python -m unittest discover -s tests -v
```

## 4. Repetir o experimento dummy

Usar a configuração corrente do `meu_experimento.yaml`:

```yaml
resources: [1, 2, 4, 8, 16]
repetitions: 3
```

Submeter pelo fluxo normal do NPAD.

O objetivo do dummy é validar o contrato estrutural do JSON. Como `model.optimize()` dura poucos milissegundos ou menos, energia regional igual a zero pode ser esperada.

## 5. Validar automaticamente o JSON PaScal

```bash
python scripts/validate_pascal_energy.py \
  resultados_finais/dummy/exp_pesquisa_gurobi_dummy_batch_pascal.json
```

Critérios de aceite estrutural:

- `config.data_descriptor.extras` existe;
- `extras.regions` existe;
- pelo menos um domínio declara `region_energy`;
- a região `1` está presente em pelo menos uma rodada;
- há amostras de energia associadas à região `1`;
- o comando retorna código de saída 0.

O validador não exige energia maior que zero no dummy.

## 6. Abrir no PaScal Viewer

Abrir o JSON nativo produzido pelo Analyzer, sem pós-processamento.

Critério de aceite: a métrica de energia deve aparecer como opção visualizável e a região `1` deve representar a chamada `model.optimize()`.

## 7. Repetir com uma instância mais longa

Escolher uma instância cuja otimização dure pelo menos alguns segundos. Em seguida executar:

```bash
python scripts/validate_pascal_energy.py \
  /caminho/para/resultado_pascal.json \
  --require-nonzero-energy
```

Critério de aceite instrumental: pelo menos uma amostra `region_energy` da região `1` maior que zero.

## 8. Validação cruzada de tempo

Comparar, para as mesmas rodadas:

- duração da região PaScal `1`;
- `metrics.gurobi_runtime_s`;
- `metrics.solve_wall_clock_s`.

Esses valores não precisam ser idênticos, mas devem ser compatíveis em ordem de grandeza e duração.

## 9. Critério para promoção do PR

O PR só deve ser promovido depois que:

1. `scripts/check_pascalops_symbols.py` retornar sucesso no NPAD;
2. os unit tests passarem;
3. o JSON dummy passar na validação estrutural;
4. o Viewer reconhecer a métrica Energy;
5. uma instância longa produzir `region_energy > 0` para a região `1`.

Não fabricar nem reestruturar manualmente o JSON do PaScal para satisfazer o Viewer.
