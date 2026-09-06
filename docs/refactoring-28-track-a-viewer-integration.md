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

## Gate de calibração no NPAD

O job `2079023` executou cinco repetições da instância
`CFL_hard_instance_20.lp.gz` com um núcleo e concluiu com código zero. O controle
entre a energia integrada na execução completa e `rapl-sysfs` apresentou:

- erro absoluto mediano: `0.196%`;
- erro absoluto máximo: `0.333%`;
- CV da energia da região `0`: `1.688%`;
- CV da região `0.1`: `1.269%`;
- CV da região `0.2`: `6.412%`.

As cinco execuções produziram energia positiva nas regiões `0`, `0.1` e `0.2`.
Quatro execuções tiveram cobertura da região raiz próxima de `99%`; a primeira
teve `85.534%`, efeito de inicialização que não comprometeu o controle global.
O gate de calibração, portanto, aprovou tanto o limite obrigatório de erro mediano
de `5%` quanto a preferência de CV de `10%`.

## Campanha representativa

O primeiro ensaio do segundo gate executou as 75 combinações previstas, mas o
backend `sysfs` produziu uma anomalia isolada no run `4;1;4`: energia global de
`-261400.335 J` e uma amostra de potência de `-2621371.789 W`. Os outros quatro
runs da mesma configuração apresentaram energia global entre `728.700 J` e
`765.659 J`. O valor negativo é fisicamente inválido e não pode ser integrado ou
imputado.

A campanha representativa passa, portanto, a usar as instâncias hard `5`, `10`,
`15`, `20` e `25`, recursos `[1, 2, 4]` e seis tentativas, totalizando 90 runs. O
sumarizador registra tentativas inválidas, exige pelo menos cinco runs válidos em
cada uma das 15 configurações e calcula erro e CV separadamente por combinação
de instância e núcleos. Misturar configurações heterogêneas produziria um CV sem
interpretação física.
