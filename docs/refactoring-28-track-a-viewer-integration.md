# Refatoração 28 — Trilha A: energia regional derivada no Viewer

## Decisão arquitetural

O `pascal-suite-python` não fabrica domínios `region_energy` nem reestrutura o JSON
do Analyzer. Quando a política de ambiente habilita RAPL, o adaptador solicita os
dois produtos nativos:

```text
--rple BACKEND --rpls BACKEND
```

`--rple` fornece energia global independente para controle. `--rpls` fornece a
série `[potência, timestamp]` usada pelo Viewer para integrar energia nos
intervalos registrados em `regions`.

## Estados do contrato

O diagnóstico diferencia três capacidades:

1. `legacy_region_energy_ready`: descriptor histórico contendo
   `values: ["region_energy"]` e mapa numérico por região;
2. `viewer_energy_ready`: qualquer entrada de `extras` iniciada por `rapl` com
   mapa numérico por região, que é o contrato efetivamente lido pelo Viewer de
   desenvolvimento;
3. `sampled_energy_derivable`: região presente e sensor
   `rapl_sample-*` com pelo menos duas amostras ordenadas cobrindo seus intervalos.

O terceiro estado ainda não significa que o Viewer implantado exibirá energia.
Ele confirma que o JSON contém a matéria-prima para o fallback a ser implementado
no repositório upstream do Viewer.

## Algoritmo requerido no Viewer

Para cada execução e sensor `rapl_sample-*`:

1. validar números finitos e timestamps estritamente crescentes;
2. ordenar e unir os intervalos de todas as ocorrências do mesmo `region_id`;
3. recortar os intervalos aos limites da execução;
4. interpolar linearmente a potência nas bordas e integrar por trapézios;
5. nas bordas externas da série, manter a primeira ou última potência somente por
   até um período amostral;
6. não somar intervalos sobrepostos de threads, pois isso duplicaria energia de
   pacote;
7. usar `--rple` apenas como controle de consistência, não como substituto da
   energia regional.

O domínio derivado pode conservar a identidade do backend, por exemplo
`rapl-sysfs`, no modelo interno do Viewer. O arquivo carregado deve permanecer
inalterado.

## Critérios de aceite

- workload de validação com pelo menos 5 segundos;
- cinco repetições com energia regional positiva;
- região de controle cobrindo quase toda a execução;
- erro relativo mediano de no máximo 5% contra `--rple`;
- teste separado com ocorrências repetidas e threads sobrepostas, usando união de
  intervalos;
- Viewer exibe Energy e EDP diretamente a partir do JSON nativo;
- nenhuma transformação do JSON é adicionada ao wrapper Python.

O probe inicial já obteve erro de `0.269%` em uma região de aproximadamente três
segundos, o que valida a abordagem antes da alteração no Viewer.
