# Refatoração 26 — resultado da validação no NPAD

## Objetivo

Validar a instrumentação manual do PaScal usada pelo runner Gurobi, corrigir falhas do binding Python e determinar se o PaScal Analyzer instalado no NPAD produz o contrato de energia regional esperado pelo PaScal Viewer.

A validação foi realizada com:

- Python `3.13.7`;
- PaScal Suite `2025-07-08`;
- `libmpascalops.so` em `/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so`.

## 1. ABI da instrumentação manual

O header instalado declara:

```c
void _pascal_start(long id, int start_line, const char *filename);
void _pascal_stop(long id, int stop_line, const char *filename);
```

O binding anterior passava somente `region_id`, causando `SIGSEGV (-11)` durante a instrumentação manual.

A Refatoração 26 corrige o binding `ctypes` para:

```python
[ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
```

para `start` e `stop`, além de resolver explicitamente os símbolos disponíveis e registrar o diagnóstico no metadata.

## 2. Testes unitários

No NPAD:

```bash
module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

python3 scripts/check_pascalops_symbols.py
python3 -m unittest discover -s tests -v
```

Resultado validado:

- `available: true`;
- `_pascal_start` resolvido;
- `_pascal_stop` resolvido;
- 6 testes executados;
- `OK`.

## 3. Resultado do smoke Python

Após a correção da ABI:

- o processo Python deixou de sofrer `SIGSEGV`;
- a execução sob o Analyzer terminou normalmente;
- porém a região manual não apareceu no JSON.

Esse comportamento foi separado da Refatoração 26 e está rastreado no issue #3: **registrar regiões PaScal corretamente via Python/ctypes**.

## 4. Controle C nativo

Um executável C nativo usando:

```c
pascal_start(1);
/* carga */
pascal_stop(1);
```

foi executado sob `pascalanalyzer -t man`.

Resultado:

- região `1` registrada corretamente;
- `start_time` e `stop_time` presentes;
- `start_line` e `stop_line` presentes;
- `thread_id` presente;
- `filename` presente;
- duração da região de aproximadamente 2 segundos.

Isso confirma que a instrumentação manual nativa do PaScal funciona no build instalado.

## 5. Matriz de modos RAPL

O job NPAD `2069555` executou o mesmo programa C nativo nos três modos abaixo, no mesmo nó.

### 5.1 `--rple sysfs`

Contrato observado:

```text
values = [start_time, stop_time, rapl-sysfs]
extras = regions
```

Resultado:

- região `1`: presente;
- energia global `rapl-sysfs`: presente;
- `region_energy`: ausente.

### 5.2 `--rpls sysfs`

Contrato observado:

```text
values = [start_time, stop_time]
extras = regions, sensors
```

Resultado:

- região `1`: presente;
- `sensors.rapl_sample-sysfs`: presente;
- amostras temporais RAPL: presentes;
- `region_energy`: ausente.

### 5.3 `--rple sysfs --rpls sysfs`

Contrato observado:

```text
values = [start_time, stop_time, rapl-sysfs]
extras = regions, sensors
```

Resultado:

- região `1`: presente;
- energia global: presente;
- amostras RAPL: presentes;
- `region_energy`: ausente.

O job terminou com `COMPLETED / 0:0`.

## 6. Conclusão sobre `region_energy`

Nenhuma combinação de `--rple` e `--rpls` do PaScal Suite `2025-07-08` produziu descriptors ou dados `region_energy`.

Além disso, a busca:

```bash
grep -RIn "region_energy" \
  /opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08
```

não encontrou implementação correspondente na árvore instalada.

Portanto, o contrato de energia regional observado nos JSONs de referência do Viewer não é produzido pelo build atual do Analyzer no NPAD.

Esse ponto está rastreado separadamente no issue #4: **obter `region_energy` no PaScal Analyzer/Viewer do NPAD**.

## 7. Escopo aprovado para merge

A Refatoração 26 pode ser mesclada em `develop` com o seguinte escopo:

1. corrigir a ABI `ctypes` e eliminar o `SIGSEGV` causado pelo binding incorreto;
2. resolver e registrar os símbolos efetivamente carregados;
3. manter fail-fast quando `libmpascalops` não estiver disponível;
4. registrar diagnóstico da instrumentação no metadata Gurobi;
5. manter o validador do contrato `region_energy` como ferramenta explícita para verificar builds futuros/compatíveis do Analyzer;
6. documentar que o build NPAD `2025-07-08` não atende atualmente esse contrato.

## 8. Itens deliberadamente não resolvidos neste PR

- registro efetivo da região manual quando `libmpascalops` é chamada dinamicamente pelo Python (`#3`);
- geração de `region_energy` pelo Analyzer e compatibilidade final com a métrica Energy do Viewer (`#4`).

Esses itens não devem ser contornados fabricando ou reestruturando o JSON PaScal no wrapper Python.

## 9. Critério final da Refatoração 26

Considera-se a Refatoração 26 concluída quando:

- [x] símbolos nativos foram confirmados no NPAD;
- [x] ABI correta foi implementada;
- [x] `SIGSEGV (-11)` decorrente da ABI incorreta foi eliminado;
- [x] 6 testes unitários passaram no NPAD;
- [x] instrumentação manual C nativa foi confirmada;
- [x] comportamento de `--rple`, `--rpls` e ambos foi caracterizado;
- [x] ausência de `region_energy` no build atual foi demonstrada;
- [x] limitações remanescentes foram separadas em issues próprios.

O merge deste PR estabiliza `develop` e cria uma baseline correta para os próximos trabalhos, sem afirmar suporte a energia regional que o Analyzer instalado ainda não fornece.
